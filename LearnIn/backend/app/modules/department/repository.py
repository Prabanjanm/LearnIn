from sqlalchemy.orm import Session

from app.common.repositories.base_repository import BaseRepository
from .model import Department


class DepartmentRepository(BaseRepository):

    def __init__(self):
        super().__init__(Department)

    def get_by_exam(
        self,
        db: Session,
        exam_id: int
    ):
        return (
            db.query(Department)
            .filter(
                Department.exam_id == exam_id
            )
            .order_by(
                Department.display_order
            )
            .all()
        )