from unittest.mock import MagicMock

import pytest

from app.common.exceptions.exceptions import GoogleDriveConfigError
from app.core.google_drive import GoogleDriveClient


def test_missing_oauth_config_raises_config_error():
    client = GoogleDriveClient()

    with pytest.raises(GoogleDriveConfigError):
        client.service


def _client_with_mock_service():
    client = GoogleDriveClient()
    mock_service = MagicMock()
    client._service = mock_service
    return client, mock_service


def test_get_or_create_folder_reuses_existing_folder():
    client, mock_service = _client_with_mock_service()

    mock_service.files.return_value.list.return_value.execute.return_value = {
        "files": [{"id": "existing-folder-id", "name": "GATE"}]
    }

    folder_id = client.get_or_create_folder("GATE", parent_id="root-id")

    assert folder_id == "existing-folder-id"
    mock_service.files.return_value.create.assert_not_called()


def test_get_or_create_folder_creates_when_missing():
    client, mock_service = _client_with_mock_service()

    mock_service.files.return_value.list.return_value.execute.return_value = {
        "files": []
    }
    mock_service.files.return_value.create.return_value.execute.return_value = {
        "id": "new-folder-id"
    }

    folder_id = client.get_or_create_folder("CSE", parent_id="root-id")

    assert folder_id == "new-folder-id"


def test_get_or_create_folder_path_walks_each_segment():
    client, mock_service = _client_with_mock_service()

    mock_service.files.return_value.list.return_value.execute.return_value = {
        "files": []
    }
    mock_service.files.return_value.create.return_value.execute.side_effect = [
        {"id": "papers-id"},
        {"id": "gate-id"},
        {"id": "cse-id"},
    ]

    final_id = client.get_or_create_folder_path(
        ["Papers", "GATE", "CSE"],
        root_folder_id="root-id",
    )

    assert final_id == "cse-id"
    assert mock_service.files.return_value.create.call_count == 3


def test_upload_file_returns_only_metadata_fields():
    client, mock_service = _client_with_mock_service()

    mock_service.files.return_value.create.return_value.execute.return_value = {
        "id": "file-123",
        "name": "paper.pdf",
        "mimeType": "application/pdf",
        "size": "2048",
    }

    result = client.upload_file(
        b"%PDF-1.4 ...",
        "paper.pdf",
        "application/pdf",
        folder_id="folder-1",
        public=False,
    )

    assert result.file_id == "file-123"
    assert result.mime_type == "application/pdf"
    assert result.file_size == 2048
    mock_service.permissions.assert_not_called()


def test_upload_file_sets_public_permission_by_default():
    client, mock_service = _client_with_mock_service()

    mock_service.files.return_value.create.return_value.execute.return_value = {
        "id": "file-456",
        "name": "notes.pdf",
        "mimeType": "application/pdf",
        "size": "512",
    }

    client.upload_file(b"data", "notes.pdf", "application/pdf", folder_id="folder-1")

    mock_service.permissions.return_value.create.assert_called_once_with(
        fileId="file-456",
        body={"role": "reader", "type": "anyone"},
    )
