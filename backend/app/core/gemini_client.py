"""
Thin wrapper around the Gemini vision API, used as the preferred scanned-PDF
OCR engine for Question Paper Processing (see
app/modules/paper_processing/extraction.py) whenever GEMINI_API_KEY is set -
otherwise that module falls back to pytesseract.

Mirrors app/core/google_drive.py's GoogleDriveClient/get_drive_client()
pattern on purpose: a thin class wrapping the real SDK client + an
lru_cache'd module-level accessor, so tests can swap the whole thing out
the same way tests already swap get_drive_client() for a fake.
"""
from functools import lru_cache

from google import genai
from google.genai import types

from app.common.exceptions.exceptions import GeminiConfigError
from app.core.config import settings

# Fast, vision-capable model - OCR-style transcription does not need a
# larger/slower model. Uses Google's own "latest flash" moving alias rather
# than a pinned version number: Gemini model versions are retired on a
# schedule outside this project's control (confirmed directly against the
# live API while building this - "gemini-2.0-flash" had already been
# retired), so pinning one here would need to be revisited on Google's
# timeline, not this codebase's.
GEMINI_OCR_MODEL = "gemini-flash-latest"

# Fixed instruction, not user/admin editable: transcribe only, never
# summarize/translate/complete/correct - same "never invent text" rule the
# rest of this pipeline already holds itself to (see question_parser.py).
GEMINI_OCR_PROMPT = (
    "Transcribe every word of visible text in this exam paper page image, "
    "exactly as written, in natural reading order (top to bottom, left to "
    "right). Do not translate, correct, summarize, describe, or add any "
    "commentary or formatting - output only the transcribed text itself, "
    "nothing else. If the page has no readable text, output nothing."
)


class GeminiClient:
    """
    Callers never touch the underlying google-genai SDK client directly -
    request the OCR text for one page image, get a string back.
    """

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            if not settings.GEMINI_API_KEY:
                raise GeminiConfigError(
                    "GEMINI_API_KEY is not set. Add it to the environment to "
                    "use Gemini for scanned-PDF OCR."
                )
            self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        return self._client

    def extract_text_from_image(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        """
        One page image in, transcribed text out. Any failure - missing key,
        network error, an empty/blocked response - is the caller's problem
        to translate into the pipeline's own exception vocabulary (see
        extraction.py's extract_with_gemini*); this method never swallows
        an error into a silently empty string.
        """
        response = self.client.models.generate_content(
            model=GEMINI_OCR_MODEL,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                GEMINI_OCR_PROMPT,
            ],
        )
        return (response.text or "").strip()


@lru_cache
def get_gemini_client() -> GeminiClient:
    return GeminiClient()
