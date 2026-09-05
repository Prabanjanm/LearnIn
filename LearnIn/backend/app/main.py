import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

import app.models

from app.common.exceptions.exceptions import (
    AlreadyExistsException,
    GoogleDriveConfigError,
    InvalidCredentialsException,
    LearnInException,
    NotFoundException,
)
from app.common.middleware import CsrfOriginCheckMiddleware, SecurityHeadersMiddleware
from app.core.config import settings
from app.modules.admin.router import router as admin_router
from app.modules.admin.pages import router as admin_pages_router
from app.modules.exam.router import router as exam_router
from app.modules.home.router import router as home_router
from app.modules.department.router import router as department_router
from app.modules.subject.router import router as subject_router
from app.modules.paper.router import router as paper_router
from app.modules.question.router import router as question_router
from app.modules.option.router import router as option_router
from app.modules.resource.router import router as resource_router
from app.modules.mock_test.router import router as mock_test_router
from app.modules.mock_test_question.router import router as mock_test_question_router
from app.modules.blog.router import router as blog_router
from app.modules.search.router import router as search_router
from app.modules.pages.router import router as pages_router
from app.modules.student.middleware import StudentIdentityMiddleware
from app.modules.student.router import router as student_router

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    debug=settings.DEBUG,
)

app.add_middleware(StudentIdentityMiddleware)
app.add_middleware(CsrfOriginCheckMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

templates = Jinja2Templates(directory="app/templates")

app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static"
)


app.include_router(home_router)
app.include_router(admin_router)
app.include_router(admin_pages_router)
app.include_router(exam_router)
app.include_router(department_router)
app.include_router(subject_router)
app.include_router(paper_router)
app.include_router(question_router)
app.include_router(option_router)
app.include_router(resource_router)
app.include_router(mock_test_router)
app.include_router(mock_test_question_router)
app.include_router(blog_router)
app.include_router(search_router)
app.include_router(student_router)

# Must be last: /{exam_slug} etc. are dynamic single/multi-segment catch-alls
# that would shadow every route above if registered earlier.
app.include_router(pages_router)


EXCEPTION_STATUS_CODES = {
    NotFoundException: 404,
    AlreadyExistsException: 409,
    InvalidCredentialsException: 401,
    GoogleDriveConfigError: 503,
}

_ERROR_MESSAGES = {
    401: "You need to be logged in to do that.",
    403: "You don't have permission to do that.",
    404: "We couldn't find that page.",
    409: "That conflicts with something that already exists.",
    422: "That request wasn't valid.",
    503: "This feature is temporarily unavailable. Please try again shortly.",
}


def _is_api_request(request: Request) -> bool:
    return request.url.path.startswith("/api/")


def _render_error_page(request: Request, status_code: int, message: str | None = None):
    if status_code == 404:
        return templates.TemplateResponse(
            request=request, name="pages/404.html", context={}, status_code=404
        )

    return templates.TemplateResponse(
        request=request,
        name="pages/error.html",
        context={
            "status_code": status_code,
            "message": message or _ERROR_MESSAGES.get(status_code, "Something went wrong. We couldn't complete that request."),
        },
        status_code=status_code,
    )


@app.exception_handler(LearnInException)
async def learnin_exception_handler(request: Request, exc: LearnInException):
    status_code = EXCEPTION_STATUS_CODES.get(type(exc), 400)

    if _is_api_request(request):
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return _render_error_page(request, status_code, str(exc))


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Covers everything Starlette raises itself - unmatched routes (404),
    and anything a route raises directly via HTTPException (403, 401, 503
    from the Google Drive proxy route, etc.) - so these get the same
    friendly page/JSON split as our own LearnInException family instead of
    Starlette's bare `{"detail": ...}` default."""

    if _is_api_request(request):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    return _render_error_page(request, exc.status_code, exc.detail if isinstance(exc.detail, str) else None)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    if _is_api_request(request):
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    return _render_error_page(request, 422)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Last resort for genuine bugs. Never leak a traceback to a real
    visitor - log the failing path/method (no request body, no headers,
    since those can carry auth cookies or form data) and show a generic
    friendly error. In DEBUG mode, re-raise so Starlette's own debug
    middleware still renders the full traceback for local development."""

    if settings.DEBUG:
        raise exc

    logger.exception("Unhandled error on %s %s", request.method, request.url.path)

    if _is_api_request(request):
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    return _render_error_page(request, 500)