from sqlalchemy.orm import Session

from app.common.repositories.base_repository import BaseRepository
from app.core.enums import StatusEnum

from .model import Blog


class BlogRepository(BaseRepository):

    def __init__(self):
        super().__init__(Blog)

    def get_published(
        self,
        db: Session,
        category: str | None,
        page: int,
        page_size: int
    ):
        query = db.query(Blog).filter(Blog.status == StatusEnum.PUBLISHED)

        if category:
            query = query.filter(Blog.category == category)

        query = query.order_by(Blog.published_date.desc(), Blog.created_at.desc())

        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()

        return items, total

    def get_published_by_slug(
        self,
        db: Session,
        slug: str
    ):
        return (
            db.query(Blog)
            .filter(
                Blog.slug == slug,
                Blog.status == StatusEnum.PUBLISHED,
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
            db.query(Blog)
            .filter(
                Blog.status == StatusEnum.PUBLISHED,
                Blog.title.ilike(pattern),
            )
            .limit(limit)
            .all()
        )
