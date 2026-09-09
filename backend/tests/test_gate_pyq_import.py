"""
Tests for app.common.utils.gate_pyq_import.import_gate_paper - hierarchy
mapping onto an existing Exam/Department/Subject tree, idempotency
(re-running never duplicates), and honest validation reporting (never
invents content for something that can't be mapped).

Uses its own isolated in-memory SQLite database, same reasoning as
tests/test_cleanup_mock_content_data.py: Exam.code/name/slug are globally
unique, so seeding a "GATE" exam here must not collide with any other
test file sharing the suite's persistent DB.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 - registers every model on Base.metadata
from app.core.base import Base
from app.core.enums import StatusEnum
from app.modules.department.model import Department
from app.modules.exam.model import Exam
from app.modules.option.model import Option
from app.modules.paper.model import Paper
from app.modules.question.model import Question
from app.modules.subject.model import Subject

from app.common.utils.gate_pyq_import import import_gate_paper


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


@pytest.fixture()
def gate_cs_hierarchy(isolated_db):
    """Mirrors what scripts/seed_gate_hierarchy.py actually seeds: Exam -> Department -> Subject, nothing below."""
    db = isolated_db
    exam = Exam(name="GATE", code="GATE", slug="gate", display_order=1, status=StatusEnum.PUBLISHED)
    db.add(exam)
    db.flush()

    department = Department(exam_id=exam.id, name="Computer Science", code="CS", slug="computer-science", display_order=1, status=StatusEnum.PUBLISHED)
    db.add(department)
    db.flush()

    algorithms = Subject(department_id=department.id, name="Algorithms", slug="algorithms", display_order=1, status=StatusEnum.PUBLISHED)
    databases = Subject(department_id=department.id, name="Databases", slug="databases", display_order=2, status=StatusEnum.PUBLISHED)
    db.add(algorithms)
    db.add(databases)
    db.commit()

    return db, exam, department, algorithms, databases


def _payload(**overrides):
    base = {
        "exam_code": "GATE",
        "department_code": "CS",
        "year": 2023,
        "duration": 180,
        "question_pdf_file_id": "drive-file-source-pdf",
        "answer_pdf_file_id": "drive-file-answer-key",
        "questions": [
            {
                "question_number": 1,
                "subject_slug": "algorithms",
                "question_type": "MCQ",
                "marks": 1,
                "negative_marks": 0.33,
                "question_text": "What is the time complexity of binary search?",
                "options": [
                    {"label": "A", "text": "O(n)"},
                    {"label": "B", "text": "O(log n)"},
                    {"label": "C", "text": "O(n log n)"},
                    {"label": "D", "text": "O(1)"},
                ],
                "correct_answer": "B",
            },
            {
                "question_number": 2,
                "subject_slug": "databases",
                "question_type": "MCQ",
                "marks": 2,
                "negative_marks": 0.66,
                "question_text": "Which normal form eliminates transitive dependency?",
                "options": [
                    {"label": "A", "text": "1NF"},
                    {"label": "B", "text": "2NF"},
                    {"label": "C", "text": "3NF"},
                    {"label": "D", "text": "BCNF"},
                ],
                "correct_answer": "C",
            },
        ],
    }
    base.update(overrides)
    return base


def test_maps_questions_into_the_correct_existing_subject_papers(gate_cs_hierarchy):
    db, exam, department, algorithms, databases = gate_cs_hierarchy

    report = import_gate_paper(db, _payload())
    db.commit()

    assert report.ok, report.fatal_error
    assert report.papers_created == 2  # one Paper per (subject, year) group
    assert report.questions_created == 2
    assert report.options_created == 8
    assert report.unmapped == []

    algo_paper = db.query(Paper).filter(Paper.subject_id == algorithms.id, Paper.year == 2023).one()
    db_paper = db.query(Paper).filter(Paper.subject_id == databases.id, Paper.year == 2023).one()

    assert algo_paper.question_file_id == "drive-file-source-pdf"
    assert algo_paper.answer_file_id == "drive-file-answer-key"
    assert algo_paper.total_questions == 1
    assert db_paper.total_questions == 1

    algo_question = db.query(Question).filter(Question.paper_id == algo_paper.id, Question.question_number == 1).one()
    assert algo_question.correct_answer == "B"
    assert algo_question.difficulty is None  # never invented - source didn't provide one

    options = db.query(Option).filter(Option.question_id == algo_question.id).order_by(Option.label).all()
    assert [o.label for o in options] == ["A", "B", "C", "D"]
    assert options[1].option_text == "O(log n)"


def test_rerunning_the_same_payload_does_not_duplicate_anything(gate_cs_hierarchy):
    db, *_ = gate_cs_hierarchy

    import_gate_paper(db, _payload())
    db.commit()

    second = import_gate_paper(db, _payload())
    db.commit()

    assert second.ok
    assert second.papers_created == 0
    assert second.papers_updated == 2
    assert second.questions_created == 0
    assert second.questions_updated == 2
    assert second.options_created == 0
    assert second.options_updated == 8

    assert db.query(Paper).count() == 2
    assert db.query(Question).count() == 2
    assert db.query(Option).count() == 8


def test_rerunning_with_changed_text_updates_in_place(gate_cs_hierarchy):
    db, *_ = gate_cs_hierarchy

    import_gate_paper(db, _payload())
    db.commit()

    changed = _payload()
    changed["questions"][0]["question_text"] = "What is the worst-case time complexity of binary search?"
    import_gate_paper(db, changed)
    db.commit()

    updated = db.query(Question).filter(Question.paper_id.in_(
        db.query(Paper.id).filter(Paper.year == 2023)
    ), Question.question_number == 1).one()
    assert updated.question_text == "What is the worst-case time complexity of binary search?"
    assert db.query(Question).count() == 2  # still no duplicate row


def test_unknown_subject_slug_is_reported_not_invented(gate_cs_hierarchy):
    db, *_ = gate_cs_hierarchy

    payload = _payload()
    payload["questions"].append({
        "question_number": 3,
        "subject_slug": "quantum-computing",  # does not exist under this department
        "question_type": "MCQ",
        "marks": 1,
        "negative_marks": 0,
        "question_text": "...",
        "options": [{"label": "A", "text": "..."}],
        "correct_answer": "A",
    })

    report = import_gate_paper(db, payload)
    db.commit()

    assert report.ok
    assert len(report.unmapped) == 1
    assert report.unmapped[0]["question_number"] == 3
    assert "quantum-computing" in report.unmapped[0]["reason"]
    # No Subject/Paper was invented to fit it in.
    assert db.query(Subject).filter(Subject.slug == "quantum-computing").count() == 0


def test_missing_required_field_is_reported_not_invented(gate_cs_hierarchy):
    db, *_ = gate_cs_hierarchy

    payload = _payload()
    del payload["questions"][0]["correct_answer"]  # source didn't provide/confirm the official answer

    report = import_gate_paper(db, payload)
    db.commit()

    assert report.ok
    assert len(report.unmapped) == 1
    assert report.unmapped[0]["question_number"] == 1
    assert "correct_answer" in report.unmapped[0]["reason"]
    # The other, valid question in the same payload still imports fine.
    assert report.questions_created == 1


def test_unknown_exam_code_is_a_fatal_error(gate_cs_hierarchy):
    db, *_ = gate_cs_hierarchy
    report = import_gate_paper(db, _payload(exam_code="NOT-A-REAL-EXAM"))
    assert not report.ok
    assert "NOT-A-REAL-EXAM" in report.fatal_error


def test_unknown_department_code_is_a_fatal_error(gate_cs_hierarchy):
    db, *_ = gate_cs_hierarchy
    report = import_gate_paper(db, _payload(department_code="ZZ"))
    assert not report.ok
    assert "ZZ" in report.fatal_error


def test_missing_question_pdf_file_id_is_a_fatal_error_not_a_blank_placeholder(gate_cs_hierarchy):
    db, *_ = gate_cs_hierarchy
    payload = _payload()
    del payload["question_pdf_file_id"]

    report = import_gate_paper(db, payload)
    assert not report.ok
    assert "question_pdf_file_id" in report.fatal_error
    assert db.query(Paper).count() == 0
