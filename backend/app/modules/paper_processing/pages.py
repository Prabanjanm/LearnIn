"""
Bespoke admin HTML routes for the Question Paper Processing workflow.

This workflow does not fit the generic ENTITY_REGISTRY CRUD engine (it is a
multi-step pipeline with its own review UI), so it gets dedicated routes and
templates - the same choice already made for Question and MockTest. Route
functions stay thin; the work lives in service.py / background.py.
"""
import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import (
    AlreadyExistsException,
    GoogleDriveConfigError,
    InvalidStateException,
    NotFoundException,
)
from app.common.rate_limit import rate_limit
from app.common.utils.file_tracking import cleanup_drive_files
from app.core.database import get_db
from app.core.enums import ProcessingStatusEnum
from app.modules.admin.dependencies import get_optional_admin
from app.modules.admin.model import Admin
from app.modules.subject.model import Subject

from .background import is_stuck, run_pipeline_in_background
from .pdf_analysis import pdf_type_label
from .schema import PaperProcessingJobCreate
from .service import paper_processing_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Paper Processing Pages"])

templates = Jinja2Templates(directory="app/templates")

LOGIN_REDIRECT = "/admin/login"

BASE_PATH = "/admin/paper-processing"

# Statuses where the pipeline is still working and the page should poll.
BUSY_STATUSES = {
    ProcessingStatusEnum.UPLOADED,
    ProcessingStatusEnum.VALIDATING,
    ProcessingStatusEnum.CLEANING_WATERMARK,
    ProcessingStatusEnum.ANALYZING,
    ProcessingStatusEnum.EXTRACTING,
    ProcessingStatusEnum.DETECTING_QUESTIONS,
}

STATUS_LABELS = {
    ProcessingStatusEnum.UPLOADED: "Uploaded - waiting to start",
    ProcessingStatusEnum.VALIDATING: "Validating the PDF",
    ProcessingStatusEnum.VALIDATION_FAILED: "Validation failed",
    ProcessingStatusEnum.CLEANING_WATERMARK: "Checking for watermarks",
    ProcessingStatusEnum.WATERMARK_NEEDS_REVIEW: "Watermark needs manual review",
    ProcessingStatusEnum.ANALYZING: "Detecting PDF type",
    ProcessingStatusEnum.EXTRACTING: "Extracting text",
    ProcessingStatusEnum.DETECTING_QUESTIONS: "Detecting questions and options",
    ProcessingStatusEnum.READY_FOR_REVIEW: "Ready for review",
    ProcessingStatusEnum.REVIEWED: "Review saved",
    ProcessingStatusEnum.GENERATING_PDF: "Generating the LearnIn PDF",
    ProcessingStatusEnum.READY_TO_PUBLISH: "Ready to publish",
    ProcessingStatusEnum.PUBLISHED: "Published",
    ProcessingStatusEnum.FAILED: "Failed",
}


def _parse_upload_json(raw_value: str | None) -> dict:
    """
    upload-widget.js stashes {file_id, mime_type, file_size, filename} as
    JSON in a hidden input. Same contract as admin/pages.apply_upload_field,
    just shaped for this form's column names.
    """
    if not raw_value:
        return {}

    try:
        data = json.loads(raw_value)
    except (TypeError, ValueError):
        return {}

    if not isinstance(data, dict) or not data.get("file_id"):
        return {}

    return data


def _job_context(db: Session, job) -> dict:
    return {
        "job": job,
        "status_label": STATUS_LABELS.get(job.status, job.status.value),
        "pdf_type_label": pdf_type_label(job.pdf_type),
        "is_busy": job.status in BUSY_STATUSES,
        "is_stuck": is_stuck(job),
        "base_path": BASE_PATH,
    }


def _render_new_form(request: Request, admin, db: Session, error: str | None, status_code: int = 200):
    subjects = (
        db.query(Subject)
        .order_by(Subject.name)
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="admin/paper_processing/new.html",
        context={
            "admin": admin,
            "subjects": subjects,
            "error": error,
            "base_path": BASE_PATH,
        },
        status_code=status_code,
    )


# ------------------------------------------------------------------ list ----

@router.get(BASE_PATH)
def job_list(
    request: Request,
    admin: Admin | None = Depends(get_optional_admin),
    db: Session = Depends(get_db),
):
    if admin is None:
        return RedirectResponse(LOGIN_REDIRECT, status_code=303)

    jobs = paper_processing_service.list_jobs(db)

    return templates.TemplateResponse(
        request=request,
        name="admin/paper_processing/list.html",
        context={
            "admin": admin,
            "jobs": jobs,
            "status_labels": STATUS_LABELS,
            "base_path": BASE_PATH,
        },
    )


# ------------------------------------------------------------- step 1: new --

@router.get(f"{BASE_PATH}/new")
def new_job_form(
    request: Request,
    admin: Admin | None = Depends(get_optional_admin),
    db: Session = Depends(get_db),
):
    if admin is None:
        return RedirectResponse(LOGIN_REDIRECT, status_code=303)

    return _render_new_form(request, admin, db, error=None)


@router.post(f"{BASE_PATH}/new")
async def new_job_submit(
    request: Request,
    background_tasks: BackgroundTasks,
    admin: Admin | None = Depends(get_optional_admin),
    db: Session = Depends(get_db),
    _throttle: None = Depends(rate_limit(10, 60)),
):
    if admin is None:
        return RedirectResponse(LOGIN_REDIRECT, status_code=303)

    form_data = await request.form()

    source = _parse_upload_json(form_data.get("original_file_id"))
    answer = _parse_upload_json(form_data.get("answer_file_id"))

    uploaded_ids = [
        file_id for file_id in (source.get("file_id"), answer.get("file_id")) if file_id
    ]

    if not source:
        # Nothing was uploaded, so nothing to clean up.
        return _render_new_form(
            request, admin, db,
            error="Please upload the source question paper PDF before saving.",
            status_code=400,
        )

    try:
        data = PaperProcessingJobCreate(
            subject_id=int(form_data.get("subject_id") or 0),
            title=(form_data.get("title") or "").strip(),
            year=int(form_data.get("year") or 0),
            source_url=(form_data.get("source_url") or "").strip() or None,
            source_notes=(form_data.get("source_notes") or "").strip() or None,
            original_file_id=source["file_id"],
            original_mime_type=source.get("mime_type"),
            original_file_size=source.get("file_size"),
            original_filename=source.get("filename"),
            answer_file_id=answer.get("file_id"),
            answer_mime_type=answer.get("mime_type"),
            answer_file_size=answer.get("file_size"),
            answer_filename=answer.get("filename"),
        )

        job = paper_processing_service.create_job(db, admin.id, data)

    except (ValueError, NotFoundException, AlreadyExistsException) as exc:
        db.rollback()
        # The uploads already reached Drive but no row now references them -
        # delete them rather than leaking.
        cleanup_drive_files(db, uploaded_ids)
        return _render_new_form(request, admin, db, error=str(exc), status_code=400)

    except Exception:
        db.rollback()
        logger.exception("Failed to create a paper processing job")
        cleanup_drive_files(db, uploaded_ids)
        return _render_new_form(
            request, admin, db,
            error="The job could not be created. Please try again.",
            status_code=400,
        )

    background_tasks.add_task(run_pipeline_in_background, job.id)

    return RedirectResponse(f"{BASE_PATH}/{job.id}", status_code=303)


# ------------------------------------------------------------- step 2: run --

@router.get(BASE_PATH + "/{job_id}")
def job_status_page(
    job_id: int,
    request: Request,
    admin: Admin | None = Depends(get_optional_admin),
    db: Session = Depends(get_db),
):
    if admin is None:
        return RedirectResponse(LOGIN_REDIRECT, status_code=303)

    try:
        job = paper_processing_service.get_job(db, job_id)
    except NotFoundException:
        return RedirectResponse(BASE_PATH, status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="admin/paper_processing/status.html",
        context={"admin": admin, **_job_context(db, job)},
    )


@router.post(BASE_PATH + "/{job_id}/reprocess")
def reprocess_job(
    job_id: int,
    background_tasks: BackgroundTasks,
    admin: Admin | None = Depends(get_optional_admin),
    db: Session = Depends(get_db),
    _throttle: None = Depends(rate_limit(10, 60)),
):
    """
    Re-runs the pipeline from the start. Safe to call on a job that was
    interrupted by a restart (see background.py) or that failed: every stage
    is idempotent and the untouched original PDF is never overwritten.
    """
    if admin is None:
        return RedirectResponse(LOGIN_REDIRECT, status_code=303)

    try:
        job = paper_processing_service.get_job(db, job_id)
    except NotFoundException:
        return RedirectResponse(BASE_PATH, status_code=303)

    if job.status == ProcessingStatusEnum.PUBLISHED:
        return RedirectResponse(f"{BASE_PATH}/{job_id}/preview", status_code=303)

    job.cancel_requested = False
    paper_processing_service.set_status(db, job, ProcessingStatusEnum.UPLOADED)
    background_tasks.add_task(run_pipeline_in_background, job.id)

    return RedirectResponse(f"{BASE_PATH}/{job_id}", status_code=303)


@router.post(BASE_PATH + "/{job_id}/stop")
def stop_job(
    job_id: int,
    admin: Admin | None = Depends(get_optional_admin),
    db: Session = Depends(get_db),
    _throttle: None = Depends(rate_limit(10, 60)),
):
    """
    Asks a running job to stop at its next stage checkpoint (see
    `background._checkpoint`). Not an instant kill - there is no task queue
    to interrupt a thread outright - but it reliably halts the job within
    one stage, without ever touching the untouched original upload.
    """
    if admin is None:
        return RedirectResponse(LOGIN_REDIRECT, status_code=303)

    try:
        paper_processing_service.request_cancel(db, job_id)
    except NotFoundException:
        return RedirectResponse(BASE_PATH, status_code=303)
    except InvalidStateException:
        pass  # already finished/not running - nothing to stop, not an error

    return RedirectResponse(f"{BASE_PATH}/{job_id}", status_code=303)


# ---------------------------------------------------------- step 3: review --

@router.get(BASE_PATH + "/{job_id}/review")
def review_page(
    job_id: int,
    request: Request,
    admin: Admin | None = Depends(get_optional_admin),
    db: Session = Depends(get_db),
):
    if admin is None:
        return RedirectResponse(LOGIN_REDIRECT, status_code=303)

    try:
        job = paper_processing_service.get_job(db, job_id)
    except NotFoundException:
        return RedirectResponse(BASE_PATH, status_code=303)

    if job.status in BUSY_STATUSES:
        return RedirectResponse(f"{BASE_PATH}/{job_id}", status_code=303)

    questions = paper_processing_service.list_questions(db, job_id)

    return templates.TemplateResponse(
        request=request,
        name="admin/paper_processing/review.html",
        context={
            "admin": admin,
            "questions": questions,
            "error": request.query_params.get("error"),
            **_job_context(db, job),
        },
    )


@router.post(BASE_PATH + "/{job_id}/save")
def save_review(
    job_id: int,
    admin: Admin | None = Depends(get_optional_admin),
    db: Session = Depends(get_db),
):
    """
    Marks the review complete. Deliberately does NOT create real
    Question/Option rows - those are written once, at publish time, so that
    an unpublished job can never leak machine-extracted content into the
    student-facing tables.
    """
    if admin is None:
        return RedirectResponse(LOGIN_REDIRECT, status_code=303)

    try:
        paper_processing_service.mark_reviewed(db, job_id)
    except NotFoundException:
        return RedirectResponse(BASE_PATH, status_code=303)
    except InvalidStateException as exc:
        return RedirectResponse(
            f"{BASE_PATH}/{job_id}/review?error={_quote(str(exc))}",
            status_code=303,
        )

    return RedirectResponse(f"{BASE_PATH}/{job_id}/preview", status_code=303)


# ------------------------------------------------------- step 4: generate ---

@router.post(BASE_PATH + "/{job_id}/generate-pdf")
def generate_pdf(
    job_id: int,
    admin: Admin | None = Depends(get_optional_admin),
    db: Session = Depends(get_db),
    _throttle: None = Depends(rate_limit(10, 60)),
):
    if admin is None:
        return RedirectResponse(LOGIN_REDIRECT, status_code=303)

    try:
        paper_processing_service.generate_pdf(db, job_id)
    except NotFoundException:
        return RedirectResponse(BASE_PATH, status_code=303)
    except (InvalidStateException, GoogleDriveConfigError) as exc:
        return RedirectResponse(
            f"{BASE_PATH}/{job_id}/preview?error={_quote(str(exc))}",
            status_code=303,
        )
    except Exception:
        logger.exception("Unexpected failure generating the PDF for job %s", job_id)
        return RedirectResponse(
            f"{BASE_PATH}/{job_id}/preview?error="
            + _quote("The PDF could not be generated. Please try again."),
            status_code=303,
        )

    return RedirectResponse(f"{BASE_PATH}/{job_id}/preview", status_code=303)


# -------------------------------------------------------- step 5: preview ---

@router.get(BASE_PATH + "/{job_id}/preview")
def preview_page(
    job_id: int,
    request: Request,
    admin: Admin | None = Depends(get_optional_admin),
    db: Session = Depends(get_db),
):
    if admin is None:
        return RedirectResponse(LOGIN_REDIRECT, status_code=303)

    try:
        job = paper_processing_service.get_job(db, job_id)
    except NotFoundException:
        return RedirectResponse(BASE_PATH, status_code=303)

    questions = paper_processing_service.list_questions(db, job_id)

    return templates.TemplateResponse(
        request=request,
        name="admin/paper_processing/preview.html",
        context={
            "admin": admin,
            "questions": questions,
            "blockers": paper_processing_service.publish_blockers(db, job),
            "verified_count": sum(1 for q in questions if not q.needs_review),
            "extra_images_count": sum(1 for q in questions if len(q.images) > 1),
            "error": request.query_params.get("error"),
            **_job_context(db, job),
        },
    )


# -------------------------------------------------------- step 6: publish ---

@router.post(BASE_PATH + "/{job_id}/publish")
def publish(
    job_id: int,
    admin: Admin | None = Depends(get_optional_admin),
    db: Session = Depends(get_db),
    _throttle: None = Depends(rate_limit(5, 60)),
):
    if admin is None:
        return RedirectResponse(LOGIN_REDIRECT, status_code=303)

    try:
        paper_processing_service.publish_job(db, job_id)
    except NotFoundException:
        return RedirectResponse(BASE_PATH, status_code=303)
    except (InvalidStateException, AlreadyExistsException) as exc:
        return RedirectResponse(
            f"{BASE_PATH}/{job_id}/preview?error={_quote(str(exc))}",
            status_code=303,
        )
    except Exception:
        db.rollback()
        logger.exception("Unexpected failure publishing job %s", job_id)
        return RedirectResponse(
            f"{BASE_PATH}/{job_id}/preview?error="
            + _quote("Publishing failed. Please try again."),
            status_code=303,
        )

    return RedirectResponse(f"{BASE_PATH}/{job_id}/preview?published=1", status_code=303)


def _quote(message: str) -> str:
    from urllib.parse import quote

    return quote(message, safe="")
