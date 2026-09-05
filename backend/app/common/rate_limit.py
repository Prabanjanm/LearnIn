"""
A minimal in-memory sliding-window rate limiter for the handful of
routes that actually need abuse protection (login brute-force, signup
spam, mock-test submission spam). Deliberately not Redis-backed or a
third-party dependency - this app runs as a single process today, and an
in-memory limiter is the smallest thing that actually helps; if LearnIn
ever runs multiple worker processes/instances behind a load balancer,
each would keep its own counters (a real limitation, noted rather than
hidden), at which point a shared store would become worth the added
infrastructure.
"""
import time
from collections import defaultdict

from fastapi import HTTPException, Request

_buckets: dict[str, list[float]] = defaultdict(list)


def rate_limit(max_requests: int, window_seconds: int):
    """Returns a FastAPI dependency limiting a route to `max_requests`
    per `window_seconds`, keyed per (route path, client IP)."""

    def dependency(request: Request) -> None:
        client_host = request.client.host if request.client else "unknown"
        key = f"{request.url.path}:{client_host}"
        now = time.monotonic()

        bucket = _buckets[key]
        while bucket and now - bucket[0] > window_seconds:
            bucket.pop(0)

        if len(bucket) >= max_requests:
            raise HTTPException(status_code=429, detail="Too many requests. Please try again in a moment.")

        bucket.append(now)

    return dependency
