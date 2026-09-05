"""
One-off script: seed ~50 mock records into every admin-manageable category
via the real running admin HTTP API (not direct DB writes), so it goes
through the same validation/service layer the admin UI uses.

Usage:
    cd backend
    python scripts/seed_mock_data.py
"""
import itertools
import random
import sys
import time

import requests

BASE_URL = "http://127.0.0.1:8000"
ADMIN_EMAIL = "you@learnin.app"
ADMIN_PASSWORD = "Tester@123"
COUNT = 50

QUESTION_PDF = r"C:\Users\Poovendhiran\Downloads\Screenshot 2026-07-17 102901.pdf"

session = requests.Session()


def login():
    resp = session.post(
        f"{BASE_URL}/admin/login",
        data={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        allow_redirects=False,
    )
    if resp.status_code not in (302, 303):
        print("Login failed:", resp.status_code, resp.text[:500])
        sys.exit(1)
    print("Logged in as admin.")


def upload_file(category: str) -> dict:
    with open(QUESTION_PDF, "rb") as fh:
        resp = session.post(
            f"{BASE_URL}/admin/upload",
            files={"file": ("mock.pdf", fh, "application/pdf")},
            data={"category": category},
        )
    if resp.status_code != 200:
        print(f"Upload failed for category={category}:", resp.status_code, resp.text[:500])
        sys.exit(1)
    return resp.json()


def create(entity_key: str, payload: dict) -> bool:
    resp = session.post(
        f"{BASE_URL}/admin/manage/{entity_key}/new",
        data=payload,
        allow_redirects=False,
    )
    if resp.status_code not in (302, 303):
        print(f"Create {entity_key} failed:", resp.status_code, resp.text[:800])
        return False
    return True


def upload_field_json(meta: dict) -> str:
    import json
    return json.dumps(meta)


def main():
    login()

    print("Uploading shared mock PDF for papers/resources categories...")
    paper_file = upload_file("papers")
    resource_file = upload_file("resources")

    # ---- Exams ----
    exam_ids = []
    for i in range(1, COUNT + 1):
        payload = {
            "name": f"Mock Exam {i}",
            "code": f"MEX{i:03d}",
            "description": f"Auto-generated mock exam #{i} for seeding/testing.",
            "display_order": i,
            "status": "PUBLISHED",
        }
        create("exams", payload)
    print(f"Created {COUNT} exams.")

    # Fetch back exam ids via the list API isn't available generically, so
    # query the DB directly for ids (read-only) to build FK chains.
    from app.core.database import SessionLocal
    from app.modules.exam.model import Exam
    from app.modules.department.model import Department
    from app.modules.subject.model import Subject
    from app.modules.paper.model import Paper
    from app.modules.question.model import Question

    db = SessionLocal()
    exam_ids = [row.id for row in db.query(Exam.id).order_by(Exam.id.desc()).limit(COUNT)]
    exam_ids.reverse()
    db.close()

    # ---- Departments ----
    for i in range(1, COUNT + 1):
        exam_id = exam_ids[i % len(exam_ids)]
        payload = {
            "exam_id": exam_id,
            "name": f"Mock Department {i}",
            "code": f"MDP{i:03d}",
            "display_order": i,
            "status": "PUBLISHED",
        }
        create("departments", payload)
    print(f"Created {COUNT} departments.")

    db = SessionLocal()
    dept_ids = [row.id for row in db.query(Department.id).order_by(Department.id.desc()).limit(COUNT)]
    dept_ids.reverse()
    db.close()

    # ---- Subjects ----
    for i in range(1, COUNT + 1):
        dept_id = dept_ids[i % len(dept_ids)]
        payload = {
            "department_id": dept_id,
            "name": f"Mock Subject {i}",
            "display_order": i,
            "status": "PUBLISHED",
        }
        create("subjects", payload)
    print(f"Created {COUNT} subjects.")

    db = SessionLocal()
    subject_ids = [row.id for row in db.query(Subject.id).order_by(Subject.id.desc()).limit(COUNT)]
    subject_ids.reverse()
    db.close()

    # ---- Papers (reuse one uploaded PDF's file id for every paper) ----
    for i in range(1, COUNT + 1):
        subject_id = subject_ids[i % len(subject_ids)]
        payload = {
            "subject_id": subject_id,
            "title": f"Mock Paper {i}",
            "year": 2000 + (i % 26),
            "question_file_id": upload_field_json({
                "file_id": paper_file["file_id"],
                "mime_type": paper_file["mime_type"],
                "file_size": paper_file["file_size"],
                "filename": paper_file["filename"],
            }),
            "duration": 120,
            "status": "PUBLISHED",
        }
        create("papers", payload)
    print(f"Created {COUNT} papers.")

    db = SessionLocal()
    paper_ids = [row.id for row in db.query(Paper.id).order_by(Paper.id.desc()).limit(COUNT)]
    paper_ids.reverse()
    db.close()

    # ---- Resources (reuse one uploaded PDF's file id for every resource) ----
    resource_types = ["NOTES", "PYQ", "FORMULA_SHEET", "REVISION_NOTES", "IMPORTANT_QUESTIONS", "CHEAT_SHEET"]
    for i in range(1, COUNT + 1):
        subject_id = subject_ids[i % len(subject_ids)]
        payload = {
            "subject_id": subject_id,
            "title": f"Mock Resource {i}",
            "description": f"Auto-generated mock resource #{i}.",
            "resource_type": resource_types[i % len(resource_types)],
            "google_drive_file_id": upload_field_json({
                "file_id": resource_file["file_id"],
                "mime_type": resource_file["mime_type"],
                "file_size": resource_file["file_size"],
                "filename": resource_file["filename"],
            }),
            "status": "PUBLISHED",
        }
        create("resources", payload)
    print(f"Created {COUNT} resources.")

    # ---- Blogs (independent) ----
    for i in range(1, COUNT + 1):
        payload = {
            "title": f"Mock Blog Post {i}",
            "content": f"# Mock Blog Post {i}\n\nThis is auto-generated mock blog content for seeding/testing purposes.",
            "category": "General",
            "tags": "mock,test,seed",
            "status": "PUBLISHED",
        }
        create("blogs", payload)
    print(f"Created {COUNT} blogs.")

    # ---- Questions (each with 4 options, MCQ) ----
    for i in range(1, COUNT + 1):
        paper_id = paper_ids[i % len(paper_ids)]
        payload = {
            "paper_id": paper_id,
            "question_number": i,
            "question_type": "MCQ",
            "difficulty": random.choice(["EASY", "MEDIUM", "HARD"]),
            "question_text": f"Mock question #{i}: what is the answer to auto-generated question {i}?",
            "marks": 1,
            "negative_marks": 0.25,
            "correct_answer": "A",
            "explanation": f"Explanation for mock question #{i}.",
            "status": "PUBLISHED",
            "option_a_text": "Option A",
            "option_b_text": "Option B",
            "option_c_text": "Option C",
            "option_d_text": "Option D",
        }
        create("questions", payload)
    print(f"Created {COUNT} questions (each with 4 options).")

    db = SessionLocal()
    question_ids_by_paper = {}
    rows = db.query(Question.id, Question.paper_id).order_by(Question.id.desc()).limit(COUNT)
    for qid, pid in rows:
        question_ids_by_paper.setdefault(pid, []).append(qid)
    db.close()

    # ---- Mock tests (one per paper that has questions, else skip) ----
    created_mock_tests = 0
    paper_cycle = itertools.cycle(question_ids_by_paper.keys()) if question_ids_by_paper else iter([])
    for i in range(1, COUNT + 1):
        if not question_ids_by_paper:
            break
        pid = next(paper_cycle)
        qids = question_ids_by_paper[pid]
        payload = {
            "paper_id": pid,
            "title": f"Mock Test {i}",
            "description": f"Auto-generated mock test #{i}.",
            "duration": 60,
            "total_marks": len(qids),
            "question_ids": ",".join(str(q) for q in qids),
            "status": "PUBLISHED",
        }
        if create("mock_tests", payload):
            created_mock_tests += 1
    print(f"Created {created_mock_tests} mock tests.")

    print("Done seeding mock data.")


if __name__ == "__main__":
    main()
