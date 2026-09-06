"""
Central validation policy for admin file uploads.

Every upload widget (exam icon, paper PDF, question image, ...) posts to the
same /admin/upload endpoint with a `category`. This module is the single
place that decides what each category accepts, so no upload path can bypass
size/type checks by going through a different form field.
"""
from dataclasses import dataclass

from app.core.config import settings

# SVG is deliberately not an allowed image type. An SVG is XML that can
# carry <script>, event-handler attributes, and other executable content -
# writing a correct, complete SVG sanitizer is its own hard problem, and
# nothing in this app actually needs SVG's scalability over a plain raster
# icon (JPEG/PNG/WEBP/GIF cover every real use here). Rejecting it outright
# is the smaller, safer surface.
IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
PDF_MIME_TYPES = {"application/pdf"}
PDF_EXTENSIONS = {".pdf"}

# Magic-byte signatures for every extension this app accepts - checked
# against the actual uploaded bytes so a renamed/mislabeled file (e.g. an
# HTML file saved as "paper.pdf" with a forged Content-Type) is rejected
# even though its extension and declared MIME type both look legitimate.
_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    ".pdf": (b"%PDF-",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".gif": (b"GIF87a", b"GIF89a"),
    # WEBP is "RIFF" + 4-byte size + "WEBP" - the size varies per file, so
    # the fixed prefix/suffix are checked instead of one contiguous magic.
    ".webp": (b"RIFF",),
}


def _has_valid_signature(extension: str, content: bytes) -> bool:
    signatures = _SIGNATURES.get(extension)
    if signatures is None:
        # No signature registered for this extension - nothing to check
        # against (shouldn't happen for any currently allowed extension).
        return True

    if extension == ".webp":
        return content.startswith(b"RIFF") and content[8:12] == b"WEBP"

    return any(content.startswith(sig) for sig in signatures)


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
    "paper_processing_sources": CategoryPolicy(frozenset(PDF_MIME_TYPES), frozenset(PDF_EXTENSIONS), settings.MAX_PDF_UPLOAD_BYTES),
    "resources": CategoryPolicy(
        frozenset(PDF_MIME_TYPES | IMAGE_MIME_TYPES),
        frozenset(PDF_EXTENSIONS | IMAGE_EXTENSIONS),
        settings.MAX_PDF_UPLOAD_BYTES,
    ),
    "blogs": CategoryPolicy(frozenset(IMAGE_MIME_TYPES), frozenset(IMAGE_EXTENSIONS), settings.MAX_IMAGE_UPLOAD_BYTES),
    "avatars": CategoryPolicy(frozenset(IMAGE_MIME_TYPES), frozenset(IMAGE_EXTENSIONS), settings.MAX_IMAGE_UPLOAD_BYTES),
}

# Header/control characters and path separators stripped from every uploaded
# filename before it's handed to Drive - Drive itself has no filesystem path
# concept, but the raw name is echoed back in JSON responses, stored in DB
# columns, and used as a Content-Disposition filename on download, so it
# still needs to be safe as plain text (no CR/LF header-injection, no
# unbounded length).
MAX_FILENAME_LENGTH = 200


def sanitize_filename(filename: str) -> str:
    cleaned = "".join(
        ch for ch in filename
        if ord(ch) >= 32 and ch not in '"/\\'
    ).strip()

    return (cleaned or "upload")[:MAX_FILENAME_LENGTH]


class UploadValidationError(ValueError):
    """Raised when an upload fails category/MIME/extension/size validation."""


def validate_upload(
    category: str | None,
    filename: str,
    mime_type: str | None,
    file_size: int,
    content: bytes | None = None,
) -> None:
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

    if content is not None and not _has_valid_signature(extension, content):
        raise UploadValidationError(
            f"File content does not match a valid {extension} file. "
            "The file may be corrupted or mislabeled."
        )
