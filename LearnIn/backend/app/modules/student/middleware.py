from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.database import SessionLocal
from app.core.security import decode_access_token

from .dependencies import STUDENT_ACCESS_TOKEN_COOKIE_NAME
from .repository import StudentRepository

_repository = StudentRepository()


class StudentIdentityMiddleware:
    """
    Resolves the logged-in student (if any) from the session cookie once
    per request and stashes it on request.state.student, so templates -
    the navbar in particular, which renders on every public page - can
    show the right login state without every single page route needing
    its own `Depends(get_optional_student)` parameter and context entry.
    Routes that actually gate behavior on the student (dashboard, mock
    test submission) still use get_current_student/get_optional_student
    explicitly; this just covers display.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        request.state.student = None

        token = request.cookies.get(STUDENT_ACCESS_TOKEN_COOKIE_NAME)
        if token:
            payload = decode_access_token(token)
            if payload and "sub" in payload:
                db = SessionLocal()
                try:
                    student = _repository.get_by_email(db, payload["sub"])
                    if student is not None and student.is_active:
                        request.state.student = student
                finally:
                    db.close()

        await self.app(scope, receive, send)
