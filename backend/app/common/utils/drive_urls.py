"""
Google Drive file_ids are the only thing ever persisted - actual sharing
URLs are always derived on demand from the id, never stored. Centralizing
that derivation here means every template/schema builds identical URLs and
a future change (e.g. switching CDN/proxy) only touches one place.
"""


def drive_view_url(file_id: str | None) -> str | None:
    if not file_id:
        return None
    return f"https://drive.google.com/file/d/{file_id}/view"


def drive_download_url(file_id: str | None) -> str | None:
    if not file_id:
        return None
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def drive_thumbnail_url(file_id: str | None, width: int = 400) -> str | None:
    if not file_id:
        return None
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w{width}"
