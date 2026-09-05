from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_and_fetch_exam(admin_auth_headers):
    response = client.post(
        "/api/exams/",
        json={"name": "Graduate Aptitude Test", "code": "GATE"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "GATE"
    assert body["slug"] == "graduate-aptitude-test"


def test_create_exam_requires_admin():
    response = client.post(
        "/api/exams/",
        json={"name": "Unauthorized Exam", "code": "UNAUTH"},
    )
    assert response.status_code == 401


def test_duplicate_exam_code_conflicts(admin_auth_headers):
    client.post(
        "/api/exams/",
        json={"name": "Common Admission Test", "code": "CAT"},
        headers=admin_auth_headers,
    )

    response = client.post(
        "/api/exams/",
        json={"name": "Common Admission Test Again", "code": "CAT"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 409


def test_department_subject_hierarchy(admin_auth_headers):
    exam = client.post(
        "/api/exams/",
        json={"name": "Test Exam Hierarchy", "code": "TEH"},
        headers=admin_auth_headers,
    ).json()

    department = client.post(
        "/api/departments/",
        json={"exam_id": exam["id"], "name": "Computer Science", "code": "CSE"},
        headers=admin_auth_headers,
    ).json()
    assert department["slug"] == "computer-science"

    subject = client.post(
        "/api/subjects/",
        json={"department_id": department["id"], "name": "Algorithms", "status": "PUBLISHED"},
        headers=admin_auth_headers,
    ).json()
    assert subject["slug"] == "algorithms"

    listed = client.get(
        "/api/subjects/",
        params={"department_id": department["id"]},
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == subject["id"]


def test_duplicate_department_code_conflicts(admin_auth_headers):
    exam = client.post(
        "/api/exams/",
        json={"name": "Duplicate Dept Exam", "code": "DDE"},
        headers=admin_auth_headers,
    ).json()

    client.post(
        "/api/departments/",
        json={"exam_id": exam["id"], "name": "Mechanical", "code": "ME"},
        headers=admin_auth_headers,
    )

    response = client.post(
        "/api/departments/",
        json={"exam_id": exam["id"], "name": "Mechanical Again", "code": "ME"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 409
