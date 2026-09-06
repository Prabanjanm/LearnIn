from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _make_exam(admin_auth_headers, code="UPD"):
    return client.post(
        "/api/exams/",
        json={"name": f"Update Test Exam {code}", "code": code},
        headers=admin_auth_headers,
    ).json()


def test_exam_update_publish_archive_and_delete(admin_auth_headers):
    exam = _make_exam(admin_auth_headers, code="UPD1")

    updated = client.patch(
        f"/api/exams/{exam['id']}",
        json={"description": "Updated description"},
        headers=admin_auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "Updated description"
    assert updated.json()["status"] == "DRAFT"

    published = client.post(f"/api/exams/{exam['id']}/publish", headers=admin_auth_headers)
    assert published.status_code == 200
    assert published.json()["status"] == "PUBLISHED"

    archived = client.post(f"/api/exams/{exam['id']}/archive", headers=admin_auth_headers)
    assert archived.json()["status"] == "ARCHIVED"

    deleted = client.delete(f"/api/exams/{exam['id']}", headers=admin_auth_headers)
    assert deleted.status_code == 204

    missing = client.get(f"/api/exams/{exam['id']}")
    assert missing.status_code == 404


def test_exam_update_and_delete_require_admin():
    exam_id = 999999

    assert client.patch(f"/api/exams/{exam_id}", json={"description": "x"}).status_code == 401
    assert client.delete(f"/api/exams/{exam_id}").status_code == 401


def test_exam_icon_replacement_cleans_up_old_drive_file(admin_auth_headers, monkeypatch):
    deleted_ids = []
    monkeypatch.setattr(
        "app.common.utils.file_tracking.get_drive_client",
        lambda: type("_Client", (), {"delete_file": staticmethod(lambda fid: deleted_ids.append(fid))})(),
    )

    exam = client.post(
        "/api/exams/",
        json={
            "name": "Icon Replacement Exam",
            "code": "ICONREP",
            "icon_file_id": "old-icon-id",
            "icon_mime_type": "image/png",
            "icon_file_size": 100,
            "icon_filename": "old.png",
        },
        headers=admin_auth_headers,
    ).json()

    response = client.patch(
        f"/api/exams/{exam['id']}",
        json={"icon_file_id": "new-icon-id", "icon_mime_type": "image/png", "icon_filename": "new.png"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["icon_file_id"] == "new-icon-id"
    assert deleted_ids == ["old-icon-id"]


def test_exam_icon_not_deleted_if_still_referenced_elsewhere(admin_auth_headers, monkeypatch):
    """A shared file id must never be deleted from Drive while another row
    still references it - is_file_referenced() must block cleanup here."""
    deleted_ids = []
    monkeypatch.setattr(
        "app.common.utils.file_tracking.get_drive_client",
        lambda: type("_Client", (), {"delete_file": staticmethod(lambda fid: deleted_ids.append(fid))})(),
    )

    shared_icon = {
        "icon_file_id": "shared-icon-id",
        "icon_mime_type": "image/png",
        "icon_file_size": 100,
        "icon_filename": "shared.png",
    }

    exam_a = client.post(
        "/api/exams/",
        json={"name": "Shared Icon Exam A", "code": "SHAREDA", **shared_icon},
        headers=admin_auth_headers,
    ).json()
    exam_b = client.post(
        "/api/exams/",
        json={"name": "Shared Icon Exam B", "code": "SHAREDB", **shared_icon},
        headers=admin_auth_headers,
    ).json()

    client.patch(
        f"/api/exams/{exam_a['id']}",
        json={"icon_file_id": "new-icon-id"},
        headers=admin_auth_headers,
    )

    assert deleted_ids == []

    client.delete(f"/api/exams/{exam_a['id']}", headers=admin_auth_headers)
    client.delete(f"/api/exams/{exam_b['id']}", headers=admin_auth_headers)


def test_option_update_and_delete(admin_auth_headers):
    exam = _make_exam(admin_auth_headers, code="OPTEX")
    department = client.post(
        "/api/departments/",
        json={"exam_id": exam["id"], "name": "Opt Dept", "code": "OD"},
        headers=admin_auth_headers,
    ).json()
    subject = client.post(
        "/api/subjects/",
        json={"department_id": department["id"], "name": "Opt Subject"},
        headers=admin_auth_headers,
    ).json()
    paper = client.post(
        "/api/papers/",
        json={"subject_id": subject["id"], "title": "Opt Paper", "year": 2024, "question_file_id": "qf-1"},
        headers=admin_auth_headers,
    ).json()
    question = client.post(
        "/api/questions/",
        json={
            "paper_id": paper["id"],
            "question_number": 1,
            "question_type": "MCQ",
            "question_text": "2+2?",
            "correct_answer": "B",
            "difficulty": "EASY",
            "options": [
                {"label": "A", "option_text": "3"},
                {"label": "B", "option_text": "4"},
            ],
        },
        headers=admin_auth_headers,
    ).json()

    option = question["options"][0]

    updated = client.patch(
        f"/api/options/{option['id']}",
        json={"option_text": "Three"},
        headers=admin_auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["option_text"] == "Three"

    deleted = client.delete(f"/api/options/{option['id']}", headers=admin_auth_headers)
    assert deleted.status_code == 204


def test_question_update_replaces_options_transactionally(admin_auth_headers):
    exam = _make_exam(admin_auth_headers, code="QUPD")
    department = client.post(
        "/api/departments/",
        json={"exam_id": exam["id"], "name": "Q Dept", "code": "QD"},
        headers=admin_auth_headers,
    ).json()
    subject = client.post(
        "/api/subjects/",
        json={"department_id": department["id"], "name": "Q Subject"},
        headers=admin_auth_headers,
    ).json()
    paper = client.post(
        "/api/papers/",
        json={"subject_id": subject["id"], "title": "Q Paper", "year": 2024, "question_file_id": "qf-2"},
        headers=admin_auth_headers,
    ).json()
    question = client.post(
        "/api/questions/",
        json={
            "paper_id": paper["id"],
            "question_number": 1,
            "question_type": "MCQ",
            "question_text": "Original text",
            "correct_answer": "A",
            "difficulty": "EASY",
            "options": [
                {"label": "A", "option_text": "One"},
                {"label": "B", "option_text": "Two"},
            ],
        },
        headers=admin_auth_headers,
    ).json()

    updated = client.patch(
        f"/api/questions/{question['id']}",
        json={
            "question_text": "Updated text",
            "options": [
                {"label": "A", "option_text": "New One"},
                {"label": "B", "option_text": "New Two"},
                {"label": "C", "option_text": "New Three"},
            ],
        },
        headers=admin_auth_headers,
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["question_text"] == "Updated text"
    assert len(body["options"]) == 3
    assert {opt["option_text"] for opt in body["options"]} == {"New One", "New Two", "New Three"}


def test_mock_test_question_add_remove_and_reorder(admin_auth_headers):
    exam = _make_exam(admin_auth_headers, code="MTQ")
    department = client.post(
        "/api/departments/",
        json={"exam_id": exam["id"], "name": "MTQ Dept", "code": "MD"},
        headers=admin_auth_headers,
    ).json()
    subject = client.post(
        "/api/subjects/",
        json={"department_id": department["id"], "name": "MTQ Subject"},
        headers=admin_auth_headers,
    ).json()
    paper = client.post(
        "/api/papers/",
        json={"subject_id": subject["id"], "title": "MTQ Paper", "year": 2024, "question_file_id": "qf-3"},
        headers=admin_auth_headers,
    ).json()

    question_ids = []
    for i in range(3):
        question = client.post(
            "/api/questions/",
            json={
                "paper_id": paper["id"],
                "question_number": i + 1,
                "question_type": "MCQ",
                "question_text": f"Question {i}",
                "correct_answer": "A",
                "difficulty": "EASY",
                "options": [{"label": "A", "option_text": "x"}],
            },
            headers=admin_auth_headers,
        ).json()
        question_ids.append(question["id"])

    mock_test = client.post(
        "/api/mock-tests/",
        json={"paper_id": paper["id"], "title": "MTQ Test", "question_ids": question_ids[:2]},
        headers=admin_auth_headers,
    ).json()
    assert mock_test["total_questions"] == 2

    add_response = client.post(
        "/api/mock-test-questions/",
        json={"mock_test_id": mock_test["id"], "question_id": question_ids[2]},
        headers=admin_auth_headers,
    )
    assert add_response.status_code == 200
    link_id = add_response.json()["id"]

    duplicate = client.post(
        "/api/mock-test-questions/",
        json={"mock_test_id": mock_test["id"], "question_id": question_ids[2]},
        headers=admin_auth_headers,
    )
    assert duplicate.status_code == 409

    listed = client.get(
        "/api/mock-test-questions/",
        params={"mock_test_id": mock_test["id"]},
        headers=admin_auth_headers,
    )
    assert len(listed.json()) == 3

    reordered = client.put(
        f"/api/mock-tests/{mock_test['id']}/questions/reorder",
        json={"question_ids": [question_ids[2], question_ids[0], question_ids[1]]},
        headers=admin_auth_headers,
    )
    assert reordered.status_code == 200
    orders = {item["question"]["id"]: item["question_order"] for item in reordered.json()}
    assert orders[question_ids[2]] == 1
    assert orders[question_ids[0]] == 2
    assert orders[question_ids[1]] == 3

    removed = client.delete(f"/api/mock-test-questions/{link_id}", headers=admin_auth_headers)
    assert removed.status_code == 204

    final_test = client.patch(
        f"/api/mock-tests/{mock_test['id']}",
        json={"title": "MTQ Test Updated"},
        headers=admin_auth_headers,
    )
    assert final_test.json()["total_questions"] == 2


def test_paper_bulk_publish_and_archive_from_list_page(admin_auth_headers):
    exam = _make_exam(admin_auth_headers, code="BULKPAPER")
    department = client.post(
        "/api/departments/",
        json={"exam_id": exam["id"], "name": "Bulk Paper Dept", "code": "BPD"},
        headers=admin_auth_headers,
    ).json()
    subject = client.post(
        "/api/subjects/",
        json={"department_id": department["id"], "name": "Bulk Paper Subject"},
        headers=admin_auth_headers,
    ).json()
    paper = client.post(
        "/api/papers/",
        json={"subject_id": subject["id"], "title": "Bulk Paper", "year": 2027, "question_file_id": "qf-bulk"},
        headers=admin_auth_headers,
    ).json()

    published = client.post(
        "/admin/manage/papers/bulk",
        data={"action": "PUBLISHED", "ids": [str(paper["id"])]},
        headers=admin_auth_headers,
        follow_redirects=False,
    )
    assert published.status_code == 303
    assert "bulk_failed" not in published.headers["location"]
    assert client.get(f"/api/papers/{paper['id']}").json()["status"] == "PUBLISHED"

    archived = client.post(
        "/admin/manage/papers/bulk",
        data={"action": "ARCHIVED", "ids": [str(paper["id"])]},
        headers=admin_auth_headers,
        follow_redirects=False,
    )
    assert archived.status_code == 303


def test_paper_bulk_delete_cleans_up_drive_files(admin_auth_headers, monkeypatch):
    deleted_ids = []
    monkeypatch.setattr(
        "app.common.utils.file_tracking.get_drive_client",
        lambda: type("_Client", (), {"delete_file": staticmethod(lambda fid: deleted_ids.append(fid))})(),
    )

    exam = _make_exam(admin_auth_headers, code="BULKDEL")
    department = client.post(
        "/api/departments/",
        json={"exam_id": exam["id"], "name": "Bulk Del Dept", "code": "BDD"},
        headers=admin_auth_headers,
    ).json()
    subject = client.post(
        "/api/subjects/",
        json={"department_id": department["id"], "name": "Bulk Del Subject"},
        headers=admin_auth_headers,
    ).json()
    paper = client.post(
        "/api/papers/",
        json={"subject_id": subject["id"], "title": "Bulk Del Paper", "year": 2028, "question_file_id": "qf-bulkdel"},
        headers=admin_auth_headers,
    ).json()

    response = client.post(
        "/admin/manage/papers/bulk",
        data={"action": "delete", "ids": [str(paper["id"])]},
        headers=admin_auth_headers,
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert deleted_ids == ["qf-bulkdel"]
    assert client.get(f"/api/papers/{paper['id']}").status_code == 404


def test_bulk_action_unexpected_error_is_caught_not_500(admin_auth_headers, monkeypatch):
    """
    Regression test: entity_bulk_action previously had no exception handling
    at all - any failure on any selected row (a delete blocked by a foreign
    key, a bad enum value, anything) surfaced as a raw 500 and aborted the
    whole batch. It must now catch, log, roll back, and keep going.
    """
    exam = _make_exam(admin_auth_headers, code="BULKERR")

    def _boom(db, obj):
        raise RuntimeError("simulated unexpected failure")

    monkeypatch.setattr("app.modules.exam.service.exam_service.update", _boom)

    response = client.post(
        "/admin/manage/exams/bulk",
        data={"action": "PUBLISHED", "ids": [str(exam["id"])]},
        headers=admin_auth_headers,
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "bulk_failed=1" in response.headers["location"]


def test_bulk_delete_on_exam_archives_instead_of_hard_deleting(admin_auth_headers, db_session):
    """
    Exam/Department/Subject are the academic hierarchy - a real DELETE would
    cascade away every child Paper/Question/Option beneath them. The admin
    bulk "delete" action must archive these three entities instead of
    removing the row, so the data survives and can be restored via the
    ARCHIVED -> DRAFT/PUBLISHED bulk action.
    """
    from app.modules.exam.model import Exam

    exam = _make_exam(admin_auth_headers, code="SOFTDEL")

    response = client.post(
        "/admin/manage/exams/bulk",
        data={"action": "delete", "ids": [str(exam["id"])]},
        headers=admin_auth_headers,
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "bulk_failed" not in response.headers["location"]

    row = db_session.query(Exam).filter(Exam.id == exam["id"]).first()
    assert row is not None, "row must still exist - only archived, never hard-deleted"
    assert row.status.value == "ARCHIVED"


def test_resource_update_replaces_file_and_cleans_up_old(admin_auth_headers, monkeypatch):
    deleted_ids = []
    monkeypatch.setattr(
        "app.common.utils.file_tracking.get_drive_client",
        lambda: type("_Client", (), {"delete_file": staticmethod(lambda fid: deleted_ids.append(fid))})(),
    )

    exam = _make_exam(admin_auth_headers, code="RES")
    department = client.post(
        "/api/departments/",
        json={"exam_id": exam["id"], "name": "Res Dept", "code": "RD"},
        headers=admin_auth_headers,
    ).json()
    subject = client.post(
        "/api/subjects/",
        json={"department_id": department["id"], "name": "Res Subject"},
        headers=admin_auth_headers,
    ).json()
    resource = client.post(
        "/api/resources/",
        json={
            "subject_id": subject["id"],
            "title": "Formula Sheet",
            "resource_type": "FORMULA_SHEET",
            "google_drive_file_id": "old-res-file",
        },
        headers=admin_auth_headers,
    ).json()

    updated = client.patch(
        f"/api/resources/{resource['id']}",
        json={"google_drive_file_id": "new-res-file"},
        headers=admin_auth_headers,
    )
    assert updated.status_code == 200
    assert deleted_ids == ["old-res-file"]

    deleted = client.delete(f"/api/resources/{resource['id']}", headers=admin_auth_headers)
    assert deleted.status_code == 204
    assert "new-res-file" in deleted_ids
