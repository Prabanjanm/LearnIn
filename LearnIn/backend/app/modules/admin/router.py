from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db

from .dependencies import get_current_admin
from .model import Admin
from .schema import AdminLogin, AdminResponse, Token
from .service import admin_service

router = APIRouter(
    prefix="/api/admin",
    tags=["Admin"]
)


@router.post("/login", response_model=Token)
def login(
    data: AdminLogin,
    db: Session = Depends(get_db)
):
    return admin_service.login(db, data)


@router.get("/me", response_model=AdminResponse)
def get_me(
    current_admin: Admin = Depends(get_current_admin)
):
    return current_admin
