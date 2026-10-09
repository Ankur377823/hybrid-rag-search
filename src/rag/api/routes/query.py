"""Grounded question answering and search routes with multi-user isolation."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from ...auth.dependencies import optional_current_user
from ...middleware.rate_limit import rate_limit_dependency
from ...models import Answer

router = APIRouter(prefix="/v1", tags=["query"], dependencies=[Depends(rate_limit_dependency)])


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    document_id: str | None = None


@router.post("/ask", response_model=Answer)
async def ask_question(
    req: AskRequest,
    request: Request,
    user: dict[str, Any] | None = Depends(optional_current_user),
) -> Answer:
    app_state = request.app.state.app_state
    user_id = user["id"] if user else None

    # Execute grounded RAG pipeline scoped to the user (and optional document)
    answer = await app_state.engine.answer(
        req.question,
        user_id=user_id,
        document_id=req.document_id,
    )

    # Record usage & audit history if authenticated
    if user_id:
        try:
            tokens_estimate = len(req.question.split()) + len(answer.text.split())
            await app_state.usage_repo.record_usage(user_id, tokens=tokens_estimate)
            await app_state.history_repo.add(
                user_id=user_id,
                question=req.question,
                document_id=req.document_id,
                answer_text=answer.text,
                composite_confidence=answer.composite_confidence,
                is_idk=answer.is_idk,
                latency_ms=answer.latency_ms,
            )
        except Exception:
            pass

    return answer
