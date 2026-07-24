import json

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.exceptions.exceptions import (
    AlreadyExistsException,
    GoogleDriveConfigError,
    InvalidCredentialsException,
    NotFoundException,
)
from app.core.database import get_db
from app.core.google_drive import get_drive_client
from app.core.security import create_access_token
from app.modules.blog.model import Blog
from app.modules.department.model import Department
from app.modules.exam.model import Exam
from app.modules.mock_test.model import MockTest
from app.modules.mock_test.schema import MockTestCreate
from app.modules.mock_test.service import mock_test_service
from app.modules.paper.model import Paper
from app.modules.question.model import Question
from app.modules.question.schema import OptionIn, QuestionCreate
from app.modules.question.service import question_service
from app.modules.resource.model import Resource
from app.modules.subject.model import Subject

from .crud_config import ENTITY_REGISTRY, FIELD_UPLOAD, STATUS_FIELD, coerce_form_value
from .dependencies import ACCESS_TOKEN_COOKIE_NAME, get_current_admin, get_optional_admin
from .model import Admin
from .service import admin_service

router = APIRouter(tags=["Admin Pages"])

templates = Jinja2Templates(directory="app/templates")


def apply_upload_field(field: dict, raw_value: str | None, payload: dict) -> None:
    """
    Expands one upload field's JSON blob ({file_id, mime_type, file_size,
    filename}, produced by upload-widget.js) into the schema keys the
    entity's Create schema actually declares: `field["name"]` gets the
    file_id, and metadata_prefix + "_mime_type" / "_file_size" / "_filename"
    get the rest. Shared by the generic form engine and the custom
    Question/MockTest forms so this parsing only lives in one place.
    """
    prefix = field.get("metadata_prefix", field["name"])

    if not raw_value:
        payload[field["name"]] = None
        payload[f"{prefix}_mime_type"] = None
        payload[f"{prefix}_file_size"] = None
        payload[f"{prefix}_filename"] = None
        return

    try:
        data = json.loads(raw_value)
    except (TypeError, ValueError):
        payload[field["name"]] = None
        return

    payload[field["name"]] = data.get("file_id")
    payload[f"{prefix}_mime_type"] = data.get("mime_type")
    payload[f"{prefix}_file_size"] = data.get("file_size")
    payload[f"{prefix}_filename"] = data.get("filename")


# ---------------------------------------------------------------- auth ----

@router.get("/admin/login")
def login_page(request: Request, admin: Admin | None = Depends(get_optional_admin)):
    if admin is not None:
        return RedirectResponse("/admin", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="admin/login.html",
        context={"error": None},
    )


@router.post("/admin/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        admin = admin_service.authenticate(db, email, password)
    except InvalidCredentialsException:
        return templates.TemplateResponse(
            request=request,
            name="admin/login.html",
            context={"error": "Invalid email or password"},
            status_code=401,
        )

    token = create_access_token(subject=admin.email)

    response = RedirectResponse("/admin", status_code=303)
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24,
    )
    return response


@router.get("/admin/logout")
def logout():
    response = RedirectResponse("/admin/login", status_code=303)
    response.delete_cookie(ACCESS_TOKEN_COOKIE_NAME)
    return response


# ----------------------------------------------------------- dashboard ----

STAT_ENTITIES = [
    ("exams", "Exams", Exam, "exam"),
    ("departments", "Departments", Department, "department"),
    ("subjects", "Subjects", Subject, "subject"),
    ("papers", "Papers", Paper, "paper"),
    ("questions", "Questions", Question, "question"),
    ("resources", "Resources", Resource, "resource"),
    ("blogs", "Blogs", Blog, "blog"),
    ("mock_tests", "Mock Tests", MockTest, "mocktest"),
]

FILE_SIZE_COLUMNS = [
    (Exam, "icon_file_size"),
    (Department, "icon_file_size"),
    (Subject, "icon_file_size"),
    (Blog, "thumbnail_file_size"),
    (Resource, "google_drive_file_size"),
    (Paper, "question_file_size"),
    (Paper, "answer_file_size"),
    (Question, "image_file_size"),
]

RECENT_MODELS = [
    ("Exam", Exam, "name"),
    ("Paper", Paper, "title"),
    ("Resource", Resource, "title"),
    ("Blog", Blog, "title"),
]


def format_bytes(num_bytes: float) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


@router.get("/admin")
def dashboard(
    request: Request,
    admin: Admin | None = Depends(get_optional_admin),
    db: Session = Depends(get_db),
):
    if admin is None:
        return RedirectResponse("/admin/login", status_code=303)

    entities = [
        {"key": key, "label": config["label"]}
        for key, config in ENTITY_REGISTRY.items()
    ]

    stats = [
        {"key": key, "label": label, "icon": icon_name, "count": db.query(model).count()}
        for key, label, model, icon_name in STAT_ENTITIES
    ]

    total_bytes = 0
    for model, column in FILE_SIZE_COLUMNS:
        total = db.query(func.sum(getattr(model, column))).scalar()
        if total:
            total_bytes += total

    recent_items = []
    for type_label, model, title_attr in RECENT_MODELS:
        rows = db.query(model).order_by(model.created_at.desc()).limit(5).all()
        for row in rows:
            recent_items.append(
                {
                    "type": type_label,
                    "title": getattr(row, title_attr),
                    "created_at": row.created_at,
                    "status": getattr(row, "status", None),
                }
            )
    recent_items.sort(key=lambda item: item["created_at"], reverse=True)
    recent_items = recent_items[:8]

    return templates.TemplateResponse(
        request=request,
        name="admin/dashboard.html",
        context={
            "admin": admin,
            "entities": entities,
            "stats": stats,
            "storage_display": format_bytes(total_bytes),
            "recent_items": recent_items,
        },
    )


# ------------------------------------------------- custom: questions -----
# Registered before the generic wildcard route below so these literal
# paths win for entity_key == "questions" (nested options need a bespoke form).

QUESTION_FORM_FIELDS = [
    {"name": "paper_id", "label": "Paper ID", "type": "number", "required": True},
    {"name": "question_number", "label": "Question number", "type": "number", "required": True},
    {"name": "question_type", "label": "Type", "type": "select", "required": True, "options": ["MCQ", "MSQ", "NAT"]},
    {"name": "difficulty", "label": "Difficulty", "type": "select", "required": True, "options": ["EASY", "MEDIUM", "HARD"]},
    {"name": "question_text", "label": "Question text", "type": "textarea", "required": True},
    {
        "name": "image_file_id",
        "label": "Question image (optional)",
        "type": FIELD_UPLOAD,
        "category": "question_images",
        "accept": "image/*",
        "metadata_prefix": "image",
        "required": False,
    },
    {"name": "marks", "label": "Marks", "type": "number", "required": False, "default": 1},
    {"name": "negative_marks", "label": "Negative marks", "type": "number", "required": False, "default": 0},
    {"name": "correct_answer", "label": "Correct answer (e.g. B or A,C or 3.5)", "type": "text", "required": True},
    {"name": "explanation", "label": "Explanation (optional)", "type": "textarea", "required": False},
    {
        "name": "explanation_image_file_id",
        "label": "Explanation image (optional)",
        "type": FIELD_UPLOAD,
        "category": "question_images",
        "accept": "image/*",
        "metadata_prefix": "explanation_image",
        "required": False,
    },
    {"name": "option_a_text", "label": "Option A", "type": "text", "required": False},
    {
        "name": "option_a_image_file_id",
        "label": "Option A image (optional)",
        "type": FIELD_UPLOAD,
        "category": "question_images",
        "accept": "image/*",
        "metadata_prefix": "option_a_image",
        "required": False,
    },
    {"name": "option_b_text", "label": "Option B", "type": "text", "required": False},
    {
        "name": "option_b_image_file_id",
        "label": "Option B image (optional)",
        "type": FIELD_UPLOAD,
        "category": "question_images",
        "accept": "image/*",
        "metadata_prefix": "option_b_image",
        "required": False,
    },
    {"name": "option_c_text", "label": "Option C", "type": "text", "required": False},
    {
        "name": "option_c_image_file_id",
        "label": "Option C image (optional)",
        "type": FIELD_UPLOAD,
        "category": "question_images",
        "accept": "image/*",
        "metadata_prefix": "option_c_image",
        "required": False,
    },
    {"name": "option_d_text", "label": "Option D", "type": "text", "required": False},
    {
        "name": "option_d_image_file_id",
        "label": "Option D image (optional)",
        "type": FIELD_UPLOAD,
        "category": "question_images",
        "accept": "image/*",
        "metadata_prefix": "option_d_image",
        "required": False,
    },
    STATUS_FIELD,
]


def _question_form_field(name: str) -> dict:
    return next(f for f in QUESTION_FORM_FIELDS if f["name"] == name)


@router.get("/admin/manage/questions/new")
def question_form(request: Request, admin: Admin | None = Depends(get_optional_admin)):
    if admin is None:
        return RedirectResponse("/admin/login", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="admin/form.html",
        context={
            "admin": admin,
            "entity_key": "questions",
            "label": "Questions",
            "fields": QUESTION_FORM_FIELDS,
            "error": None,
        },
    )


@router.post("/admin/manage/questions/new")
async def question_create(
    request: Request,
    admin: Admin | None = Depends(get_optional_admin),
    db: Session = Depends(get_db),
):
    if admin is None:
        return RedirectResponse("/admin/login", status_code=303)

    form_data = await request.form()

    options = []
    for label in ("A", "B", "C", "D"):
        text = form_data.get(f"option_{label.lower()}_text")
        if not text:
            continue

        option_image_field = _question_form_field(f"option_{label.lower()}_image_file_id")
        option_image_payload: dict = {}
        apply_upload_field(option_image_field, form_data.get(option_image_field["name"]), option_image_payload)

        prefix = f"option_{label.lower()}_image"
        options.append(OptionIn(
            label=label,
            option_text=text,
            image_file_id=option_image_payload.get(f"{prefix}_file_id"),
            image_mime_type=option_image_payload.get(f"{prefix}_mime_type"),
            image_file_size=option_image_payload.get(f"{prefix}_file_size"),
            image_filename=option_image_payload.get(f"{prefix}_filename"),
        ))

    image_payload: dict = {}
    apply_upload_field(_question_form_field("image_file_id"), form_data.get("image_file_id"), image_payload)

    explanation_image_payload: dict = {}
    apply_upload_field(
        _question_form_field("explanation_image_file_id"),
        form_data.get("explanation_image_file_id"),
        explanation_image_payload,
    )

    try:
        data = QuestionCreate(
            paper_id=int(form_data.get("paper_id")),
            question_number=int(form_data.get("question_number")),
            question_type=form_data.get("question_type"),
            difficulty=form_data.get("difficulty"),
            question_text=form_data.get("question_text"),
            image_file_id=image_payload.get("image_file_id"),
            image_mime_type=image_payload.get("image_mime_type"),
            image_file_size=image_payload.get("image_file_size"),
            image_filename=image_payload.get("image_filename"),
            marks=float(form_data.get("marks") or 1),
            negative_marks=float(form_data.get("negative_marks") or 0),
            correct_answer=form_data.get("correct_answer"),
            explanation=form_data.get("explanation") or None,
            explanation_image_file_id=explanation_image_payload.get("explanation_image_file_id"),
            explanation_image_mime_type=explanation_image_payload.get("explanation_image_mime_type"),
            explanation_image_file_size=explanation_image_payload.get("explanation_image_file_size"),
            explanation_image_filename=explanation_image_payload.get("explanation_image_filename"),
            options=options,
            status=form_data.get("status") or "DRAFT",
        )
        question_service.create_question(db, data)
    except IntegrityError as e:
        db.rollback()

        print("========== IntegrityError ==========")
        print(e)
        print("---------- ORIGINAL ERROR ----------")
        print(e.orig)

        raise

    except (ValueError, NotFoundException) as exc:
        return templates.TemplateResponse(
            request=request,
            name="admin/form.html",
            context={
                "admin": admin,
                "entity_key": "questions",
                "label": "Questions",
                "fields": QUESTION_FORM_FIELDS,
                "error": f"Invalid input: {exc}",
            },
            status_code=400,
        )

    return RedirectResponse("/admin/manage/questions?success=1", status_code=303)


# ------------------------------------------------- custom: mock tests ----

MOCK_TEST_FORM_FIELDS = [
    {"name": "paper_id", "label": "Paper ID", "type": "number", "required": True},
    {"name": "title", "label": "Title", "type": "text", "required": True},
    {"name": "description", "label": "Description", "type": "textarea", "required": False},
    {"name": "duration", "label": "Duration (minutes)", "type": "number", "required": False, "default": 180},
    {"name": "total_marks", "label": "Total marks", "type": "number", "required": False, "default": 100},
    {"name": "question_ids", "label": "Question IDs (comma separated)", "type": "text", "required": True},
    STATUS_FIELD,
]


@router.get("/admin/manage/mock_tests/new")
def mock_test_form(request: Request, admin: Admin | None = Depends(get_optional_admin)):
    if admin is None:
        return RedirectResponse("/admin/login", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="admin/form.html",
        context={
            "admin": admin,
            "entity_key": "mock_tests",
            "label": "Mock Tests",
            "fields": MOCK_TEST_FORM_FIELDS,
            "error": None,
        },
    )


@router.post("/admin/manage/mock_tests/new")
async def mock_test_create(
    request: Request,
    admin: Admin | None = Depends(get_optional_admin),
    db: Session = Depends(get_db),
):
    if admin is None:
        return RedirectResponse("/admin/login", status_code=303)

    form_data = await request.form()

    try:
        raw_ids = form_data.get("question_ids", "")
        question_ids = [int(part.strip()) for part in raw_ids.split(",") if part.strip()]

        data = MockTestCreate(
            paper_id=int(form_data.get("paper_id")),
            title=form_data.get("title"),
            description=form_data.get("description") or None,
            duration=int(form_data.get("duration") or 180),
            total_marks=int(form_data.get("total_marks") or 100),
            question_ids=question_ids,
            status=form_data.get("status") or "DRAFT",
        )
        mock_test_service.create_mock_test(db, data)
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            request=request,
            name="admin/form.html",
            context={
                "admin": admin,
                "entity_key": "mock_tests",
                "label": "Mock Tests",
                "fields": MOCK_TEST_FORM_FIELDS,
                "error": "A mock test with conflicting data already exists.",
            },
            status_code=400,
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request=request,
            name="admin/form.html",
            context={
                "admin": admin,
                "entity_key": "mock_tests",
                "label": "Mock Tests",
                "fields": MOCK_TEST_FORM_FIELDS,
                "error": f"Invalid input: {exc}",
            },
            status_code=400,
        )

    return RedirectResponse("/admin/manage/mock_tests?success=1", status_code=303)


# ------------------------------------------------------ generic CRUD -----

@router.get("/admin/manage/{entity_key}")
def entity_list(
    entity_key: str,
    request: Request,
    admin: Admin | None = Depends(get_optional_admin),
    db: Session = Depends(get_db),
):
    if admin is None:
        return RedirectResponse("/admin/login", status_code=303)

    config = ENTITY_REGISTRY.get(entity_key)
    if config is None:
        return RedirectResponse("/admin", status_code=303)

    rows = config["service"].get_all(db)

    return templates.TemplateResponse(
        request=request,
        name="admin/list.html",
        context={
            "admin": admin,
            "entity_key": entity_key,
            "label": config["label"],
            "columns": config["list_columns"],
            "rows": rows,
        },
    )


@router.get("/admin/manage/{entity_key}/new")
def entity_form(
    entity_key: str,
    request: Request,
    admin: Admin | None = Depends(get_optional_admin),
):
    if admin is None:
        return RedirectResponse("/admin/login", status_code=303)

    config = ENTITY_REGISTRY.get(entity_key)
    if config is None or config["schema"] is None:
        return RedirectResponse("/admin", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="admin/form.html",
        context={
            "admin": admin,
            "entity_key": entity_key,
            "label": config["label"],
            "fields": config["form_fields"],
            "error": None,
        },
    )


@router.post("/admin/manage/{entity_key}/new")
async def entity_create(
    entity_key: str,
    request: Request,
    admin: Admin | None = Depends(get_optional_admin),
    db: Session = Depends(get_db),
):
    if admin is None:
        return RedirectResponse("/admin/login", status_code=303)

    config = ENTITY_REGISTRY.get(entity_key)
    if config is None or config["schema"] is None:
        return RedirectResponse("/admin", status_code=303)

    form_data = await request.form()
    payload = {}

    for field in config["form_fields"]:
        raw_value = form_data.get(field["name"])

        if field["type"] == FIELD_UPLOAD:
            apply_upload_field(field, raw_value, payload)
        else:
            payload[field["name"]] = coerce_form_value(field, raw_value)

    try:
        schema_instance = config["schema"](**payload)
        method = getattr(config["service"], config["create_method"])
        method(db, schema_instance)
    except (AlreadyExistsException, NotFoundException, GoogleDriveConfigError) as exc:
        return templates.TemplateResponse(
            request=request,
            name="admin/form.html",
            context={
                "admin": admin,
                "entity_key": entity_key,
                "label": config["label"],
                "fields": config["form_fields"],
                "error": str(exc),
            },
            status_code=400,
        )
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            request=request,
            name="admin/form.html",
            context={
                "admin": admin,
                "entity_key": entity_key,
                "label": config["label"],
                "fields": config["form_fields"],
                "error": "This conflicts with an existing record (duplicate value in a unique field).",
            },
            status_code=400,
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request=request,
            name="admin/form.html",
            context={
                "admin": admin,
                "entity_key": entity_key,
                "label": config["label"],
                "fields": config["form_fields"],
                "error": f"Invalid input: {exc}",
            },
            status_code=400,
        )

    return RedirectResponse(f"/admin/manage/{entity_key}?success=1", status_code=303)


@router.post("/admin/manage/{entity_key}/bulk")
async def entity_bulk_action(
    entity_key: str,
    request: Request,
    admin: Admin | None = Depends(get_optional_admin),
    db: Session = Depends(get_db),
):
    if admin is None:
        return RedirectResponse("/admin/login", status_code=303)

    config = ENTITY_REGISTRY.get(entity_key)
    if config is None:
        return RedirectResponse("/admin", status_code=303)

    form_data = await request.form()
    action = form_data.get("action")
    ids = [int(raw_id) for raw_id in form_data.getlist("ids") if raw_id]

    for obj_id in ids:
        obj = config["service"].get_by_id(db, obj_id)
        if obj is None:
            continue

        if action == "delete":
            config["service"].delete(db, obj)
        elif action in ("DRAFT", "PUBLISHED", "ARCHIVED") and hasattr(obj, "status"):
            obj.status = action
            config["service"].update(db, obj)

    return RedirectResponse(f"/admin/manage/{entity_key}?success=1", status_code=303)


# ------------------------------------------------------- file uploads ----

@router.post("/admin/upload")
async def upload_file(
    file: UploadFile = File(...),
    category: str | None = Form(None),
    _admin: Admin = Depends(get_current_admin),
):
    content = await file.read()
    client = get_drive_client()

    try:
        result = client.upload_file(
            content,
            filename=file.filename or "upload",
            mime_type=file.content_type or "application/octet-stream",
            category=category,
        )
    except GoogleDriveConfigError as exc:
        return {"error": str(exc)}

    return {
        "file_id": result.file_id,
        "mime_type": result.mime_type,
        "file_size": result.file_size,
        "filename": result.name,
    }
