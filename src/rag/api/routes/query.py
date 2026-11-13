"""Grounded question answering route. Login is required."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, StringConstraints

from ...auth.dependencies import get_current_user
from ...logging import get_logger
from ...middleware.rate_limit import rate_limit_dependency
from ...models import Answer

log = get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["query"], dependencies=[Depends(rate_limit_dependency)])


class AskRequest(BaseModel):
    # Spaces are trimmed first, so a question of only spaces is rejected (422).
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    document_id: str | None = None


@router.post("/ask", response_model=Answer)
async def ask_question(
    req: AskRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> Answer:
    app_state = request.app.state.app_state
    user_id = str(current_user["id"])

    # Run the RAG pipeline, searching only this user's chunks.
    answer: Answer = await app_state.engine.answer(
        req.question,
        user_id=user_id,
        document_id=req.document_id,
    )

    # Save usage and history. A failure here must not hide the answer.
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
    except Exception as exc:
        log.warning("query.history_save_failed", error=str(exc))

    return answer
