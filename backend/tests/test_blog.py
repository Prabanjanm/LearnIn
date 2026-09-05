from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_blog_create_requires_admin():
    response = client.post(
        "/api/blogs/",
        json={"title": "How to crack GATE", "content": "Some tips."},
    )
    assert response.status_code == 401


def test_blog_create_and_public_listing_pagination(admin_auth_headers):
    for i in range(3):
        client.post(
            "/api/blogs/",
            json={
                "title": f"GATE Prep Tips {i}",
                "content": "Content body.",
                "category": "exam-tips",
                "status": "PUBLISHED",
            },
            headers=admin_auth_headers,
        )

    listed = client.get(
        "/api/blogs/",
        params={"category": "exam-tips", "page": 1, "page_size": 2},
    )
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] >= 3
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2


def test_blog_duplicate_slug_conflicts(admin_auth_headers):
    client.post(
        "/api/blogs/",
        json={"title": "Duplicate Blog Post", "content": "Body"},
        headers=admin_auth_headers,
    )

    response = client.post(
        "/api/blogs/",
        json={"title": "Duplicate Blog Post", "content": "Body again"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 409


def test_blog_fetch_by_slug_returns_full_content(admin_auth_headers):
    client.post(
        "/api/blogs/",
        json={"title": "Fetch Me By Slug", "content": "Full content here", "status": "PUBLISHED"},
        headers=admin_auth_headers,
    )

    response = client.get("/api/blogs/fetch-me-by-slug")
    assert response.status_code == 200
    assert response.json()["content"] == "Full content here"


def test_blog_draft_not_reachable_by_slug(admin_auth_headers):
    client.post(
        "/api/blogs/",
        json={"title": "Still A Draft Post", "content": "Not ready yet"},
        headers=admin_auth_headers,
    )

    response = client.get("/api/blogs/still-a-draft-post")
    assert response.status_code == 404
