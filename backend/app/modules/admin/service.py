from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import (
    AlreadyExistsException,
    InvalidCredentialsException,
)
from app.common.services.base_service import BaseService
from app.core.security import create_access_token, hash_password, verify_password

from .model import Admin
from .repository import AdminRepository
from .schema import AdminLogin, Token


class AdminService(BaseService):

    def __init__(self):
        super().__init__(AdminRepository())

    def authenticate(
        self,
        db: Session,
        email: str,
        password: str
    ) -> Admin:

        admin = self.repository.get_by_email(db, email)

        if not admin or not admin.is_active:
            raise InvalidCredentialsException("Invalid email or password")

        if not verify_password(password, admin.hashed_password):
            raise InvalidCredentialsException("Invalid email or password")

        return admin

    def login(
        self,
        db: Session,
        data: AdminLogin
    ) -> Token:

        admin = self.authenticate(db, data.email, data.password)

        access_token = create_access_token(
            subject=str(admin.id),
            token_type="admin",
            token_version=admin.token_version,
        )

        return Token(access_token=access_token)

    def create_admin(
        self,
        db: Session,
        email: str,
        password: str,
        full_name: str | None = None
    ) -> Admin:

        if self.repository.get_by_email(db, email):
            raise AlreadyExistsException("Admin with this email already exists")

        admin = Admin(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
        )

        return self.repository.create(db, admin)


admin_service = AdminService()
