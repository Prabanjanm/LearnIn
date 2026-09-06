from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import (
    AlreadyExistsException,
    InvalidCredentialsException,
)
from app.common.services.base_service import BaseService
from app.common.utils.file_tracking import cleanup_drive_file
from app.core.security import hash_password, verify_password

from .model import Student
from .repository import StudentRepository
from .schema import StudentProfileUpdate


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

    def update_profile(
        self,
        db: Session,
        student: Student,
        data: StudentProfileUpdate,
    ) -> Student:
        student.full_name = data.full_name
        return self.repository.update(db, student)

    def change_password(
        self,
        db: Session,
        student: Student,
        current_password: str,
        new_password: str,
    ) -> Student:
        if not verify_password(current_password, student.hashed_password):
            raise InvalidCredentialsException("Current password is incorrect")

        student.hashed_password = hash_password(new_password)
        # Invalidate every token issued before this change - the old cookie's
        # JWT still carries the previous token_version and will now fail
        # `_resolve_student`'s comparison, even though it hasn't expired yet.
        student.token_version += 1

        return self.repository.update(db, student)

    def set_avatar(
        self,
        db: Session,
        student: Student,
        file_id: str,
    ) -> Student:
        previous_file_id = student.avatar_file_id
        student.avatar_file_id = file_id
        updated = self.repository.update(db, student)

        if previous_file_id and previous_file_id != file_id:
            cleanup_drive_file(db, previous_file_id)

        return updated


student_service = StudentService()
