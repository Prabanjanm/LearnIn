from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.common.repositories.base_repository import BaseRepository
from app.core.enums import StatusEnum
from app.modules.department.model import Department
from app.modules.paper.model import Paper
from app.modules.subject.model import Subject

from .model import MockTest


class MockTestRepository(BaseRepository):

    def __init__(self):
        super().__init__(MockTest)

    def get_by_paper(
        self,
        db: Session,
        paper_id: int
    ):
        return (
            db.query(MockTest)
            .filter(MockTest.paper_id == paper_id)
            .order_by(MockTest.created_at.desc())
            .all()
        )

    def get_published_by_paper(
        self,
        db: Session,
        paper_id: int
    ):
        return (
            db.query(MockTest)
            .filter(
                MockTest.paper_id == paper_id,
                MockTest.status == StatusEnum.PUBLISHED,
            )
            .order_by(MockTest.created_at.desc())
            .all()
        )

    def get_published_by_id(
        self,
        db: Session,
        mock_test_id: int
    ):
        return (
            db.query(MockTest)
            .filter(
                MockTest.id == mock_test_id,
                MockTest.status == StatusEnum.PUBLISHED,
            )
            .first()
        )

    def get_recent_published(
        self,
        db: Session,
        limit: int = 6
    ):
        """Newest published mock tests site-wide, for the homepage's
        mock-test section - eager-loads the paper/subject/department/exam
        chain each card needs for its URL/meta."""
        return (
            db.query(MockTest)
            .options(
                selectinload(MockTest.paper)
                .selectinload(Paper.subject)
                .selectinload(Subject.department)
                .selectinload(Department.exam)
            )
            .filter(MockTest.status == StatusEnum.PUBLISHED)
            .order_by(MockTest.created_at.desc())
            .limit(limit)
            .all()
        )

    def count_published_by_exam(
        self,
        db: Session
    ) -> dict[int, int]:
        """One grouped query for the homepage exam cards' real mock-test
        counts - never N+1'd per exam."""
        rows = (
            db.query(Department.exam_id, func.count(MockTest.id))
            .join(Paper, MockTest.paper_id == Paper.id)
            .join(Subject, Paper.subject_id == Subject.id)
            .join(Department, Subject.department_id == Department.id)
            .filter(MockTest.status == StatusEnum.PUBLISHED)
            .group_by(Department.exam_id)
            .all()
        )
        return {exam_id: count for exam_id, count in rows}

    def get_filtered(
        self,
        db: Session,
        exam_id: int | None = None,
        department_id: int | None = None,
        subject_id: int | None = None,
        term: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ):
        """Powers the /mock-tests browse page. Same shape as
        PaperRepository.get_filtered - only real columns/relationships,
        no difficulty filter since MockTest has no difficulty column."""
        query = (
            db.query(MockTest)
            .join(Paper, MockTest.paper_id == Paper.id)
            .join(Subject, Paper.subject_id == Subject.id)
            .join(Department, Subject.department_id == Department.id)
            .options(
                selectinload(MockTest.paper)
                .selectinload(Paper.subject)
                .selectinload(Subject.department)
                .selectinload(Department.exam)
            )
            .filter(MockTest.status == StatusEnum.PUBLISHED)
        )

        if exam_id is not None:
            query = query.filter(Department.exam_id == exam_id)
        if department_id is not None:
            query = query.filter(Subject.department_id == department_id)
        if subject_id is not None:
            query = query.filter(Paper.subject_id == subject_id)
        if term:
            query = query.filter(MockTest.title.ilike(f"%{term}%"))

        query = query.order_by(MockTest.created_at.desc())

        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return items, total
