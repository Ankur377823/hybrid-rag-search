"""Authentication utilities: password hashing and JWT tokens.

Passwords: PBKDF2-HMAC-SHA256 from the Python standard library.
Tokens:    the PyJWT library (signing, signature check and expiry check).
"""

from __future__ import annotations

import hashlib
import secrets
import time
from datetime import timedelta
from typing import Any

import jwt

DEFAULT_TOKEN_LIFETIME_SECONDS = 24 * 3600


def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with 100,000 iterations and random salt."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations=100_000,
    )
    return f"pbkdf2_sha256$100000${salt}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against stored PBKDF2 hash using constant-time comparison."""
    try:
        parts = hashed_password.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = parts[2]
        stored_hash = parts[3]
        computed = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations=iterations,
        )
        return secrets.compare_digest(computed.hex(), stored_hash)
    except Exception:
        return False


def create_access_token(
    data: dict[str, Any],
    secret_key: str,
    algorithm: str = "HS256",
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT. Adds `iat` (issued at) and `exp` (expires at)."""
    now = int(time.time())
    lifetime = (
        int(expires_delta.total_seconds()) if expires_delta else DEFAULT_TOKEN_LIFETIME_SECONDS
    )
    payload = {**data, "iat": now, "exp": now + lifetime}
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_access_token(
    token: str,
    secret_key: str,
    algorithm: str = "HS256",
) -> dict[str, Any] | None:
    """Return the token's payload, or None if it is invalid or expired.

    `algorithms=[algorithm]` is important: only the algorithm we signed with is
    accepted, so a token cannot choose a weaker one for itself.
    """
    try:
        payload: dict[str, Any] = jwt.decode(token, secret_key, algorithms=[algorithm])
    except jwt.PyJWTError:
        return None
    return payload
