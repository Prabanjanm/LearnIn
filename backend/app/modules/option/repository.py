from sqlalchemy.orm import Session

from app.common.repositories.base_repository import BaseRepository

from .model import Option


class OptionRepository(BaseRepository):

    def __init__(self):
        super().__init__(Option)

    def get_by_question(
        self,
        db: Session,
        question_id: int
    ):
        return (
            db.query(Option)
            .filter(Option.question_id == question_id)
            .order_by(Option.label)
            .all()
        )

    def exists_by_label(
        self,
        db: Session,
        question_id: int,
        label: str
    ) -> bool:
        return (
            db.query(Option)
            .filter(
                Option.question_id == question_id,
                Option.label == label,
            )
            .first()
            is not None
        )
