from enum import Enum


class StatusEnum(str, Enum):

    DRAFT = "DRAFT"

    PUBLISHED = "PUBLISHED"

    ARCHIVED = "ARCHIVED"


class QuestionType(str, Enum):

    MCQ = "MCQ"

    MSQ = "MSQ"

    NAT = "NAT"


class DifficultyEnum(str, Enum):

    EASY = "EASY"

    MEDIUM = "MEDIUM"

    HARD = "HARD"


class ProcessingStatusEnum(str, Enum):
    """
    Lifecycle of one "Question Paper Processing" job (upload -> publish).
    Every stage the background pipeline enters is written to the DB so the
    admin's status polling reflects real progress rather than a spinner
    that never moves.
    """

    UPLOADED = "UPLOADED"

    VALIDATING = "VALIDATING"

    VALIDATION_FAILED = "VALIDATION_FAILED"

    CLEANING_WATERMARK = "CLEANING_WATERMARK"

    WATERMARK_NEEDS_REVIEW = "WATERMARK_NEEDS_REVIEW"

    ANALYZING = "ANALYZING"

    EXTRACTING = "EXTRACTING"

    DETECTING_QUESTIONS = "DETECTING_QUESTIONS"

    READY_FOR_REVIEW = "READY_FOR_REVIEW"

    REVIEWED = "REVIEWED"

    GENERATING_PDF = "GENERATING_PDF"

    READY_TO_PUBLISH = "READY_TO_PUBLISH"

    PUBLISHED = "PUBLISHED"

    FAILED = "FAILED"


class PdfTypeEnum(str, Enum):

    TEXT = "TEXT"

    SCANNED = "SCANNED"

    UNKNOWN = "UNKNOWN"


class WatermarkStatusEnum(str, Enum):

    NOT_NEEDED = "NOT_NEEDED"

    CLEANED = "CLEANED"

    NEEDS_MANUAL_REVIEW = "NEEDS_MANUAL_REVIEW"


class ExtractionConfidenceEnum(str, Enum):
    """
    How much the parser trusts one detected question block. Never a claim
    about correctness of the *content* - only about how cleanly the block
    could be segmented out of the extracted text.
    """

    HIGH = "HIGH"

    MEDIUM = "MEDIUM"

    LOW = "LOW"


class ImageSourceType(str, Enum):
    """
    How one ExtractedQuestionImage was obtained. Purely provenance - it does
    not affect how the image is treated afterwards (all are opaque, unedited
    binary assets), but it helps an admin judge how much to trust an
    automatically-detected association versus one they attached by hand.
    """

    # A real embedded raster image (JPEG/PNG XObject) found in the PDF.
    EMBEDDED_RASTER = "EMBEDDED_RASTER"

    # A vector drawing (paths/curves, not a raster image) detected via the
    # page's graphics/drawing commands and rendered to a raster crop because
    # there is no "extract the vector as-is" operation that preserves it
    # faithfully outside a PDF viewer.
    VECTOR_RENDER = "VECTOR_RENDER"

    # No specific graphic object was identified, but the question's region
    # on the page contains more vertical space than its recognised text
    # accounts for - the region was rendered at high resolution rather than
    # silently discarded, and is always flagged for admin confirmation.
    REGION_RENDER = "REGION_RENDER"

    # Attached by an admin directly on the review screen.
    MANUAL = "MANUAL"


class ResourceType(str, Enum):

    NOTES = "NOTES"

    PYQ = "PYQ"

    FORMULA_SHEET = "FORMULA_SHEET"

    REVISION_NOTES = "REVISION_NOTES"

    IMPORTANT_QUESTIONS = "IMPORTANT_QUESTIONS"

    CHEAT_SHEET = "CHEAT_SHEET"


class ConductedTestAttemptStatus(str, Enum):
    """Lifecycle of one student's attempt at an institute-conducted test.
    Terminal once anything other than IN_PROGRESS is set - see
    conducted_test_attempt/service.py for why every finalization path is
    idempotent rather than re-checking this everywhere."""

    IN_PROGRESS = "IN_PROGRESS"

    SUBMITTED = "SUBMITTED"

    AUTO_SUBMITTED = "AUTO_SUBMITTED"

    TERMINATED = "TERMINATED"


class TerminationReason(str, Enum):
    """Why a conducted-test attempt was finalized. Stored even for a
    normal manual submit so every attempt has a uniform, reportable
    reason rather than a nullable field that's only sometimes set."""

    TAB_SWITCH = "TAB_SWITCH"

    FULLSCREEN_EXIT = "FULLSCREEN_EXIT"

    TIME_EXPIRED = "TIME_EXPIRED"

    MANUAL_SUBMIT = "MANUAL_SUBMIT"

    ADMIN_TERMINATED = "ADMIN_TERMINATED"