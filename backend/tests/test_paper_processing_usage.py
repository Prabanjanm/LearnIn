"""
Coverage for the Paper Processing "structured upload" workflow added on top
of the existing pipeline: exam/department/subject(s) hierarchy validation,
multi-subject fan-out, "Use This Paper For" automation (Resource/MockTest
creation), duplicate prevention, later usage changes, and authorization.

Reuses the existing pipeline's fixtures/helpers (FakeDriveClient, _make_subject,
_create_job, run_pipeline, _clear_all_flags) rather than duplicating them.
"""
import uuid

import pytest

from app.common.rate_limit import reset_rate_limits
from app.core.enums import StatusEnum
from app.modules.mock_test.model import MockTest
from app.modules.paper.model import Paper
from app.modules.paper_processing.background import run_pipeline
from app.modules.paper_processing.service import paper_processing_service
from app.modules.resource.model import Resource

from pdf_fixtures import sample_paper_pdf, text_pdf  # noqa: E402

from test_paper_processing_flow import (  # noqa: E402
    UI,
    _SUBJECT_HIERARCHY,
    _clear_all_flags,
    _create_job,
    _make_subject,
    _upload_blob,
    client,
    drive,
)


# ------------------------------------------------ answer key auto-extraction --

def test_answer_key_pdf_fills_in_type_marks_and_correct_answer_at_publish(
    admin_auth_headers, drive, db_session, monkeypatch
):
    subject_id = _make_subject(admin_auth_headers, "AK1")
    exam_id, department_id = _SUBJECT_HIERARCHY[subject_id]

    started: list[uuid.UUID] = []
    monkeypatch.setattr(
        "app.modules.paper_processing.pages.run_pipeline_in_background",
        lambda job_id: started.append(job_id),
    )

    source_id = drive.seed(sample_paper_pdf())
    key_source_id = drive.seed(text_pdf([
        "1\n1\nMCQ\nGA\nA\n1\n"
        "2\n1\nMCQ\nGA\nB\n1\n"
        "3\n1\nMCQ\nGA\nC\n2\n"
        "4\n1\nMSQ\nGA\nA;B\n2\n"
    ]))

    response = client.post(
        f"{UI}/new",
        data={
            "exam_id": str(exam_id),
            "department_id": str(department_id),
            "subject_ids": [str(subject_id)],
            "title": "Key Test Paper",
            "year": "2024",
            "paper_type": "PREVIOUS_YEAR",
            "usage_flags": ["PREVIOUS_YEAR_PAPERS"],
            "original_file_id": _upload_blob(source_id),
            "answer_file_id": _upload_blob(key_source_id, filename="key.pdf"),
        },
        headers=admin_auth_headers,
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    job_id = uuid.UUID(response.headers["location"].rsplit("/", 1)[1])
    assert started == [job_id]

    run_pipeline(db_session, job_id)

    job = paper_processing_service.get_job(db_session, job_id)
    assert job.status.value == "READY_FOR_REVIEW"
    assert job.error_message and "Answer key matched" in job.error_message

    questions = paper_processing_service._questions.list_for_job(db_session, job_id)
    by_number = {q.question_number: q for q in questions}

    assert by_number[1].correct_answer == "A"
    assert by_number[1].question_type.value == "MCQ"
    assert by_number[1].marks == 1.0

    assert by_number[4].correct_answer == "A;B"
    assert by_number[4].question_type.value == "MSQ"
    assert by_number[4].marks == 2.0
    assert by_number[4].negative_marks == 0.0

    _clear_all_flags(job_id, admin_auth_headers)
    client.post(f"{UI}/{job_id}/save", headers=admin_auth_headers, follow_redirects=False)
    client.post(f"{UI}/{job_id}/generate-pdf", headers=admin_auth_headers, follow_redirects=False)
    publish_response = client.post(
        f"{UI}/{job_id}/publish", headers=admin_auth_headers, follow_redirects=False
    )
    assert "error=" not in publish_response.headers["location"], publish_response.headers["location"]

    from app.modules.question.model import Question

    db_session.expire_all()
    job = paper_processing_service.get_job(db_session, job_id)
    published = (
        db_session.query(Question)
        .filter(Question.paper_id == job.paper_id)
        .order_by(Question.question_number)
        .all()
    )

    assert published[0].correct_answer == "A"
    assert published[0].question_type.value == "MCQ"
    assert published[0].marks == 1.0

    assert published[3].correct_answer == "A;B"
    assert published[3].question_type.value == "MSQ"
    assert published[3].marks == 2.0
    assert published[3].negative_marks == 0.0


def test_a_job_with_no_answer_key_still_publishes_with_the_old_defaults(
    admin_auth_headers, drive, db_session, monkeypatch
):
    subject_id = _make_subject(admin_auth_headers, "AK2")
    job_id = _create_job(admin_auth_headers, drive, monkeypatch, subject_id, sample_paper_pdf())

    run_pipeline(db_session, job_id)

    job = paper_processing_service.get_job(db_session, job_id)
    assert job.error_message is None

    questions = paper_processing_service._questions.list_for_job(db_session, job_id)
    assert all(q.question_type is None and q.marks is None for q in questions)


def _publish(admin_auth_headers, db_session, job_id):
    run_pipeline(db_session, job_id)
    _clear_all_flags(job_id, admin_auth_headers)
    client.post(f"{UI}/{job_id}/save", headers=admin_auth_headers, follow_redirects=False)
    client.post(f"{UI}/{job_id}/generate-pdf", headers=admin_auth_headers, follow_redirects=False)
    response = client.post(f"{UI}/{job_id}/publish", headers=admin_auth_headers, follow_redirects=False)
    assert "error=" not in response.headers["location"], response.headers["location"]


# ------------------------------------------------------ hierarchy/multi-subject --

def test_multi_subject_selection_creates_one_job_and_one_paper_per_subject(
    admin_auth_headers, drive, db_session, monkeypatch
):
    exam = client.post("/api/exams/", json={"name": "Multi Exam", "code": "MEX1Z"}, headers=admin_auth_headers).json()
    department = client.post(
        "/api/departments/",
        json={"exam_id": exam["id"], "name": "Dept", "code": "MD1Z"},
        headers=admin_auth_headers,
    ).json()
    algo = client.post("/api/subjects/", json={"department_id": department["id"], "name": "Algorithms"}, headers=admin_auth_headers).json()
    dbms = client.post("/api/subjects/", json={"department_id": department["id"], "name": "Databases"}, headers=admin_auth_headers).json()

    started: list[uuid.UUID] = []
    monkeypatch.setattr(
        "app.modules.paper_processing.pages.run_pipeline_in_background",
        lambda job_id: started.append(job_id),
    )
    source_id = drive.seed(sample_paper_pdf())

    response = client.post(
        f"{UI}/new",
        data={
            "exam_id": str(exam["id"]),
            "department_id": str(department["id"]),
            "subject_ids": [str(algo["id"]), str(dbms["id"])],
            "title": "GATE Combined Paper",
            "year": "2023",
            "paper_type": "PREVIOUS_YEAR",
            "usage_flags": ["PREVIOUS_YEAR_PAPERS"],
            "original_file_id": _upload_blob(source_id),
            "answer_file_id": "",
        },
        headers=admin_auth_headers,
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text
    # Multiple subjects -> lands on the list, not a single job's page.
    assert response.headers["location"] == UI
    assert len(started) == 2

    jobs_by_subject = {}
    for job_id in started:
        job = paper_processing_service.get_job(db_session, job_id)
        jobs_by_subject[job.subject_id] = job

    assert set(jobs_by_subject.keys()) == {uuid.UUID(algo["id"]), uuid.UUID(dbms["id"])}
    # Both jobs share the exact same uploaded source file - no re-upload.
    assert len({job.original_file_id for job in jobs_by_subject.values()}) == 1
    # Job titles were disambiguated per subject.
    assert "Algorithms" in jobs_by_subject[uuid.UUID(algo["id"])].title
    assert "Databases" in jobs_by_subject[uuid.UUID(dbms["id"])].title


def test_subject_from_a_different_department_is_rejected(admin_auth_headers):
    exam = client.post("/api/exams/", json={"name": "Hier Exam", "code": "HEX1"}, headers=admin_auth_headers).json()
    dept_a = client.post("/api/departments/", json={"exam_id": exam["id"], "name": "Dept A", "code": "HDA"}, headers=admin_auth_headers).json()
    dept_b = client.post("/api/departments/", json={"exam_id": exam["id"], "name": "Dept B", "code": "HDB"}, headers=admin_auth_headers).json()
    subject_in_b = client.post("/api/subjects/", json={"department_id": dept_b["id"], "name": "Wrong Dept Subject"}, headers=admin_auth_headers).json()

    response = client.post(
        f"{UI}/new",
        data={
            "exam_id": str(exam["id"]),
            "department_id": str(dept_a["id"]),  # picked dept A...
            "subject_ids": [str(subject_in_b["id"])],  # ...but the subject belongs to dept B
            "title": "Should Fail",
            "year": "2023",
            "paper_type": "PREVIOUS_YEAR",
            "usage_flags": ["PREVIOUS_YEAR_PAPERS"],
            "original_file_id": _upload_blob("irrelevant-since-it-should-fail-first"),
            "answer_file_id": "",
        },
        headers=admin_auth_headers,
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "does not belong to the selected department" in response.text


def test_department_not_belonging_to_the_selected_exam_is_rejected(admin_auth_headers):
    exam_a = client.post("/api/exams/", json={"name": "Exam A", "code": "EXA1"}, headers=admin_auth_headers).json()
    exam_b = client.post("/api/exams/", json={"name": "Exam B", "code": "EXB1"}, headers=admin_auth_headers).json()
    dept_of_b = client.post("/api/departments/", json={"exam_id": exam_b["id"], "name": "Dept", "code": "DOB1"}, headers=admin_auth_headers).json()

    response = client.post(
        f"{UI}/new",
        data={
            "exam_id": str(exam_a["id"]),
            "department_id": str(dept_of_b["id"]),
            "subject_ids": [str(uuid.uuid4())],
            "title": "Should Fail",
            "year": "2023",
            "original_file_id": _upload_blob("whatever"),
            "answer_file_id": "",
        },
        headers=admin_auth_headers,
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "does not belong to the selected exam" in response.text


def test_missing_required_fields_are_rejected(admin_auth_headers):
    response = client.post(
        f"{UI}/new",
        data={
            "title": "No hierarchy at all",
            "year": "2023",
            "original_file_id": _upload_blob("whatever"),
            "answer_file_id": "",
        },
        headers=admin_auth_headers,
        follow_redirects=False,
    )
    assert response.status_code == 400


# ------------------------------------------------------------ usage automation --

def test_mock_test_flag_creates_a_mock_test_from_the_published_paper(
    admin_auth_headers, drive, db_session, monkeypatch
):
    subject_id = _make_subject(admin_auth_headers, "MT1")
    job_id = _create_job(
        admin_auth_headers, drive, monkeypatch, subject_id, sample_paper_pdf(),
        title="Mock Test Source", year=2021,
    )
    _publish(admin_auth_headers, db_session, job_id)

    db_session.expire_all()
    job = paper_processing_service.get_job(db_session, job_id)
    mock_tests = db_session.query(MockTest).filter(MockTest.paper_id == job.paper_id).all()

    assert len(mock_tests) == 1
    assert mock_tests[0].total_questions == job.questions_extracted
    assert mock_tests[0].status == StatusEnum.DRAFT


def test_resource_flag_creates_a_resource_pointing_at_the_same_pdf(
    admin_auth_headers, drive, db_session, monkeypatch
):
    subject_id = _make_subject(admin_auth_headers, "RS1")
    job_id = _create_job(
        admin_auth_headers, drive, monkeypatch, subject_id, sample_paper_pdf(),
        title="Resource Source", year=2020,
        usage_flags=("PREVIOUS_YEAR_PAPERS", "PRACTICE", "MOCK_TEST", "RESOURCE"),
    )
    _publish(admin_auth_headers, db_session, job_id)

    db_session.expire_all()
    job = paper_processing_service.get_job(db_session, job_id)
    paper = db_session.query(Paper).filter(Paper.id == job.paper_id).first()

    resources = db_session.query(Resource).filter(Resource.subject_id == subject_id).all()
    assert len(resources) == 1
    assert resources[0].google_drive_file_id == paper.question_file_id


def test_reapplying_usage_never_duplicates_the_mock_test_or_resource(
    admin_auth_headers, drive, db_session, monkeypatch
):
    subject_id = _make_subject(admin_auth_headers, "RA1")
    job_id = _create_job(
        admin_auth_headers, drive, monkeypatch, subject_id, sample_paper_pdf(),
        title="Reapply Source", year=2016,
        usage_flags=("PREVIOUS_YEAR_PAPERS", "PRACTICE", "MOCK_TEST", "RESOURCE"),
    )
    _publish(admin_auth_headers, db_session, job_id)

    job = paper_processing_service.get_job(db_session, job_id)
    # Calling apply_usage again (e.g. a second preview-page visit) must not
    # create a second MockTest/Resource for the same paper.
    paper_processing_service.apply_usage(db_session, job.paper)
    paper_processing_service.apply_usage(db_session, job.paper)

    db_session.expire_all()
    assert db_session.query(MockTest).filter(MockTest.paper_id == job.paper_id).count() == 1
    assert db_session.query(Resource).filter(Resource.subject_id == subject_id).count() == 1


def test_unchecking_a_usage_flag_later_archives_its_row_without_deleting_it(
    admin_auth_headers, drive, db_session, monkeypatch
):
    subject_id = _make_subject(admin_auth_headers, "UU1")
    job_id = _create_job(
        admin_auth_headers, drive, monkeypatch, subject_id, sample_paper_pdf(),
        title="Update Usage Source", year=2015,
        usage_flags=("PREVIOUS_YEAR_PAPERS", "PRACTICE", "MOCK_TEST", "RESOURCE"),
    )
    _publish(admin_auth_headers, db_session, job_id)

    response = client.post(
        f"{UI}/{job_id}/usage",
        data={"usage_flags": ["PREVIOUS_YEAR_PAPERS"]},  # Mock Tests/Resource unchecked now
        headers=admin_auth_headers,
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "error=" not in response.headers["location"]

    db_session.expire_all()
    job = paper_processing_service.get_job(db_session, job_id)
    mock_test = db_session.query(MockTest).filter(MockTest.paper_id == job.paper_id).first()
    resource = db_session.query(Resource).filter(Resource.subject_id == subject_id).first()

    # Archived, not deleted - StatusMixin is the only lifecycle mechanism.
    assert mock_test is not None and mock_test.status == StatusEnum.ARCHIVED
    assert resource is not None and resource.status == StatusEnum.ARCHIVED


def test_rechecking_a_usage_flag_restores_the_archived_row(
    admin_auth_headers, drive, db_session, monkeypatch
):
    subject_id = _make_subject(admin_auth_headers, "UU2")
    job_id = _create_job(
        admin_auth_headers, drive, monkeypatch, subject_id, sample_paper_pdf(),
        title="Restore Usage Source", year=2014,
    )
    _publish(admin_auth_headers, db_session, job_id)
    job = paper_processing_service.get_job(db_session, job_id)
    mock_test_id = db_session.query(MockTest).filter(MockTest.paper_id == job.paper_id).first().id

    client.post(f"{UI}/{job_id}/usage", data={"usage_flags": []}, headers=admin_auth_headers, follow_redirects=False)
    client.post(
        f"{UI}/{job_id}/usage",
        data={"usage_flags": ["MOCK_TEST"]},
        headers=admin_auth_headers,
        follow_redirects=False,
    )

    db_session.expire_all()
    mock_test = db_session.query(MockTest).filter(MockTest.id == mock_test_id).first()
    assert mock_test.status == StatusEnum.DRAFT
    # Still the same row - not a second mock test.
    assert db_session.query(MockTest).filter(MockTest.paper_id == job.paper_id).count() == 1


def test_updating_usage_before_publish_is_rejected(admin_auth_headers, drive, monkeypatch):
    subject_id = _make_subject(admin_auth_headers, "UU3")
    job_id = _create_job(
        admin_auth_headers, drive, monkeypatch, subject_id, sample_paper_pdf(),
        title="Not Published Yet", year=2013,
    )
    response = client.post(
        f"{UI}/{job_id}/usage",
        data={"usage_flags": ["MOCK_TEST"]},
        headers=admin_auth_headers,
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "error=" in response.headers["location"]


# -------------------------------------------------------- duplicate prevention --

def test_duplicate_subject_year_is_skipped_not_processed_a_second_time(
    admin_auth_headers, drive, db_session, monkeypatch
):
    subject_id = _make_subject(admin_auth_headers, "DP1")
    first_job = _create_job(
        admin_auth_headers, drive, monkeypatch, subject_id, sample_paper_pdf(),
        title="First Attempt", year=2012,
    )
    _publish(admin_auth_headers, db_session, first_job)

    # A real Paper for (subject, 2012) now exists - a second upload for the
    # exact same subject+year must be skipped at creation, not silently
    # allowed to create a second Paper later.
    started: list[uuid.UUID] = []
    monkeypatch.setattr(
        "app.modules.paper_processing.pages.run_pipeline_in_background",
        lambda job_id: started.append(job_id),
    )
    source_id = drive.seed(sample_paper_pdf())
    job = paper_processing_service.get_job(db_session, first_job)
    exam_id = job.subject.department.exam_id
    department_id = job.subject.department_id

    response = client.post(
        f"{UI}/new",
        data={
            "exam_id": str(exam_id),
            "department_id": str(department_id),
            "subject_ids": [str(subject_id)],
            "title": "Second Attempt Same Year",
            "year": "2012",
            "original_file_id": _upload_blob(source_id),
            "answer_file_id": "",
        },
        headers=admin_auth_headers,
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "already exists" in response.text
    assert started == []
    db_session.expire_all()
    assert db_session.query(Paper).filter(Paper.subject_id == subject_id, Paper.year == 2012).count() == 1


# ------------------------------------------------------------------- failure --

def test_failed_job_never_creates_a_paper_or_touches_usage(admin_auth_headers, drive, db_session, monkeypatch):
    from pdf_fixtures import corrupted_pdf

    subject_id = _make_subject(admin_auth_headers, "FAIL1")
    job_id = _create_job(
        admin_auth_headers, drive, monkeypatch, subject_id, corrupted_pdf(),
        title="Corrupted Upload", year=2011,
    )
    run_pipeline(db_session, job_id)

    db_session.expire_all()
    job = paper_processing_service.get_job(db_session, job_id)
    assert job.status.value == "VALIDATION_FAILED"
    assert job.paper_id is None
    assert db_session.query(Paper).filter(Paper.title == "Corrupted Upload").count() == 0
    assert db_session.query(MockTest).count() == 0 or all(
        mt.paper_id != job.paper_id for mt in db_session.query(MockTest).all()
    )


# --------------------------------------------------------------- authorization --

def test_unauthenticated_request_cannot_create_a_job(drive):
    source_id = drive.seed(sample_paper_pdf())
    response = client.post(
        f"{UI}/new",
        data={
            "exam_id": str(uuid.uuid4()), "department_id": str(uuid.uuid4()),
            "subject_ids": [str(uuid.uuid4())],
            "title": "No Auth", "year": "2023",
            "original_file_id": _upload_blob(source_id), "answer_file_id": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_unauthenticated_request_cannot_update_usage():
    response = client.post(f"{UI}/{uuid.uuid4()}/usage", data={"usage_flags": []}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


# --------------------------------------- usage for a paper with no job ---
#
# A paper created directly through the generic admin CRUD (or imported
# before "Use This Paper For" existed) has no PaperProcessingJob at all -
# it must still be manageable from /admin/paper-processing/papers.

def _make_paper_without_a_job(admin_auth_headers, drive, suffix: str, year=2022):
    """Mirrors what the generic Papers admin screen (or an older importer)
    would do - a real Paper + Question, created without ever touching the
    paper_processing pipeline."""
    subject_id = _make_subject(admin_auth_headers, suffix)
    file_id = drive.seed(sample_paper_pdf())

    paper = client.post(
        "/api/papers/",
        json={
            "subject_id": str(subject_id),
            "title": f"No-Job Paper {suffix}",
            "year": year,
            "question_file_id": file_id,
            "status": "DRAFT",
        },
        headers=admin_auth_headers,
    ).json()

    client.post(
        "/api/questions/",
        json={
            "paper_id": paper["id"],
            "question_number": 1,
            "question_type": "MCQ",
            "question_text": "2 + 2 = ?",
            "correct_answer": "B",
            "marks": 1,
            "negative_marks": 0,
            "options": [{"label": "A", "option_text": "3"}, {"label": "B", "option_text": "4"}],
            "status": "DRAFT",
        },
        headers=admin_auth_headers,
    )

    return uuid.UUID(paper["id"]), subject_id


def test_papers_list_includes_a_paper_with_no_processing_job(admin_auth_headers, drive):
    paper_id, _ = _make_paper_without_a_job(admin_auth_headers, drive, "NJ1")

    response = client.get(f"{UI}/papers", headers=admin_auth_headers)
    assert response.status_code == 200
    assert f"{UI}/papers/{paper_id}/usage" in response.text


def test_setting_usage_on_a_paper_with_no_job_creates_mock_test_and_resource(
    admin_auth_headers, drive, db_session
):
    paper_id, subject_id = _make_paper_without_a_job(admin_auth_headers, drive, "NJ2")

    page = client.get(f"{UI}/papers/{paper_id}/usage", headers=admin_auth_headers)
    assert page.status_code == 200
    assert "Nothing selected" in page.text

    response = client.post(
        f"{UI}/papers/{paper_id}/usage",
        data={"usage_flags": ["PREVIOUS_YEAR_PAPERS", "MOCK_TEST", "RESOURCE"]},
        headers=admin_auth_headers,
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "usage_updated=1" in response.headers["location"]

    db_session.expire_all()
    paper = db_session.query(Paper).filter(Paper.id == paper_id).first()
    assert set(paper.usage_flags_list()) == {"PREVIOUS_YEAR_PAPERS", "MOCK_TEST", "RESOURCE"}
    assert db_session.query(MockTest).filter(MockTest.paper_id == paper_id).count() == 1
    assert db_session.query(Resource).filter(Resource.subject_id == subject_id).count() == 1

    # Reflected back on the usage page too.
    page_after = client.get(f"{UI}/papers/{paper_id}/usage", headers=admin_auth_headers)
    assert "Mock Test" in page_after.text
    assert "Resources" in page_after.text


def test_unauthenticated_request_cannot_view_or_update_a_papers_usage_page(admin_auth_headers, drive):
    paper_id, _ = _make_paper_without_a_job(admin_auth_headers, drive, "NJ3")

    view = client.get(f"{UI}/papers/{paper_id}/usage", follow_redirects=False)
    assert view.status_code == 303
    assert view.headers["location"] == "/admin/login"

    update = client.post(f"{UI}/papers/{paper_id}/usage", data={"usage_flags": []}, follow_redirects=False)
    assert update.status_code == 303
    assert update.headers["location"] == "/admin/login"


def test_unknown_paper_id_redirects_instead_of_erroring(admin_auth_headers):
    response = client.get(f"{UI}/papers/{uuid.uuid4()}/usage", headers=admin_auth_headers, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"{UI}/papers"


def _upload_blob(file_id: str, filename="source.pdf") -> str:
    import json
    return json.dumps({
        "file_id": file_id,
        "mime_type": "application/pdf",
        "file_size": 1234,
        "filename": filename,
    })


@pytest.fixture(autouse=True)
def _reset_rate_limits_between_tests():
    reset_rate_limits()
    yield


# --------------------------------------------------------- overlay markup --

def test_new_job_page_renders_the_ocr_overlay_hidden_and_the_double_submit_guard(
    admin_auth_headers,
):
    response = client.get(f"{UI}/new", headers=admin_auth_headers)
    assert response.status_code == 200
    assert 'data-pp-ocr-overlay' in response.text
    assert 'id="paper-processing-form"' in response.text
    assert '/static/js/components/paper-processing.js' in response.text


def test_status_page_renders_the_ocr_overlay_visible_while_busy(
    admin_auth_headers, drive, db_session, monkeypatch
):
    subject_id = _make_subject(admin_auth_headers, "OV1")
    job_id = _create_job(admin_auth_headers, drive, monkeypatch, subject_id, sample_paper_pdf())

    response = client.get(f"{UI}/{job_id}", headers=admin_auth_headers)
    assert response.status_code == 200
    assert 'data-pp-ocr-overlay' in response.text
    # Busy (UPLOADED, just created) - the overlay must not carry the
    # `hidden` attribute, mirroring how the existing spinner is rendered.
    import re
    overlay_tag = re.search(r'<div class="pp-ocr-overlay"[^>]*>', response.text).group(0)
    assert re.search(r'(?<!aria-)\bhidden\b', overlay_tag) is None

    run_pipeline(db_session, job_id)
    response = client.get(f"{UI}/{job_id}", headers=admin_auth_headers)
    overlay_tag = re.search(r'<div class="pp-ocr-overlay"[^>]*>', response.text).group(0)
    assert re.search(r'(?<!aria-)\bhidden\b', overlay_tag) is not None


# --------------------------------------------- upload speed / visibility ---

def test_category_is_public_exempts_only_paper_processing_sources():
    from app.core.google_drive import category_is_public

    assert category_is_public("paper_processing_sources") is False
    assert category_is_public("papers") is True
    assert category_is_public("resources") is True
    assert category_is_public(None) is True


def test_uploading_a_paper_processing_source_skips_the_public_permission_call(
    admin_auth_headers, drive
):
    """
    The source question paper / answer key PDFs are only ever downloaded
    back server-side by the pipeline itself - nothing links to them
    publicly - so making them public would just be a wasted Drive API round
    trip on every upload. Confirms /admin/upload passes public=False for
    this category (the FakeDriveClient records every call's kwargs).
    """
    calls = []
    original_upload_file = drive.upload_file

    def spy_upload_file(*args, **kwargs):
        calls.append(kwargs)
        return original_upload_file(*args, **kwargs)

    drive.upload_file = spy_upload_file

    response = client.post(
        "/admin/upload",
        files={"file": ("source.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
        data={"category": "paper_processing_sources"},
        headers=admin_auth_headers,
    )

    assert response.status_code == 200, response.text
    assert len(calls) == 1
    assert calls[0]["public"] is False
