from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import (
    AlreadyExistsException,
    InvalidCredentialsException,
)
from app.common.services.base_service import BaseService
from app.core.security import hash_password, verify_password

from .model import Student
from .repository import StudentRepository


class StudentService(BaseService):

    def __init__(self):
        super().__init__(StudentRepository())

    def authenticate(
        self,
        db: Session,
        email: str,
        password: str
    ) -> Student:

        student = self.repository.get_by_email(db, email)

        if not student or not student.is_active:
            raise InvalidCredentialsException("Invalid email or password")

        if not verify_password(password, student.hashed_password):
            raise InvalidCredentialsException("Invalid email or password")

        return student

    def signup(
        self,
        db: Session,
        email: str,
        password: str,
        full_name: str | None = None
    ) -> Student:

        if self.repository.get_by_email(db, email):
            raise AlreadyExistsException("An account with this email already exists")

        student = Student(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
        )

        return self.repository.create(db, student)


student_service = StudentService()
