"""In-memory sliding window rate limiter for API endpoints."""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request, status


class RateLimiter:
    """Thread-safe sliding-window rate limiter per client key."""

    def __init__(self, requests_per_minute: int = 60):
        self.limit = requests_per_minute
        self.window = 60.0  # seconds
        self._history: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, key: str) -> None:
        now = time.time()
        cutoff = now - self.window
        with self._lock:
            timestamps = self._history[key]
            # Prune expired timestamps
            self._history[key] = [t for t in timestamps if t > cutoff]
            if len(self._history[key]) >= self.limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded: maximum {self.limit} requests per minute.",
                    headers={"Retry-After": "60"},
                )
            self._history[key].append(now)


_default_limiter = RateLimiter(60)


async def rate_limit_dependency(request: Request) -> None:
    """FastAPI dependency to rate limit by client IP or Authorization header."""
    client_ip = request.client.host if request.client else "unknown"
    auth_header = request.headers.get("Authorization", "")
    key = auth_header if auth_header else client_ip
    _default_limiter.check(key)
