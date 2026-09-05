from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _build_subject(admin_auth_headers, suffix: str):
    exam = client.post(
        "/api/exams/",
        json={"name": f"Flow Exam {suffix}", "code": f"FE{suffix}"},
        headers=admin_auth_headers,
    ).json()

    department = client.post(
        "/api/departments/",
        json={"exam_id": exam["id"], "name": "Computer Science", "code": f"CSE{suffix}"},
        headers=admin_auth_headers,
    ).json()

    subject = client.post(
        "/api/subjects/",
        json={"department_id": department["id"], "name": "Algorithms"},
        headers=admin_auth_headers,
    ).json()

    return subject


def test_paper_requires_admin_and_rejects_duplicate_year(admin_auth_headers):
    subject = _build_subject(admin_auth_headers, "A")

    unauthorized = client.post(
        "/api/papers/",
        json={
            "subject_id": subject["id"],
            "title": "GATE 2025",
            "year": 2025,
            "question_file_id": "drive-file-1",
        },
    )
    assert unauthorized.status_code == 401

    created = client.post(
        "/api/papers/",
        json={
            "subject_id": subject["id"],
            "title": "GATE 2025",
            "year": 2025,
            "question_file_id": "drive-file-1",
        },
        headers=admin_auth_headers,
    )
    assert created.status_code == 200
    assert created.json()["total_questions"] == 0

    duplicate = client.post(
        "/api/papers/",
        json={
            "subject_id": subject["id"],
            "title": "GATE 2025 Again",
            "year": 2025,
            "question_file_id": "drive-file-2",
        },
        headers=admin_auth_headers,
    )
    assert duplicate.status_code == 409


def test_question_creation_hides_answer_from_public_and_updates_paper_count(admin_auth_headers):
    subject = _build_subject(admin_auth_headers, "B")

    paper = client.post(
        "/api/papers/",
        json={
            "subject_id": subject["id"],
            "title": "GATE 2024",
            "year": 2024,
            "question_file_id": "drive-file-3",
            "status": "PUBLISHED",
        },
        headers=admin_auth_headers,
    ).json()

    question = client.post(
        "/api/questions/",
        json={
            "paper_id": paper["id"],
            "question_number": 1,
            "question_type": "MCQ",
            "question_text": "What is 2 + 2?",
            "correct_answer": "B",
            "explanation": "Basic arithmetic.",
            "difficulty": "EASY",
            "options": [
                {"label": "A", "option_text": "3"},
                {"label": "B", "option_text": "4"},
                {"label": "C", "option_text": "5"},
            ],
            "status": "PUBLISHED",
        },
        headers=admin_auth_headers,
    ).json()
    assert question["correct_answer"] == "B"
    assert len(question["options"]) == 3

    paper_after = client.get(f"/api/papers/{paper['id']}").json()
    assert paper_after["total_questions"] == 1

    public_view = client.get(f"/api/questions/{question['id']}").json()
    assert "correct_answer" not in public_view
    assert "explanation" not in public_view
    assert len(public_view["options"]) == 3

    wrong_check = client.post(
        f"/api/questions/{question['id']}/check",
        json={"answer": "A"},
    ).json()
    assert wrong_check["is_correct"] is False
    assert wrong_check["correct_answer"] == "B"

    right_check = client.post(
        f"/api/questions/{question['id']}/check",
        json={"answer": "b"},
    ).json()
    assert right_check["is_correct"] is True


def test_msq_answer_checking_ignores_order(admin_auth_headers):
    subject = _build_subject(admin_auth_headers, "C")

    paper = client.post(
        "/api/papers/",
        json={
            "subject_id": subject["id"],
            "title": "GATE 2023",
            "year": 2023,
            "question_file_id": "drive-file-4",
        },
        headers=admin_auth_headers,
    ).json()

    question = client.post(
        "/api/questions/",
        json={
            "paper_id": paper["id"],
            "question_number": 1,
            "question_type": "MSQ",
            "question_text": "Which are prime?",
            "correct_answer": "A,C",
            "difficulty": "MEDIUM",
            "options": [
                {"label": "A", "option_text": "2"},
                {"label": "B", "option_text": "4"},
                {"label": "C", "option_text": "3"},
            ],
            "status": "PUBLISHED",
        },
        headers=admin_auth_headers,
    ).json()

    result = client.post(
        f"/api/questions/{question['id']}/check",
        json={"answer": "C, A"},
    ).json()
    assert result["is_correct"] is True


def test_option_duplicate_label_rejected(admin_auth_headers):
    subject = _build_subject(admin_auth_headers, "D")

    paper = client.post(
        "/api/papers/",
        json={
            "subject_id": subject["id"],
            "title": "GATE 2022",
            "year": 2022,
            "question_file_id": "drive-file-5",
        },
        headers=admin_auth_headers,
    ).json()

    question = client.post(
        "/api/questions/",
        json={
            "paper_id": paper["id"],
            "question_number": 1,
            "question_type": "MCQ",
            "question_text": "Sample?",
            "correct_answer": "A",
            "difficulty": "EASY",
            "options": [{"label": "A", "option_text": "First"}],
        },
        headers=admin_auth_headers,
    ).json()

    response = client.post(
        "/api/options/",
        json={"question_id": question["id"], "label": "A", "option_text": "Duplicate"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 409


def test_draft_question_not_reachable_publicly(admin_auth_headers):
    subject = _build_subject(admin_auth_headers, "E")

    paper = client.post(
        "/api/papers/",
        json={
            "subject_id": subject["id"],
            "title": "GATE 2021",
            "year": 2021,
            "question_file_id": "drive-file-6",
            "status": "PUBLISHED",
        },
        headers=admin_auth_headers,
    ).json()

    question = client.post(
        "/api/questions/",
        json={
            "paper_id": paper["id"],
            "question_number": 1,
            "question_type": "MCQ",
            "question_text": "Still in review?",
            "correct_answer": "A",
            "difficulty": "EASY",
            "options": [{"label": "A", "option_text": "Yes"}],
        },
        headers=admin_auth_headers,
    ).json()

    listed = client.get("/api/questions/", params={"paper_id": paper["id"]})
    assert listed.json() == []

    detail = client.get(f"/api/questions/{question['id']}")
    assert detail.status_code == 404

    check = client.post(f"/api/questions/{question['id']}/check", json={"answer": "A"})
    assert check.status_code == 404
