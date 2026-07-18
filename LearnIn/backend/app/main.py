from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import app.models

from app.core.config import settings
from app.modules.exam.router import router as exam_router
from app.modules.home.router import router as home_router
from app.modules.department.router import router as department_router

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
app.include_router(exam_router)
app.include_router(department_router)


@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="base.html",
        context={}
    )