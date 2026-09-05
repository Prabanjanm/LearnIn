"""
Cross-cutting HTTP-layer hardening that doesn't belong to any one module:
security response headers and a lightweight CSRF defense for cookie-based
auth. Both are plain ASGI middleware (matching the existing
StudentIdentityMiddleware pattern in app/modules/student/middleware.py)
rather than a third-party dependency, since the app is small enough that
a few dozen lines cover what's actually needed here.
"""
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings

# The exact set of external hosts this app's own templates actually load
# from - see templates/layouts/base.html (Google Fonts) and
# app/common/utils/drive_urls.py (Drive-hosted file previews/downloads).
# Widen this list only when a template genuinely starts using a new host.
_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: https://drive.google.com https://lh3.googleusercontent.com; "
    "connect-src 'self'; "
    "frame-ancestors 'self'; "
    "form-action 'self'; "
    "base-uri 'self'; "
    "object-src 'none'"
)
# script-src/style-src keep 'unsafe-inline' because the admin CMS uses a
# handful of small inline <script>/style blocks (flash toasts, JSON-LD)
# rather than a nonce/hash scheme - a stricter CSP would need those
# rewritten first. Everything else here is a real, deliberate restriction.


class SecurityHeadersMiddleware:
    """Adds the response headers every page should carry regardless of
    route - clickjacking/MIME-sniffing/referrer/permissions hardening,
    plus HSTS only once the deployment is actually HTTPS (settings.DEBUG
    off is this app's signal for "this is the production config")."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                headers.append((b"x-content-type-options", b"nosniff"))
                headers.append((b"x-frame-options", b"SAMEORIGIN"))
                headers.append((b"referrer-policy", b"strict-origin-when-cross-origin"))
                headers.append((b"permissions-policy", b"geolocation=(), microphone=(), camera=()"))
                headers.append((b"content-security-policy", _CSP.encode()))
                if not settings.DEBUG:
                    # Only sent once the deployment is confirmed HTTPS
                    # (DEBUG=False is this app's production signal) -
                    # enabling HSTS on a domain that isn't fully HTTPS-ready
                    # yet would break plain-HTTP access entirely.
                    headers.append((b"strict-transport-security", b"max-age=63072000; includeSubDomains"))
            await send(message)

        await self.app(scope, receive, send_wrapper)


_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


class CsrfOriginCheckMiddleware:
    """
    Lightweight CSRF defense for the app's cookie-based auth (student and
    admin sessions both read the JWT from a cookie - see
    app/modules/student/dependencies.py and app/modules/admin/dependencies.py
    - so a malicious third-party page's cross-site request would carry
    that cookie automatically unless something checks where the request
    actually came from).

    Rather than retrofitting a CSRF token into every form/fetch call
    across the app, this validates the browser-supplied Origin (falling
    back to Referer's origin, since some older/privacy-hardened browser
    configurations omit Origin on same-site navigations) against the
    request's own Host for every state-changing method. A request with
    neither header is allowed through - that's what a same-origin
    fetch()/form submission from a modern browser normally omits only
    when both are stripped by a privacy setting, and it's also the shape
    of a same-origin server-to-server call - but a request carrying an
    Origin/Referer that points somewhere else is rejected outright.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in _SAFE_METHODS:
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        source = request.headers.get("origin") or request.headers.get("referer")

        if source:
            source_host = source.split("://", 1)[-1].split("/", 1)[0]
            request_host = request.headers.get("host", "")
            if source_host != request_host:
                response = PlainTextResponse("Cross-origin request blocked", status_code=403)
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)
