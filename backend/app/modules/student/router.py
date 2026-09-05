from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token

from .dependencies import get_current_student
from .model import Student
from .schema import StudentLogin, StudentResponse, StudentSignup, Token
from .service import student_service

router = APIRouter(
    prefix="/api/students",
    tags=["Students"]
)


@router.post("/signup", response_model=Token)
def signup(
    data: StudentSignup,
    db: Session = Depends(get_db),
):
    student = student_service.signup(db, data.email, data.password, data.full_name)
    return Token(access_token=create_access_token(subject=student.email))


@router.post("/login", response_model=Token)
def login(
    data: StudentLogin,
    db: Session = Depends(get_db),
):
    student = student_service.authenticate(db, data.email, data.password)
    return Token(access_token=create_access_token(subject=student.email))


@router.get("/me", response_model=StudentResponse)
def get_me(
    current_student: Student = Depends(get_current_student),
):
    return current_student
