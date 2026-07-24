from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import app.models

from app.common.exceptions.exceptions import (
    AlreadyExistsException,
    GoogleDriveConfigError,
    InvalidCredentialsException,
    LearnInException,
    NotFoundException,
)
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

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0"
)

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

# Must be last: /{exam_slug} etc. are dynamic single/multi-segment catch-alls
# that would shadow every route above if registered earlier.
app.include_router(pages_router)


EXCEPTION_STATUS_CODES = {
    NotFoundException: 404,
    AlreadyExistsException: 409,
    InvalidCredentialsException: 401,
    GoogleDriveConfigError: 503,
}


@app.exception_handler(LearnInException)
async def learnin_exception_handler(request: Request, exc: LearnInException):
    status_code = EXCEPTION_STATUS_CODES.get(type(exc), 400)

    return JSONResponse(
        status_code=status_code,
        content={"detail": str(exc)},
    )