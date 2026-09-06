from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.database import SessionLocal

from .dependencies import STUDENT_ACCESS_TOKEN_COOKIE_NAME, _resolve_student


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
            db = SessionLocal()
            try:
                # Reuses the exact same resolution rules (type/tv claim
                # checks, id-based lookup) as get_current_student/
                # get_optional_student, instead of a second hand-rolled
                # copy that could silently drift out of sync with them.
                request.state.student = _resolve_student(db, token)
            finally:
                db.close()

        await self.app(scope, receive, send)
