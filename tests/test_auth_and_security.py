from __future__ import annotations

from datetime import timedelta
import time
import pytest
from fastapi import HTTPException

from rag.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from rag.middleware.rate_limit import RateLimiter


def test_password_hashing_and_verification() -> None:
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)

    assert hashed.startswith("pbkdf2_sha256$100000$")
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword", hashed) is False
    assert verify_password(password, "invalid_hash_string") is False
    assert verify_password(password, "pbkdf2_sha256$100000$short") is False


def test_jwt_create_and_decode_valid() -> None:
    secret = "test-secret-key"
    payload = {"sub": "user_123", "email": "test@example.com", "role": "admin"}
    token = create_access_token(payload, secret_key=secret, expires_delta=timedelta(minutes=30))

    assert isinstance(token, str)
    decoded = decode_access_token(token, secret_key=secret)
    assert decoded is not None
    assert decoded["sub"] == "user_123"
    assert decoded["email"] == "test@example.com"
    assert "exp" in decoded
    assert "iat" in decoded


def test_jwt_invalid_secret_or_tampered() -> None:
    secret = "correct-secret"
    wrong_secret = "wrong-secret"
    payload = {"sub": "user_456"}
    token = create_access_token(payload, secret_key=secret)

    # Decoding with wrong secret returns None
    assert decode_access_token(token, secret_key=wrong_secret) is None

    # Tampered token returns None
    tampered = token[:-5] + "XXXXX"
    assert decode_access_token(tampered, secret_key=secret) is None

    # Malformed token returns None
    assert decode_access_token("not-a-valid-token", secret_key=secret) is None


def test_jwt_expired_token() -> None:
    secret = "test-secret"
    payload = {"sub": "user_expired"}
    # Token that expired 10 seconds ago
    token = create_access_token(payload, secret_key=secret, expires_delta=timedelta(seconds=-10))

    assert decode_access_token(token, secret_key=secret) is None


def test_rate_limiter_allows_under_limit_and_blocks_over() -> None:
    limiter = RateLimiter(requests_per_minute=3)
    client_key = "192.168.1.100"

    # 3 requests should succeed
    limiter.check(client_key)
    limiter.check(client_key)
    limiter.check(client_key)

    # 4th request must raise 429 Too Many Requests
    with pytest.raises(HTTPException) as exc_info:
        limiter.check(client_key)
    assert exc_info.value.status_code == 429
    assert "Rate limit exceeded" in exc_info.value.detail


def test_rate_limiter_isolates_different_keys() -> None:
    limiter = RateLimiter(requests_per_minute=2)
    key_a = "client_A"
    key_b = "client_B"

    limiter.check(key_a)
    limiter.check(key_a)

    # Key A is exhausted
    with pytest.raises(HTTPException):
        limiter.check(key_a)

    # Key B can still make requests
    limiter.check(key_b)
    limiter.check(key_b)
