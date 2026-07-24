from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import AlreadyExistsException, NotFoundException
from app.common.services.base_service import BaseService
from app.common.utils.slug import generate_slug

from .model import Blog
from .repository import BlogRepository
from .schema import BlogCreate


class BlogService(BaseService):

    def __init__(self):
        super().__init__(BlogRepository())

    def create_blog(
        self,
        db: Session,
        data: BlogCreate
    ) -> Blog:

        slug = generate_slug(data.title)

        if self.repository.exists_by_slug(db, slug):
            raise AlreadyExistsException("A blog with this title already exists")

        blog = Blog(
            title=data.title,
            thumbnail_file_id=data.thumbnail_file_id,
            thumbnail_mime_type=data.thumbnail_mime_type,
            thumbnail_file_size=data.thumbnail_file_size,
            thumbnail_filename=data.thumbnail_filename,
            content=data.content,
            category=data.category,
            tags=data.tags,
            published_date=data.published_date,
            meta_title=data.meta_title,
            meta_description=data.meta_description,
            status=data.status,
            slug=slug,
        )

        return self.repository.create(db, blog)

    def get_published(
        self,
        db: Session,
        category: str | None = None,
        page: int = 1,
        page_size: int = 20
    ):
        return self.repository.get_published(db, category, page, page_size)

    def get_published_by_slug(
        self,
        db: Session,
        slug: str
    ) -> Blog:

        blog = self.repository.get_published_by_slug(db, slug)

        if blog is None:
            raise NotFoundException("Blog not found")

        return blog


blog_service = BlogService()
