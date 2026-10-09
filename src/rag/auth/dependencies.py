"""FastAPI dependency injection for user authentication and authorization."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..config import Settings
from ..db.repository import UserRepository
from .security import decode_access_token

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> dict[str, Any]:
    """Retrieve and validate the currently authenticated user from Bearer token."""
    app_state = getattr(request.app.state, "app_state", None)
    if not app_state:
        raise HTTPException(status_code=500, detail="App state not initialized")

    settings: Settings = app_state.settings
    user_repo: UserRepository = app_state.user_repo

    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(
        credentials.credentials,
        secret_key=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = str(payload["sub"])
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def optional_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> dict[str, Any] | None:
    """Optionally extract authenticated user; returns None if anonymous."""
    try:
        return await get_current_user(request, credentials)
    except HTTPException:
        return None
