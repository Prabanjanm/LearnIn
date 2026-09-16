from pathlib import Path
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")


class Settings:

    APP_NAME = os.getenv("APP_NAME", "LearnIn")

    # Defaults to False (production-safe) rather than True: DEBUG also
    # gates traceback leakage (main.py), HSTS (SecurityHeadersMiddleware),
    # and the auth cookies' Secure flag (pages/router.py, admin/pages.py) -
    # a missing env var in a real deployment must fail toward "secure",
    # not toward "debug". Local development sets DEBUG=True explicitly
    # in .env.
    DEBUG = os.getenv("DEBUG", "False") == "True"

    DATABASE_URL = os.getenv("DATABASE_URL")

    SECRET_KEY = os.getenv("SECRET_KEY")

    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

    GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

    # OAuth user credentials (not a service account) - Drive file uploads
    # need a real Google account's storage quota. See scripts/authorize_google_drive.py.
    GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")

    GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")

    GOOGLE_OAUTH_REFRESH_TOKEN = os.getenv("GOOGLE_OAUTH_REFRESH_TOKEN")

    # Scanned-PDF OCR engine for Question Paper Processing (see
    # app/core/gemini_client.py / app/modules/paper_processing/extraction.py).
    # Optional - unset falls back to the Tesseract/pytesseract path.
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    # Pre-created per-category folders (Drive UI), so the admin never has to
    # paste a folder or file link - see core/google_drive.py CATEGORY_FOLDER_SETTINGS.
    GOOGLE_DRIVE_EXAMS_FOLDER_ID = os.getenv("GOOGLE_DRIVE_EXAMS_FOLDER_ID")
    GOOGLE_DRIVE_DEPARTMENTS_FOLDER_ID = os.getenv("GOOGLE_DRIVE_DEPARTMENTS_FOLDER_ID")
    GOOGLE_DRIVE_SUBJECTS_FOLDER_ID = os.getenv("GOOGLE_DRIVE_SUBJECTS_FOLDER_ID")
    GOOGLE_DRIVE_PAPERS_FOLDER_ID = os.getenv("GOOGLE_DRIVE_PAPERS_FOLDER_ID")
    GOOGLE_DRIVE_RESOURCES_FOLDER_ID = os.getenv("GOOGLE_DRIVE_RESOURCES_FOLDER_ID")
    GOOGLE_DRIVE_BLOGS_FOLDER_ID = os.getenv("GOOGLE_DRIVE_BLOGS_FOLDER_ID")
    GOOGLE_DRIVE_IMAGES_FOLDER_ID = os.getenv("GOOGLE_DRIVE_IMAGES_FOLDER_ID")
    GOOGLE_DRIVE_QUESTION_IMAGES_FOLDER_ID = os.getenv("GOOGLE_DRIVE_QUESTION_IMAGES_FOLDER_ID")
    GOOGLE_DRIVE_THUMBNAILS_FOLDER_ID = os.getenv("GOOGLE_DRIVE_THUMBNAILS_FOLDER_ID")
    GOOGLE_DRIVE_PAPER_PROCESSING_FOLDER_ID = os.getenv("GOOGLE_DRIVE_PAPER_PROCESSING_FOLDER_ID")

    # Admin upload size limits, in MB, converted to bytes for upload_policy.py.
    MAX_IMAGE_UPLOAD_BYTES = int(os.getenv("MAX_IMAGE_UPLOAD_MB", "5")) * 1024 * 1024
    MAX_PDF_UPLOAD_BYTES = int(os.getenv("MAX_PDF_UPLOAD_MB", "20")) * 1024 * 1024

    # Outbound transactional email (Brevo SMTP relay).
    SMTP_HOST = os.getenv("SMTP_HOST")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER")
    SMTP_PASS = os.getenv("SMTP_PASS")
    SENDER_EMAIL = os.getenv("SENDER_EMAIL")


settings = Settings()

if not settings.SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY environment variable must be set - the app cannot sign "
        "or verify auth tokens without it."
    )