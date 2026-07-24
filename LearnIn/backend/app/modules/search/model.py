from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import BaseModel


class SearchLog(BaseModel):

    __tablename__ = "search_logs"

    query: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True
    )

    results_count: Mapped[int] = mapped_column(
        Integer,
        default=0
    )
