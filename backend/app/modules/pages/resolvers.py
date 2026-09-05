"""
Shared slug-chain resolution for the public site's nested SEO URLs:
/{exam_slug}/{department_slug}/{subject_slug}/{year}

Every page below the exam level needs its full ancestor chain (to build
breadcrumbs and validate the URL actually nests correctly), so this is
centralized here instead of repeated per page route. Each context also
knows how to render its own breadcrumb trail, since it already holds
every slug needed to build the ancestor URLs.
"""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.modules.department.model import Department
from app.modules.department.service import department_service
from app.modules.exam.model import Exam
from app.modules.exam.service import exam_service
from app.modules.paper.model import Paper
from app.modules.paper.service import paper_service
from app.modules.subject.model import Subject
from app.modules.subject.service import subject_service


@dataclass
class ExamContext:
    exam: Exam

    def breadcrumb_trail(self) -> list[dict]:
        """Crumbs for everything ABOVE this context's own entity."""
        return []

    def breadcrumbs_with_current(self, label, url: str | None = None) -> list[dict]:
        return self.breadcrumb_trail() + [{"label": label, "url": url}]


@dataclass
class DepartmentContext(ExamContext):
    department: Department

    def breadcrumb_trail(self) -> list[dict]:
        return [{"label": self.exam.name, "url": f"/{self.exam.slug}"}]


@dataclass
class SubjectContext(DepartmentContext):
    subject: Subject

    def breadcrumb_trail(self) -> list[dict]:
        return super().breadcrumb_trail() + [
            {"label": self.department.name, "url": f"/{self.exam.slug}/{self.department.slug}"}
        ]


@dataclass
class PaperContext(SubjectContext):
    paper: Paper

    def breadcrumb_trail(self) -> list[dict]:
        return super().breadcrumb_trail() + [
            {
                "label": self.subject.name,
                "url": f"/{self.exam.slug}/{self.department.slug}/{self.subject.slug}",
            }
        ]

    def paper_url(self) -> str:
        return f"/{self.exam.slug}/{self.department.slug}/{self.subject.slug}/{self.paper.year}"


def resolve_exam(db: Session, exam_slug: str) -> ExamContext:
    exam = exam_service.get_published_by_slug(db, exam_slug)
    return ExamContext(exam=exam)


def resolve_department(db: Session, exam_slug: str, department_slug: str) -> DepartmentContext:
    exam_ctx = resolve_exam(db, exam_slug)
    department = department_service.get_published_by_slug(db, exam_ctx.exam.id, department_slug)

    return DepartmentContext(exam=exam_ctx.exam, department=department)


def resolve_subject(
    db: Session,
    exam_slug: str,
    department_slug: str,
    subject_slug: str
) -> SubjectContext:
    department_ctx = resolve_department(db, exam_slug, department_slug)
    subject = subject_service.get_published_by_slug(db, department_ctx.department.id, subject_slug)

    return SubjectContext(
        exam=department_ctx.exam,
        department=department_ctx.department,
        subject=subject,
    )


def resolve_paper(
    db: Session,
    exam_slug: str,
    department_slug: str,
    subject_slug: str,
    year: int
) -> PaperContext:
    subject_ctx = resolve_subject(db, exam_slug, department_slug, subject_slug)
    paper = paper_service.get_published_by_year(db, subject_ctx.subject.id, year)

    return PaperContext(
        exam=subject_ctx.exam,
        department=subject_ctx.department,
        subject=subject_ctx.subject,
        paper=paper,
    )
