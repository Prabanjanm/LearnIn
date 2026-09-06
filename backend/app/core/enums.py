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