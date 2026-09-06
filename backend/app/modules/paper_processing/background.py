"""
The processing pipeline and its in-process runner.

There is no task queue in this codebase (no Celery/RQ/Redis), and this
feature does not introduce one. Processing runs through FastAPI's own
`BackgroundTasks`, in the same process that served the request, with its own
database session.

Consequences, stated plainly rather than hidden:
  * a server restart mid-processing loses that job's progress. The job is
    left sitting in whatever stage it reached; `recover_stuck_job` lets the
    admin simply re-run it from the beginning, which is safe because every
    stage is idempotent and the untouched original PDF is never overwritten.
  * a very large scanned PDF occupies a worker thread while it OCRs.

`run_pipeline` is a plain function taking a session, so tests (and the
recovery path) can call it synchronously instead of racing a real
background task.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.enums import PdfTypeEnum, ProcessingStatusEnum, WatermarkStatusEnum
from app.core.google_drive import get_drive_client

from .extraction import ExtractionError, OcrUnavailableError, extract_text_with_positions
from .model import PaperProcessingJob
from .pdf_analysis import analyze_pdf
from .pdf_validation import PdfValidationError, validate_pdf
from .question_parser import parse_questions
from .question_visuals import detect_question_visuals
from .service import IN_FLIGHT_STATUSES, paper_processing_service
from .watermark import clean_watermarks

logger = logging.getLogger(__name__)


GENERIC_FAILURE_MESSAGE = (
    "Something went wrong while processing this PDF. The original upload is "
    "safe - you can try running processing again, or contact an administrator."
)

CANCELLED_MESSAGE = "Processing was stopped by an admin."


class _Cancelled(Exception):
    """Internal control-flow signal - never escapes `run_pipeline`."""


def _checkpoint(db: Session, job: PaperProcessingJob, stage: str) -> None:
    """
    Called between every stage: logs where the pipeline actually is (the
    single most useful thing for diagnosing "why is this stuck at X"), and
    stops the run here if an admin asked it to via the Stop button - this is
    the only place a running job can be interrupted, since there is no task
    queue to kill a thread outright.
    """
    logger.info("Job %s: checkpoint reached - %s", job.id, stage)

    if paper_processing_service.is_cancel_requested(db, job):
        logger.info("Job %s: stop requested, halting at '%s'", job.id, stage)
        raise _Cancelled()


def run_pipeline(db: Session, job_id: int) -> PaperProcessingJob:
    """
    Runs validation -> watermark cleaning -> type detection -> extraction ->
    question detection for one job, committing between stages so the admin's
    status polling shows real progress.

    Always leaves the job in a terminal state (READY_FOR_REVIEW,
    VALIDATION_FAILED or FAILED). Never raises for an expected failure.
    """
    service = paper_processing_service
    job = service.get_job(db, job_id)

    logger.info(
        "Job %s: starting pipeline (title=%r, original_filename=%r)",
        job.id, job.title, job.original_filename,
    )

    client = get_drive_client()

    try:
        # ------------------------------------------------------- 1. validate --
        service.set_status(db, job, ProcessingStatusEnum.VALIDATING)
        _checkpoint(db, job, "before download")

        logger.info("Job %s: downloading original PDF (file_id=%s)", job.id, job.original_file_id)
        try:
            content = client.download_file(job.original_file_id)
        except Exception:
            logger.exception("Job %s: could not download the source PDF", job.id)
            return service.fail_job(
                db, job,
                "The uploaded PDF could not be read back from storage. "
                "Please try uploading it again.",
            )
        logger.info("Job %s: downloaded %d bytes", job.id, len(content))

        try:
            validate_pdf(content)
            logger.info("Job %s: PDF validation passed", job.id)
        except PdfValidationError as exc:
            logger.info("Job %s: PDF validation failed - %s", job.id, exc)
            return service.fail_job(
                db, job, str(exc), ProcessingStatusEnum.VALIDATION_FAILED
            )
        except Exception:
            logger.exception("Job %s: unexpected error validating the PDF", job.id)
            return service.fail_job(
                db, job, GENERIC_FAILURE_MESSAGE, ProcessingStatusEnum.VALIDATION_FAILED
            )

        # ----------------------------------------------- 2. watermark cleaning --
        service.set_status(db, job, ProcessingStatusEnum.CLEANING_WATERMARK)
        _checkpoint(db, job, "before watermark cleaning")

        working_content = content

        try:
            watermark_result = clean_watermarks(content)
        except Exception:
            logger.exception("Job %s: watermark pass crashed", job.id)
            # Failing to clean is never a reason to lose the paper - flag it
            # and carry on with the untouched original.
            watermark_result = None

        if watermark_result is None:
            job.watermark_status = WatermarkStatusEnum.NEEDS_MANUAL_REVIEW
            db.commit()
            logger.info("Job %s: watermark cleaning skipped (needs manual review)", job.id)
        else:
            job.watermark_status = watermark_result.status
            logger.info("Job %s: watermark status = %s", job.id, watermark_result.status.value)

            if watermark_result.content:
                try:
                    upload = client.upload_file(
                        watermark_result.content,
                        filename=f"cleaned-{job.original_filename or 'source.pdf'}",
                        mime_type="application/pdf",
                        category="paper_processing_sources",
                    )
                    job.cleaned_file_id = upload.file_id
                    job.cleaned_mime_type = upload.mime_type
                    job.cleaned_file_size = upload.file_size
                    job.cleaned_filename = upload.name
                    working_content = watermark_result.content
                    logger.info("Job %s: stored cleaned PDF (file_id=%s)", job.id, upload.file_id)
                except Exception:
                    logger.exception("Job %s: could not store the cleaned PDF", job.id)
                    # Keep going with the in-memory cleaned bytes; the admin
                    # just does not get a stored copy of them.
                    working_content = watermark_result.content
                    job.watermark_status = WatermarkStatusEnum.NEEDS_MANUAL_REVIEW

            db.commit()

        # ------------------------------------------------------- 3. pdf type --
        service.set_status(db, job, ProcessingStatusEnum.ANALYZING)
        _checkpoint(db, job, "before PDF type analysis")

        analysis = analyze_pdf(working_content)
        job.pdf_type = analysis["pdf_type"]
        db.commit()
        logger.info(
            "Job %s: pdf_type=%s (text_pages=%s/%s, total_chars=%s)",
            job.id, analysis["pdf_type"].value if analysis["pdf_type"] else None,
            analysis["text_pages"], analysis["page_count"], analysis["total_chars"],
        )

        # ------------------------------------------------------ 4. extraction --
        service.set_status(db, job, ProcessingStatusEnum.EXTRACTING)
        _checkpoint(db, job, "before text/OCR extraction")

        logger.info(
            "Job %s: extracting %s (pdf_type=%s)", job.id,
            "with OCR" if job.pdf_type != PdfTypeEnum.TEXT else "text layer",
            job.pdf_type.value if job.pdf_type else None,
        )
        try:
            text, ocr_used, blocks = extract_text_with_positions(
                working_content, job.pdf_type or PdfTypeEnum.UNKNOWN
            )
        except OcrUnavailableError as exc:
            # Hard failure by design: a missing OCR engine must never look
            # like "this paper contained no questions".
            logger.warning("Job %s: OCR unavailable - %s", job.id, exc)
            return service.fail_job(db, job, str(exc))
        except ExtractionError as exc:
            logger.warning("Job %s: extraction failed - %s", job.id, exc)
            return service.fail_job(db, job, str(exc))
        except Exception:
            logger.exception("Job %s: unexpected extraction failure", job.id)
            return service.fail_job(db, job, GENERIC_FAILURE_MESSAGE)

        job.ocr_used = ocr_used
        db.commit()
        logger.info(
            "Job %s: extraction produced %d characters across %d positioned blocks (ocr_used=%s)",
            job.id, len(text), len(blocks), ocr_used,
        )

        # ----------------------------------------------- 5. question detection --
        service.set_status(db, job, ProcessingStatusEnum.DETECTING_QUESTIONS)
        _checkpoint(db, job, "before question/option detection")

        try:
            parsed = parse_questions(text, ocr_used=ocr_used)
        except Exception:
            logger.exception("Job %s: question detection failed", job.id)
            return service.fail_job(db, job, GENERIC_FAILURE_MESSAGE)
        logger.info("Job %s: detected %d question blocks", job.id, len(parsed))

        # Diagrams/graphs/tables are associated by geometry, not by the
        # parsed text itself - a failure here must never lose the questions
        # that were already successfully parsed, so it is logged and
        # treated as "no visuals found" rather than failing the whole job.
        try:
            visuals = detect_question_visuals(working_content, parsed, blocks)
        except Exception:
            logger.exception("Job %s: visual/diagram detection failed", job.id)
            visuals = {}
        total_visuals = sum(len(v) for v in visuals.values())
        logger.info(
            "Job %s: found %d visual asset(s) across %d question(s)",
            job.id, total_visuals, len(visuals),
        )

        _checkpoint(db, job, "before saving detected questions")

        try:
            service.replace_extracted_questions(db, job, parsed, ocr_used=ocr_used, visuals=visuals)
        except Exception:
            logger.exception("Job %s: could not store extracted questions", job.id)
            db.rollback()
            return service.fail_job(db, job, GENERIC_FAILURE_MESSAGE)

        if not parsed:
            # A real, reportable outcome - the admin can still add questions
            # by hand on the review screen, so this is not a dead end.
            logger.info("Job %s: no questions detected - ready for manual entry", job.id)
            return service.set_status(
                db, job,
                ProcessingStatusEnum.READY_FOR_REVIEW,
                "No questions could be detected automatically in this PDF. "
                "You can add them manually on the review screen.",
            )

        logger.info("Job %s: pipeline finished, ready for review", job.id)
        return service.set_status(db, job, ProcessingStatusEnum.READY_FOR_REVIEW)

    except _Cancelled:
        return service.fail_job(db, job, CANCELLED_MESSAGE)


def run_pipeline_in_background(job_id: int) -> None:
    """
    Entry point for `BackgroundTasks.add_task`. Opens its own session: the
    request's session is closed the moment the response is sent, so reusing
    it here would blow up mid-pipeline.
    """
    db = SessionLocal()
    try:
        run_pipeline(db, job_id)
    except Exception:
        # Belt and braces - run_pipeline handles expected failures itself,
        # but a background task that raises would otherwise vanish silently.
        logger.exception("Job %s: paper processing pipeline crashed", job_id)
        try:
            job = paper_processing_service.get_job(db, job_id)
            paper_processing_service.fail_job(db, job, GENERIC_FAILURE_MESSAGE)
        except Exception:
            logger.exception("Job %s: could not record pipeline failure", job_id)
    finally:
        db.close()


# A job that is genuinely still working commits real progress at least this
# often (every stage transition, and every question during image uploads -
# see PaperProcessingService.replace_extracted_questions) - once an
# in-flight job's `updated_at` is older than this, nothing is actually
# moving it forward any more (most likely a server restart), rather than it
# just being a slow stage on a paper with many diagrams.
STUCK_AFTER = timedelta(minutes=3)


def is_stuck(job: PaperProcessingJob) -> bool:
    """
    True only if the job looks *abandoned* mid-pipeline, not merely "in an
    in-flight status" - a paper with a hundred-plus diagrams can legitimately
    spend several real minutes in DETECTING_QUESTIONS uploading images one
    at a time, and that must not be shown to the admin as "stuck".
    """
    if job.status not in IN_FLIGHT_STATUSES:
        return False

    if job.updated_at is None:
        return True

    updated_at = job.updated_at
    if updated_at.tzinfo is None:
        # SQLite (tests, and any dev DB using it) returns naive datetimes
        # even though the column is declared timezone-aware; Postgres does
        # not. Treat a naive value as UTC either way.
        updated_at = updated_at.replace(tzinfo=timezone.utc)

    return datetime.now(timezone.utc) - updated_at > STUCK_AFTER
