from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.admin.model import Admin
from app.modules.institution.dependencies import INSTITUTION_ACCESS_TOKEN_COOKIE_NAME
from app.modules.institution.model import Institution, InstitutionUser
from app.modules.student.dependencies import STUDENT_ACCESS_TOKEN_COOKIE_NAME
from app.modules.student.model import Student

client = TestClient(app)


# --------------------------------------------------------------- helpers --

def _make_admin(db_session, email: str) -> Admin:
    admin = Admin(email=email, hashed_password=hash_password("AdminPass123!"), full_name="Test Admin")
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def _admin_headers(admin: Admin) -> dict:
    token = create_access_token(subject=str(admin.id), token_type="admin", token_version=admin.token_version)
    return {"Authorization": f"Bearer {token}"}


def _make_institution(db_session, name: str, conducted_test_enabled: bool = True) -> Institution:
    institution = Institution(name=name, slug=name.lower().replace(" ", "-"), conducted_test_enabled=conducted_test_enabled)
    db_session.add(institution)
    db_session.commit()
    db_session.refresh(institution)
    return institution


def _make_institution_user(db_session, institution: Institution, email: str) -> InstitutionUser:
    user = InstitutionUser(
        institution_id=institution.id,
        email=email,
        hashed_password=hash_password("InstitutionPass123!"),
        full_name="Institution User",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _institution_headers(user: InstitutionUser) -> dict:
    token = create_access_token(subject=str(user.id), token_type="institution_user", token_version=user.token_version)
    return {"Authorization": f"Bearer {token}"}


def _make_student(db_session, email: str) -> Student:
    student = Student(email=email, hashed_password=hash_password("StudentPass123!"), full_name="Test Student")
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)
    return student


def _student_cookies(student: Student) -> dict:
    token = create_access_token(subject=str(student.id), token_type="student", token_version=student.token_version)
    return {STUDENT_ACCESS_TOKEN_COOKIE_NAME: token}


def _build_mock_test(admin_headers: dict, suffix: str) -> dict:
    exam = client.post(
        "/api/exams/",
        json={"name": f"Conducted Exam {suffix}", "code": f"CTX{suffix}"},
        headers=admin_headers,
    ).json()
    department = client.post(
        "/api/departments/",
        json={"exam_id": exam["id"], "name": "Computer Science", "code": f"CS{suffix}"},
        headers=admin_headers,
    ).json()
    subject = client.post(
        "/api/subjects/",
        json={"department_id": department["id"], "name": "Data Structures"},
        headers=admin_headers,
    ).json()
    paper = client.post(
        "/api/papers/",
        json={"subject_id": subject["id"], "title": f"GATE {suffix}", "year": 2021, "question_file_id": f"drive-{suffix}"},
        headers=admin_headers,
    ).json()
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
            "options": [{"label": "A", "option_text": "1"}, {"label": "B", "option_text": "2"}],
        },
        headers=admin_headers,
    ).json()
    mock_test = client.post(
        "/api/mock-tests/",
        json={
            "paper_id": paper["id"],
            "title": f"Conducted Mock {suffix}",
            "question_ids": [q1["id"]],
            "status": "PUBLISHED",
        },
        headers=admin_headers,
    ).json()
    return mock_test


def _create_conducted_test(institution_headers: dict, mock_test_id: int, minutes_from_now: int = -1, duration_minutes: int = 60) -> dict:
    start = datetime.now(timezone.utc) + timedelta(minutes=minutes_from_now)
    response = client.post(
        "/api/institution/conducted-tests/",
        json={
            "mock_test_id": mock_test_id,
            "title": "Conducted Test",
            "instructions": "Follow the rules.",
            "duration_minutes": duration_minutes,
            "scheduled_start_at": start.isoformat(),
        },
        headers=institution_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _activate(institution_headers, conducted_test_id):
    response = client.post(f"/api/institution/conducted-tests/{conducted_test_id}/activate", headers=institution_headers)
    assert response.status_code == 200
    return response.json()


def _setup_enabled_institution(db_session, suffix: str):
    """One platform admin (only used to build the shared question bank),
    plus one enabled institution + its user - the standard setup most
    tests build on."""
    platform_admin = _make_admin(db_session, f"platform-admin-{suffix}@learnin.app")
    mock_test = _build_mock_test(_admin_headers(platform_admin), suffix)
    institution = _make_institution(db_session, f"Institution {suffix}", conducted_test_enabled=True)
    user = _make_institution_user(db_session, institution, f"user-{suffix}@institution.example")
    return mock_test, institution, user


# ------------------------------------------------------------ authorization --

def test_normal_student_cannot_create_conducted_test(db_session):
    student = _make_student(db_session, "student-no-create@learnin.app")

    response = client.post(
        "/api/institution/conducted-tests/",
        json={
            "mock_test_id": 1,
            "title": "Should Fail",
            "duration_minutes": 30,
            "scheduled_start_at": datetime.now(timezone.utc).isoformat(),
        },
        cookies=_student_cookies(student),
    )
    assert response.status_code == 401


def test_admin_token_cannot_create_conducted_test(db_session):
    """A LearnIn Admin JWT is a distinct token type - it's never accepted
    by get_current_institution_user, even though Admin used to be the
    creator under the old (incorrect) design."""
    admin = _make_admin(db_session, "plain-admin@learnin.app")

    response = client.post(
        "/api/institution/conducted-tests/",
        json={
            "mock_test_id": 1,
            "title": "Should Fail",
            "duration_minutes": 30,
            "scheduled_start_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=_admin_headers(admin),
    )
    assert response.status_code == 401


def test_institution_without_feature_enabled_cannot_create(db_session):
    admin = _make_admin(db_session, "helper-admin-1@learnin.app")
    mock_test = _build_mock_test(_admin_headers(admin), "P1")

    institution = _make_institution(db_session, "Disabled Institution", conducted_test_enabled=False)
    user = _make_institution_user(db_session, institution, "user@disabled.example")

    response = client.post(
        "/api/institution/conducted-tests/",
        json={
            "mock_test_id": mock_test["id"],
            "title": "Should Fail",
            "duration_minutes": 30,
            "scheduled_start_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=_institution_headers(user),
    )
    assert response.status_code == 403


def test_institution_with_feature_enabled_can_create_with_unique_code(db_session):
    mock_test, institution, user = _setup_enabled_institution(db_session, "C1")

    conducted_test = _create_conducted_test(_institution_headers(user), mock_test["id"], minutes_from_now=10)

    assert conducted_test["test_code"].startswith("LIN-")
    assert len(conducted_test["test_code"]) == 9
    assert conducted_test["status"] == "DRAFT"
    assert conducted_test["institution_id"] == institution.id
    assert conducted_test["created_by_institution_user_id"] == user.id


def test_institution_user_can_only_access_own_institution_data(db_session):
    mock_test_a, institution_a, user_a = _setup_enabled_institution(db_session, "A1")
    _mock_test_b, institution_b, user_b = _setup_enabled_institution(db_session, "B1")
    assert institution_a.id != institution_b.id

    conducted_test = _create_conducted_test(_institution_headers(user_a), mock_test_a["id"], minutes_from_now=10)

    # user_b belongs to a *different* institution and must not be able to
    # manage or even see institution_a's test via its own token.
    forbidden_get = client.get(
        f"/api/institution/conducted-tests/{conducted_test['id']}",
        headers=_institution_headers(user_b),
    )
    assert forbidden_get.status_code == 404

    own_list = client.get("/api/institution/conducted-tests/", headers=_institution_headers(user_b)).json()
    assert all(t["id"] != conducted_test["id"] for t in own_list)


# ------------------------------------------------------- multi-tenant IDOR --

def _two_institution_setup(db_session, suffix: str):
    mock_test_a, institution_a, user_a = _setup_enabled_institution(db_session, f"{suffix}A")
    _mock_test_b, institution_b, user_b = _setup_enabled_institution(db_session, f"{suffix}B")
    conducted_test = _create_conducted_test(_institution_headers(user_a), mock_test_a["id"], minutes_from_now=-1, duration_minutes=60)
    _activate(_institution_headers(user_a), conducted_test["id"])
    return conducted_test, user_a, user_b


def test_institution_b_cannot_view_institution_a_test(db_session):
    conducted_test, _user_a, user_b = _two_institution_setup(db_session, "MT1")

    response = client.get(f"/api/institution/conducted-tests/{conducted_test['id']}", headers=_institution_headers(user_b))
    assert response.status_code == 404


def test_institution_b_cannot_modify_institution_a_test(db_session):
    conducted_test, _user_a, user_b = _two_institution_setup(db_session, "MT2")

    response = client.patch(
        f"/api/institution/conducted-tests/{conducted_test['id']}",
        json={"title": "Hijacked"},
        headers=_institution_headers(user_b),
    )
    assert response.status_code == 404


def test_institution_b_cannot_archive_institution_a_test(db_session):
    conducted_test, _user_a, user_b = _two_institution_setup(db_session, "MT3")

    response = client.delete(f"/api/institution/conducted-tests/{conducted_test['id']}", headers=_institution_headers(user_b))
    assert response.status_code == 404


def test_institution_b_cannot_view_institution_a_participants(db_session):
    conducted_test, _user_a, user_b = _two_institution_setup(db_session, "MT4")

    response = client.get(
        f"/api/institution/conducted-tests/{conducted_test['id']}/participants",
        headers=_institution_headers(user_b),
    )
    assert response.status_code == 404


def test_institution_b_cannot_view_institution_a_results(db_session):
    conducted_test, user_a, user_b = _two_institution_setup(db_session, "MT5")
    student = _make_student(db_session, "idor-result-student@learnin.app")
    cookies = _student_cookies(student)

    client.post("/api/conducted-tests/join", json={"test_code": conducted_test["test_code"]}, cookies=cookies)
    client.post(f"/api/conducted-tests/{conducted_test['id']}/start", cookies=cookies)
    result = client.post(f"/api/conducted-tests/{conducted_test['id']}/submit", cookies=cookies).json()

    # institution B cannot view this result even through the results
    # endpoint under its own (real, activated) test id...
    denied_via_own_test = client.get(
        f"/api/institution/conducted-tests/{conducted_test['id']}/results/{result['result_code']}",
        headers=_institution_headers(user_b),
    )
    assert denied_via_own_test.status_code == 404

    # ...and owner A can.
    allowed = client.get(
        f"/api/institution/conducted-tests/{conducted_test['id']}/results/{result['result_code']}",
        headers=_institution_headers(user_a),
    )
    assert allowed.status_code == 200


def test_institution_b_cannot_terminate_institution_a_attempt(db_session):
    conducted_test, _user_a, user_b = _two_institution_setup(db_session, "MT6")
    student = _make_student(db_session, "idor-terminate-student@learnin.app")
    cookies = _student_cookies(student)

    client.post("/api/conducted-tests/join", json={"test_code": conducted_test["test_code"]}, cookies=cookies)
    client.post(f"/api/conducted-tests/{conducted_test['id']}/start", cookies=cookies)

    response = client.post(
        f"/api/institution/conducted-tests/{conducted_test['id']}/attempts/{student.id}/terminate",
        headers=_institution_headers(user_b),
    )
    assert response.status_code == 404


# --------------------------------------------------------------- join flow --

def test_join_with_invalid_code_rejected(db_session):
    student = _make_student(db_session, "join-invalid@learnin.app")

    response = client.post(
        "/api/conducted-tests/join",
        json={"test_code": "LIN-ZZZZZ"},
        cookies=_student_cookies(student),
    )
    assert response.status_code == 404


def test_join_requires_active_published_test(db_session):
    mock_test, _institution, user = _setup_enabled_institution(db_session, "C3")
    student = _make_student(db_session, "join-draft@learnin.app")
    conducted_test = _create_conducted_test(_institution_headers(user), mock_test["id"], minutes_from_now=10)

    # Still DRAFT (never activated) - join must fail with the same
    # generic message as an unknown code, not reveal that it exists.
    response = client.post(
        "/api/conducted-tests/join",
        json={"test_code": conducted_test["test_code"]},
        cookies=_student_cookies(student),
    )
    assert response.status_code == 404


# --------------------------------------------------------- full attempt flow --

def test_full_join_start_answer_submit_flow_and_one_attempt_enforced(db_session):
    mock_test, _institution, user = _setup_enabled_institution(db_session, "C4")
    student = _make_student(db_session, "flow-student-1@learnin.app")
    conducted_test = _create_conducted_test(_institution_headers(user), mock_test["id"], minutes_from_now=-1, duration_minutes=60)
    _activate(_institution_headers(user), conducted_test["id"])

    cookies = _student_cookies(student)

    joined = client.post("/api/conducted-tests/join", json={"test_code": conducted_test["test_code"]}, cookies=cookies)
    assert joined.status_code == 200
    assert joined.json()["already_completed"] is False

    started = client.post(f"/api/conducted-tests/{conducted_test['id']}/start", cookies=cookies)
    assert started.status_code == 200
    start_data = started.json()
    assert start_data["remaining_seconds"] > 0
    question_id = start_data["questions"][0]["question"]["id"]

    # Resuming (e.g. a page refresh) must return the same attempt, not a
    # second one - the unique(conducted_test_id, student_id) constraint
    # is what actually guarantees this at the DB level.
    started_again = client.post(f"/api/conducted-tests/{conducted_test['id']}/start", cookies=cookies)
    assert started_again.status_code == 200

    answered = client.post(
        f"/api/conducted-tests/{conducted_test['id']}/answer",
        json={"question_id": question_id, "answer": "B"},
        cookies=cookies,
    )
    assert answered.status_code == 204

    submitted = client.post(f"/api/conducted-tests/{conducted_test['id']}/submit", cookies=cookies)
    assert submitted.status_code == 200
    result = submitted.json()
    assert result["status"] == "SUBMITTED"
    assert result["termination_reason"] == "MANUAL_SUBMIT"
    assert result["correct_count"] == 1
    assert result["scored_marks"] == 2.0

    # Locked attempt cannot be modified further.
    late_answer = client.post(
        f"/api/conducted-tests/{conducted_test['id']}/answer",
        json={"question_id": question_id, "answer": "A"},
        cookies=cookies,
    )
    assert late_answer.status_code == 400

    # Idempotent re-submit (e.g. a violation racing a manual submit)
    # returns the same finalized result rather than erroring.
    resubmit = client.post(f"/api/conducted-tests/{conducted_test['id']}/submit", cookies=cookies)
    assert resubmit.status_code == 200
    assert resubmit.json()["result_code"] == result["result_code"]

    # A second /start after completion is rejected - one attempt only.
    second_start = client.post(f"/api/conducted-tests/{conducted_test['id']}/start", cookies=cookies)
    assert second_start.status_code == 403

    # join_for_instructions now reports already_completed too.
    rejoin = client.post("/api/conducted-tests/join", json={"test_code": conducted_test["test_code"]}, cookies=cookies)
    assert rejoin.status_code == 200
    assert rejoin.json()["already_completed"] is True


def test_late_join_after_window_closed_is_rejected(db_session):
    mock_test, _institution, user = _setup_enabled_institution(db_session, "C5")
    student = _make_student(db_session, "late-student@learnin.app")
    # Scheduled window: started 120 minutes ago, only lasted 10 minutes -
    # already closed well before "now".
    conducted_test = _create_conducted_test(
        _institution_headers(user), mock_test["id"], minutes_from_now=-120, duration_minutes=10
    )
    _activate(_institution_headers(user), conducted_test["id"])

    cookies = _student_cookies(student)
    response = client.post(f"/api/conducted-tests/{conducted_test['id']}/start", cookies=cookies)
    assert response.status_code == 400


def test_tab_switch_violation_auto_submits_and_locks(db_session):
    mock_test, _institution, user = _setup_enabled_institution(db_session, "C6")
    student = _make_student(db_session, "violation-student@learnin.app")
    conducted_test = _create_conducted_test(_institution_headers(user), mock_test["id"], minutes_from_now=-1, duration_minutes=60)
    _activate(_institution_headers(user), conducted_test["id"])

    cookies = _student_cookies(student)
    client.post("/api/conducted-tests/join", json={"test_code": conducted_test["test_code"]}, cookies=cookies)
    client.post(f"/api/conducted-tests/{conducted_test['id']}/start", cookies=cookies)

    response = client.post(
        f"/api/conducted-tests/{conducted_test['id']}/violation",
        json={"reason": "TAB_SWITCH"},
        cookies=cookies,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "AUTO_SUBMITTED"
    assert data["termination_reason"] == "TAB_SWITCH"

    # Locked - no further answers accepted.
    blocked = client.post(
        f"/api/conducted-tests/{conducted_test['id']}/answer",
        json={"question_id": 1, "answer": "A"},
        cookies=cookies,
    )
    assert blocked.status_code == 400


def test_private_result_access_and_student_idor_protection(db_session):
    mock_test, _institution, user = _setup_enabled_institution(db_session, "C7")
    owner_student = _make_student(db_session, "result-owner@learnin.app")
    other_student = _make_student(db_session, "result-other@learnin.app")
    conducted_test = _create_conducted_test(_institution_headers(user), mock_test["id"], minutes_from_now=-1, duration_minutes=60)
    _activate(_institution_headers(user), conducted_test["id"])

    owner_cookies = _student_cookies(owner_student)
    client.post("/api/conducted-tests/join", json={"test_code": conducted_test["test_code"]}, cookies=owner_cookies)
    client.post(f"/api/conducted-tests/{conducted_test['id']}/start", cookies=owner_cookies)
    result = client.post(f"/api/conducted-tests/{conducted_test['id']}/submit", cookies=owner_cookies).json()
    result_code = result["result_code"]

    # No auth at all - result id alone must not grant access, and the
    # rejection must not leak any report data alongside the 401.
    client.cookies.clear()
    unauthenticated = client.get(f"/api/conducted-tests/results/{result_code}")
    assert unauthenticated.status_code == 401
    assert "scored_marks" not in unauthenticated.text
    assert result["result_code"] not in unauthenticated.text

    # Authenticated as a different student - still forbidden, and again
    # no report data in the response body.
    other_cookies = _student_cookies(other_student)
    forbidden = client.get(f"/api/conducted-tests/results/{result_code}", cookies=other_cookies)
    assert forbidden.status_code == 403
    assert "scored_marks" not in forbidden.text

    # Owner can view their own result.
    allowed = client.get(f"/api/conducted-tests/results/{result_code}", cookies=owner_cookies)
    assert allowed.status_code == 200
    assert allowed.json()["result_code"] == result_code

    # The owning institution can view it via its own results endpoint.
    institution_view = client.get(
        f"/api/institution/conducted-tests/{conducted_test['id']}/results/{result_code}",
        headers=_institution_headers(user),
    )
    assert institution_view.status_code == 200

    # A well-formed but entirely made-up result code is just as
    # unauthorized as a real one an attacker doesn't own - the code
    # itself carries no authority, only ownership does.
    guessed_code = "LIN-RZZZZZZZZ"
    guessed = client.get(f"/api/conducted-tests/results/{guessed_code}", cookies=other_cookies)
    assert guessed.status_code == 404


def test_no_public_download_share_or_export_endpoints_exist(db_session):
    """There must be no way to fetch a result's data or an exported
    file without going through the normal authenticated/authorized
    endpoint - guards against a share/download/PDF/print route ever
    being added (or resurfacing) for this private data."""
    mock_test, _institution, user = _setup_enabled_institution(db_session, "C7B")
    student = _make_student(db_session, "no-export-student@learnin.app")
    conducted_test = _create_conducted_test(_institution_headers(user), mock_test["id"], minutes_from_now=-1, duration_minutes=60)
    _activate(_institution_headers(user), conducted_test["id"])

    cookies = _student_cookies(student)
    client.post("/api/conducted-tests/join", json={"test_code": conducted_test["test_code"]}, cookies=cookies)
    client.post(f"/api/conducted-tests/{conducted_test['id']}/start", cookies=cookies)
    result = client.post(f"/api/conducted-tests/{conducted_test['id']}/submit", cookies=cookies).json()
    result_code = result["result_code"]

    guessed_paths = [
        f"/api/conducted-tests/results/{result_code}/download",
        f"/api/conducted-tests/results/{result_code}/pdf",
        f"/api/conducted-tests/results/{result_code}/export",
        f"/api/conducted-tests/results/{result_code}/share",
        f"/api/conducted-tests/results/{result_code}.pdf",
        "/api/conducted-tests/results/share",
        f"/conducted-tests/results/{result_code}/download",
        f"/conducted-tests/results/{result_code}/print",
    ]
    for path in guessed_paths:
        response = client.get(path, cookies=cookies)
        # 404: no route matches at all. 422: it happened to collide with
        # the public exam/paper catch-all's path *shape* (e.g.
        # /{exam_slug}/{department_slug}/{subject_slug}/{year}) and
        # failed that route's own int-parsing - either way, no
        # download/share/export handler for this result ever ran.
        assert response.status_code in (404, 422), f"unexpected route exists: {path} -> {response.status_code}"
        assert "scored_marks" not in response.text

    # No unauthenticated variant of the real endpoint either.
    client.cookies.clear()
    assert client.get(f"/api/conducted-tests/results/{result_code}").status_code == 401


def test_soft_delete_archives_and_preserves_results(db_session):
    mock_test, _institution, user = _setup_enabled_institution(db_session, "C8")
    student = _make_student(db_session, "archive-student@learnin.app")
    conducted_test = _create_conducted_test(_institution_headers(user), mock_test["id"], minutes_from_now=-1, duration_minutes=60)
    _activate(_institution_headers(user), conducted_test["id"])

    cookies = _student_cookies(student)
    client.post("/api/conducted-tests/join", json={"test_code": conducted_test["test_code"]}, cookies=cookies)
    client.post(f"/api/conducted-tests/{conducted_test['id']}/start", cookies=cookies)
    result = client.post(f"/api/conducted-tests/{conducted_test['id']}/submit", cookies=cookies).json()

    deleted = client.delete(f"/api/institution/conducted-tests/{conducted_test['id']}", headers=_institution_headers(user))
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "ARCHIVED"

    # The result itself is never deleted just because the test was archived.
    still_visible = client.get(f"/api/conducted-tests/results/{result['result_code']}", cookies=cookies)
    assert still_visible.status_code == 200


def test_audit_timestamps_present(db_session):
    mock_test, _institution, user = _setup_enabled_institution(db_session, "C9")
    conducted_test = _create_conducted_test(_institution_headers(user), mock_test["id"], minutes_from_now=10)

    assert conducted_test["created_at"] is not None

    from app.modules.conducted_test.repository import ConductedTestRepository
    row = ConductedTestRepository().get_by_id(db_session, conducted_test["id"])
    assert row.created_at is not None
    assert row.updated_at is not None
    assert row.institution_id == _institution.id
    assert row.created_by_institution_user_id == user.id


# ------------------------------------------------------------- admin control --

def test_admin_can_enable_and_disable_institution_conducted_test_feature(db_session):
    platform_admin = _make_admin(db_session, "toggle-admin@learnin.app")
    institution = _make_institution(db_session, "Togglable Institution", conducted_test_enabled=False)
    user = _make_institution_user(db_session, institution, "toggle-user@institution.example")
    mock_test = _build_mock_test(_admin_headers(platform_admin), "TOG")

    # Disabled by default - blocked server-side.
    blocked = client.post(
        "/api/institution/conducted-tests/",
        json={
            "mock_test_id": mock_test["id"],
            "title": "Blocked",
            "duration_minutes": 30,
            "scheduled_start_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=_institution_headers(user),
    )
    assert blocked.status_code == 403

    # Admin enables it.
    enable = client.post(
        f"/api/admin/institutions/{institution.id}/conducted-test-feature?enabled=true",
        headers=_admin_headers(platform_admin),
    )
    assert enable.status_code == 200
    assert enable.json()["conducted_test_enabled"] is True

    allowed = client.post(
        "/api/institution/conducted-tests/",
        json={
            "mock_test_id": mock_test["id"],
            "title": "Now Allowed",
            "duration_minutes": 30,
            "scheduled_start_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=_institution_headers(user),
    )
    assert allowed.status_code == 200

    # Admin disables it again.
    disable = client.post(
        f"/api/admin/institutions/{institution.id}/conducted-test-feature?enabled=false",
        headers=_admin_headers(platform_admin),
    )
    assert disable.status_code == 200
    assert disable.json()["conducted_test_enabled"] is False

    blocked_again = client.post(
        "/api/institution/conducted-tests/",
        json={
            "mock_test_id": mock_test["id"],
            "title": "Blocked Again",
            "duration_minutes": 30,
            "scheduled_start_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=_institution_headers(user),
    )
    assert blocked_again.status_code == 403


def test_admin_can_create_institution_and_institution_user(db_session):
    platform_admin = _make_admin(db_session, "creator-admin@learnin.app")

    created = client.post(
        "/api/admin/institutions/",
        json={"name": "Brand New College", "conducted_test_enabled": True},
        headers=_admin_headers(platform_admin),
    )
    assert created.status_code == 200
    institution_id = created.json()["id"]

    created_user = client.post(
        f"/api/admin/institutions/{institution_id}/users",
        json={"email": "admin-created@institution.example", "password": "StrongPass123!", "full_name": "Someone"},
        headers=_admin_headers(platform_admin),
    )
    assert created_user.status_code == 200

    login = client.post(
        "/api/institution/login",
        json={"email": "admin-created@institution.example", "password": "StrongPass123!"},
    )
    assert login.status_code == 200
    assert "access_token" in login.json()


def test_normal_admin_cannot_log_in_as_institution_and_vice_versa(db_session):
    """The two token types are distinct - an admin JWT never resolves as
    an institution user and an institution JWT never resolves as an
    admin, even though both are Bearer tokens issued by the same
    create_access_token()."""
    admin = _make_admin(db_session, "cross-token-admin@learnin.app")
    institution = _make_institution(db_session, "Cross Token Institution")
    user = _make_institution_user(db_session, institution, "cross-token-user@institution.example")

    admin_as_institution = client.get("/api/institution/me", headers=_admin_headers(admin))
    assert admin_as_institution.status_code == 401

    institution_as_admin = client.get("/api/admin/me", headers=_institution_headers(user))
    assert institution_as_admin.status_code == 401
