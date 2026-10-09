"""Authentication utilities: secure password hashing and JWT token processing."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import timedelta
from typing import Any


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


def _b64encode_url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64decode_url(text: str) -> bytes:
    padding = 4 - (len(text) % 4)
    if padding < 4:
        text += "=" * padding
    return base64.urlsafe_b64decode(text.encode("utf-8"))


def create_access_token(
    data: dict[str, Any],
    secret_key: str,
    algorithm: str = "HS256",
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT token."""
    to_encode = data.copy()
    now = int(time.time())
    expire = now + int(expires_delta.total_seconds()) if expires_delta else now + (24 * 3600)
    to_encode.update({"iat": now, "exp": expire})

    # Standard JWT creation (robust, works without C-extensions)
    header = {"typ": "JWT", "alg": algorithm}
    h_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    p_bytes = json.dumps(to_encode, separators=(",", ":")).encode("utf-8")

    segment1 = _b64encode_url(h_bytes)
    segment2 = _b64encode_url(p_bytes)
    signing_input = f"{segment1}.{segment2}".encode()

    signature = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    segment3 = _b64encode_url(signature)

    return f"{segment1}.{segment2}.{segment3}"


def decode_access_token(
    token: str,
    secret_key: str,
    algorithm: str = "HS256",
) -> dict[str, Any] | None:
    """Decode and verify a signed JWT token."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        segment1, segment2, segment3 = parts
        signing_input = f"{segment1}.{segment2}".encode()

        expected_sig = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
        actual_sig = _b64decode_url(segment3)
        if not secrets.compare_digest(expected_sig, actual_sig):
            return None

        payload_bytes = _b64decode_url(segment2)
        payload = json.loads(payload_bytes.decode("utf-8"))

        # Verify expiration
        exp = payload.get("exp")
        if exp is not None and int(exp) < int(time.time()):
            return None

        return payload
    except Exception:
        return None
