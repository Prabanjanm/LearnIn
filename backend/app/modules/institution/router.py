from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.common.rate_limit import rate_limit
from app.core.database import get_db
from app.core.security import create_access_token

from .dependencies import get_current_institution_user
from .model import InstitutionUser
from .schema import InstitutionLogin, InstitutionUserResponse, Token
from .service import institution_user_service

router = APIRouter(
    prefix="/api/institution",
    tags=["Institution"]
)


@router.post("/login", response_model=Token, dependencies=[Depends(rate_limit(10, 60))])
def login(
    data: InstitutionLogin,
    db: Session = Depends(get_db)
):
    user = institution_user_service.authenticate(db, data.email, data.password)

    access_token = create_access_token(
        subject=str(user.id),
        token_type="institution_user",
        token_version=user.token_version,
    )

    return Token(access_token=access_token)


@router.get("/me", response_model=InstitutionUserResponse)
def get_me(
    current_user: InstitutionUser = Depends(get_current_institution_user)
):
    return current_user
