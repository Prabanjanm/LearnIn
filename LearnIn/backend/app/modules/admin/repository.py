from sqlalchemy.orm import Session

from app.common.repositories.base_repository import BaseRepository

from .model import Admin


class AdminRepository(BaseRepository):

    def __init__(self):
        super().__init__(Admin)

    def get_by_email(
        self,
        db: Session,
        email: str
    ):
        return (
            db.query(Admin)
            .filter(Admin.email == email)
            .first()
        )
