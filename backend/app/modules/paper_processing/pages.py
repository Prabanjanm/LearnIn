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
from app.core.enums import PaperTypeEnum, PaperUsageEnum, ProcessingStatusEnum
from app.modules.admin.dependencies import get_optional_admin
from app.modules.admin.model import Admin
from app.modules.department.model import Department
from app.modules.exam.model import Exam
from app.modules.paper.service import paper_service
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

# Shared by the "new job" form, a job's preview page, and the standalone
# per-paper usage page (papers with no processing job at all) - one list,
# used everywhere "Use This Paper For" is rendered.
USAGE_OPTIONS = [
    (PaperUsageEnum.PREVIOUS_YEAR_PAPERS, "Previous Year Papers"),
    (PaperUsageEnum.PRACTICE, "Practice"),
    (PaperUsageEnum.MOCK_TEST, "Mock Tests"),
    (PaperUsageEnum.SUBJECT_PRACTICE, "Subject Practice"),
    (PaperUsageEnum.EXAM_PRACTICE, "Exam Practice"),
    (PaperUsageEnum.RESOURCE, "Resources"),
]

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


def _build_exam_tree(db: Session) -> list[dict]:
    """
    Every exam -> department -> subject, nested, for the "new job" form's
    cascading selects - one JSON blob rendered once, filtered entirely in
    the browser (no per-selection round trip). Not filtered to PUBLISHED
    only: an admin has always been able to attach a paper to any subject
    here, including one still in DRAFT.
    """
    exams = db.query(Exam).order_by(Exam.name).all()
    departments = db.query(Department).order_by(Department.name).all()
    subjects = db.query(Subject).order_by(Subject.name).all()

    subjects_by_department: dict[int, list[dict]] = {}
    for subject in subjects:
        subjects_by_department.setdefault(subject.department_id, []).append(
            {"id": subject.id, "name": subject.name}
        )

    departments_by_exam: dict[int, list[dict]] = {}
    for department in departments:
        departments_by_exam.setdefault(department.exam_id, []).append({
            "id": department.id,
            "name": department.name,
            "subjects": subjects_by_department.get(department.id, []),
        })

    return [
        {"id": exam.id, "name": exam.name, "departments": departments_by_exam.get(exam.id, [])}
        for exam in exams
    ]


def _render_new_form(request: Request, admin, db: Session, error: str | None, status_code: int = 200):
    return templates.TemplateResponse(
        request=request,
        name="admin/paper_processing/new.html",
        context={
            "admin": admin,
            "exam_tree_json": json.dumps(_build_exam_tree(db)),
            "paper_types": list(PaperTypeEnum),
            "usage_options": USAGE_OPTIONS,
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

    def fail(message: str):
        db.rollback()
        cleanup_drive_files(db, uploaded_ids)
        return _render_new_form(request, admin, db, error=message, status_code=400)

    if not source:
        # Nothing was uploaded, so nothing to clean up.
        return fail("Please upload the source question paper PDF before saving.")

    # --- validate the exam -> department -> subject(s) chain server-side --
    # (the cascading selects already only ever offer a consistent chain,
    # but the request body is never trusted just because the form was
    # built correctly - a subject belonging to a different department must
    # be rejected here regardless of what the client sent.)
    try:
        exam_id = int(form_data.get("exam_id") or 0)
        department_id = int(form_data.get("department_id") or 0)
        subject_ids = [int(v) for v in form_data.getlist("subject_ids") if v]
        year = int(form_data.get("year") or 0)
    except ValueError:
        return fail("Exam, department, subject and year must be selected.")

    if not subject_ids:
        return fail("Select at least one subject.")

    department = db.query(Department).filter(Department.id == department_id).first()
    if department is None or department.exam_id != exam_id:
        return fail("The selected department does not belong to the selected exam.")

    subjects = db.query(Subject).filter(Subject.id.in_(subject_ids)).all()
    if len(subjects) != len(set(subject_ids)):
        return fail("One or more selected subjects could not be found.")
    for subject in subjects:
        if subject.department_id != department_id:
            return fail(
                f"'{subject.name}' does not belong to the selected department - "
                "pick subjects from the same department as the paper."
            )

    title = (form_data.get("title") or "").strip()
    if not title:
        return fail("A paper title is required.")
    if not year:
        return fail("A paper year is required.")

    paper_type_raw = (form_data.get("paper_type") or "").strip()
    paper_type = PaperTypeEnum(paper_type_raw) if paper_type_raw in PaperTypeEnum.__members__ else None

    usage_flags = [
        value for value in form_data.getlist("usage_flags")
        if value in PaperUsageEnum.__members__
    ]

    # --- duplicate prevention: skip (not fail outright) any subject that --
    # already has a Paper for this exact year - re-uploading the same
    # paper never creates a second record. A second in-flight *job* for
    # the same (subject, year) is deliberately still allowed here (a
    # retry/second attempt before either has published is just data, not
    # a duplicate) - Paper.uq_subject_year is what actually rejects a
    # second one at publish time (see PaperProcessingService.publish_job).
    skipped: list[str] = []
    subjects_to_process = []
    for subject in subjects:
        if paper_service.repository.get_by_subject_and_year(db, subject.id, year) is not None:
            skipped.append(f"{subject.name} (a paper for {year} already exists)")
            continue
        subjects_to_process.append(subject)

    if not subjects_to_process:
        return fail(
            "Nothing to process - " + "; ".join(skipped)
            if skipped else "Nothing to process."
        )

    created_jobs = []
    try:
        for subject in subjects_to_process:
            job_title = title if len(subjects_to_process) == 1 else f"{title} - {subject.name}"

            data = PaperProcessingJobCreate(
                subject_id=subject.id,
                title=job_title,
                year=year,
                paper_type=paper_type,
                usage_flags=usage_flags,
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
            created_jobs.append(paper_processing_service.create_job(db, admin.id, data))

    except (ValueError, NotFoundException, AlreadyExistsException) as exc:
        return fail(str(exc))

    except Exception:
        logger.exception("Failed to create a paper processing job")
        return fail("The job could not be created. Please try again.")

    for job in created_jobs:
        background_tasks.add_task(run_pipeline_in_background, job.id)

    if len(created_jobs) == 1:
        return RedirectResponse(f"{BASE_PATH}/{created_jobs[0].id}", status_code=303)

    # Multiple subjects selected - one job per subject was created and
    # started; land on the list rather than picking one arbitrarily.
    return RedirectResponse(BASE_PATH, status_code=303)


# ---------------------------------------------- manage usage on any paper ---
#
# "Use This Paper For" for a paper that has no PaperProcessingJob at all -
# created directly through the generic admin CRUD (/admin/manage/papers),
# imported before this feature existed, or otherwise not run through this
# pipeline. A paper WITH a job still gets managed from its own preview page
# (see update_usage above) - this is the other entry point onto the exact
# same PaperProcessingService.update_usage_for_paper.
#
# NOTE: these routes must be registered before "/{job_id}" below - otherwise
# a request for "/papers" would match "/{job_id}" first (job_id: int) and
# fail path-parameter conversion with a 422 before ever reaching this route.

@router.get(BASE_PATH + "/papers")
def papers_list(
    request: Request,
    admin: Admin | None = Depends(get_optional_admin),
    db: Session = Depends(get_db),
):
    if admin is None:
        return RedirectResponse(LOGIN_REDIRECT, status_code=303)

    papers = paper_service.repository.list_all_with_hierarchy(db)

    return templates.TemplateResponse(
        request=request,
        name="admin/paper_processing/papers_list.html",
        context={
            "admin": admin,
            "papers": papers,
            "base_path": BASE_PATH,
        },
    )


@router.get(BASE_PATH + "/papers/{paper_id}/usage")
def paper_usage_page(
    paper_id: int,
    request: Request,
    admin: Admin | None = Depends(get_optional_admin),
    db: Session = Depends(get_db),
):
    if admin is None:
        return RedirectResponse(LOGIN_REDIRECT, status_code=303)

    try:
        paper = paper_service.get_or_404(db, paper_id, "Paper not found")
    except NotFoundException:
        return RedirectResponse(f"{BASE_PATH}/papers", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="admin/paper_processing/paper_usage.html",
        context={
            "admin": admin,
            "paper": paper,
            "available_at": paper_processing_service.apply_usage(db, paper),
            "usage_options": USAGE_OPTIONS,
            "selected_usage": set(paper.usage_flags_list()),
            "error": request.query_params.get("error"),
            "base_path": BASE_PATH,
        },
    )


@router.post(BASE_PATH + "/papers/{paper_id}/usage")
async def paper_usage_update(
    paper_id: int,
    request: Request,
    admin: Admin | None = Depends(get_optional_admin),
    db: Session = Depends(get_db),
    _throttle: None = Depends(rate_limit(10, 60)),
):
    if admin is None:
        return RedirectResponse(LOGIN_REDIRECT, status_code=303)

    form_data = await request.form()
    usage_flags = [v for v in form_data.getlist("usage_flags") if v in PaperUsageEnum.__members__]

    try:
        paper_processing_service.update_usage_for_paper(db, paper_id, usage_flags)
    except NotFoundException:
        return RedirectResponse(f"{BASE_PATH}/papers", status_code=303)

    return RedirectResponse(f"{BASE_PATH}/papers/{paper_id}/usage?usage_updated=1", status_code=303)


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
            "message": request.query_params.get("message"),
            **_job_context(db, job),
        },
    )


@router.post(BASE_PATH + "/{job_id}/answer-key")
async def attach_answer_key(
    job_id: int,
    request: Request,
    admin: Admin | None = Depends(get_optional_admin),
    db: Session = Depends(get_db),
    _throttle: None = Depends(rate_limit(10, 60)),
):
    """
    Attaches or replaces the answer key on a job that already has questions
    staged - for the common case of the question paper being uploaded (and
    processed) before the key was ready.
    """
    if admin is None:
        return RedirectResponse(LOGIN_REDIRECT, status_code=303)

    form_data = await request.form()
    answer = _parse_upload_json(form_data.get("answer_file_id"))

    if not answer:
        return RedirectResponse(
            f"{BASE_PATH}/{job_id}/review?error="
            + _quote("Please upload the answer key PDF before saving."),
            status_code=303,
        )

    try:
        message = paper_processing_service.set_answer_key(
            db, job_id,
            file_id=answer["file_id"],
            mime_type=answer.get("mime_type"),
            file_size=answer.get("file_size"),
            filename=answer.get("filename"),
        )
    except NotFoundException:
        return RedirectResponse(BASE_PATH, status_code=303)
    except InvalidStateException as exc:
        return RedirectResponse(
            f"{BASE_PATH}/{job_id}/review?error={_quote(str(exc))}",
            status_code=303,
        )

    return RedirectResponse(
        f"{BASE_PATH}/{job_id}/review?message={_quote(message)}",
        status_code=303,
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
            "available_at": paper_processing_service.apply_usage(db, job.paper) if job.paper_id else [],
            "usage_options": USAGE_OPTIONS,
            "selected_usage": set(job.paper.usage_flags_list()) if job.paper_id else set(job.usage_flags_list()),
            **_job_context(db, job),
        },
    )


@router.post(BASE_PATH + "/{job_id}/usage")
async def update_usage(
    job_id: int,
    request: Request,
    admin: Admin | None = Depends(get_optional_admin),
    db: Session = Depends(get_db),
    _throttle: None = Depends(rate_limit(10, 60)),
):
    """
    Changes "Use This Paper For" on an already-published paper - re-applied
    immediately (see PaperProcessingService.apply_usage): a newly-checked
    area is created/restored, a newly-unchecked one is archived.
    """
    if admin is None:
        return RedirectResponse(LOGIN_REDIRECT, status_code=303)

    form_data = await request.form()
    usage_flags = [v for v in form_data.getlist("usage_flags") if v in PaperUsageEnum.__members__]

    try:
        paper_processing_service.update_usage(db, job_id, usage_flags)
    except NotFoundException:
        return RedirectResponse(BASE_PATH, status_code=303)
    except InvalidStateException as exc:
        return RedirectResponse(
            f"{BASE_PATH}/{job_id}/preview?error={_quote(str(exc))}",
            status_code=303,
        )

    return RedirectResponse(f"{BASE_PATH}/{job_id}/preview?usage_updated=1", status_code=303)


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


@router.post(BASE_PATH + "/{job_id}/go-live")
def go_live(
    job_id: int,
    admin: Admin | None = Depends(get_optional_admin),
    db: Session = Depends(get_db),
    _throttle: None = Depends(rate_limit(5, 60)),
):
    """Makes an already-published (but still DRAFT) paper visible to students."""
    if admin is None:
        return RedirectResponse(LOGIN_REDIRECT, status_code=303)

    try:
        paper_processing_service.go_live(db, job_id)
    except NotFoundException:
        return RedirectResponse(BASE_PATH, status_code=303)
    except InvalidStateException as exc:
        return RedirectResponse(
            f"{BASE_PATH}/{job_id}/preview?error={_quote(str(exc))}",
            status_code=303,
        )

    return RedirectResponse(f"{BASE_PATH}/{job_id}/preview?live=1", status_code=303)


def _quote(message: str) -> str:
    from urllib.parse import quote

    return quote(message, safe="")
