from sqlalchemy.orm import Session, selectinload

from app.common.repositories.base_repository import BaseRepository
from app.core.enums import StatusEnum
from app.modules.department.model import Department
from app.modules.paper.model import Paper
from app.modules.subject.model import Subject

from .model import Question


class QuestionRepository(BaseRepository):

    def __init__(self):
        super().__init__(Question)

    def get_published_by_paper(
        self,
        db: Session,
        paper_id: int
    ):
        return (
            db.query(Question)
            .options(selectinload(Question.options))
            .filter(
                Question.paper_id == paper_id,
                Question.status == StatusEnum.PUBLISHED,
            )
            .order_by(Question.question_number)
            .all()
        )

    def get_published_by_id(
        self,
        db: Session,
        question_id: int
    ):
        return (
            db.query(Question)
            .options(selectinload(Question.options))
            .filter(
                Question.id == question_id,
                Question.status == StatusEnum.PUBLISHED,
            )
            .first()
        )

    def search(
        self,
        db: Session,
        term: str,
        limit: int = 5
    ):
        pattern = f"%{term}%"
        return (
            db.query(Question)
            .options(
                selectinload(Question.paper)
                .selectinload(Paper.subject)
                .selectinload(Subject.department)
                .selectinload(Department.exam)
            )
            .filter(
                Question.status == StatusEnum.PUBLISHED,
                Question.question_text.ilike(pattern),
            )
            .limit(limit)
            .all()
        )
