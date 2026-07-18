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