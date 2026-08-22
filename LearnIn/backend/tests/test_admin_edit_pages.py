import json

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_exam_edit_form_renders_prefilled(admin_auth_headers):
    exam = client.post(
        "/api/exams/",
        json={"name": "Edit Page Exam", "code": "EDITPAGE", "description": "Original desc"},
        headers=admin_auth_headers,
    ).json()

    response = client.get(f"/admin/manage/exams/{exam['id']}/edit", headers=admin_auth_headers)
    assert response.status_code == 200
    assert "Original desc" in response.text
    assert f'action="/admin/manage/exams/{exam["id"]}/edit"' in response.text


def test_exam_edit_form_embed_mode_renders_bare_drawer_page(admin_auth_headers):
    exam = client.post(
        "/api/exams/",
        json={"name": "Embed Edit Exam", "code": "EMBEDEDIT"},
        headers=admin_auth_headers,
    ).json()

    response = client.get(
        f"/admin/manage/exams/{exam['id']}/edit", params={"embed": "true"}, headers=admin_auth_headers
    )
    assert response.status_code == 200
    assert "admin-drawer-body" in response.text
    assert "admin-sidebar" not in response.text
    assert 'name="embed" value="1"' in response.text


def test_exam_edit_submit_embed_mode_returns_postmessage_page_not_redirect(admin_auth_headers):
    exam = client.post(
        "/api/exams/",
        json={"name": "Embed Submit Exam", "code": "EMBEDSUBMIT"},
        headers=admin_auth_headers,
    ).json()

    response = client.post(
        f"/admin/manage/exams/{exam['id']}/edit",
        data={
            "name": "Embed Submit Exam",
            "code": "EMBEDSUBMIT",
            "description": "Saved from drawer",
            "display_order": "0",
            "status": "PUBLISHED",
            "embed": "1",
        },
        headers=admin_auth_headers,
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert "admin-drawer-saved" in response.text

    fetched = client.get(f"/api/exams/{exam['id']}")
    assert fetched.json()["description"] == "Saved from drawer"


def test_exam_edit_submit_updates_via_html_form(admin_auth_headers):
    exam = client.post(
        "/api/exams/",
        json={"name": "Edit Submit Exam", "code": "EDITSUBMIT"},
        headers=admin_auth_headers,
    ).json()

    response = client.post(
        f"/admin/manage/exams/{exam['id']}/edit",
        data={
            "name": "Edit Submit Exam",
            "code": "EDITSUBMIT",
            "description": "Updated via HTML form",
            "display_order": "0",
            "status": "PUBLISHED",
        },
        headers=admin_auth_headers,
        follow_redirects=False,
    )
    assert response.status_code == 303

    fetched = client.get(f"/api/exams/{exam['id']}").json()
    assert fetched["description"] == "Updated via HTML form"
    assert fetched["status"] == "PUBLISHED"


def test_list_page_has_edit_links_and_filter_inputs(admin_auth_headers):
    exam = client.post(
        "/api/exams/",
        json={"name": "List Page Exam", "code": "LISTPAGE"},
        headers=admin_auth_headers,
    ).json()

    response = client.get("/admin/manage/exams", headers=admin_auth_headers)
    assert response.status_code == 200
    assert f"/admin/manage/exams/{exam['id']}/edit" in response.text
    assert "data-col-filter=" in response.text
    assert "data-sortable" in response.text


def test_list_page_pagination_controls_render_and_page_size_works(admin_auth_headers):
    for i in range(3):
        client.post(
            "/api/exams/",
            json={"name": f"Pagination Exam {i}", "code": f"PAGE{i}"},
            headers=admin_auth_headers,
        )

    response = client.get(
        "/admin/manage/exams", params={"page_size": 10}, headers=admin_auth_headers
    )
    assert response.status_code == 200
    assert "data-page-size-select" in response.text
    assert "of " in response.text
    assert "data-page-jump-input" in response.text

    small_page = client.get(
        "/admin/manage/exams", params={"page_size": 10, "page": 1}, headers=admin_auth_headers
    )
    assert small_page.status_code == 200

    invalid_size = client.get(
        "/admin/manage/exams", params={"page_size": 9999}, headers=admin_auth_headers
    )
    assert invalid_size.status_code == 200


def test_paper_edit_form_prefills_valid_json_for_required_file_field(admin_auth_headers):
    """
    Regression test: the upload widget's pre-filled hidden input used to be
    rendered as value="{{ json|tojson }}" inside a DOUBLE-quoted HTML
    attribute. tojson does not escape the JSON's own structural double
    quotes (it only escapes for <script> embedding), so a real browser
    would parse value="{"file_id": ...}" as truncated at the first internal
    quote - corrupting the field. On submit this nulled out a required,
    non-nullable column (Paper.question_file_id) and made every edit that
    didn't re-upload the file fail. This asserts the hidden input is
    single-quoted and contains complete, valid, correctly-keyed JSON.
    """
    import re

    exam = client.post(
        "/api/exams/", json={"name": "Paper Prefill Exam", "code": "PAPERPREFILL"}, headers=admin_auth_headers
    ).json()
    department = client.post(
        "/api/departments/",
        json={"exam_id": exam["id"], "name": "Paper Prefill Dept", "code": "PPD"},
        headers=admin_auth_headers,
    ).json()
    subject = client.post(
        "/api/subjects/",
        json={"department_id": department["id"], "name": "Paper Prefill Subject"},
        headers=admin_auth_headers,
    ).json()
    paper = client.post(
        "/api/papers/",
        json={
            "subject_id": subject["id"],
            "title": "Paper Prefill Paper",
            "year": 2030,
            "question_file_id": "qf-prefill",
            "question_file_mime_type": "application/pdf",
            "question_filename": "prefill.pdf",
        },
        headers=admin_auth_headers,
    ).json()

    form = client.get(f"/admin/manage/papers/{paper['id']}/edit", headers=admin_auth_headers)
    assert form.status_code == 200

    match = re.search(r'name="question_file_id"\s*data-upload-hidden\s*value=\'([^\']*)\'', form.text)
    assert match, "expected a single-quoted, complete hidden input value"

    parsed = json.loads(match.group(1))
    assert parsed["file_id"] == "qf-prefill"
    assert parsed["filename"] == "prefill.pdf"


def test_paper_edit_changing_only_status_does_not_null_required_file_field(admin_auth_headers):
    """
    End-to-end version of the regression above: submitting the edit form
    with the file field's pre-filled JSON (exactly as a real browser would
    send it) and only changing status must not touch question_file_id.
    """
    exam = client.post(
        "/api/exams/", json={"name": "Paper Status Exam", "code": "PAPERSTATUS"}, headers=admin_auth_headers
    ).json()
    department = client.post(
        "/api/departments/",
        json={"exam_id": exam["id"], "name": "Paper Status Dept", "code": "PSD"},
        headers=admin_auth_headers,
    ).json()
    subject = client.post(
        "/api/subjects/",
        json={"department_id": department["id"], "name": "Paper Status Subject"},
        headers=admin_auth_headers,
    ).json()
    paper = client.post(
        "/api/papers/",
        json={
            "subject_id": subject["id"],
            "title": "Paper Status Paper",
            "year": 2031,
            "question_file_id": "qf-status",
        },
        headers=admin_auth_headers,
    ).json()

    submit = client.post(
        f"/admin/manage/papers/{paper['id']}/edit",
        data={
            "subject_id": str(subject["id"]),
            "title": "Paper Status Paper",
            "year": "2031",
            "question_file_id": json.dumps({"file_id": "qf-status", "mime_type": None, "file_size": None, "filename": None}),
            "answer_file_id": "",
            "duration": "",
            "status": "PUBLISHED",
        },
        headers=admin_auth_headers,
        follow_redirects=False,
    )
    assert submit.status_code == 303

    fetched = client.get(f"/api/papers/{paper['id']}")
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["question_file_id"] == "qf-status"
    assert body["status"] == "PUBLISHED"


def test_list_page_queues_success_toast_from_query_param(admin_auth_headers):
    response = client.get("/admin/manage/exams", params={"success": "1"}, headers=admin_auth_headers)
    assert response.status_code == 200
    assert "data-toast-stack" in response.text
    assert "__adminFlashToasts" in response.text
    assert "Saved successfully." in response.text


def test_list_page_queues_error_toast_on_bulk_failed(admin_auth_headers):
    response = client.get("/admin/manage/exams", params={"bulk_failed": "2"}, headers=admin_auth_headers)
    assert response.status_code == 200
    assert 'variant: "error"' in response.text
    assert "2 of the selected items could not be updated" in response.text


def test_exam_view_drawer_renders_readonly_details_with_download_link(admin_auth_headers):
    exam = client.post(
        "/api/exams/",
        json={
            "name": "View Drawer Exam",
            "code": "VIEWDRAWER",
            "icon_file_id": "view-icon-file-id",
            "icon_mime_type": "image/png",
            "icon_file_size": 1234,
            "icon_filename": "view-icon.png",
        },
        headers=admin_auth_headers,
    ).json()

    response = client.get(f"/admin/manage/exams/{exam['id']}/view", headers=admin_auth_headers)
    assert response.status_code == 200
    assert "View Drawer Exam" in response.text
    assert "view-icon.png" in response.text
    assert "/api/admin/files/view-icon-file-id/download" in response.text
    # Read-only: no <form> action posting anywhere, unlike the edit drawer.
    assert "<form" not in response.text


def test_list_page_has_view_icon_button(admin_auth_headers):
    exam = client.post(
        "/api/exams/",
        json={"name": "View Icon Exam", "code": "VIEWICON"},
        headers=admin_auth_headers,
    ).json()

    response = client.get("/admin/manage/exams", headers=admin_auth_headers)
    assert response.status_code == 200
    assert f"/admin/manage/exams/{exam['id']}/view" in response.text


def test_admin_file_download_proxies_drive_bytes(admin_auth_headers, monkeypatch):
    class _FakeDriveClient:
        def get_file_metadata(self, file_id):
            return {"name": "question-paper.pdf", "mimeType": "application/pdf"}

        def download_file(self, file_id):
            return b"%PDF-1.4 fake content"

    monkeypatch.setattr("app.modules.admin.router.get_drive_client", lambda: _FakeDriveClient())

    response = client.get("/api/admin/files/some-file-id/download", headers=admin_auth_headers)
    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 fake content"
    assert response.headers["content-type"] == "application/pdf"
    assert 'attachment; filename="question-paper.pdf"' in response.headers["content-disposition"]


def test_admin_file_download_skips_metadata_round_trip_when_hinted(admin_auth_headers, monkeypatch):
    metadata_calls = []

    class _FakeDriveClient:
        def get_file_metadata(self, file_id):
            metadata_calls.append(file_id)
            return {"name": "should-not-be-used.pdf", "mimeType": "application/pdf"}

        def download_file(self, file_id):
            return b"fast content"

    monkeypatch.setattr("app.modules.admin.router.get_drive_client", lambda: _FakeDriveClient())

    response = client.get(
        "/api/admin/files/some-file-id/download",
        params={"filename": "known.pdf", "mime_type": "application/pdf"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    assert response.content == b"fast content"
    assert 'filename="known.pdf"' in response.headers["content-disposition"]
    assert metadata_calls == []


def test_admin_file_download_requires_admin():
    response = client.get("/api/admin/files/some-file-id/download")
    assert response.status_code == 401


def test_admin_file_download_returns_502_on_drive_failure(admin_auth_headers, monkeypatch):
    class _FailingDriveClient:
        def get_file_metadata(self, file_id):
            raise RuntimeError("boom")

    monkeypatch.setattr("app.modules.admin.router.get_drive_client", lambda: _FailingDriveClient())

    response = client.get("/api/admin/files/some-file-id/download", headers=admin_auth_headers)
    assert response.status_code == 502


def test_question_edit_form_renders_and_submit_updates(admin_auth_headers):
    exam = client.post(
        "/api/exams/", json={"name": "QEdit Exam", "code": "QEDIT"}, headers=admin_auth_headers
    ).json()
    department = client.post(
        "/api/departments/",
        json={"exam_id": exam["id"], "name": "QEdit Dept", "code": "QED"},
        headers=admin_auth_headers,
    ).json()
    subject = client.post(
        "/api/subjects/",
        json={"department_id": department["id"], "name": "QEdit Subject"},
        headers=admin_auth_headers,
    ).json()
    paper = client.post(
        "/api/papers/",
        json={"subject_id": subject["id"], "title": "QEdit Paper", "year": 2024, "question_file_id": "qf-edit"},
        headers=admin_auth_headers,
    ).json()
    question = client.post(
        "/api/questions/",
        json={
            "paper_id": paper["id"],
            "question_number": 1,
            "question_type": "MCQ",
            "question_text": "Original question text",
            "correct_answer": "A",
            "difficulty": "EASY",
            "options": [{"label": "A", "option_text": "Alpha"}],
        },
        headers=admin_auth_headers,
    ).json()

    form_page = client.get(f"/admin/manage/questions/{question['id']}/edit", headers=admin_auth_headers)
    assert form_page.status_code == 200
    assert "Original question text" in form_page.text
    assert "Alpha" in form_page.text

    submit = client.post(
        f"/admin/manage/questions/{question['id']}/edit",
        data={
            "question_number": "1",
            "question_type": "MCQ",
            "difficulty": "EASY",
            "question_text": "Updated question text",
            "marks": "1",
            "negative_marks": "0",
            "correct_answer": "A",
            "option_a_text": "Alpha Updated",
            "status": "DRAFT",
        },
        headers=admin_auth_headers,
        follow_redirects=False,
    )
    assert submit.status_code == 303

    updated = client.get(f"/api/questions/{question['id']}/admin", headers=admin_auth_headers).json()
    assert updated["question_text"] == "Updated question text"
    assert updated["options"][0]["option_text"] == "Alpha Updated"
