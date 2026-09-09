"""
Safety tests for scripts/cleanup_mock_content_data.py - the script that
removes mock/demo exam-hierarchy content ahead of a real GATE PYQ import.

Uses its own isolated in-memory SQLite database (not the shared
tests/conftest.py db_session) because build_plan()/execute_plan() operate
on the *entire* database by design (that's the whole point of the real
script) - running them against the shared, cross-test-file DB would sweep
up and delete every other test's leftover exam/paper/question data too.

Seeds one real "GATE" exam subtree (preserved) alongside a mock exam
subtree with a paper/question/option/mock-test, a Resource attached to the
mock subject, and a ConductedTest + attempt/answer on the mock mock-test -
then asserts the plan targets exactly the mock content and nothing else,
and that executing it actually leaves the DB in that state.
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 - registers every model on Base.metadata
from app.core.base import Base
from app.core.enums import QuestionType, ResourceType, StatusEnum
from app.core.security import hash_password
from app.modules.conducted_test.model import ConductedTest
from app.modules.conducted_test_attempt.model import ConductedTestAttempt, ConductedTestAttemptAnswer
from app.modules.department.model import Department
from app.modules.exam.model import Exam
from app.modules.institution.model import Institution, InstitutionUser
from app.modules.mock_test.model import MockTest
from app.modules.mock_test_question.model import MockTestQuestion
from app.modules.option.model import Option
from app.modules.paper.model import Paper
from app.modules.question.model import Question
from app.modules.resource.model import Resource
from app.modules.student.model import Student
from app.modules.subject.model import Subject

from scripts.cleanup_mock_content_data import build_plan, execute_plan


@pytest.fixture()
def isolated_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _seed_exam_subtree(db, *, code, name, slug_prefix, with_content=True):
    exam = Exam(name=name, code=code, slug=slug_prefix, display_order=1, status=StatusEnum.PUBLISHED)
    db.add(exam)
    db.flush()

    department = Department(exam_id=exam.id, name=f"{name} Dept", code=f"{code}D", slug=f"{slug_prefix}-dept", display_order=1, status=StatusEnum.PUBLISHED)
    db.add(department)
    db.flush()

    subject = Subject(department_id=department.id, name=f"{name} Subject", slug=f"{slug_prefix}-subject", display_order=1, status=StatusEnum.PUBLISHED)
    db.add(subject)
    db.flush()

    if not with_content:
        return exam, department, subject, None, None, None

    paper = Paper(subject_id=subject.id, title=f"{name} Paper", year=2024, question_file_id=f"{slug_prefix}-file", total_questions=1, status=StatusEnum.PUBLISHED)
    db.add(paper)
    db.flush()

    question = Question(
        paper_id=paper.id, question_number=1, question_type=QuestionType.MCQ,
        question_text="2 + 2 = ?", correct_answer="B", marks=1, negative_marks=0,
        status=StatusEnum.PUBLISHED,
    )
    db.add(question)
    db.flush()

    db.add(Option(question_id=question.id, label="A", option_text="3"))
    db.add(Option(question_id=question.id, label="B", option_text="4"))
    db.flush()

    mock_test = MockTest(paper_id=paper.id, title=f"{name} Mock Test", duration=60, total_marks=1, total_questions=1, status=StatusEnum.PUBLISHED)
    db.add(mock_test)
    db.flush()

    db.add(MockTestQuestion(mock_test_id=mock_test.id, question_id=question.id, question_order=1))
    db.flush()

    return exam, department, subject, paper, question, mock_test


def test_plan_targets_only_mock_content_and_preserves_the_real_gate_subtree(isolated_db):
    db = isolated_db

    real_exam, real_dept, real_subject, real_paper, real_question, real_mock_test = _seed_exam_subtree(
        db, code="GATE", name="GATE", slug_prefix="gate"
    )
    mock_exam, mock_dept, mock_subject, mock_paper, mock_question, mock_mock_test = _seed_exam_subtree(
        db, code="MEX1", name="Mock Exam 1", slug_prefix="mock-exam-1"
    )
    resource = Resource(
        subject_id=mock_subject.id, title="Mock Resource", resource_type=ResourceType.NOTES,
        google_drive_file_id="resource-file", status=StatusEnum.PUBLISHED,
    )
    db.add(resource)
    db.commit()

    # Capture ids up front - after execute_plan()+commit() expires these
    # ORM objects, and re-touching an attribute on one whose row was just
    # deleted raises ObjectDeletedError instead of just being stale.
    real_exam_id, real_paper_id, real_question_id, real_mock_test_id = real_exam.id, real_paper.id, real_question.id, real_mock_test.id
    mock_exam_id, mock_dept_id, mock_subject_id = mock_exam.id, mock_dept.id, mock_subject.id
    mock_paper_id, mock_question_id, mock_mock_test_id = mock_paper.id, mock_question.id, mock_mock_test.id
    resource_id = resource.id

    plan = build_plan(db, preserve_exam_code="GATE")

    # The real GATE exam is identified and none of its subtree is queued.
    assert plan.real_exam_id == real_exam_id
    assert real_exam_id not in plan.exam_ids
    assert real_paper_id not in plan.paper_ids
    assert real_question_id not in plan.question_ids
    assert real_mock_test_id not in plan.mock_test_ids

    # The mock exam's content is queued for deletion...
    assert mock_paper_id in plan.paper_ids
    assert mock_question_id in plan.question_ids
    assert mock_mock_test_id in plan.mock_test_ids

    # ...but the mock exam/department/subject rows themselves are not -
    # deleting them would cascade into the Resource, which is out of scope.
    assert mock_exam_id in plan.exam_ids
    assert mock_dept_id in plan.department_ids
    assert mock_subject_id in plan.subject_ids

    execute_plan(db, plan)
    db.commit()

    # Mock content gone.
    assert db.get(Paper, mock_paper_id) is None
    assert db.get(Question, mock_question_id) is None
    assert db.get(MockTest, mock_mock_test_id) is None
    assert db.query(Option).filter(Option.question_id == mock_question_id).count() == 0
    assert db.query(MockTestQuestion).filter(MockTestQuestion.mock_test_id == mock_mock_test_id).count() == 0

    # Real GATE content untouched.
    assert db.get(Paper, real_paper_id) is not None
    assert db.get(Question, real_question_id) is not None
    assert db.get(MockTest, real_mock_test_id) is not None

    # Resource survives, and so does the (now-empty) mock exam/department/subject.
    assert db.get(Resource, resource_id) is not None
    assert db.get(Exam, mock_exam_id) is not None
    assert db.get(Department, mock_dept_id) is not None
    assert db.get(Subject, mock_subject_id) is not None


def test_conducted_test_referencing_a_mock_mock_test_is_removed_with_its_attempts(isolated_db):
    db = isolated_db

    _seed_exam_subtree(db, code="GATE", name="GATE", slug_prefix="gate")
    mock = _seed_exam_subtree(db, code="MEX1", name="Mock Exam 1", slug_prefix="mock-exam-1")
    mock_mock_test, mock_question = mock[5], mock[4]

    institution = Institution(name="Test Institute", slug="test-institute", status=StatusEnum.PUBLISHED)
    db.add(institution)
    db.flush()
    institution_user = InstitutionUser(institution_id=institution.id, email="cleanup-test@institute.example", hashed_password=hash_password("Test@1234"))
    db.add(institution_user)
    db.flush()
    student = Student(email="cleanup-test-student@example.com", hashed_password=hash_password("Test@1234"))
    db.add(student)
    db.flush()

    conducted = ConductedTest(
        mock_test_id=mock_mock_test.id, institution_id=institution.id, created_by_institution_user_id=institution_user.id,
        title="conducted on mock data", test_code="ABCDE", duration_minutes=60,
        scheduled_start_at=datetime.now(timezone.utc), status=StatusEnum.PUBLISHED,
    )
    db.add(conducted)
    db.flush()

    attempt = ConductedTestAttempt(
        conducted_test_id=conducted.id, student_id=student.id, result_code="RESULT123",
        started_at=datetime.now(timezone.utc),
    )
    db.add(attempt)
    db.flush()

    db.add(ConductedTestAttemptAnswer(attempt_id=attempt.id, question_id=mock_question.id, selected_answer="A", is_correct=False, marks_awarded=0))
    db.commit()

    conducted_id, attempt_id = conducted.id, attempt.id

    plan = build_plan(db, preserve_exam_code="GATE")
    assert conducted_id in plan.conducted_test_ids
    assert attempt_id in plan.conducted_attempt_ids

    execute_plan(db, plan)
    db.commit()

    assert db.get(ConductedTest, conducted_id) is None
    assert db.query(ConductedTestAttempt).filter(ConductedTestAttempt.conducted_test_id == conducted_id).count() == 0


def test_refuses_to_run_when_no_real_gate_exam_exists(isolated_db):
    db = isolated_db
    _seed_exam_subtree(db, code="MEX1", name="Mock Exam 1", slug_prefix="mock-exam-1")
    db.commit()

    with pytest.raises(ValueError):
        build_plan(db, preserve_exam_code="GATE")


def test_rerunning_the_plan_is_a_no_op_the_second_time(isolated_db):
    """Idempotency: nothing left to delete on a second pass, and it doesn't error."""
    db = isolated_db
    _seed_exam_subtree(db, code="GATE", name="GATE", slug_prefix="gate")
    _seed_exam_subtree(db, code="MEX1", name="Mock Exam 1", slug_prefix="mock-exam-1")
    db.commit()

    first_plan = build_plan(db, preserve_exam_code="GATE")
    execute_plan(db, first_plan)
    db.commit()

    second_plan = build_plan(db, preserve_exam_code="GATE")
    assert second_plan.paper_ids == []
    assert second_plan.question_ids == []
    assert second_plan.mock_test_ids == []
    execute_plan(db, second_plan)  # must not raise
    db.commit()
