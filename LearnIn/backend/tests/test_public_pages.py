from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _build_full_hierarchy(admin_auth_headers, suffix: str):
    exam = client.post(
        "/api/exams/",
        json={"name": f"Public Page Exam {suffix}", "code": f"PPE{suffix}", "status": "PUBLISHED"},
        headers=admin_auth_headers,
    ).json()

    department = client.post(
        "/api/departments/",
        json={
            "exam_id": exam["id"],
            "name": "Civil Engineering",
            "code": f"CE{suffix}",
            "status": "PUBLISHED",
        },
        headers=admin_auth_headers,
    ).json()

    subject = client.post(
        "/api/subjects/",
        json={
            "department_id": department["id"],
            "name": "Structural Analysis",
            "status": "PUBLISHED",
        },
        headers=admin_auth_headers,
    ).json()

    paper = client.post(
        "/api/papers/",
        json={
            "subject_id": subject["id"],
            "title": f"GATE {suffix}",
            "year": 2021,
            "question_file_id": "drive-file-x",
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
            "question_text": "Sample structural question?",
            "correct_answer": "A",
            "difficulty": "EASY",
            "options": [
                {"label": "A", "option_text": "Correct"},
                {"label": "B", "option_text": "Wrong"},
            ],
            "status": "PUBLISHED",
        },
        headers=admin_auth_headers,
    ).json()

    mock_test = client.post(
        "/api/mock-tests/",
        json={
            "paper_id": paper["id"],
            "title": "Full Mock",
            "question_ids": [question["id"]],
            "status": "PUBLISHED",
        },
        headers=admin_auth_headers,
    ).json()

    return exam, department, subject, paper, mock_test


def test_exam_department_subject_paper_pages_render(admin_auth_headers):
    exam, department, subject, paper, mock_test = _build_full_hierarchy(admin_auth_headers, "A")

    exam_page = client.get(f"/{exam['slug']}")
    assert exam_page.status_code == 200
    assert department["name"] in exam_page.text
    assert 'class="container breadcrumbs"' in exam_page.text
    assert 'class="entity-card"' in exam_page.text

    dept_page = client.get(f"/{exam['slug']}/{department['slug']}")
    assert dept_page.status_code == 200
    assert subject["name"] in dept_page.text
    assert f'<a href="/{exam["slug"]}">{exam["name"]}</a>' in dept_page.text

    subject_page = client.get(f"/{exam['slug']}/{department['slug']}/{subject['slug']}")
    assert subject_page.status_code == 200
    assert str(paper["year"]) in subject_page.text

    paper_page = client.get(f"/{exam['slug']}/{department['slug']}/{subject['slug']}/{paper['year']}")
    assert paper_page.status_code == 200
    assert "Practice Online" in paper_page.text
    assert mock_test["title"] in paper_page.text

    practice_page = client.get(
        f"/{exam['slug']}/{department['slug']}/{subject['slug']}/{paper['year']}/practice"
    )
    assert practice_page.status_code == 200

    mock_test_page = client.get(
        f"/{exam['slug']}/{department['slug']}/{subject['slug']}/{paper['year']}/mock-test/{mock_test['id']}"
    )
    assert mock_test_page.status_code == 200
    assert mock_test["title"] in mock_test_page.text
    # Full 6-level breadcrumb trail: Home / exam / department / subject / year / mock test.
    paper_url = f"/{exam['slug']}/{department['slug']}/{subject['slug']}/{paper['year']}"
    assert f'<a href="{paper_url}">{paper["year"]}</a>' in mock_test_page.text


def test_unknown_exam_slug_returns_404():
    response = client.get("/no-such-exam-slug-xyz")
    assert response.status_code == 404
    assert "404" in response.text


def test_unknown_paper_year_returns_404(admin_auth_headers):
    exam, department, subject, _paper, _mock_test = _build_full_hierarchy(admin_auth_headers, "B")

    response = client.get(f"/{exam['slug']}/{department['slug']}/{subject['slug']}/1999")
    assert response.status_code == 404


def test_draft_content_hidden_from_public_pages(admin_auth_headers):
    draft_exam = client.post(
        "/api/exams/",
        json={"name": "Draft Gating Exam", "code": "DGE"},
        headers=admin_auth_headers,
    ).json()
    assert draft_exam["status"] == "DRAFT"

    assert client.get(f"/{draft_exam['slug']}").status_code == 404
    assert client.get(f"/api/exams/{draft_exam['id']}").status_code == 404
    assert draft_exam["code"] not in client.get("/api/exams/").text

    published_exam = client.post(
        "/api/exams/",
        json={"name": "Draft Gating Exam Parent", "code": "DGEP", "status": "PUBLISHED"},
        headers=admin_auth_headers,
    ).json()

    draft_department = client.post(
        "/api/departments/",
        json={"exam_id": published_exam["id"], "name": "Draft Dept", "code": "DD"},
        headers=admin_auth_headers,
    ).json()

    # Parent exam page still renders...
    exam_page = client.get(f"/{published_exam['slug']}")
    assert exam_page.status_code == 200
    assert draft_department["name"] not in exam_page.text

    # ...but the draft department's own page is not reachable.
    dept_page = client.get(f"/{published_exam['slug']}/{draft_department['slug']}")
    assert dept_page.status_code == 404


def test_draft_exam_excluded_from_sitemap_published_exam_included(admin_auth_headers):
    draft_exam = client.post(
        "/api/exams/",
        json={"name": "Draft Sitemap Exam", "code": "DSME", "status": "DRAFT"},
        headers=admin_auth_headers,
    ).json()

    published_exam = client.post(
        "/api/exams/",
        json={"name": "Published Sitemap Exam", "code": "PSME", "status": "PUBLISHED"},
        headers=admin_auth_headers,
    ).json()

    sitemap = client.get("/sitemap.xml").text
    assert draft_exam["slug"] not in sitemap
    assert published_exam["slug"] in sitemap


def test_blog_list_and_detail_pages_render(admin_auth_headers):
    client.post(
        "/api/blogs/",
        json={
            "title": "Public Page Blog Post",
            "content": "## Heading\n\nSome **bold** content.",
            "status": "PUBLISHED",
        },
        headers=admin_auth_headers,
    )

    list_page = client.get("/blogs")
    assert list_page.status_code == 200
    assert "Public Page Blog Post" in list_page.text

    detail_page = client.get("/blogs/public-page-blog-post")
    assert detail_page.status_code == 200
    assert "<strong>bold</strong>" in detail_page.text
    assert "<h2>Heading</h2>" in detail_page.text


def test_search_page_renders_with_and_without_query(admin_auth_headers):
    _build_full_hierarchy(admin_auth_headers, "C")

    empty = client.get("/search")
    assert empty.status_code == 200

    with_query = client.get("/search", params={"q": "Public Page Exam C"})
    assert with_query.status_code == 200
    assert "result" in with_query.text.lower()


def test_static_pages_and_seo_routes():
    for path in ("/about", "/contact", "/privacy", "/disclaimer"):
        response = client.get(path)
        assert response.status_code == 200

    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert "Sitemap:" in robots.text

    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    assert "<urlset" in sitemap.text
