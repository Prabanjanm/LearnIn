from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_search_finds_exam_department_subject_and_builds_urls(admin_auth_headers):
    exam = client.post(
        "/api/exams/",
        json={"name": "Search Test Exam Unique", "code": "STEU", "status": "PUBLISHED"},
        headers=admin_auth_headers,
    ).json()

    department = client.post(
        "/api/departments/",
        json={
            "exam_id": exam["id"],
            "name": "Search Test Department",
            "code": "STD",
            "status": "PUBLISHED",
        },
        headers=admin_auth_headers,
    ).json()

    client.post(
        "/api/subjects/",
        json={
            "department_id": department["id"],
            "name": "Search Test Subject",
            "status": "PUBLISHED",
        },
        headers=admin_auth_headers,
    )

    response = client.get("/api/search/", params={"q": "Search Test"})
    assert response.status_code == 200
    body = response.json()

    types = {item["type"] for item in body["results"]}
    assert "exam" in types
    assert "department" in types
    assert "subject" in types

    exam_result = next(item for item in body["results"] if item["type"] == "exam")
    assert exam_result["url"] == f"/{exam['slug']}"

    department_result = next(item for item in body["results"] if item["type"] == "department")
    assert department_result["url"] == f"/{exam['slug']}/{department['slug']}"


def test_search_excludes_draft_exam(admin_auth_headers):
    client.post(
        "/api/exams/",
        json={"name": "Search Draft Omega Exam", "code": "SDOE"},
        headers=admin_auth_headers,
    )

    response = client.get("/api/search/", params={"q": "Search Draft Omega"})
    assert response.status_code == 200
    assert response.json()["results"] == []


def test_search_finds_published_blog_only(admin_auth_headers):
    client.post(
        "/api/blogs/",
        json={"title": "Draft Search Zeta Post", "content": "unpublished", "status": "DRAFT"},
        headers=admin_auth_headers,
    )
    client.post(
        "/api/blogs/",
        json={"title": "Published Search Zeta Post", "content": "live", "status": "PUBLISHED"},
        headers=admin_auth_headers,
    )

    response = client.get("/api/search/", params={"q": "Search Zeta"})
    assert response.status_code == 200

    blog_titles = {
        item["title"] for item in response.json()["results"] if item["type"] == "blog"
    }
    assert "Published Search Zeta Post" in blog_titles
    assert "Draft Search Zeta Post" not in blog_titles
