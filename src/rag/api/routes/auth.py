"""Authentication routes: registration, login, and user profile."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from ...auth.dependencies import get_current_user
from ...auth.security import create_access_token, hash_password, verify_password
from ...middleware.rate_limit import rate_limit_dependency

router = APIRouter(prefix="/v1/auth", tags=["auth"], dependencies=[Depends(rate_limit_dependency)])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest, request: Request) -> AuthResponse:
    app_state = request.app.state.app_state
    norm_email = req.email.lower().strip()
    user = await app_state.user_repo.get_by_email(norm_email)

    if not user or not verify_password(req.password, user.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    token = create_access_token(
        data={"sub": user["id"], "email": user["email"]},
        secret_key=app_state.settings.jwt_secret,
        algorithm=app_state.settings.jwt_algorithm,
    )
    return AuthResponse(
        access_token=token,
        user={"id": user["id"], "email": user["email"], "created_at": user["created_at"]},
    )


@router.get("/me", response_model=dict[str, Any])
async def me(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return current_user
