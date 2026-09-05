from pathlib import Path
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")


class Settings:

    APP_NAME = os.getenv("APP_NAME", "LearnIn")

    DEBUG = os.getenv("DEBUG", "True") == "True"

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

    # Admin upload size limits, in MB, converted to bytes for upload_policy.py.
    MAX_IMAGE_UPLOAD_BYTES = int(os.getenv("MAX_IMAGE_UPLOAD_MB", "5")) * 1024 * 1024
    MAX_PDF_UPLOAD_BYTES = int(os.getenv("MAX_PDF_UPLOAD_MB", "20")) * 1024 * 1024


settings = Settings()