"""
Removes ONLY mock/demo/seed exam-hierarchy content, in preparation for a
real GATE PYQ import - never a blanket TRUNCATE.

What "mock" means here, precisely: papers, questions, options, mock
tests (+ their sessions/attempts/answers), and any conducted_tests
(+ their attempts/answers) that hang off any exam other than the one real
exam seeded by scripts/seed_gate_hierarchy.py (identified by its stable
natural key, Exam.code == "GATE" - never a hardcoded id).

Explicitly NEVER touched, no matter what: admins, students, institutions,
institution_users, blogs, resources, search_logs, the unrelated
paper_processing_jobs/extracted_* tables' *other* rows, and the real GATE
exam subtree (exam_id == the "GATE" exam's id) - including its subjects,
even though some of those subjects currently have zero papers.

The mock exams/departments/subjects THEMSELVES are deliberately left in
place, empty: 50 of the 51 mock subjects each have a real "Mock Resource"
row attached via a foreign key, and resources are explicitly out of scope
for this cleanup - so deleting those subjects (and their parent
departments/exams) isn't possible without also deleting the resources
that reference them. Only the content that has no such dependency
(papers and everything under them, mock tests, conducted tests) is
removed.

Every delete is an explicit, table-by-table bulk DELETE scoped to ids
computed from the mock exam subtree - no ORM cascade is used here on
purpose: Subject's own `resources` relationship also cascades on delete,
which would take the (intentionally preserved) mock-titled Resource rows
down with it. Doing every step by hand avoids that even by accident.

Drive files (Paper.question_file_id/answer_file_id, Question.image_file_id/
explanation_image_file_id, Option.image_file_id) are collected before the
DB delete, then cleaned up from Drive afterward only if no surviving row
(including the Resources this script leaves alone) still references them -
see app/common/utils/file_tracking.py.

One more dependency, discovered by actually running this against
production: the separate, otherwise-untouched PDF-extraction feature
(paper_processing_jobs / extracted_questions / extracted_options /
extracted_question_images - no app model exists for these, so they're
queried with raw SQL and only if the table actually exists) has its own
foreign keys into papers.id and subjects.id. A handful of its rows point
at mock papers/subjects, which blocks deleting those with a FK violation.
This script deletes only the specific processing-job rows (and their
extracted_* children) that reference a paper or subject being removed
here - never the feature's other rows, and never its schema.

Defaults to a dry run: reports exactly what would be deleted, deletes
nothing. Pass --execute to actually delete, inside one transaction.

Usage:
    cd backend
    python scripts/cleanup_mock_content_data.py            # dry run (default)
    python scripts/cleanup_mock_content_data.py --execute   # actually deletes
"""
import argparse
import sys
from dataclasses import dataclass, field

sys.path.insert(0, ".")

import app.models  # noqa: E402, F401 - registers every model so relationship() strings resolve

from sqlalchemy import inspect, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.common.utils.file_tracking import cleanup_drive_files  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.modules.conducted_test.model import ConductedTest  # noqa: E402
from app.modules.conducted_test_attempt.model import ConductedTestAttempt, ConductedTestAttemptAnswer  # noqa: E402
from app.modules.department.model import Department  # noqa: E402
from app.modules.exam.model import Exam  # noqa: E402
from app.modules.mock_test.model import MockTest  # noqa: E402
from app.modules.mock_test_attempt.model import (  # noqa: E402
    MockTestAttempt,
    MockTestAttemptAnswer,
    MockTestSession,
    MockTestSessionAnswer,
)
from app.modules.mock_test_question.model import MockTestQuestion  # noqa: E402
from app.modules.option.model import Option  # noqa: E402
from app.modules.paper.model import Paper  # noqa: E402
from app.modules.question.model import Question  # noqa: E402
from app.modules.subject.model import Subject  # noqa: E402

PRESERVE_EXAM_CODE = "GATE"

# The unrelated PDF-extraction feature's tables have no app model (see
# module docstring) - referenced by raw table/column name only, and only
# queried if the table actually exists (it doesn't in a fresh test DB).
_EXTRACTION_TABLES = ("extracted_question_images", "extracted_options", "extracted_questions", "paper_processing_jobs")


@dataclass
class CleanupPlan:
    real_exam_id: int
    real_exam_code: str
    real_exam_name: str

    exam_ids: list[int] = field(default_factory=list)
    department_ids: list[int] = field(default_factory=list)
    subject_ids: list[int] = field(default_factory=list)
    paper_ids: list[int] = field(default_factory=list)
    question_ids: list[int] = field(default_factory=list)
    option_ids: list[int] = field(default_factory=list)
    mock_test_ids: list[int] = field(default_factory=list)
    mock_test_question_ids: list[int] = field(default_factory=list)
    session_ids: list[int] = field(default_factory=list)
    session_answer_ids: list[int] = field(default_factory=list)
    attempt_ids: list[int] = field(default_factory=list)
    attempt_answer_ids: list[int] = field(default_factory=list)
    conducted_test_ids: list[int] = field(default_factory=list)
    conducted_attempt_ids: list[int] = field(default_factory=list)
    conducted_attempt_answer_ids: list[int] = field(default_factory=list)
    file_ids: list[str] = field(default_factory=list)

    # (table_name, id) pairs from the unrelated extraction feature, in
    # delete order - only populated if those tables exist.
    extraction_rows: list[tuple] = field(default_factory=list)

    def report_lines(self) -> list[str]:
        lines = [
            f"Preserving exam: id={self.real_exam_id} code={self.real_exam_code!r} name={self.real_exam_name!r}",
            "(and every department/subject under it, and any real papers/questions under those)",
            "Mock exams/departments/subjects themselves are left in place empty - see module docstring "
            "(50 of 51 mock subjects have a real Resource row attached).\n",
            "Rows that will be deleted:",
            f"  papers: {len(self.paper_ids)}",
            f"  questions: {len(self.question_ids)}",
            f"  options: {len(self.option_ids)}",
            f"  mock_tests: {len(self.mock_test_ids)}",
            f"  mock_test_questions: {len(self.mock_test_question_ids)}",
            f"  mock_test_sessions: {len(self.session_ids)}",
            f"  mock_test_session_answers: {len(self.session_answer_ids)}",
            f"  mock_test_attempts: {len(self.attempt_ids)}",
            f"  mock_test_attempt_answers: {len(self.attempt_answer_ids)}",
            f"  conducted_tests: {len(self.conducted_test_ids)}",
            f"  conducted_test_attempts: {len(self.conducted_attempt_ids)}",
            f"  conducted_test_attempt_answers: {len(self.conducted_attempt_answer_ids)}",
            f"  unrelated extraction-feature rows (only ones pointing at deleted mock data): {len(self.extraction_rows)}",
            f"  Drive files to check for cleanup: {len(self.file_ids)}",
            "",
            f"Left in place (empty, not deleted): {len(self.exam_ids)} mock exams, "
            f"{len(self.department_ids)} mock departments, {len(self.subject_ids)} mock subjects.",
        ]
        return lines


def _ids(query) -> list:
    return [row[0] for row in query.all()]


def build_plan(db: Session, preserve_exam_code: str = PRESERVE_EXAM_CODE) -> CleanupPlan:
    real_exam = db.query(Exam).filter(Exam.code == preserve_exam_code).one_or_none()
    if real_exam is None:
        raise ValueError(f"No exam with code={preserve_exam_code!r} found, so nothing would be preserved.")

    plan = CleanupPlan(real_exam_id=real_exam.id, real_exam_code=real_exam.code, real_exam_name=real_exam.name)

    plan.exam_ids = _ids(db.query(Exam.id).filter(Exam.id != real_exam.id))
    plan.department_ids = _ids(db.query(Department.id).filter(Department.exam_id.in_(plan.exam_ids))) if plan.exam_ids else []
    plan.subject_ids = _ids(db.query(Subject.id).filter(Subject.department_id.in_(plan.department_ids))) if plan.department_ids else []
    plan.paper_ids = _ids(db.query(Paper.id).filter(Paper.subject_id.in_(plan.subject_ids))) if plan.subject_ids else []
    plan.question_ids = _ids(db.query(Question.id).filter(Question.paper_id.in_(plan.paper_ids))) if plan.paper_ids else []
    plan.option_ids = _ids(db.query(Option.id).filter(Option.question_id.in_(plan.question_ids))) if plan.question_ids else []
    plan.mock_test_ids = _ids(db.query(MockTest.id).filter(MockTest.paper_id.in_(plan.paper_ids))) if plan.paper_ids else []
    plan.mock_test_question_ids = _ids(db.query(MockTestQuestion.id).filter(MockTestQuestion.mock_test_id.in_(plan.mock_test_ids))) if plan.mock_test_ids else []
    plan.session_ids = _ids(db.query(MockTestSession.id).filter(MockTestSession.mock_test_id.in_(plan.mock_test_ids))) if plan.mock_test_ids else []
    plan.session_answer_ids = _ids(db.query(MockTestSessionAnswer.id).filter(MockTestSessionAnswer.session_id.in_(plan.session_ids))) if plan.session_ids else []
    plan.attempt_ids = _ids(db.query(MockTestAttempt.id).filter(MockTestAttempt.mock_test_id.in_(plan.mock_test_ids))) if plan.mock_test_ids else []
    plan.attempt_answer_ids = _ids(db.query(MockTestAttemptAnswer.id).filter(MockTestAttemptAnswer.attempt_id.in_(plan.attempt_ids))) if plan.attempt_ids else []
    plan.conducted_test_ids = _ids(db.query(ConductedTest.id).filter(ConductedTest.mock_test_id.in_(plan.mock_test_ids))) if plan.mock_test_ids else []
    plan.conducted_attempt_ids = _ids(db.query(ConductedTestAttempt.id).filter(ConductedTestAttempt.conducted_test_id.in_(plan.conducted_test_ids))) if plan.conducted_test_ids else []
    plan.conducted_attempt_answer_ids = _ids(db.query(ConductedTestAttemptAnswer.id).filter(ConductedTestAttemptAnswer.attempt_id.in_(plan.conducted_attempt_ids))) if plan.conducted_attempt_ids else []

    file_ids: list[str] = []
    if plan.paper_ids:
        file_ids += _ids(db.query(Paper.question_file_id).filter(Paper.id.in_(plan.paper_ids), Paper.question_file_id.isnot(None)))
        file_ids += _ids(db.query(Paper.answer_file_id).filter(Paper.id.in_(plan.paper_ids), Paper.answer_file_id.isnot(None)))
    if plan.question_ids:
        file_ids += _ids(db.query(Question.image_file_id).filter(Question.id.in_(plan.question_ids), Question.image_file_id.isnot(None)))
        file_ids += _ids(db.query(Question.explanation_image_file_id).filter(Question.id.in_(plan.question_ids), Question.explanation_image_file_id.isnot(None)))
    if plan.option_ids:
        file_ids += _ids(db.query(Option.image_file_id).filter(Option.id.in_(plan.option_ids), Option.image_file_id.isnot(None)))
    plan.file_ids = sorted(set(file_ids))

    # Unrelated extraction feature - see module docstring. Skipped entirely
    # if the tables don't exist (e.g. the test DB never creates them).
    inspector = inspect(db.bind)
    if inspector.has_table("paper_processing_jobs") and (plan.paper_ids or plan.subject_ids):
        job_ids = _ids(db.execute(
            text("select id from paper_processing_jobs where paper_id in :paper_ids or subject_id in :subject_ids")
            .bindparams(paper_ids=tuple(plan.paper_ids or [-1]), subject_ids=tuple(plan.subject_ids or [-1])),
        ))
        extracted_question_ids = _ids(db.execute(
            text("select id from extracted_questions where job_id in :ids").bindparams(ids=tuple(job_ids or [-1]))
        )) if job_ids else []
        extracted_option_ids = _ids(db.execute(
            text("select id from extracted_options where extracted_question_id in :ids").bindparams(ids=tuple(extracted_question_ids or [-1]))
        )) if extracted_question_ids else []
        extracted_image_ids = _ids(db.execute(
            text("select id from extracted_question_images where extracted_question_id in :ids").bindparams(ids=tuple(extracted_question_ids or [-1]))
        )) if extracted_question_ids else []

        plan.extraction_rows = (
            [("extracted_question_images", i) for i in extracted_image_ids]
            + [("extracted_options", i) for i in extracted_option_ids]
            + [("extracted_questions", i) for i in extracted_question_ids]
            + [("paper_processing_jobs", i) for i in job_ids]
        )

    return plan


def execute_plan(db: Session, plan: CleanupPlan) -> None:
    """Deepest-first, explicit, no ORM cascade - see module docstring."""

    def delete(model, ids):
        if ids:
            db.query(model).filter(model.id.in_(ids)).delete(synchronize_session=False)

    for table, row_id in plan.extraction_rows:
        db.execute(text(f"delete from {table} where id = :id"), {"id": row_id})

    delete(ConductedTestAttemptAnswer, plan.conducted_attempt_answer_ids)
    delete(ConductedTestAttempt, plan.conducted_attempt_ids)
    delete(ConductedTest, plan.conducted_test_ids)
    delete(MockTestSessionAnswer, plan.session_answer_ids)
    delete(MockTestSession, plan.session_ids)
    delete(MockTestAttemptAnswer, plan.attempt_answer_ids)
    delete(MockTestAttempt, plan.attempt_ids)
    delete(MockTestQuestion, plan.mock_test_question_ids)
    delete(MockTest, plan.mock_test_ids)
    delete(Option, plan.option_ids)
    delete(Question, plan.question_ids)
    delete(Paper, plan.paper_ids)
    # Mock exams/departments/subjects are deliberately NOT deleted here -
    # see module docstring (resources FK dependency).


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Actually delete. Without this flag, only reports what would be deleted.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        try:
            plan = build_plan(db)
        except ValueError as exc:
            print(f"Refusing to run: {exc}")
            sys.exit(1)

        print("\n".join(plan.report_lines()))

        if not args.execute:
            print("\nDry run only - nothing deleted. Re-run with --execute to actually delete.")
            return

        execute_plan(db, plan)
        db.commit()
        print("\nDeleted. Cleaning up now-orphaned Drive files (skipped if still referenced elsewhere)...")
        cleanup_drive_files(db, plan.file_ids)
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
