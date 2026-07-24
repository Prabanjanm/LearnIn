from sqlalchemy.orm import Session

from app.common.repositories.base_repository import BaseRepository

from .model import SearchLog


class SearchLogRepository(BaseRepository):

    def __init__(self):
        super().__init__(SearchLog)

    def log(
        self,
        db: Session,
        query: str,
        results_count: int
    ) -> SearchLog:
        entry = SearchLog(query=query, results_count=results_count)
        return self.create(db, entry)
