from datetime import date

from pydantic import BaseModel, ConfigDict, computed_field

from app.common.utils.drive_urls import drive_view_url
from app.core.enums import StatusEnum


class BlogBase(BaseModel):
    title: str
    content: str


class BlogCreate(BlogBase):
    category: str | None = None
    tags: str | None = None
    published_date: date | None = None
    thumbnail_file_id: str | None = None
    thumbnail_mime_type: str | None = None
    thumbnail_file_size: int | None = None
    thumbnail_filename: str | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    status: StatusEnum = StatusEnum.DRAFT


class BlogUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    category: str | None = None
    tags: str | None = None
    published_date: date | None = None
    thumbnail_file_id: str | None = None
    thumbnail_mime_type: str | None = None
    thumbnail_file_size: int | None = None
    thumbnail_filename: str | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    status: StatusEnum | None = None


class BlogResponse(BlogBase):

    id: int
    slug: str
    category: str | None = None
    tags: str | None = None
    published_date: date | None = None
    thumbnail_file_id: str | None = None
    thumbnail_filename: str | None = None
    status: StatusEnum
    meta_title: str | None = None
    meta_description: str | None = None

    model_config = ConfigDict(
        from_attributes=True
    )

    @computed_field
    @property
    def thumbnail_url(self) -> str | None:
        return drive_view_url(self.thumbnail_file_id)


class BlogListResponse(BaseModel):
    items: list[BlogResponse]
    total: int
    page: int
    page_size: int
