from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.common.rate_limit import rate_limit
from app.core.database import get_db
from app.core.enums import TerminationReason
from app.modules.question.schema import QuestionPublicResponse
from app.modules.student.dependencies import get_current_student
from app.modules.student.model import Student

from .schema import (
    JoinTestRequest,
    JoinTestResponse,
    MyResultListItem,
    SaveAnswerRequest,
    StartAttemptResponse,
    SubmitResponse,
    ViolationRequest,
)
from .service import conducted_test_attempt_service

router = APIRouter(
    prefix="/api/conducted-tests",
    tags=["Conducted Tests"]
)


@router.post("/join", response_model=JoinTestResponse, dependencies=[Depends(rate_limit(20, 60))])
def join(
    data: JoinTestRequest,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
):
    """Looks up a shared test code and returns the instructions-screen
    payload only - no attempt is created and no questions are exposed
    until the student explicitly starts (POST /{id}/start)."""
    result = conducted_test_attempt_service.join_for_instructions(db, data.test_code, student)
    conducted_test = result["conducted_test"]

    return JoinTestResponse(
        conducted_test_id=conducted_test.id,
        title=conducted_test.title,
        instructions=conducted_test.instructions,
        duration_minutes=conducted_test.duration_minutes,
        scheduled_start_at=conducted_test.scheduled_start_at,
        window_ends_at=result["window_ends_at"],
        already_completed=result["already_completed"],
    )


@router.post("/{conducted_test_id}/start", response_model=StartAttemptResponse)
def start(
    conducted_test_id: int,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
):
    result = conducted_test_attempt_service.start_or_resume(db, conducted_test_id, student)

    return StartAttemptResponse(
        attempt_id=result["attempt"].id,
        remaining_seconds=result["remaining_seconds"],
        window_ends_at=result["window_ends_at"],
        questions=[
            {"question": QuestionPublicResponse.model_validate(question).model_dump()}
            for question in result["questions"]
        ],
        answers=result["answers"],
    )


@router.post("/{conducted_test_id}/answer", status_code=204, dependencies=[Depends(rate_limit(120, 60))])
def save_answer(
    conducted_test_id: int,
    data: SaveAnswerRequest,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
):
    conducted_test_attempt_service.save_answer(
        db, conducted_test_id, student, data.question_id, data.answer
    )


@router.post("/{conducted_test_id}/violation", response_model=SubmitResponse)
def report_violation(
    conducted_test_id: int,
    data: ViolationRequest,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
):
    attempt = conducted_test_attempt_service.record_violation(
        db, conducted_test_id, student, TerminationReason(data.reason)
    )
    return _submit_response(attempt)


@router.post("/{conducted_test_id}/submit", response_model=SubmitResponse, dependencies=[Depends(rate_limit(20, 60))])
def submit(
    conducted_test_id: int,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
):
    attempt = conducted_test_attempt_service.submit(db, conducted_test_id, student)
    return _submit_response(attempt)


@router.get("/my-results", response_model=list[MyResultListItem])
def my_results(
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
):
    attempts = conducted_test_attempt_service.get_my_results(db, student)
    return [
        MyResultListItem(
            test_title=attempt.conducted_test.title,
            result_code=attempt.result_code,
            started_at=attempt.started_at,
            submitted_at=attempt.submitted_at,
            scored_marks=attempt.scored_marks,
            total_marks=attempt.total_marks,
            percentage=(
                round(100 * max(0.0, attempt.scored_marks) / attempt.total_marks, 1)
                if attempt.total_marks else None
            ),
            status=attempt.status.value,
        )
        for attempt in attempts
    ]


@router.get("/results/{result_code}")
def result_detail(
    result_code: str,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
):
    return conducted_test_attempt_service.get_result_for_student(db, result_code, student)


def _submit_response(attempt) -> SubmitResponse:
    return SubmitResponse(
        attempt_id=attempt.id,
        result_code=attempt.result_code,
        status=attempt.status.value,
        termination_reason=attempt.termination_reason.value if attempt.termination_reason else None,
        scored_marks=attempt.scored_marks or 0.0,
        total_marks=attempt.total_marks or 0.0,
        correct_count=attempt.correct_count or 0,
        incorrect_count=attempt.incorrect_count or 0,
        unanswered_count=attempt.unanswered_count or 0,
    )
