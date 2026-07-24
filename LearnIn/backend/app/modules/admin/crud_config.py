"""
Generic, data-driven config for the Jinja admin CRUD pages.

Each entry describes one manageable entity: which service to call, which
Pydantic schema validates the create form, which columns to show in the
list view, and which fields to render in the create form. This lets a
single pair of templates (list.html / form.html) serve every entity
instead of duplicating near-identical CRUD templates per module.

Upload fields (type=FIELD_UPLOAD) never ask the admin for a Drive id/URL -
the widget uploads automatically and stashes {file_id, mime_type,
file_size, filename} as JSON in one form field; `metadata_prefix` tells
admin/pages.py which model columns to expand that JSON into
(e.g. prefix "icon" -> icon_file_id/icon_mime_type/icon_file_size/icon_filename).
"""
from app.modules.blog.schema import BlogCreate
from app.modules.blog.service import blog_service
from app.modules.department.schema import DepartmentCreate
from app.modules.department.service import department_service
from app.modules.exam.schema import ExamCreate
from app.modules.exam.service import exam_service
from app.modules.mock_test.service import mock_test_service
from app.modules.option.schema import OptionCreate
from app.modules.option.service import option_service
from app.modules.paper.schema import PaperCreate
from app.modules.paper.service import paper_service
from app.modules.question.service import question_service
from app.modules.resource.schema import ResourceCreate
from app.modules.resource.service import resource_service
from app.modules.subject.schema import SubjectCreate
from app.modules.subject.service import subject_service

FIELD_TEXT = "text"
FIELD_TEXTAREA = "textarea"
FIELD_NUMBER = "number"
FIELD_SELECT = "select"
FIELD_UPLOAD = "upload"
FIELD_MARKDOWN = "markdown"

STATUS_FIELD = {
    "name": "status",
    "label": "Status",
    "type": FIELD_SELECT,
    "required": True,
    "options": ["DRAFT", "PUBLISHED", "ARCHIVED"],
    "default": "DRAFT",
}


ENTITY_REGISTRY = {
    "exams": {
        "label": "Exams",
        "service": exam_service,
        "create_method": "create_exam",
        "schema": ExamCreate,
        "list_columns": ["id", "name", "code", "slug", "status", "display_order"],
        "form_fields": [
            {"name": "name", "label": "Name", "type": FIELD_TEXT, "required": True},
            {"name": "code", "label": "Code", "type": FIELD_TEXT, "required": True},
            {"name": "description", "label": "Description", "type": FIELD_TEXTAREA, "required": False},
            {
                "name": "icon_file_id",
                "label": "Exam Icon",
                "type": FIELD_UPLOAD,
                "category": "exams",
                "accept": "image/*",
                "metadata_prefix": "icon",
                "required": False,
            },
            {"name": "display_order", "label": "Display order", "type": FIELD_NUMBER, "required": False, "default": 0},
            STATUS_FIELD,
        ],
    },
    "departments": {
        "label": "Departments",
        "service": department_service,
        "create_method": "create_department",
        "schema": DepartmentCreate,
        "list_columns": ["id", "exam_id", "name", "code", "slug", "status", "display_order"],
        "form_fields": [
            {"name": "exam_id", "label": "Exam ID", "type": FIELD_NUMBER, "required": True},
            {"name": "name", "label": "Name", "type": FIELD_TEXT, "required": True},
            {"name": "code", "label": "Code", "type": FIELD_TEXT, "required": True},
            {
                "name": "icon_file_id",
                "label": "Department Icon",
                "type": FIELD_UPLOAD,
                "category": "departments",
                "accept": "image/*",
                "metadata_prefix": "icon",
                "required": False,
            },
            {"name": "display_order", "label": "Display order", "type": FIELD_NUMBER, "required": False, "default": 0},
            STATUS_FIELD,
        ],
    },
    "subjects": {
        "label": "Subjects",
        "service": subject_service,
        "create_method": "create_subject",
        "schema": SubjectCreate,
        "list_columns": ["id", "department_id", "name", "slug", "status", "display_order"],
        "form_fields": [
            {"name": "department_id", "label": "Department ID", "type": FIELD_NUMBER, "required": True},
            {"name": "name", "label": "Name", "type": FIELD_TEXT, "required": True},
            {
                "name": "icon_file_id",
                "label": "Subject Icon",
                "type": FIELD_UPLOAD,
                "category": "subjects",
                "accept": "image/*",
                "metadata_prefix": "icon",
                "required": False,
            },
            {"name": "display_order", "label": "Display order", "type": FIELD_NUMBER, "required": False, "default": 0},
            STATUS_FIELD,
        ],
    },
    "papers": {
        "label": "Papers",
        "service": paper_service,
        "create_method": "create_paper",
        "schema": PaperCreate,
        "list_columns": ["id", "subject_id", "title", "year", "status", "total_questions"],
        "form_fields": [
            {"name": "subject_id", "label": "Subject ID", "type": FIELD_NUMBER, "required": True},
            {"name": "title", "label": "Title", "type": FIELD_TEXT, "required": True},
            {"name": "year", "label": "Year", "type": FIELD_NUMBER, "required": True},
            {
                "name": "question_file_id",
                "label": "Question paper PDF",
                "type": FIELD_UPLOAD,
                "category": "papers",
                "accept": ".pdf",
                "metadata_prefix": "question_file",
                "required": True,
            },
            {
                "name": "answer_file_id",
                "label": "Answer key PDF",
                "type": FIELD_UPLOAD,
                "category": "papers",
                "accept": ".pdf",
                "metadata_prefix": "answer_file",
                "required": False,
            },
            {"name": "duration", "label": "Duration (minutes)", "type": FIELD_NUMBER, "required": False},
            STATUS_FIELD,
        ],
    },
    "resources": {
        "label": "Resources",
        "service": resource_service,
        "create_method": "create_resource",
        "schema": ResourceCreate,
        "list_columns": ["id", "subject_id", "title", "resource_type", "status"],
        "form_fields": [
            {"name": "subject_id", "label": "Subject ID", "type": FIELD_NUMBER, "required": True},
            {"name": "title", "label": "Title", "type": FIELD_TEXT, "required": True},
            {"name": "description", "label": "Description", "type": FIELD_TEXTAREA, "required": False},
            {
                "name": "resource_type",
                "label": "Type",
                "type": FIELD_SELECT,
                "required": True,
                "options": ["NOTES", "PYQ", "FORMULA_SHEET", "REVISION_NOTES", "IMPORTANT_QUESTIONS", "CHEAT_SHEET"],
            },
            {
                "name": "google_drive_file_id",
                "label": "File",
                "type": FIELD_UPLOAD,
                "category": "resources",
                "accept": ".pdf,image/*",
                "metadata_prefix": "google_drive",
                "required": True,
            },
            STATUS_FIELD,
        ],
    },
    "options": {
        "label": "Options",
        "service": option_service,
        "create_method": "create_option",
        "schema": OptionCreate,
        "list_columns": ["id", "question_id", "label", "option_text"],
        "form_fields": [
            {"name": "question_id", "label": "Question ID", "type": FIELD_NUMBER, "required": True},
            {"name": "label", "label": "Label (A/B/C/D)", "type": FIELD_TEXT, "required": True},
            {"name": "option_text", "label": "Option text", "type": FIELD_TEXTAREA, "required": True},
            {
                "name": "image_file_id",
                "label": "Option image (optional)",
                "type": FIELD_UPLOAD,
                "category": "question_images",
                "accept": "image/*",
                "metadata_prefix": "image",
                "required": False,
            },
        ],
    },
    "questions": {
        # Create form is custom (nested options) - see admin/pages.py.
        "label": "Questions",
        "service": question_service,
        "create_method": None,
        "schema": None,
        "list_columns": ["id", "paper_id", "question_number", "question_type", "difficulty", "status"],
        "form_fields": [],
    },
    "mock_tests": {
        # Create form is custom (question_ids list) - see admin/pages.py.
        "label": "Mock Tests",
        "service": mock_test_service,
        "create_method": None,
        "schema": None,
        "list_columns": ["id", "paper_id", "title", "total_questions", "duration", "status"],
        "form_fields": [],
    },
    "blogs": {
        "label": "Blogs",
        "service": blog_service,
        "create_method": "create_blog",
        "schema": BlogCreate,
        "list_columns": ["id", "title", "slug", "category", "status"],
        "form_fields": [
            {"name": "title", "label": "Title", "type": FIELD_TEXT, "required": True},
            {"name": "content", "label": "Content (Markdown)", "type": FIELD_MARKDOWN, "required": True},
            {"name": "category", "label": "Category", "type": FIELD_TEXT, "required": False},
            {"name": "tags", "label": "Tags (comma separated)", "type": FIELD_TEXT, "required": False},
            {
                "name": "thumbnail_file_id",
                "label": "Thumbnail image",
                "type": FIELD_UPLOAD,
                "category": "thumbnails",
                "accept": "image/*",
                "metadata_prefix": "thumbnail",
                "required": False,
            },
            {"name": "meta_title", "label": "SEO meta title (optional)", "type": FIELD_TEXT, "required": False},
            {"name": "meta_description", "label": "SEO meta description (optional)", "type": FIELD_TEXTAREA, "required": False},
            STATUS_FIELD,
        ],
    },
}


def coerce_form_value(field: dict, raw_value: str | None):
    if raw_value is None or raw_value == "":
        return None

    if field["type"] == FIELD_NUMBER:
        return float(raw_value) if "." in raw_value else int(raw_value)

    return raw_value
