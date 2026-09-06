
class LearnInException(Exception):
    pass


class NotFoundException(LearnInException):
    pass


class AlreadyExistsException(LearnInException):
    pass


class InvalidCredentialsException(LearnInException):
    pass


class GoogleDriveConfigError(LearnInException):
    pass


class InvalidStateException(LearnInException):
    """Request is well-formed and authorized, but not valid given the
    current state of the resource - e.g. saving an answer to an attempt
    that has already expired or been submitted. Maps to 400 (the default
    fallback status in main.py's EXCEPTION_STATUS_CODES)."""
    pass


class ForbiddenException(LearnInException):
    """The caller is authenticated but not authorized for this specific
    resource - e.g. a student viewing another student's result, or an
    admin managing a conducted test they didn't create. Maps to 403."""
    pass