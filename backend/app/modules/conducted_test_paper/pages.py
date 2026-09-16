"""
Institution HTML routes for the "upload my own paper" conducted-test flow -
mirrors paper_processing/pages.py's structure (upload -> status -> review
-> confirm), scoped to an institution session instead of an admin one, and
narrower (no subject/mock-test/PDF-regeneration steps - see model.py).
"""
import json
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import InvalidStateException, NotFoundException
from app.common.rate_limit import rate_limit
from app.core.database import get_db
from app.core.enums import ProcessingStatusEnum
from app.modules.institution.dependencies import get_optional_institution_user
from app.modules.institution.model import InstitutionUser

from .background import is_stuck, run_pipeline_in_background
from .schema import ConductedTestPaperJobCreate
from .service import conducted_test_paper_job_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Conducted Test Papers (Institution Pages)"])

templates = Jinja2Templates(directory="app/templates")

LOGIN_REDIRECT = "/login"

BASE_PATH = "/institution/conducted-test-papers"

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
    ProcessingStatusEnum.ANALYZING: "Detecting PDF type",
    ProcessingStatusEnum.EXTRACTING: "Extracting text",
    ProcessingStatusEnum.DETECTING_QUESTIONS: "Detecting questions and options",
    ProcessingStatusEnum.READY_FOR_REVIEW: "Ready for review",
    ProcessingStatusEnum.REVIEWED: "Review saved - ready to confirm",
    ProcessingStatusEnum.PUBLISHED: "Confirmed and saved",
    ProcessingStatusEnum.FAILED: "Failed",
}


def _parse_upload_json(raw_value: str | None) -> dict:
    if not raw_value:
        return {}
    try:
        data = json.loads(raw_value)
    except (TypeError, ValueError):
        return {}
    if not isinstance(data, dict) or not data.get("file_id"):
        return {}
    return data


def _job_context(job) -> dict:
    return {
        "job": job,
        "status_label": STATUS_LABELS.get(job.status, job.status.value),
        "is_busy": job.status in BUSY_STATUSES,
        "is_stuck": is_stuck(job),
        "base_path": BASE_PATH,
    }


# ------------------------------------------------------------------ list ----

@router.get(BASE_PATH)
def job_list(
    request: Request,
    user: InstitutionUser | None = Depends(get_optional_institution_user),
    db: Session = Depends(get_db),
):
    if user is None:
        return RedirectResponse(LOGIN_REDIRECT, status_code=303)

    jobs = conducted_test_paper_job_service.list_jobs(db, user.institution_id)

    return templates.TemplateResponse(
        request=request,
        name="conducted_test/paper_job_list.html",
        context={"user": user, "jobs": jobs, "status_labels": STATUS_LABELS, "base_path": BASE_PATH},
    )


# ------------------------------------------------------------- step 1: new --

@router.get(f"{BASE_PATH}/new")
def new_job_form(
    request: Request,
    user: InstitutionUser | None = Depends(get_optional_institution_user),
):
    if user is None:
        return RedirectResponse(LOGIN_REDIRECT, status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="conducted_test/paper_job_new.html",
        context={"user": user, "error": None, "base_path": BASE_PATH},
    )


@router.post(f"{BASE_PATH}/new")
async def new_job_submit(
    request: Request,
    background_tasks: BackgroundTasks,
    user: InstitutionUser | None = Depends(get_optional_institution_user),
    db: Session = Depends(get_db),
    _throttle: None = Depends(rate_limit(10, 60)),
):
    if user is None:
        return RedirectResponse(LOGIN_REDIRECT, status_code=303)

    form_data = await request.form()
    source = _parse_upload_json(form_data.get("original_file_id"))

    if not source:
        return templates.TemplateResponse(
            request=request,
            name="conducted_test/paper_job_new.html",
            context={
                "user": user,
                "base_path": BASE_PATH,
                "error": "Please upload the question paper PDF before saving.",
            },
            status_code=400,
        )

    try:
        data = ConductedTestPaperJobCreate(
            title=(form_data.get("title") or "").strip(),
            original_file_id=source["file_id"],
            original_mime_type=source.get("mime_type"),
            original_file_size=source.get("file_size"),
            original_filename=source.get("filename"),
        )
        job = conducted_test_paper_job_service.create_job(db, user.institution_id, user.id, data)
    except Exception:
        db.rollback()
        logger.exception("Failed to create a conducted test paper job")
        return templates.TemplateResponse(
            request=request,
            name="conducted_test/paper_job_new.html",
            context={"user": user, "base_path": BASE_PATH, "error": "The upload could not be saved. Please try again."},
            status_code=400,
        )

    background_tasks.add_task(run_pipeline_in_background, job.id)

    return RedirectResponse(f"{BASE_PATH}/{job.id}", status_code=303)


# ------------------------------------------------------------- step 2: run --

@router.get(BASE_PATH + "/{job_id}")
def job_status_page(
    job_id: uuid.UUID,
    request: Request,
    user: InstitutionUser | None = Depends(get_optional_institution_user),
    db: Session = Depends(get_db),
):
    if user is None:
        return RedirectResponse(LOGIN_REDIRECT, status_code=303)

    try:
        job = conducted_test_paper_job_service.get_job(db, job_id, user.institution_id)
    except NotFoundException:
        return RedirectResponse(BASE_PATH, status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="conducted_test/paper_job_status.html",
        context={"user": user, **_job_context(job)},
    )


@router.post(BASE_PATH + "/{job_id}/reprocess")
def reprocess_job(
    job_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    user: InstitutionUser | None = Depends(get_optional_institution_user),
    db: Session = Depends(get_db),
    _throttle: None = Depends(rate_limit(10, 60)),
):
    if user is None:
        return RedirectResponse(LOGIN_REDIRECT, status_code=303)

    try:
        job = conducted_test_paper_job_service.get_job(db, job_id, user.institution_id)
    except NotFoundException:
        return RedirectResponse(BASE_PATH, status_code=303)

    if job.status == ProcessingStatusEnum.PUBLISHED:
        return RedirectResponse(f"{BASE_PATH}/{job_id}/review", status_code=303)

    job.cancel_requested = False
    conducted_test_paper_job_service.set_status(db, job, ProcessingStatusEnum.UPLOADED)
    background_tasks.add_task(run_pipeline_in_background, job.id)

    return RedirectResponse(f"{BASE_PATH}/{job_id}", status_code=303)


@router.post(BASE_PATH + "/{job_id}/stop")
def stop_job(
    job_id: uuid.UUID,
    user: InstitutionUser | None = Depends(get_optional_institution_user),
    db: Session = Depends(get_db),
    _throttle: None = Depends(rate_limit(10, 60)),
):
    if user is None:
        return RedirectResponse(LOGIN_REDIRECT, status_code=303)

    try:
        conducted_test_paper_job_service.request_cancel(db, job_id, user.institution_id)
    except NotFoundException:
        return RedirectResponse(BASE_PATH, status_code=303)
    except InvalidStateException:
        pass

    return RedirectResponse(f"{BASE_PATH}/{job_id}", status_code=303)


# ---------------------------------------------------------- step 3: review --

@router.get(BASE_PATH + "/{job_id}/review")
def review_page(
    job_id: uuid.UUID,
    request: Request,
    user: InstitutionUser | None = Depends(get_optional_institution_user),
    db: Session = Depends(get_db),
):
    if user is None:
        return RedirectResponse(LOGIN_REDIRECT, status_code=303)

    try:
        job = conducted_test_paper_job_service.get_job(db, job_id, user.institution_id)
    except NotFoundException:
        return RedirectResponse(BASE_PATH, status_code=303)

    if job.status in BUSY_STATUSES:
        return RedirectResponse(f"{BASE_PATH}/{job_id}", status_code=303)

    questions = conducted_test_paper_job_service.list_questions(db, job_id)

    return templates.TemplateResponse(
        request=request,
        name="conducted_test/paper_job_review.html",
        context={
            "user": user,
            "questions": questions,
            "blockers": conducted_test_paper_job_service.publish_blockers(db, job),
            "error": request.query_params.get("error"),
            "published": request.query_params.get("published"),
            **_job_context(job),
        },
    )


@router.post(BASE_PATH + "/{job_id}/save")
def save_review(
    job_id: uuid.UUID,
    user: InstitutionUser | None = Depends(get_optional_institution_user),
    db: Session = Depends(get_db),
):
    if user is None:
        return RedirectResponse(LOGIN_REDIRECT, status_code=303)

    try:
        conducted_test_paper_job_service.mark_reviewed(db, job_id, user.institution_id)
    except NotFoundException:
        return RedirectResponse(BASE_PATH, status_code=303)
    except InvalidStateException as exc:
        return RedirectResponse(f"{BASE_PATH}/{job_id}/review?error={_quote(str(exc))}", status_code=303)

    return RedirectResponse(f"{BASE_PATH}/{job_id}/review", status_code=303)


# ---------------------------------------------------------- step 4: publish --

@router.post(BASE_PATH + "/{job_id}/publish")
def publish(
    job_id: uuid.UUID,
    user: InstitutionUser | None = Depends(get_optional_institution_user),
    db: Session = Depends(get_db),
    _throttle: None = Depends(rate_limit(5, 60)),
):
    if user is None:
        return RedirectResponse(LOGIN_REDIRECT, status_code=303)

    try:
        conducted_test_paper_job_service.publish_job(db, job_id, user.institution_id)
    except NotFoundException:
        return RedirectResponse(BASE_PATH, status_code=303)
    except InvalidStateException as exc:
        return RedirectResponse(f"{BASE_PATH}/{job_id}/review?error={_quote(str(exc))}", status_code=303)
    except Exception:
        db.rollback()
        logger.exception("Unexpected failure confirming conducted test paper job %s", job_id)
        return RedirectResponse(
            f"{BASE_PATH}/{job_id}/review?error=" + _quote("Confirming failed. Please try again."),
            status_code=303,
        )

    return RedirectResponse(f"{BASE_PATH}/{job_id}/review?published=1", status_code=303)


def _quote(message: str) -> str:
    from urllib.parse import quote
    return quote(message, safe="")
