"""In-memory sliding window rate limiter for API endpoints."""

from __future__ import annotations

import time
from threading import Lock

from fastapi import HTTPException, Request, status

from ..auth.security import decode_access_token


class RateLimiter:
    """Thread-safe sliding-window rate limiter per client key."""

    MAX_TRACKED_KEYS = 10_000

    def __init__(self, requests_per_minute: int = 60):
        self.limit = requests_per_minute
        self.window = 60.0  # seconds
        self._history: dict[str, list[float]] = {}
        self._lock = Lock()

    def check(self, key: str) -> None:
        """Record one request for `key`. Raises HTTP 429 when over the limit."""
        now = time.time()
        cutoff = now - self.window
        with self._lock:
            recent = [t for t in self._history.get(key, []) if t > cutoff]
            if len(recent) >= self.limit:
                self._history[key] = recent
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded: maximum {self.limit} requests per minute.",
                    headers={"Retry-After": "60"},
                )
            recent.append(now)
            self._history[key] = recent
            if len(self._history) > self.MAX_TRACKED_KEYS:
                self._forget_idle_keys(cutoff)

    def reset(self) -> None:
        with self._lock:
            self._history.clear()

    def _forget_idle_keys(self, cutoff: float) -> None:
        """Drop clients with no request inside the window, so memory stays bounded."""
        idle = [key for key, times in self._history.items() if not times or times[-1] <= cutoff]
        for key in idle:
            del self._history[key]


_default_limiter = RateLimiter(60)


def client_key(request: Request) -> str:
    """Who is making this request, for rate-limit counting.

    - A VALID login token  -> counted per user id.
    - Anything else        -> counted per IP address.

    The raw Authorization header is never used as the key: a caller could send
    a different fake header on every request and never be limited.
    """
    auth_header = request.headers.get("Authorization", "")
    app_state = getattr(request.app.state, "app_state", None)
    settings = getattr(app_state, "settings", None)
    if settings is not None and auth_header.lower().startswith("bearer "):
        payload = decode_access_token(
            auth_header[7:].strip(),
            secret_key=settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
        if payload and "sub" in payload:
            return f"user:{payload['sub']}"
    client_ip = request.client.host if request.client else "unknown"
    return f"ip:{client_ip}"


async def rate_limit_dependency(request: Request) -> None:
    """FastAPI dependency: rate limit every request by user id or IP address."""
    _default_limiter.check(client_key(request))
