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
production: the PDF-extraction feature (app.modules.paper_processing) has
its own foreign keys into papers.id and subjects.id. A handful of its rows
point at mock papers/subjects, which blocks deleting those with a FK
violation. This script deletes only the specific PaperProcessingJob rows
(and their ExtractedQuestion/ExtractedOption/ExtractedQuestionImage
children) that reference a paper or subject being removed here - never
the feature's other rows.

Defaults to a dry run: reports exactly what would be deleted, deletes
nothing. Pass --execute to actually delete, inside one transaction.

Usage:
    cd backend
    python scripts/cleanup_mock_content_data.py            # dry run (default)
    python scripts/cleanup_mock_content_data.py --execute   # actually deletes
"""
import argparse
import sys
import uuid
from dataclasses import dataclass, field

sys.path.insert(0, ".")

import app.models  # noqa: E402, F401 - registers every model so relationship() strings resolve

from sqlalchemy import or_  # noqa: E402
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
from app.modules.paper_processing.model import (  # noqa: E402
    ExtractedOption,
    ExtractedQuestion,
    ExtractedQuestionImage,
    PaperProcessingJob,
)
from app.modules.question.model import Question  # noqa: E402
from app.modules.subject.model import Subject  # noqa: E402

PRESERVE_EXAM_CODE = "GATE"


@dataclass
class CleanupPlan:
    real_exam_id: uuid.UUID
    real_exam_code: str
    real_exam_name: str

    exam_ids: list[uuid.UUID] = field(default_factory=list)
    department_ids: list[uuid.UUID] = field(default_factory=list)
    subject_ids: list[uuid.UUID] = field(default_factory=list)
    paper_ids: list[uuid.UUID] = field(default_factory=list)
    question_ids: list[uuid.UUID] = field(default_factory=list)
    option_ids: list[uuid.UUID] = field(default_factory=list)
    mock_test_ids: list[uuid.UUID] = field(default_factory=list)
    mock_test_question_ids: list[uuid.UUID] = field(default_factory=list)
    session_ids: list[uuid.UUID] = field(default_factory=list)
    session_answer_ids: list[uuid.UUID] = field(default_factory=list)
    attempt_ids: list[uuid.UUID] = field(default_factory=list)
    attempt_answer_ids: list[uuid.UUID] = field(default_factory=list)
    conducted_test_ids: list[uuid.UUID] = field(default_factory=list)
    conducted_attempt_ids: list[uuid.UUID] = field(default_factory=list)
    conducted_attempt_answer_ids: list[uuid.UUID] = field(default_factory=list)
    file_ids: list[str] = field(default_factory=list)

    job_ids: list[uuid.UUID] = field(default_factory=list)
    extracted_question_ids: list[uuid.UUID] = field(default_factory=list)
    extracted_option_ids: list[uuid.UUID] = field(default_factory=list)
    extracted_image_ids: list[uuid.UUID] = field(default_factory=list)

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
            f"  paper_processing_jobs (only ones pointing at deleted mock data): {len(self.job_ids)}",
            f"  extracted_questions / extracted_options / extracted_question_images: "
            f"{len(self.extracted_question_ids)} / {len(self.extracted_option_ids)} / {len(self.extracted_image_ids)}",
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

    # See module docstring: PaperProcessingJob has its own FKs into
    # papers.id/subjects.id - only the specific jobs (and their extracted_*
    # children) tied to a paper/subject being removed here are deleted.
    # Built as explicit OR'd conditions (never `plan.paper_ids or [-1]`) since
    # these are UUID columns - an int sentinel would raise a type error.
    if plan.paper_ids or plan.subject_ids:
        conditions = []
        if plan.paper_ids:
            conditions.append(PaperProcessingJob.paper_id.in_(plan.paper_ids))
        if plan.subject_ids:
            conditions.append(PaperProcessingJob.subject_id.in_(plan.subject_ids))
        plan.job_ids = _ids(db.query(PaperProcessingJob.id).filter(or_(*conditions)))
    if plan.job_ids:
        plan.extracted_question_ids = _ids(db.query(ExtractedQuestion.id).filter(ExtractedQuestion.job_id.in_(plan.job_ids)))
    if plan.extracted_question_ids:
        plan.extracted_option_ids = _ids(db.query(ExtractedOption.id).filter(ExtractedOption.extracted_question_id.in_(plan.extracted_question_ids)))
        plan.extracted_image_ids = _ids(db.query(ExtractedQuestionImage.id).filter(ExtractedQuestionImage.extracted_question_id.in_(plan.extracted_question_ids)))

    return plan


def execute_plan(db: Session, plan: CleanupPlan) -> None:
    """Deepest-first, explicit, no ORM cascade - see module docstring."""

    def delete(model, ids):
        if ids:
            db.query(model).filter(model.id.in_(ids)).delete(synchronize_session=False)

    delete(ExtractedQuestionImage, plan.extracted_image_ids)
    delete(ExtractedOption, plan.extracted_option_ids)
    delete(ExtractedQuestion, plan.extracted_question_ids)
    delete(PaperProcessingJob, plan.job_ids)
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
