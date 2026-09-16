"""
The processing pipeline for an institution's uploaded conducted-test paper.

Deliberately reuses the exact same stateless pipeline functions the
platform admin's paper_processing.background uses (validate_pdf,
clean_watermarks, analyze_pdf, extract_text_with_positions,
parse_questions) - none of those depend on PaperProcessingJob/Admin/
Subject, they just operate on PDF bytes in and structured data out, so
there is no reason to fork that logic. What's institution-specific is
only the job bookkeeping (this module's own service/model) and the
narrower scope: no diagram/image detection stage and no re-branded PDF
regeneration (see model.py's docstring for why).

Same execution model as paper_processing.background: no task queue,
runs via FastAPI BackgroundTasks in-process, with its own DB session -
see that module's docstring for the consequences (server restart loses
progress; re-running is always safe since every stage is idempotent and
the original upload is never overwritten).
"""
import logging
import uuid

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.enums import PdfTypeEnum, ProcessingStatusEnum, WatermarkStatusEnum
from app.core.google_drive import get_drive_client
from app.modules.paper_processing.extraction import ExtractionError, OcrUnavailableError, extract_text_with_positions
from app.modules.paper_processing.pdf_analysis import analyze_pdf
from app.modules.paper_processing.pdf_validation import PdfValidationError, validate_pdf
from app.modules.paper_processing.question_parser import parse_questions
from app.modules.paper_processing.watermark import clean_watermarks

from .model import ConductedTestPaperJob
from .service import IN_FLIGHT_STATUSES, conducted_test_paper_job_service

logger = logging.getLogger(__name__)

GENERIC_FAILURE_MESSAGE = (
    "Something went wrong while processing this PDF. The original upload is "
    "safe - you can try running processing again, or contact your platform "
    "administrator if this keeps happening."
)

CANCELLED_MESSAGE = "Processing was stopped."


class _Cancelled(Exception):
    """Internal control-flow signal - never escapes `run_pipeline`."""


def _checkpoint(db: Session, job: ConductedTestPaperJob, stage: str) -> None:
    logger.info("Conducted test paper job %s: checkpoint reached - %s", job.id, stage)

    if conducted_test_paper_job_service.is_cancel_requested(db, job):
        logger.info("Conducted test paper job %s: stop requested, halting at '%s'", job.id, stage)
        raise _Cancelled()


def run_pipeline(db: Session, job_id: uuid.UUID) -> ConductedTestPaperJob:
    """
    Runs validation -> watermark cleaning -> type detection -> extraction ->
    question detection for one job. Always leaves the job in a terminal
    state (READY_FOR_REVIEW, VALIDATION_FAILED or FAILED).
    """
    service = conducted_test_paper_job_service
    job = service.get_job(db, job_id)

    logger.info(
        "Conducted test paper job %s: starting pipeline (title=%r)",
        job.id, job.title,
    )

    client = get_drive_client()

    try:
        service.set_status(db, job, ProcessingStatusEnum.VALIDATING)
        _checkpoint(db, job, "before download")

        try:
            content = client.download_file(job.original_file_id)
        except Exception:
            logger.exception("Conducted test paper job %s: could not download the source PDF", job.id)
            return service.fail_job(
                db, job,
                "The uploaded PDF could not be read back from storage. "
                "Please try uploading it again.",
            )

        try:
            validate_pdf(content)
        except PdfValidationError as exc:
            return service.fail_job(db, job, str(exc), ProcessingStatusEnum.VALIDATION_FAILED)
        except Exception:
            logger.exception("Conducted test paper job %s: unexpected error validating the PDF", job.id)
            return service.fail_job(db, job, GENERIC_FAILURE_MESSAGE, ProcessingStatusEnum.VALIDATION_FAILED)

        service.set_status(db, job, ProcessingStatusEnum.CLEANING_WATERMARK)
        _checkpoint(db, job, "before watermark cleaning")

        working_content = content

        try:
            watermark_result = clean_watermarks(content)
        except Exception:
            logger.exception("Conducted test paper job %s: watermark pass crashed", job.id)
            watermark_result = None

        if watermark_result is None:
            job.watermark_status = WatermarkStatusEnum.NEEDS_MANUAL_REVIEW
            db.commit()
        else:
            job.watermark_status = watermark_result.status

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
                except Exception:
                    logger.exception("Conducted test paper job %s: could not store the cleaned PDF", job.id)
                    working_content = watermark_result.content
                    job.watermark_status = WatermarkStatusEnum.NEEDS_MANUAL_REVIEW

            db.commit()

        service.set_status(db, job, ProcessingStatusEnum.ANALYZING)
        _checkpoint(db, job, "before PDF type analysis")

        analysis = analyze_pdf(working_content)
        job.pdf_type = analysis["pdf_type"]
        db.commit()

        service.set_status(db, job, ProcessingStatusEnum.EXTRACTING)
        _checkpoint(db, job, "before text/OCR extraction")

        try:
            text, ocr_used, _blocks = extract_text_with_positions(
                working_content, job.pdf_type or PdfTypeEnum.UNKNOWN
            )
        except OcrUnavailableError as exc:
            logger.warning("Conducted test paper job %s: OCR unavailable - %s", job.id, exc)
            return service.fail_job(db, job, str(exc))
        except ExtractionError as exc:
            logger.warning("Conducted test paper job %s: extraction failed - %s", job.id, exc)
            return service.fail_job(db, job, str(exc))
        except Exception:
            logger.exception("Conducted test paper job %s: unexpected extraction failure", job.id)
            return service.fail_job(db, job, GENERIC_FAILURE_MESSAGE)

        job.ocr_used = ocr_used
        db.commit()

        service.set_status(db, job, ProcessingStatusEnum.DETECTING_QUESTIONS)
        _checkpoint(db, job, "before question/option detection")

        try:
            parsed = parse_questions(text, ocr_used=ocr_used)
        except Exception:
            logger.exception("Conducted test paper job %s: question detection failed", job.id)
            return service.fail_job(db, job, GENERIC_FAILURE_MESSAGE)

        _checkpoint(db, job, "before saving detected questions")

        try:
            service.replace_extracted_questions(db, job, parsed, ocr_used=ocr_used)
        except Exception:
            logger.exception("Conducted test paper job %s: could not store extracted questions", job.id)
            db.rollback()
            return service.fail_job(db, job, GENERIC_FAILURE_MESSAGE)

        if not parsed:
            return service.set_status(
                db, job,
                ProcessingStatusEnum.READY_FOR_REVIEW,
                "No questions could be detected automatically in this PDF. "
                "You can add them manually on the review screen.",
            )

        return service.set_status(db, job, ProcessingStatusEnum.READY_FOR_REVIEW)

    except _Cancelled:
        return service.fail_job(db, job, CANCELLED_MESSAGE)


def run_pipeline_in_background(job_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        run_pipeline(db, job_id)
    except Exception:
        logger.exception("Conducted test paper job %s: pipeline crashed", job_id)
        try:
            job = conducted_test_paper_job_service.get_job(db, job_id)
            conducted_test_paper_job_service.fail_job(db, job, GENERIC_FAILURE_MESSAGE)
        except Exception:
            logger.exception("Conducted test paper job %s: could not record pipeline failure", job_id)
    finally:
        db.close()


def is_stuck(job: ConductedTestPaperJob) -> bool:
    """Same 3-minute abandonment heuristic as paper_processing.background.is_stuck."""
    from datetime import datetime, timedelta, timezone

    if job.status not in IN_FLIGHT_STATUSES:
        return False

    if job.updated_at is None:
        return True

    updated_at = job.updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)

    return datetime.now(timezone.utc) - updated_at > timedelta(minutes=3)
