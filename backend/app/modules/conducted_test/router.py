from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.enums import StatusEnum
from app.modules.institution.dependencies import get_current_institution_user
from app.modules.institution.model import InstitutionUser
from app.modules.mock_test.repository import MockTestRepository

from .schema import ConductedTestCreate, ConductedTestParticipantResponse, ConductedTestResponse, ConductedTestUpdate
from .service import conducted_test_service

router = APIRouter(
    prefix="/api/institution/conducted-tests",
    tags=["Conducted Tests (Institution)"]
)

"""
Institution-only from here down - a normal LearnIn Admin JWT is never
accepted by get_current_institution_user (it's a distinct token "type"),
and every lookup/mutation is scoped to institution_user.institution_id
inside conducted_test_service, not merely by the {conducted_test_id} in
the URL. Cross-institution access always 404s (see
ConductedTestService.get_for_manage / repository.get_by_id_for_institution).
"""


@router.get("/available-mock-tests")
def available_mock_tests(
    db: Session = Depends(get_db),
    _institution_user: InstitutionUser = Depends(get_current_institution_user),
):
    """Published mock tests an authorized institution can attach a
    conducted test to - the "select an existing LearnIn Mock Test" step.
    Deliberately a plain dict list (id/title only) rather than the full
    MockTestResponse schema, since this is only ever used to populate a
    picker. Mock tests are platform-wide content, not institution-scoped,
    so every institution sees the same published catalog."""
    repo = MockTestRepository()
    mock_tests = repo.get_all(db)
    return [
        {"id": mock_test.id, "title": mock_test.title, "total_questions": mock_test.total_questions}
        for mock_test in mock_tests
        if mock_test.status == StatusEnum.PUBLISHED
    ]


@router.post("/", response_model=ConductedTestResponse)
def create(
    data: ConductedTestCreate,
    db: Session = Depends(get_db),
    institution_user: InstitutionUser = Depends(get_current_institution_user),
):
    return conducted_test_service.create(db, institution_user, data)


@router.get("/", response_model=list[ConductedTestResponse])
def list_mine(
    db: Session = Depends(get_db),
    institution_user: InstitutionUser = Depends(get_current_institution_user),
):
    return conducted_test_service.list_for_institution(db, institution_user)


@router.get("/{conducted_test_id}", response_model=ConductedTestResponse)
def get_one(
    conducted_test_id: int,
    db: Session = Depends(get_db),
    institution_user: InstitutionUser = Depends(get_current_institution_user),
):
    return conducted_test_service.get_for_manage(db, conducted_test_id, institution_user)


@router.patch("/{conducted_test_id}", response_model=ConductedTestResponse)
def update(
    conducted_test_id: int,
    data: ConductedTestUpdate,
    db: Session = Depends(get_db),
    institution_user: InstitutionUser = Depends(get_current_institution_user),
):
    return conducted_test_service.update(db, institution_user, conducted_test_id, data)


@router.post("/{conducted_test_id}/activate", response_model=ConductedTestResponse)
def activate(
    conducted_test_id: int,
    db: Session = Depends(get_db),
    institution_user: InstitutionUser = Depends(get_current_institution_user),
):
    return conducted_test_service.activate(db, institution_user, conducted_test_id)


@router.post("/{conducted_test_id}/deactivate", response_model=ConductedTestResponse)
def deactivate(
    conducted_test_id: int,
    db: Session = Depends(get_db),
    institution_user: InstitutionUser = Depends(get_current_institution_user),
):
    return conducted_test_service.deactivate(db, institution_user, conducted_test_id)


@router.delete("/{conducted_test_id}", response_model=ConductedTestResponse)
def soft_delete(
    conducted_test_id: int,
    db: Session = Depends(get_db),
    institution_user: InstitutionUser = Depends(get_current_institution_user),
):
    return conducted_test_service.soft_delete(db, institution_user, conducted_test_id)


@router.get("/{conducted_test_id}/participants", response_model=list[ConductedTestParticipantResponse])
def participants(
    conducted_test_id: int,
    db: Session = Depends(get_db),
    institution_user: InstitutionUser = Depends(get_current_institution_user),
):
    from app.modules.conducted_test_attempt.service import conducted_test_attempt_service

    conducted_test = conducted_test_service.get_for_manage(db, conducted_test_id, institution_user)
    return conducted_test_attempt_service.get_participants(db, conducted_test)


@router.get("/{conducted_test_id}/results/{result_code}")
def result_for_institution(
    conducted_test_id: int,
    result_code: str,
    db: Session = Depends(get_db),
    institution_user: InstitutionUser = Depends(get_current_institution_user),
):
    from app.modules.conducted_test_attempt.service import conducted_test_attempt_service

    conducted_test_service.get_for_manage(db, conducted_test_id, institution_user)
    return conducted_test_attempt_service.get_result_for_institution(
        db, result_code, institution_user.institution_id
    )


@router.post("/{conducted_test_id}/attempts/{student_id}/terminate")
def terminate_attempt(
    conducted_test_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    institution_user: InstitutionUser = Depends(get_current_institution_user),
):
    from app.modules.conducted_test_attempt.service import conducted_test_attempt_service

    conducted_test = conducted_test_service.get_for_manage(db, conducted_test_id, institution_user)
    return conducted_test_attempt_service.terminate_attempt(db, conducted_test, student_id)
