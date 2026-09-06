"""
End-to-end coverage of the Question Paper Processing workflow.

Google Drive is never really called: a fake client keeps uploaded bytes in a
dict, which is enough for the pipeline (upload -> download -> re-upload) and
keeps the tests hermetic.

The pipeline is invoked directly rather than through FastAPI's background
task machinery, so assertions never race a real background thread.
"""
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.common.exceptions.exceptions import InvalidStateException
from app.common.rate_limit import reset_rate_limits
from app.core.enums import (
    DifficultyEnum,
    ProcessingStatusEnum,
    QuestionType,
    StatusEnum,
)
from app.core.google_drive import DriveUploadResult
from app.main import app
from app.modules.option.model import Option
from app.modules.paper.model import Paper
from app.modules.paper_processing import background as background_module
from app.modules.paper_processing import service as service_module
from app.modules.paper_processing.background import run_pipeline
from app.modules.paper_processing.extraction import OcrUnavailableError
from app.modules.paper_processing.service import paper_processing_service
from app.modules.question.model import Question

from pdf_fixtures import (  # noqa: E402 - tests/ is on sys.path via pytest rootdir
    corrupted_pdf,
    sample_paper_pdf,
    scanned_pdf,
)

client = TestClient(app)

API = "/api/admin/paper-processing"
UI = "/admin/paper-processing"


class FakeDriveClient:
    """In-memory stand-in for GoogleDriveClient."""

    def __init__(self):
        self.files: dict[str, tuple[bytes, str, str]] = {}
        self.deleted: list[str] = []

    def seed(self, content: bytes, filename="source.pdf") -> str:
        file_id = f"drive-{uuid.uuid4().hex[:12]}"
        self.files[file_id] = (content, "application/pdf", filename)
        return file_id

    def upload_file(self, content, filename, mime_type, category=None, **kwargs):
        file_id = self.seed(content, filename)
        return DriveUploadResult(
            file_id=file_id,
            mime_type=mime_type,
            file_size=len(content),
            name=filename,
        )

    def download_file(self, file_id):
        return self.files[file_id][0]

    def get_file_metadata(self, file_id):
        content, mime_type, name = self.files[file_id]
        return {"id": file_id, "name": name, "mimeType": mime_type, "size": len(content)}

    def delete_file(self, file_id):
        self.deleted.append(file_id)
        self.files.pop(file_id, None)


@pytest.fixture()
def drive(monkeypatch):
    fake = FakeDriveClient()

    # Every module that reaches for a Drive client during this flow.
    monkeypatch.setattr(background_module, "get_drive_client", lambda: fake)
    monkeypatch.setattr(service_module, "get_drive_client", lambda: fake)

    import app.common.utils.file_tracking as file_tracking
    import app.modules.admin.pages as admin_pages
    import app.modules.admin.router as admin_router

    monkeypatch.setattr(file_tracking, "get_drive_client", lambda: fake)
    monkeypatch.setattr(admin_pages, "get_drive_client", lambda: fake)
    monkeypatch.setattr(admin_router, "get_drive_client", lambda: fake)

    reset_rate_limits()
    return fake


def _make_subject(admin_auth_headers, suffix: str) -> int:
    exam = client.post(
        "/api/exams/",
        json={"name": f"PP Exam {suffix}", "code": f"QPP{suffix}"},
        headers=admin_auth_headers,
    ).json()

    department = client.post(
        "/api/departments/",
        json={"exam_id": exam["id"], "name": "Computer Science", "code": f"PPD{suffix}"},
        headers=admin_auth_headers,
    ).json()

    subject = client.post(
        "/api/subjects/",
        json={"department_id": department["id"], "name": f"Algorithms {suffix}"},
        headers=admin_auth_headers,
    ).json()

    return subject["id"]


def _upload_blob(file_id: str, filename="source.pdf") -> str:
    return json.dumps({
        "file_id": file_id,
        "mime_type": "application/pdf",
        "file_size": 1234,
        "filename": filename,
    })


def _create_job(
    admin_auth_headers,
    drive,
    monkeypatch,
    subject_id: int,
    content: bytes,
    title="GATE CSE",
    year=2024,
) -> int:
    """Posts the real step-1 form, with the background task stubbed out."""
    started: list[int] = []
    monkeypatch.setattr(
        "app.modules.paper_processing.pages.run_pipeline_in_background",
        lambda job_id: started.append(job_id),
    )

    source_id = drive.seed(content)

    response = client.post(
        f"{UI}/new",
        data={
            "subject_id": str(subject_id),
            "title": title,
            "year": str(year),
            "original_file_id": _upload_blob(source_id),
            "answer_file_id": "",
            "source_url": "https://example.com/paper.pdf",
            "source_notes": "Collected for testing",
        },
        headers=admin_auth_headers,
        follow_redirects=False,
    )

    assert response.status_code == 303
    job_id = int(response.headers["location"].rsplit("/", 1)[1])

    # The route really did schedule the pipeline; the test just runs it itself.
    assert started == [job_id]

    return job_id


# ------------------------------------------------------------- pipeline ----

def test_full_pipeline_extracts_questions_from_a_text_pdf(
    admin_auth_headers, drive, db_session, monkeypatch
):
    subject_id = _make_subject(admin_auth_headers, "A")
    job_id = _create_job(
        admin_auth_headers, drive, monkeypatch, subject_id, sample_paper_pdf()
    )

    run_pipeline(db_session, job_id)

    job = paper_processing_service.get_job(db_session, job_id)

    assert job.status == ProcessingStatusEnum.READY_FOR_REVIEW
    assert job.pdf_type.value == "TEXT"
    assert job.ocr_used is False
    assert job.questions_extracted == 4

    questions = paper_processing_service._questions.list_for_job(db_session, job_id)
    assert [q.order_index for q in questions] == [1, 2, 3, 4]
    assert questions[0].question_text.startswith("What is the time complexity")
    assert [option.label for option in questions[0].options] == ["A", "B", "C", "D"]

    # Extraction never invents an answer key.
    assert all(question.correct_answer is None for question in questions)
    # The raw block is kept so the admin can compare against their edits.
    assert all(question.raw_source_text for question in questions)


def test_validation_failure_is_reported_without_a_traceback(
    admin_auth_headers, drive, db_session, monkeypatch
):
    subject_id = _make_subject(admin_auth_headers, "B")
    job_id = _create_job(
        admin_auth_headers, drive, monkeypatch, subject_id, corrupted_pdf()
    )

    run_pipeline(db_session, job_id)

    job = paper_processing_service.get_job(db_session, job_id)

    assert job.status == ProcessingStatusEnum.VALIDATION_FAILED
    assert "corrupted" in job.error_message.lower()
    assert "Traceback" not in job.error_message


def test_scanned_pdf_fails_cleanly_when_ocr_engine_is_unavailable(
    admin_auth_headers, drive, db_session, monkeypatch
):
    subject_id = _make_subject(admin_auth_headers, "C")
    job_id = _create_job(
        admin_auth_headers, drive, monkeypatch, subject_id, scanned_pdf(page_count=2)
    )

    import pytesseract

    def boom(*args, **kwargs):
        raise pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(pytesseract, "image_to_data", boom)

    run_pipeline(db_session, job_id)

    job = paper_processing_service.get_job(db_session, job_id)

    assert job.status == ProcessingStatusEnum.FAILED
    assert "OCR" in job.error_message
    assert "administrator" in job.error_message
    # Crucially, it did NOT quietly report "0 questions extracted" as if OCR
    # had succeeded on an empty page.
    assert job.questions_extracted == 0


def test_is_stuck_ignores_recent_progress_but_flags_real_staleness():
    """
    A job sitting in an in-flight status is only "stuck" once nothing has
    moved it forward in a while - a paper with many diagrams can spend real
    minutes uploading images with no status change, and that must not be
    reported as abandoned.
    """
    from datetime import datetime, timedelta, timezone

    from app.modules.paper_processing.background import is_stuck
    from app.modules.paper_processing.model import PaperProcessingJob

    job = PaperProcessingJob(status=ProcessingStatusEnum.DETECTING_QUESTIONS)

    job.updated_at = datetime.now(timezone.utc)
    assert is_stuck(job) is False

    job.updated_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    assert is_stuck(job) is True

    job.status = ProcessingStatusEnum.READY_FOR_REVIEW
    assert is_stuck(job) is False


def test_stop_button_halts_the_pipeline_at_the_next_checkpoint(
    admin_auth_headers, drive, db_session, monkeypatch
):
    """
    There is no task queue to kill a running job outright, so "stop" is
    cooperative: the flag is set, and `run_pipeline` checks it between
    stages. Setting it before the run starts must halt at the very first
    checkpoint, before any real work happens.
    """
    subject_id = _make_subject(admin_auth_headers, "L")
    job_id = _create_job(
        admin_auth_headers, drive, monkeypatch, subject_id, sample_paper_pdf()
    )

    paper_processing_service.request_cancel(db_session, job_id)

    run_pipeline(db_session, job_id)

    job = paper_processing_service.get_job(db_session, job_id)
    assert job.status == ProcessingStatusEnum.FAILED
    assert "stopped" in job.error_message.lower()
    # Nothing was extracted - the run never reached that stage.
    assert job.questions_extracted == 0


def test_stop_is_a_no_op_once_the_job_already_finished(
    admin_auth_headers, drive, db_session, monkeypatch
):
    subject_id = _make_subject(admin_auth_headers, "M")
    job_id = _create_job(
        admin_auth_headers, drive, monkeypatch, subject_id, sample_paper_pdf()
    )

    run_pipeline(db_session, job_id)
    job = paper_processing_service.get_job(db_session, job_id)
    assert job.status == ProcessingStatusEnum.READY_FOR_REVIEW

    with pytest.raises(InvalidStateException):
        paper_processing_service.request_cancel(db_session, job_id)


def test_scanned_pdf_succeeds_when_ocr_is_available(
    admin_auth_headers, drive, db_session, monkeypatch
):
    subject_id = _make_subject(admin_auth_headers, "D")
    job_id = _create_job(
        admin_auth_headers, drive, monkeypatch, subject_id, scanned_pdf(page_count=1)
    )

    import pytesseract

    lines = [
        "1. An OCR'd question?",
        "A) one",
        "B) two",
        "C) three",
        "D) four",
    ]
    fake_data = {
        "text": lines,
        "left": [10] * len(lines),
        "top": [30 * i for i in range(len(lines))],
        "width": [100] * len(lines),
        "height": [20] * len(lines),
        "block_num": [1] * len(lines),
        "par_num": [1] * len(lines),
        "line_num": list(range(len(lines))),
    }

    monkeypatch.setattr(
        pytesseract, "image_to_data", lambda *args, **kwargs: fake_data,
    )

    run_pipeline(db_session, job_id)

    job = paper_processing_service.get_job(db_session, job_id)

    assert job.status == ProcessingStatusEnum.READY_FOR_REVIEW
    assert job.ocr_used is True
    assert job.questions_extracted == 1

    question = paper_processing_service._questions.list_for_job(db_session, job_id)[0]
    # OCR'd content never reaches HIGH confidence on its own.
    assert question.confidence.value in ("MEDIUM", "LOW")


def test_ocr_unavailable_error_message_is_admin_safe():
    error = OcrUnavailableError("OCR is required for this scanned PDF")
    assert "Traceback" not in str(error)


# --------------------------------------------------------------- review ----

def test_review_endpoints_edit_delete_and_reorder(
    admin_auth_headers, drive, db_session, monkeypatch
):
    subject_id = _make_subject(admin_auth_headers, "E")
    job_id = _create_job(
        admin_auth_headers, drive, monkeypatch, subject_id, sample_paper_pdf()
    )
    run_pipeline(db_session, job_id)

    listed = client.get(f"{API}/{job_id}/questions", headers=admin_auth_headers).json()
    assert len(listed) == 4
    first_id, second_id = listed[0]["id"], listed[1]["id"]

    # Edit
    edited = client.put(
        f"{API}/{job_id}/questions/{first_id}",
        json={
            "question_text": "Corrected question text?",
            "correct_answer": "B",
            "needs_review": False,
            "options": [
                {"label": "A", "option_text": "first"},
                {"label": "B", "option_text": "second"},
                {"label": "C", "option_text": "third"},
                {"label": "D", "option_text": "fourth"},
            ],
        },
        headers=admin_auth_headers,
    )
    assert edited.status_code == 200
    assert edited.json()["question_text"] == "Corrected question text?"
    assert edited.json()["correct_answer"] == "B"

    # Reorder
    moved = client.post(
        f"{API}/{job_id}/questions/{second_id}/move",
        json={"direction": "up"},
        headers=admin_auth_headers,
    )
    assert moved.status_code == 200

    reordered = client.get(f"{API}/{job_id}/questions", headers=admin_auth_headers).json()
    assert reordered[0]["id"] == second_id
    assert reordered[1]["id"] == first_id

    # Add
    added = client.post(
        f"{API}/{job_id}/questions",
        json={
            "question_text": "A manually added question?",
            "options": [
                {"label": "A", "option_text": "yes"},
                {"label": "B", "option_text": "no"},
            ],
        },
        headers=admin_auth_headers,
    )
    assert added.status_code == 200

    # Delete
    deleted = client.delete(
        f"{API}/{job_id}/questions/{first_id}", headers=admin_auth_headers
    )
    assert deleted.status_code == 200

    remaining = client.get(f"{API}/{job_id}/questions", headers=admin_auth_headers).json()
    assert len(remaining) == 4
    # order_index is always re-densified after a delete.
    assert [item["order_index"] for item in remaining] == [1, 2, 3, 4]


def test_split_and_merge_only_reuse_real_extracted_text(
    admin_auth_headers, drive, db_session, monkeypatch
):
    subject_id = _make_subject(admin_auth_headers, "F")
    job_id = _create_job(
        admin_auth_headers, drive, monkeypatch, subject_id, sample_paper_pdf()
    )
    run_pipeline(db_session, job_id)

    listed = client.get(f"{API}/{job_id}/questions", headers=admin_auth_headers).json()
    first_id = listed[0]["id"]
    original_raw = listed[0]["raw_source_text"]

    split = client.post(
        f"{API}/{job_id}/questions/{first_id}/split",
        json={"split_at": None},
        headers=admin_auth_headers,
    )
    assert split.status_code == 200
    halves = split.json()
    assert len(halves) == 2
    # Both halves are built from the block's own extracted text, and both
    # are flagged so nobody publishes an unedited split.
    assert all(half["needs_review"] for half in halves)
    assert all(half["question_text"] in original_raw for half in halves)

    after_split = client.get(f"{API}/{job_id}/questions", headers=admin_auth_headers).json()
    assert len(after_split) == 5

    merged = client.post(
        f"{API}/{job_id}/questions/{after_split[0]['id']}/merge",
        headers=admin_auth_headers,
    )
    assert merged.status_code == 200
    assert merged.json()["needs_review"] is True

    after_merge = client.get(f"{API}/{job_id}/questions", headers=admin_auth_headers).json()
    assert len(after_merge) == 4


def test_review_and_preview_pages_render_the_extracted_content(
    admin_auth_headers, drive, db_session, monkeypatch
):
    subject_id = _make_subject(admin_auth_headers, "J")
    job_id = _create_job(
        admin_auth_headers, drive, monkeypatch, subject_id, sample_paper_pdf(),
        title="Rendered Paper", year=2016,
    )
    run_pipeline(db_session, job_id)

    review = client.get(f"{UI}/{job_id}/review", headers=admin_auth_headers)
    assert review.status_code == 200
    assert "What is the time complexity" in review.text
    assert "O(log n)" in review.text
    assert "confidence" in review.text
    # The page is explicit that nothing was invented and nothing is live yet.
    assert "Nothing here has been" in review.text
    assert "PDF type: Text-based" in review.text

    preview = client.get(f"{UI}/{job_id}/preview", headers=admin_auth_headers)
    assert preview.status_code == 200
    assert "Questions extracted" in preview.text
    assert "Answer Key: Not Available" in preview.text

    status_page = client.get(f"{UI}/{job_id}", headers=admin_auth_headers)
    assert status_page.status_code == 200
    assert "Ready for review" in status_page.text

    listing = client.get(UI, headers=admin_auth_headers)
    assert "Rendered Paper" in listing.text


def test_status_endpoint_reports_progress(admin_auth_headers, drive, db_session, monkeypatch):
    subject_id = _make_subject(admin_auth_headers, "K")
    job_id = _create_job(
        admin_auth_headers, drive, monkeypatch, subject_id, sample_paper_pdf(),
        title="Status Paper", year=2015,
    )

    before = client.get(f"{API}/{job_id}/status", headers=admin_auth_headers).json()
    assert before["status"] == "UPLOADED"
    assert before["questions_extracted"] == 0

    run_pipeline(db_session, job_id)

    after = client.get(f"{API}/{job_id}/status", headers=admin_auth_headers).json()
    assert after["status"] == "READY_FOR_REVIEW"
    assert after["pdf_type"] == "TEXT"
    assert after["questions_extracted"] == 4


# -------------------------------------------------------------- publish ----

def _clear_all_flags(job_id, admin_auth_headers):
    for question in client.get(f"{API}/{job_id}/questions", headers=admin_auth_headers).json():
        client.post(
            f"{API}/{job_id}/questions/{question['id']}/needs-review",
            json={"needs_review": False},
            headers=admin_auth_headers,
        )


def test_publish_is_blocked_until_review_and_pdf_are_complete(
    admin_auth_headers, drive, db_session, monkeypatch
):
    subject_id = _make_subject(admin_auth_headers, "G")
    job_id = _create_job(
        admin_auth_headers, drive, monkeypatch, subject_id, sample_paper_pdf(),
        title="Blocked Paper", year=2019,
    )
    run_pipeline(db_session, job_id)

    job = paper_processing_service.get_job(db_session, job_id)
    blockers = paper_processing_service.publish_blockers(db_session, job)

    assert any("standardized PDF" in blocker for blocker in blockers)

    # Publishing anyway is refused, and nothing reaches the real tables.
    response = client.post(
        f"{UI}/{job_id}/publish", headers=admin_auth_headers, follow_redirects=False
    )
    assert response.status_code == 303
    assert "error=" in response.headers["location"]

    db_session.expire_all()
    assert db_session.query(Paper).filter(Paper.title == "Blocked Paper").first() is None


def test_end_to_end_publish_creates_paper_questions_and_options(
    admin_auth_headers, drive, db_session, monkeypatch
):
    subject_id = _make_subject(admin_auth_headers, "H")
    job_id = _create_job(
        admin_auth_headers, drive, monkeypatch, subject_id, sample_paper_pdf(),
        title="Published Paper", year=2018,
    )
    run_pipeline(db_session, job_id)

    _clear_all_flags(job_id, admin_auth_headers)

    # Answer key is admin input only - set one explicitly on question 1.
    questions = client.get(f"{API}/{job_id}/questions", headers=admin_auth_headers).json()
    client.put(
        f"{API}/{job_id}/questions/{questions[0]['id']}",
        json={
            "question_text": questions[0]["question_text"],
            "correct_answer": "B",
            "needs_review": False,
            "options": [
                {"label": option["label"], "option_text": option["option_text"]}
                for option in questions[0]["options"]
            ],
        },
        headers=admin_auth_headers,
    )
    _clear_all_flags(job_id, admin_auth_headers)

    save = client.post(f"{UI}/{job_id}/save", headers=admin_auth_headers, follow_redirects=False)
    assert save.status_code == 303

    generate = client.post(
        f"{UI}/{job_id}/generate-pdf", headers=admin_auth_headers, follow_redirects=False
    )
    assert generate.status_code == 303

    db_session.expire_all()
    job = paper_processing_service.get_job(db_session, job_id)
    assert job.status == ProcessingStatusEnum.READY_TO_PUBLISH
    assert job.generated_file_id
    assert drive.files[job.generated_file_id][0].startswith(b"%PDF")

    publish = client.post(
        f"{UI}/{job_id}/publish", headers=admin_auth_headers, follow_redirects=False
    )
    assert publish.status_code == 303
    assert "published=1" in publish.headers["location"]

    db_session.expire_all()
    job = paper_processing_service.get_job(db_session, job_id)
    assert job.status == ProcessingStatusEnum.PUBLISHED
    assert job.paper_id is not None

    paper = db_session.query(Paper).filter(Paper.id == job.paper_id).one()
    assert paper.title == "Published Paper"
    assert paper.subject_id == subject_id
    assert paper.question_file_id == job.generated_file_id
    # Published as DRAFT so an admin double-checks before students see it.
    assert paper.status == StatusEnum.DRAFT

    created = (
        db_session.query(Question)
        .filter(Question.paper_id == paper.id)
        .order_by(Question.question_number)
        .all()
    )
    assert len(created) == 4
    assert created[0].correct_answer == "B"
    # Documented defaults - nothing in the source PDF states these.
    assert created[0].question_type == QuestionType.MCQ
    assert created[0].difficulty == DifficultyEnum.MEDIUM
    assert created[0].marks == 1
    # Questions the admin left without an answer use the empty sentinel.
    assert created[1].correct_answer == ""

    options = db_session.query(Option).filter(Option.question_id == created[0].id).all()
    assert len(options) == 4

    # A second publish attempt is refused rather than duplicating everything.
    again = client.post(
        f"{UI}/{job_id}/publish", headers=admin_auth_headers, follow_redirects=False
    )
    assert again.status_code == 303
    assert "already+been+published" in again.headers["location"] \
        or "already%20been%20published" in again.headers["location"]

    db_session.expire_all()
    assert db_session.query(Paper).filter(Paper.title == "Published Paper").count() == 1


def test_empty_answer_sentinel_never_marks_a_student_correct(
    admin_auth_headers, drive, db_session, monkeypatch
):
    """
    Question.correct_answer is NOT NULL, so "no answer key available" is
    stored as "". This asserts that sentinel can never be matched by a real
    submitted answer.
    """
    from app.modules.question.service import QuestionService

    class Stub:
        correct_answer = ""
        question_type = QuestionType.MCQ
        marks = 1.0
        negative_marks = 0.0

    service = QuestionService.__new__(QuestionService)
    for submitted in ("A", "B", "C", "D", "a", " b ", "3.5"):
        is_correct, _ = service.evaluate_answer(Stub(), submitted)
        assert is_correct is False


def test_duplicate_processing_of_the_same_source_is_allowed_but_year_clash_is_not(
    admin_auth_headers, drive, db_session, monkeypatch
):
    """
    Two jobs may point at the same source PDF (a re-run, a second attempt) -
    that is just data. What is rejected is publishing a second paper for the
    same subject+year, which the existing Paper uniqueness rule already
    enforces.
    """
    subject_id = _make_subject(admin_auth_headers, "I")
    content = sample_paper_pdf()

    first = _create_job(
        admin_auth_headers, drive, monkeypatch, subject_id, content,
        title="Dup Paper", year=2017,
    )
    second = _create_job(
        admin_auth_headers, drive, monkeypatch, subject_id, content,
        title="Dup Paper Again", year=2017,
    )
    assert first != second

    for job_id in (first, second):
        run_pipeline(db_session, job_id)
        _clear_all_flags(job_id, admin_auth_headers)
        client.post(f"{UI}/{job_id}/save", headers=admin_auth_headers, follow_redirects=False)
        client.post(f"{UI}/{job_id}/generate-pdf", headers=admin_auth_headers, follow_redirects=False)

    ok = client.post(f"{UI}/{first}/publish", headers=admin_auth_headers, follow_redirects=False)
    assert "error=" not in ok.headers["location"]

    clash = client.post(f"{UI}/{second}/publish", headers=admin_auth_headers, follow_redirects=False)
    assert "error=" in clash.headers["location"]

    db_session.expire_all()
    assert db_session.query(Paper).filter(Paper.year == 2017, Paper.subject_id == subject_id).count() == 1
