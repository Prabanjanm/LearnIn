from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.common.repositories.base_repository import BaseRepository
from app.core.enums import StatusEnum
from app.modules.department.model import Department
from app.modules.subject.model import Subject

from .model import Paper


class PaperRepository(BaseRepository):

    def __init__(self):
        super().__init__(Paper)

    def get_published_by_subject(
        self,
        db: Session,
        subject_id: int
    ):
        return (
            db.query(Paper)
            .filter(
                Paper.subject_id == subject_id,
                Paper.status == StatusEnum.PUBLISHED,
            )
            .order_by(Paper.year.desc())
            .all()
        )

    def get_published_by_id(
        self,
        db: Session,
        paper_id: int
    ):
        return (
            db.query(Paper)
            .filter(
                Paper.id == paper_id,
                Paper.status == StatusEnum.PUBLISHED,
            )
            .first()
        )

    def get_published_by_year(
        self,
        db: Session,
        subject_id: int,
        year: int
    ):
        return (
            db.query(Paper)
            .filter(
                Paper.subject_id == subject_id,
                Paper.year == year,
                Paper.status == StatusEnum.PUBLISHED,
            )
            .first()
        )

    def get_recent_published(
        self,
        db: Session,
        limit: int = 6
    ):
        """Newest published papers site-wide, for the homepage PYQ
        section - eager-loads the subject/department/exam chain each
        card needs for its title/meta/URL so rendering N cards never
        triggers N extra queries."""
        return (
            db.query(Paper)
            .options(
                selectinload(Paper.subject)
                .selectinload(Subject.department)
                .selectinload(Department.exam)
            )
            .filter(Paper.status == StatusEnum.PUBLISHED)
            .order_by(Paper.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_filtered(
        self,
        db: Session,
        exam_id: int | None = None,
        department_id: int | None = None,
        subject_id: int | None = None,
        year: int | None = None,
        has_answer_key: bool | None = None,
        term: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ):
        """Powers the /papers browse page. Every filter is optional and
        only ever narrows real columns/relationships - never fabricates
        a filter for data that doesn't exist (e.g. there's no paper_type
        column, so no such filter is offered)."""
        query = (
            db.query(Paper)
            .join(Subject, Paper.subject_id == Subject.id)
            .join(Department, Subject.department_id == Department.id)
            .options(
                selectinload(Paper.subject)
                .selectinload(Subject.department)
                .selectinload(Department.exam)
            )
            .filter(Paper.status == StatusEnum.PUBLISHED)
        )

        if exam_id is not None:
            query = query.filter(Department.exam_id == exam_id)
        if department_id is not None:
            query = query.filter(Subject.department_id == department_id)
        if subject_id is not None:
            query = query.filter(Paper.subject_id == subject_id)
        if year is not None:
            query = query.filter(Paper.year == year)
        if has_answer_key is True:
            query = query.filter(Paper.answer_file_id.is_not(None))
        elif has_answer_key is False:
            query = query.filter(Paper.answer_file_id.is_(None))
        if term:
            query = query.filter(Paper.title.ilike(f"%{term}%"))

        query = query.order_by(Paper.year.desc(), Paper.title.asc())

        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    def count_published_by_exam(
        self,
        db: Session
    ) -> dict[int, int]:
        """One grouped query for the homepage exam cards' real paper counts -
        never N+1'd per exam."""
        rows = (
            db.query(Department.exam_id, func.count(Paper.id))
            .join(Subject, Paper.subject_id == Subject.id)
            .join(Department, Subject.department_id == Department.id)
            .filter(Paper.status == StatusEnum.PUBLISHED)
            .group_by(Department.exam_id)
            .all()
        )
        return {exam_id: count for exam_id, count in rows}

    def get_distinct_years(
        self,
        db: Session
    ) -> list[int]:
        rows = (
            db.query(Paper.year)
            .filter(Paper.status == StatusEnum.PUBLISHED)
            .distinct()
            .order_by(Paper.year.desc())
            .all()
        )
        return [row[0] for row in rows]

    def search(
        self,
        db: Session,
        term: str,
        limit: int = 5
    ):
        pattern = f"%{term}%"
        return (
            db.query(Paper)
            .options(
                selectinload(Paper.subject)
                .selectinload(Subject.department)
                .selectinload(Department.exam)
            )
            .filter(
                Paper.status == StatusEnum.PUBLISHED,
                Paper.title.ilike(pattern),
            )
            .limit(limit)
            .all()
        )
