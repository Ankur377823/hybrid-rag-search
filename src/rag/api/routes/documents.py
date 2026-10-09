"""Document management and atomic versioning routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from ...auth.dependencies import get_current_user
from ...middleware.rate_limit import rate_limit_dependency

router = APIRouter(prefix="/v1/documents", tags=["documents"], dependencies=[Depends(rate_limit_dependency)])


class IngestDocumentResponse(BaseModel):
    document: dict[str, Any]
    reindexed: bool
    message: str


@router.post("", response_model=IngestDocumentResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> IngestDocumentResponse:
    app_state = request.app.state.app_state
    filename = file.filename or "uploaded_document"
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        doc, reindexed, msg = await app_state.doc_manager.ingest_or_update(
            user_id=current_user["id"],
            filename=filename,
            content=content,
        )
        return IngestDocumentResponse(document=doc, reindexed=reindexed, message=msg)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to process document: {exc}") from exc


@router.get("", response_model=list[dict[str, Any]])
async def list_documents(
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    app_state = request.app.state.app_state
    return await app_state.doc_repo.list_by_user(current_user["id"])


@router.get("/{document_id}", response_model=dict[str, Any])
async def get_document(
    document_id: str,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    app_state = request.app.state.app_state
    doc = await app_state.doc_repo.get_by_id(document_id, current_user["id"])
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


@router.put("/{document_id}", response_model=IngestDocumentResponse)
async def update_document(
    document_id: str,
    request: Request,
    file: UploadFile = File(...),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> IngestDocumentResponse:
    """Atomic re-indexing and version bump."""
    app_state = request.app.state.app_state
    existing = await app_state.doc_repo.get_by_id(document_id, current_user["id"])
    if not existing:
        raise HTTPException(status_code=404, detail="Document not found.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    filename = file.filename or existing["filename"]

    try:
        doc, reindexed, msg = await app_state.doc_manager.ingest_or_update(
            user_id=current_user["id"],
            filename=filename,
            content=content,
            doc_id=document_id,
        )
        return IngestDocumentResponse(document=doc, reindexed=reindexed, message=msg)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update document: {exc}") from exc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> None:
    app_state = request.app.state.app_state
    deleted = await app_state.doc_manager.delete_document(document_id, current_user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found.")


@router.get("/{document_id}/versions", response_model=list[dict[str, Any]])
async def get_document_versions(
    document_id: str,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    app_state = request.app.state.app_state
    doc = await app_state.doc_repo.get_by_id(document_id, current_user["id"])
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return await app_state.ver_repo.list_versions(document_id)
