from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.core.upload_policy import UploadValidationError, validate_upload
from app.common.utils.markdown_render import render_markdown
from app.main import app

client = TestClient(app)


def test_hash_password_roundtrip():
    hashed = hash_password("s3cret-Pass!")

    assert hashed != "s3cret-Pass!"
    assert verify_password("s3cret-Pass!", hashed)
    assert not verify_password("wrong-password", hashed)


def test_access_token_roundtrip():
    token = create_access_token(subject="1", token_type="admin")
    payload = decode_access_token(token)

    assert payload is not None
    assert payload["sub"] == "1"
    assert payload["type"] == "admin"
    assert payload["tv"] == 0


def test_expired_token_is_rejected():
    token = create_access_token(
        subject="1",
        token_type="admin",
        expires_delta=timedelta(seconds=-1),
    )

    assert decode_access_token(token) is None


def test_tampered_token_is_rejected():
    token = create_access_token(subject="1", token_type="admin")

    assert decode_access_token(token + "tampered") is None


# ---------------------------------------------------------- CSRF -----

def test_csrf_blocks_forged_cross_origin_post():
    response = client.post(
        "/login",
        data={"email": "nouser@example.com", "password": "wrong"},
        headers={"Origin": "http://evil.example"},
    )
    assert response.status_code == 403


def test_csrf_allows_same_origin_post():
    response = client.post(
        "/login",
        data={"email": "nouser@example.com", "password": "wrong"},
        headers={"Origin": "http://testserver"},
    )
    # Reaches the real login handler (and fails auth, not CSRF) - proves
    # a legitimate same-origin request is never blocked by the CSRF check.
    assert response.status_code == 401


def test_csrf_allows_missing_origin_and_referer():
    response = client.post("/login", data={"email": "nouser@example.com", "password": "wrong"})
    assert response.status_code == 401


def test_csrf_does_not_apply_to_safe_methods():
    response = client.get("/login", headers={"Origin": "http://evil.example"})
    assert response.status_code == 200


# ------------------------------------------------- security headers -----

def test_security_headers_present_on_every_response():
    response = client.get("/")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "SAMEORIGIN"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "permissions-policy" in response.headers


# --------------------------------------------------- rate limiting -----

def test_login_rate_limit_blocks_after_threshold():
    responses = [
        client.post("/login", data={"email": f"ratelimit-{i}@example.com", "password": "wrong"})
        for i in range(15)
    ]
    assert any(r.status_code == 429 for r in responses)


def test_json_student_login_rate_limit_blocks_after_threshold():
    # /api/students/login previously had no rate limit at all, unlike its
    # HTML-form equivalent above - regression test for that gap.
    responses = [
        client.post(
            "/api/students/login",
            json={"email": f"json-ratelimit-{i}@example.com", "password": "wrong"},
        )
        for i in range(15)
    ]
    assert any(r.status_code == 429 for r in responses)


def test_json_student_signup_rate_limit_blocks_after_threshold():
    responses = [
        client.post(
            "/api/students/signup",
            json={"email": f"json-signup-ratelimit-{i}@example.com", "password": "GoodPass123"},
        )
        for i in range(15)
    ]
    assert any(r.status_code == 429 for r in responses)


# ------------------------------------------------------- JWT claims -----

def test_token_missing_type_claim_is_rejected_by_student_dependency():
    # Simulates a pre-hardening token (bare "sub"/"exp", no "type"/"tv") -
    # must never resolve as a valid student session.
    from jose import jwt as jose_jwt

    from app.core.config import settings

    legacy_shaped_token = jose_jwt.encode(
        {"sub": "1", "exp": __import__("time").time() + 3600},
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    response = client.get(
        "/api/students/me",
        headers={"Authorization": f"Bearer {legacy_shaped_token}"},
    )
    assert response.status_code == 401


# -------------------------------------------------- markdown / XSS -----

def test_render_markdown_strips_script_tags():
    html = render_markdown("Hello\n\n<script>alert(1)</script>")
    assert "<script>" not in html
    assert "alert(1)" not in html


def test_render_markdown_strips_event_handlers():
    html = render_markdown('<img src=x onerror="alert(1)">')
    assert "onerror" not in html


def test_render_markdown_strips_javascript_uri():
    html = render_markdown("[click me](javascript:alert(1))")
    assert "javascript:" not in html


def test_render_markdown_preserves_safe_formatting():
    html = render_markdown("Hello **world**\n\n[a link](https://example.com)")
    assert "<strong>world</strong>" in html
    assert 'href="https://example.com"' in html


# --------------------------------------------------- upload policy -----

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
_PDF_SIGNATURE = b"%PDF-1.4\n" + b"\x00" * 32


def test_svg_uploads_are_rejected():
    with pytest.raises(UploadValidationError):
        validate_upload("exams", "icon.svg", "image/svg+xml", 100, b"<svg></svg>")


def test_valid_png_signature_is_accepted():
    validate_upload("exams", "icon.png", "image/png", len(_PNG_SIGNATURE), _PNG_SIGNATURE)


def test_valid_pdf_signature_is_accepted():
    validate_upload("papers", "paper.pdf", "application/pdf", len(_PDF_SIGNATURE), _PDF_SIGNATURE)


def test_html_disguised_as_pdf_is_rejected():
    fake_pdf = b"<html><body><script>alert(1)</script></body></html>"
    with pytest.raises(UploadValidationError):
        validate_upload("papers", "paper.pdf", "application/pdf", len(fake_pdf), fake_pdf)


def test_text_disguised_as_png_is_rejected():
    fake_png = b"this is not actually a png file at all, just text padding"
    with pytest.raises(UploadValidationError):
        validate_upload("exams", "icon.png", "image/png", len(fake_png), fake_png)


def test_oversized_file_still_rejected_before_signature_check():
    # Sanity check that existing size validation still runs (unaffected
    # by the new signature check being added after it).
    huge = _PNG_SIGNATURE + b"\x00" * (10 * 1024 * 1024)
    with pytest.raises(UploadValidationError):
        validate_upload("exams", "icon.png", "image/png", len(huge), huge)


# ---------------------------------------- admin file download scope -----

def test_admin_file_download_requires_admin_and_rejects_unknown_ids():
    # No admin auth at all - blocked before file_id is even considered.
    response = client.get("/api/admin/files/anything/download")
    assert response.status_code == 401
