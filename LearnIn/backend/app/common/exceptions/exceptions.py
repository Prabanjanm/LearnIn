
class LearnInException(Exception):
    pass


class NotFoundException(LearnInException):
    pass


class AlreadyExistsException(LearnInException):
    pass