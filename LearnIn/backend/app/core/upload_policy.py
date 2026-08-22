"""
Central validation policy for admin file uploads.

Every upload widget (exam icon, paper PDF, question image, ...) posts to the
same /admin/upload endpoint with a `category`. This module is the single
place that decides what each category accepts, so no upload path can bypass
size/type checks by going through a different form field.
"""
from dataclasses import dataclass

from app.core.config import settings

IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/svg+xml"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}
PDF_MIME_TYPES = {"application/pdf"}
PDF_EXTENSIONS = {".pdf"}


@dataclass(frozen=True)
class CategoryPolicy:
    allowed_mime_types: frozenset
    allowed_extensions: frozenset
    max_size_bytes: int


CATEGORY_POLICIES: dict[str, CategoryPolicy] = {
    "exams": CategoryPolicy(frozenset(IMAGE_MIME_TYPES), frozenset(IMAGE_EXTENSIONS), settings.MAX_IMAGE_UPLOAD_BYTES),
    "departments": CategoryPolicy(frozenset(IMAGE_MIME_TYPES), frozenset(IMAGE_EXTENSIONS), settings.MAX_IMAGE_UPLOAD_BYTES),
    "subjects": CategoryPolicy(frozenset(IMAGE_MIME_TYPES), frozenset(IMAGE_EXTENSIONS), settings.MAX_IMAGE_UPLOAD_BYTES),
    "thumbnails": CategoryPolicy(frozenset(IMAGE_MIME_TYPES), frozenset(IMAGE_EXTENSIONS), settings.MAX_IMAGE_UPLOAD_BYTES),
    "images": CategoryPolicy(frozenset(IMAGE_MIME_TYPES), frozenset(IMAGE_EXTENSIONS), settings.MAX_IMAGE_UPLOAD_BYTES),
    "question_images": CategoryPolicy(frozenset(IMAGE_MIME_TYPES), frozenset(IMAGE_EXTENSIONS), settings.MAX_IMAGE_UPLOAD_BYTES),
    "papers": CategoryPolicy(frozenset(PDF_MIME_TYPES), frozenset(PDF_EXTENSIONS), settings.MAX_PDF_UPLOAD_BYTES),
    "resources": CategoryPolicy(
        frozenset(PDF_MIME_TYPES | IMAGE_MIME_TYPES),
        frozenset(PDF_EXTENSIONS | IMAGE_EXTENSIONS),
        settings.MAX_PDF_UPLOAD_BYTES,
    ),
    "blogs": CategoryPolicy(frozenset(IMAGE_MIME_TYPES), frozenset(IMAGE_EXTENSIONS), settings.MAX_IMAGE_UPLOAD_BYTES),
}


class UploadValidationError(ValueError):
    """Raised when an upload fails category/MIME/extension/size validation."""


def validate_upload(category: str | None, filename: str, mime_type: str | None, file_size: int) -> None:
    if not category or category not in CATEGORY_POLICIES:
        raise UploadValidationError(
            f"Unknown upload category '{category}'. Allowed categories: "
            f"{', '.join(sorted(CATEGORY_POLICIES))}."
        )

    policy = CATEGORY_POLICIES[category]

    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in policy.allowed_extensions:
        raise UploadValidationError(
            f"File extension '{extension or '(none)'}' is not allowed for category '{category}'. "
            f"Allowed: {', '.join(sorted(policy.allowed_extensions))}."
        )

    if not mime_type or mime_type not in policy.allowed_mime_types:
        raise UploadValidationError(
            f"File type '{mime_type or 'unknown'}' is not allowed for category '{category}'. "
            f"Allowed: {', '.join(sorted(policy.allowed_mime_types))}."
        )

    if file_size <= 0:
        raise UploadValidationError("Uploaded file is empty.")

    if file_size > policy.max_size_bytes:
        max_mb = policy.max_size_bytes / (1024 * 1024)
        raise UploadValidationError(
            f"File exceeds the maximum allowed size of {max_mb:.0f}MB for category '{category}'."
        )
