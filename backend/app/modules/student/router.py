from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.common.rate_limit import rate_limit
from app.core.database import get_db
from app.core.security import create_access_token

from .dependencies import get_current_student
from .model import Student
from .schema import (
    ChangePasswordRequest,
    StudentLogin,
    StudentProfileUpdate,
    StudentResendOtp,
    StudentResponse,
    StudentSignup,
    StudentVerifyOtp,
    Token,
)
from .service import student_service

router = APIRouter(
    prefix="/api/students",
    tags=["Students"]
)


def _token_for(student: Student) -> Token:
    return Token(
        access_token=create_access_token(
            subject=str(student.id),
            token_type="student",
            token_version=student.token_version,
        )
    )


@router.post("/signup", response_model=Token, dependencies=[Depends(rate_limit(10, 60))])
def signup(
    data: StudentSignup,
    db: Session = Depends(get_db),
):
    student = student_service.signup(db, data.email, data.password, data.full_name)
    return _token_for(student)


@router.post("/verify-otp", response_model=StudentResponse, dependencies=[Depends(rate_limit(10, 60))])
def verify_otp(
    data: StudentVerifyOtp,
    db: Session = Depends(get_db),
):
    return student_service.verify_otp(db, data.email, data.otp)


@router.post("/resend-otp", dependencies=[Depends(rate_limit(3, 60))])
def resend_otp(
    data: StudentResendOtp,
    db: Session = Depends(get_db),
):
    student_service.resend_otp(db, data.email)
    return {"detail": "A new verification code has been sent."}


@router.post("/login", response_model=Token, dependencies=[Depends(rate_limit(10, 60))])
def login(
    data: StudentLogin,
    db: Session = Depends(get_db),
):
    student = student_service.authenticate(db, data.email, data.password)
    return _token_for(student)


@router.get("/me", response_model=StudentResponse)
def get_me(
    current_student: Student = Depends(get_current_student),
):
    return current_student


@router.patch("/me", response_model=StudentResponse)
def update_me(
    data: StudentProfileUpdate,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    return student_service.update_profile(db, current_student, data)


@router.post(
    "/me/change-password",
    response_model=Token,
    dependencies=[Depends(rate_limit(10, 60))],
)
def change_password(
    data: ChangePasswordRequest,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    student = student_service.change_password(
        db, current_student, data.current_password, data.new_password
    )
    # token_version was just bumped - issue a fresh token immediately so the
    # caller isn't locked out by their own password change.
    return _token_for(student)
