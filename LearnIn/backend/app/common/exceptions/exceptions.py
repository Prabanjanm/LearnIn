
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