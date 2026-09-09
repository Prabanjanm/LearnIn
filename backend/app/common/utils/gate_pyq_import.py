"""
Imports real GATE previous-year question papers into the existing
Exam -> Department -> Subject -> Paper -> Question -> Option hierarchy
(see scripts/seed_gate_hierarchy.py for how that hierarchy itself is
seeded). This module never invents content: every field the input doesn't
provide is left unset rather than guessed, and anything that can't be
mapped onto the existing hierarchy (an unknown subject slug, a missing
required field) is reported, not silently skipped or faked.

Input shape - one payload per (exam, department/discipline, year), matching
one real combined GATE question paper:

    {
      "exam_code": "GATE",
      "department_code": "CS",
      "year": 2023,
      "duration": 180,                       # optional, minutes
      "question_pdf_file_id": "<Drive file id, already uploaded>",
      "answer_pdf_file_id": "<Drive file id, optional>",
      "questions": [
        {
          "question_number": 1,
          "subject_slug": "algorithms",       # must already exist under the department
          "question_type": "MCQ",             # MCQ | MSQ | NAT
          "marks": 1,
          "negative_marks": 0.33,
          "question_text": "...",
          "options": [{"label": "A", "text": "..."}, ...],   # omit for NAT
          "correct_answer": "A",
          "explanation": null                 # only set if the source actually provides one
        }
      ]
    }

A real GATE paper covers many syllabus subjects in one script, but this
app's Paper row belongs to exactly one Subject (see Paper.subject_id) -
so questions are grouped by `subject_slug` and one Paper row is
get-or-created per (subject, year) group, all sharing the same source PDF
file id (Paper.question_file_id is NOT NULL - a payload with no
question_pdf_file_id is rejected outright rather than leaving it blank).

Idempotent: Paper is looked up by its existing natural unique key
(subject_id, year); Question by (paper_id, question_number); Option by
(question_id, label). Re-running the same payload updates those rows in
place instead of duplicating them - see uq_subject_year, uq_question_number,
uq_question_option in the respective models.

Question.difficulty is left null unless the payload explicitly provides
one - real official papers don't rate difficulty, and that must never be
invented (see the migration that made this column nullable).
"""
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.enums import StatusEnum
from app.modules.department.model import Department
from app.modules.exam.model import Exam
from app.modules.option.model import Option
from app.modules.paper.model import Paper
from app.modules.question.model import Question
from app.modules.subject.model import Subject

REQUIRED_QUESTION_FIELDS = ("question_number", "subject_slug", "question_type", "question_text", "correct_answer", "marks", "negative_marks")


@dataclass
class ImportReport:
    exam_code: str | None = None
    department_code: str | None = None
    year: int | None = None

    papers_created: int = 0
    papers_updated: int = 0
    questions_created: int = 0
    questions_updated: int = 0
    options_created: int = 0
    options_updated: int = 0

    # Each entry: {"question_number": int | None, "subject_slug": str | None, "reason": str}
    unmapped: list[dict] = field(default_factory=list)
    fatal_error: str | None = None

    @property
    def ok(self) -> bool:
        return self.fatal_error is None

    def summary(self) -> str:
        if not self.ok:
            return f"FAILED: {self.fatal_error}"
        lines = [
            f"Exam {self.exam_code} / Department {self.department_code} / Year {self.year}",
            f"  Papers:    {self.papers_created} created, {self.papers_updated} updated",
            f"  Questions: {self.questions_created} created, {self.questions_updated} updated",
            f"  Options:   {self.options_created} created, {self.options_updated} updated",
        ]
        if self.unmapped:
            lines.append(f"  Unmapped/skipped: {len(self.unmapped)}")
            for item in self.unmapped:
                lines.append(f"    - Q{item.get('question_number')} ({item.get('subject_slug')}): {item['reason']}")
        return "\n".join(lines)


def import_gate_paper(db: Session, payload: dict) -> ImportReport:
    report = ImportReport(
        exam_code=payload.get("exam_code"),
        department_code=payload.get("department_code"),
        year=payload.get("year"),
    )

    exam = db.query(Exam).filter(Exam.code == payload.get("exam_code")).one_or_none()
    if exam is None:
        report.fatal_error = f"No Exam with code={payload.get('exam_code')!r}"
        return report

    department = (
        db.query(Department)
        .filter(Department.exam_id == exam.id, Department.code == payload.get("department_code"))
        .one_or_none()
    )
    if department is None:
        report.fatal_error = f"No Department with code={payload.get('department_code')!r} under exam {exam.code!r}"
        return report

    year = payload.get("year")
    if not isinstance(year, int):
        report.fatal_error = "payload.year is required and must be an integer"
        return report

    question_pdf_file_id = payload.get("question_pdf_file_id")
    if not question_pdf_file_id:
        report.fatal_error = (
            "payload.question_pdf_file_id is required - Paper.question_file_id is NOT NULL, "
            "and this importer never invents a placeholder file id. Upload the source PDF "
            "through the existing admin upload endpoint first, then pass its file id here."
        )
        return report

    answer_pdf_file_id = payload.get("answer_pdf_file_id")
    duration = payload.get("duration")

    by_subject: dict[str, list[dict]] = {}
    for q in payload.get("questions", []):
        by_subject.setdefault(q.get("subject_slug"), []).append(q)

    for subject_slug, questions in by_subject.items():
        subject = (
            db.query(Subject)
            .filter(Subject.department_id == department.id, Subject.slug == subject_slug)
            .one_or_none()
        )
        if subject is None:
            for q in questions:
                report.unmapped.append({
                    "question_number": q.get("question_number"),
                    "subject_slug": subject_slug,
                    "reason": f"no Subject with slug={subject_slug!r} under department {department.code!r}",
                })
            continue

        paper = db.query(Paper).filter(Paper.subject_id == subject.id, Paper.year == year).one_or_none()
        if paper is None:
            paper = Paper(
                subject_id=subject.id,
                year=year,
                title=f"{department.code} {year} - {subject.name}",
                question_file_id=question_pdf_file_id,
                answer_file_id=answer_pdf_file_id,
                duration=duration,
                total_questions=0,
                status=StatusEnum.DRAFT,
            )
            db.add(paper)
            db.flush()
            report.papers_created += 1
        else:
            paper.question_file_id = question_pdf_file_id
            if answer_pdf_file_id:
                paper.answer_file_id = answer_pdf_file_id
            if duration:
                paper.duration = duration
            report.papers_updated += 1

        for q in questions:
            missing = [f for f in REQUIRED_QUESTION_FIELDS if q.get(f) in (None, "")]
            if missing:
                report.unmapped.append({
                    "question_number": q.get("question_number"),
                    "subject_slug": subject_slug,
                    "reason": f"missing required field(s): {', '.join(missing)}",
                })
                continue

            question = (
                db.query(Question)
                .filter(Question.paper_id == paper.id, Question.question_number == q["question_number"])
                .one_or_none()
            )
            if question is None:
                question = Question(
                    paper_id=paper.id,
                    question_number=q["question_number"],
                    question_type=q["question_type"],
                    question_text=q["question_text"],
                    correct_answer=q["correct_answer"],
                    explanation=q.get("explanation"),
                    marks=q["marks"],
                    negative_marks=q["negative_marks"],
                    difficulty=q.get("difficulty"),
                    status=StatusEnum.DRAFT,
                )
                db.add(question)
                db.flush()
                report.questions_created += 1
            else:
                question.question_type = q["question_type"]
                question.question_text = q["question_text"]
                question.correct_answer = q["correct_answer"]
                question.explanation = q.get("explanation")
                question.marks = q["marks"]
                question.negative_marks = q["negative_marks"]
                if q.get("difficulty"):
                    question.difficulty = q["difficulty"]
                report.questions_updated += 1

            for opt in q.get("options", []):
                option = (
                    db.query(Option)
                    .filter(Option.question_id == question.id, Option.label == opt["label"])
                    .one_or_none()
                )
                if option is None:
                    db.add(Option(question_id=question.id, label=opt["label"], option_text=opt["text"]))
                    report.options_created += 1
                else:
                    option.option_text = opt["text"]
                    report.options_updated += 1

        paper.total_questions = db.query(Question).filter(Question.paper_id == paper.id).count()

    return report
