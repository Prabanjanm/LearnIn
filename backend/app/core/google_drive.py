import io
from dataclasses import dataclass
from functools import lru_cache

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from app.common.exceptions.exceptions import GoogleDriveConfigError
from app.core.config import settings

SCOPES = ["https://www.googleapis.com/auth/drive"]

FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"

# Maps an upload "category" (what the admin form is uploading) to the
# pre-created Drive folder id for it, so callers never need to know a
# folder id themselves - they just say what kind of file this is.
CATEGORY_FOLDER_SETTINGS = {
    "exams": "GOOGLE_DRIVE_EXAMS_FOLDER_ID",
    "departments": "GOOGLE_DRIVE_DEPARTMENTS_FOLDER_ID",
    "subjects": "GOOGLE_DRIVE_SUBJECTS_FOLDER_ID",
    "papers": "GOOGLE_DRIVE_PAPERS_FOLDER_ID",
    "resources": "GOOGLE_DRIVE_RESOURCES_FOLDER_ID",
    "blogs": "GOOGLE_DRIVE_BLOGS_FOLDER_ID",
    "images": "GOOGLE_DRIVE_IMAGES_FOLDER_ID",
    "question_images": "GOOGLE_DRIVE_QUESTION_IMAGES_FOLDER_ID",
    "thumbnails": "GOOGLE_DRIVE_THUMBNAILS_FOLDER_ID",
    # Untouched source PDFs (and optional answer keys) collected from
    # external sites for the Question Paper Processing workflow. The
    # *generated* standardized PDF goes to "papers" instead, since it ends
    # up serving the same role as Paper.question_file_id.
    "paper_processing_sources": "GOOGLE_DRIVE_PAPER_PROCESSING_FOLDER_ID",
}


def resolve_category_folder_id(category: str | None) -> str | None:
    if category:
        setting_name = CATEGORY_FOLDER_SETTINGS.get(category)
        folder_id = getattr(settings, setting_name, None) if setting_name else None
        if folder_id:
            return folder_id

    return settings.GOOGLE_DRIVE_FOLDER_ID


@dataclass
class DriveUploadResult:
    """
    Only these fields should ever be persisted to PostgreSQL.
    The actual file bytes always stay in Google Drive.
    """

    file_id: str
    mime_type: str
    file_size: int
    name: str


class GoogleDriveClient:
    """
    Thin wrapper around the Google Drive v3 API using a service account.

    Callers never touch raw file bytes in the database - they upload here,
    store the returned file_id/mime_type/file_size, and fetch bytes back
    on demand via download_file().
    """

    def __init__(self):
        self._service = None

    @property
    def service(self):
        if self._service is None:
            self._service = self._build_service()
        return self._service

    def _build_service(self):
        if not (
            settings.GOOGLE_OAUTH_CLIENT_ID
            and settings.GOOGLE_OAUTH_CLIENT_SECRET
            and settings.GOOGLE_OAUTH_REFRESH_TOKEN
        ):
            raise GoogleDriveConfigError(
                "GOOGLE_OAUTH_CLIENT_ID/CLIENT_SECRET/REFRESH_TOKEN are not "
                "set. Run scripts/authorize_google_drive.py once to obtain "
                "them - a bare service account cannot upload file content "
                "(Google returns storageQuotaExceeded)."
            )

        # A refresh token + client credentials is enough; google-api-python-client
        # transparently calls .refresh() to mint an access token on first use.
        credentials = Credentials(
            token=None,
            refresh_token=settings.GOOGLE_OAUTH_REFRESH_TOKEN,
            client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
            client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=SCOPES,
        )

        return build(
            "drive",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )

    def get_or_create_folder(
        self,
        name: str,
        parent_id: str | None = None
    ) -> str:
        parent = parent_id or settings.GOOGLE_DRIVE_FOLDER_ID

        query = (
            f"name = '{self._escape(name)}' "
            f"and mimeType = '{FOLDER_MIME_TYPE}' "
            f"and '{parent}' in parents "
            f"and trashed = false"
        )

        results = self.service.files().list(
            q=query,
            spaces="drive",
            fields="files(id, name)",
        ).execute()

        existing = results.get("files", [])

        if existing:
            return existing[0]["id"]

        metadata = {
            "name": name,
            "mimeType": FOLDER_MIME_TYPE,
            "parents": [parent],
        }

        folder = self.service.files().create(
            body=metadata,
            fields="id",
        ).execute()

        return folder["id"]

    def get_or_create_folder_path(
        self,
        path_parts: list[str],
        root_folder_id: str | None = None
    ) -> str:
        """
        Builds/reuses nested folders, e.g. ["Papers", "GATE", "CSE"].
        """
        parent_id = root_folder_id or settings.GOOGLE_DRIVE_FOLDER_ID

        for part in path_parts:
            parent_id = self.get_or_create_folder(part, parent_id)

        return parent_id

    def upload_file(
        self,
        file_content: bytes,
        filename: str,
        mime_type: str,
        folder_id: str | None = None,
        category: str | None = None,
        public: bool = True,
    ) -> DriveUploadResult:
        """
        folder_id wins if given explicitly; otherwise the pre-created folder
        for `category` (see CATEGORY_FOLDER_SETTINGS) is used, falling back
        to the root folder. Callers never need to know a folder id.
        """
        parent = folder_id or resolve_category_folder_id(category)

        metadata = {
            "name": filename,
            "parents": [parent],
        }

        media = MediaIoBaseUpload(
            io.BytesIO(file_content),
            mimetype=mime_type,
            resumable=False,
        )

        uploaded = self.service.files().create(
            body=metadata,
            media_body=media,
            fields="id, name, mimeType, size",
        ).execute()

        if public:
            self.set_public_permission(uploaded["id"])

        return DriveUploadResult(
            file_id=uploaded["id"],
            mime_type=uploaded.get("mimeType", mime_type),
            file_size=int(uploaded.get("size", len(file_content))),
            name=uploaded.get("name", filename),
        )

    def download_file(self, file_id: str) -> bytes:
        request = self.service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()

        return buffer.getvalue()

    def get_file_metadata(self, file_id: str) -> dict:
        return self.service.files().get(
            fileId=file_id,
            fields="id, name, mimeType, size, webViewLink, webContentLink",
        ).execute()

    def delete_file(self, file_id: str) -> None:
        self.service.files().delete(fileId=file_id).execute()

    def set_public_permission(self, file_id: str) -> None:
        self.service.permissions().create(
            fileId=file_id,
            body={"role": "reader", "type": "anyone"},
        ).execute()

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace("'", "\\'")


@lru_cache
def get_drive_client() -> GoogleDriveClient:
    return GoogleDriveClient()
