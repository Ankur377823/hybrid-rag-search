"""Usage analytics and query history routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from ...auth.dependencies import get_current_user
from ...middleware.rate_limit import rate_limit_dependency

router = APIRouter(prefix="/v1", tags=["analytics"], dependencies=[Depends(rate_limit_dependency)])


@router.get("/usage", response_model=dict[str, Any])
async def get_usage(
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    app_state = request.app.state.app_state
    return await app_state.usage_repo.get_summary(current_user["id"])


@router.get("/history", response_model=list[dict[str, Any]])
async def get_history(
    request: Request,
    limit: int = 30,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    app_state = request.app.state.app_state
    return await app_state.history_repo.list_recent(current_user["id"], limit=limit)
