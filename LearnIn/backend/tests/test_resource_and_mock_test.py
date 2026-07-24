from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _build_paper(admin_auth_headers, suffix: str):
    exam = client.post(
        "/api/exams/",
        json={"name": f"Mock Flow Exam {suffix}", "code": f"MFE{suffix}"},
        headers=admin_auth_headers,
    ).json()

    department = client.post(
        "/api/departments/",
        json={"exam_id": exam["id"], "name": "Computer Science", "code": f"CS{suffix}"},
        headers=admin_auth_headers,
    ).json()

    subject = client.post(
        "/api/subjects/",
        json={"department_id": department["id"], "name": "Data Structures"},
        headers=admin_auth_headers,
    ).json()

    paper = client.post(
        "/api/papers/",
        json={
            "subject_id": subject["id"],
            "title": f"GATE {suffix}",
            "year": 2020,
            "question_file_id": f"drive-file-{suffix}",
        },
        headers=admin_auth_headers,
    ).json()

    return subject, paper


def test_resource_create_and_list(admin_auth_headers):
    subject, _paper = _build_paper(admin_auth_headers, "R1")

    unauthorized = client.post(
        "/api/resources/",
        json={
            "subject_id": subject["id"],
            "title": "Formula Sheet",
            "resource_type": "FORMULA_SHEET",
            "google_drive_file_id": "drive-res-1",
        },
    )
    assert unauthorized.status_code == 401

    created = client.post(
        "/api/resources/",
        json={
            "subject_id": subject["id"],
            "title": "Formula Sheet",
            "resource_type": "FORMULA_SHEET",
            "google_drive_file_id": "drive-res-1",
            "status": "PUBLISHED",
        },
        headers=admin_auth_headers,
    )
    assert created.status_code == 200

    listed = client.get("/api/resources/", params={"subject_id": subject["id"]})
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["resource_type"] == "FORMULA_SHEET"


def test_mock_test_full_attempt_flow(admin_auth_headers):
    _subject, paper = _build_paper(admin_auth_headers, "M1")

    q1 = client.post(
        "/api/questions/",
        json={
            "paper_id": paper["id"],
            "question_number": 1,
            "question_type": "MCQ",
            "question_text": "1 + 1 = ?",
            "correct_answer": "B",
            "difficulty": "EASY",
            "marks": 2,
            "negative_marks": 0.5,
            "options": [
                {"label": "A", "option_text": "1"},
                {"label": "B", "option_text": "2"},
            ],
        },
        headers=admin_auth_headers,
    ).json()

    q2 = client.post(
        "/api/questions/",
        json={
            "paper_id": paper["id"],
            "question_number": 2,
            "question_type": "MCQ",
            "question_text": "2 + 2 = ?",
            "correct_answer": "A",
            "difficulty": "EASY",
            "marks": 2,
            "negative_marks": 0.5,
            "options": [
                {"label": "A", "option_text": "4"},
                {"label": "B", "option_text": "5"},
            ],
        },
        headers=admin_auth_headers,
    ).json()

    mock_test = client.post(
        "/api/mock-tests/",
        json={
            "paper_id": paper["id"],
            "title": "Quick Mock",
            "question_ids": [q1["id"], q2["id"]],
            "status": "PUBLISHED",
        },
        headers=admin_auth_headers,
    ).json()
    assert mock_test["total_questions"] == 2

    questions = client.get(f"/api/mock-tests/{mock_test['id']}/questions").json()
    assert len(questions) == 2
    assert "correct_answer" not in questions[0]["question"]

    result = client.post(
        f"/api/mock-tests/{mock_test['id']}/submit",
        json={
            "answers": [
                {"question_id": q1["id"], "answer": "B"},
                {"question_id": q2["id"], "answer": "B"},
            ]
        },
    ).json()

    assert result["correct_count"] == 1
    assert result["incorrect_count"] == 1
    assert result["unanswered_count"] == 0
    assert result["scored_marks"] == 1.5


def test_mock_test_unanswered_question_scores_zero(admin_auth_headers):
    _subject, paper = _build_paper(admin_auth_headers, "M2")

    q1 = client.post(
        "/api/questions/",
        json={
            "paper_id": paper["id"],
            "question_number": 1,
            "question_type": "NAT",
            "question_text": "sqrt(9) = ?",
            "correct_answer": "3",
            "difficulty": "MEDIUM",
        },
        headers=admin_auth_headers,
    ).json()

    mock_test = client.post(
        "/api/mock-tests/",
        json={
            "paper_id": paper["id"],
            "title": "NAT Mock",
            "question_ids": [q1["id"]],
            "status": "PUBLISHED",
        },
        headers=admin_auth_headers,
    ).json()

    result = client.post(
        f"/api/mock-tests/{mock_test['id']}/submit",
        json={"answers": []},
    ).json()

    assert result["unanswered_count"] == 1
    assert result["scored_marks"] == 0


def test_draft_mock_test_and_resource_not_reachable_publicly(admin_auth_headers):
    subject, paper = _build_paper(admin_auth_headers, "M3")

    client.post(
        "/api/resources/",
        json={
            "subject_id": subject["id"],
            "title": "Draft Cheat Sheet",
            "resource_type": "CHEAT_SHEET",
            "google_drive_file_id": "drive-res-draft",
        },
        headers=admin_auth_headers,
    )
    resources = client.get("/api/resources/", params={"subject_id": subject["id"]}).json()
    assert resources == []

    q1 = client.post(
        "/api/questions/",
        json={
            "paper_id": paper["id"],
            "question_number": 1,
            "question_type": "MCQ",
            "question_text": "Draft mock question?",
            "correct_answer": "A",
            "difficulty": "EASY",
            "options": [{"label": "A", "option_text": "Yes"}],
            "status": "PUBLISHED",
        },
        headers=admin_auth_headers,
    ).json()

    mock_test = client.post(
        "/api/mock-tests/",
        json={"paper_id": paper["id"], "title": "Draft Mock", "question_ids": [q1["id"]]},
        headers=admin_auth_headers,
    ).json()

    assert client.get(f"/api/mock-tests/{mock_test['id']}").status_code == 404
    assert client.get(f"/api/mock-tests/{mock_test['id']}/questions").status_code == 404
    assert client.post(
        f"/api/mock-tests/{mock_test['id']}/submit", json={"answers": []}
    ).status_code == 404
