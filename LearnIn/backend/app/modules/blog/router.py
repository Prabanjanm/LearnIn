from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.admin.dependencies import get_current_admin

from .schema import BlogCreate, BlogListResponse, BlogResponse, BlogUpdate
from .service import blog_service

router = APIRouter(
    prefix="/api/blogs",
    tags=["Blogs"]
)


@router.get("/", response_model=BlogListResponse)
def get_all(
    category: str | None = None,
    page: int = 1,
    page_size: int = 12,
    db: Session = Depends(get_db)
):
    items, total = blog_service.get_published(db, category, page, page_size)
    return BlogListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{slug}", response_model=BlogResponse)
def get_one(
    slug: str,
    db: Session = Depends(get_db)
):
    return blog_service.get_published_by_slug(db, slug)


@router.post("/", response_model=BlogResponse)
def create(
    data: BlogCreate,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    return blog_service.create_blog(db, data)


@router.patch("/{blog_id}", response_model=BlogResponse)
def update(
    blog_id: int,
    data: BlogUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    blog = blog_service.get_or_404(db, blog_id, "Blog not found")
    return blog_service.update_blog(db, blog, data)


@router.delete("/{blog_id}", status_code=204)
def delete(
    blog_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    blog = blog_service.get_or_404(db, blog_id, "Blog not found")
    blog_service.delete_blog(db, blog)
