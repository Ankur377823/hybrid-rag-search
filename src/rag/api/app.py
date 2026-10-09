"""FastAPI factory: modular routes, multi-user isolation, database, and auth."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..config import Settings
from ..db.database import Database
from ..db.repository import (
    DocumentRepository,
    HistoryRepository,
    UsageRepository,
    UserRepository,
    VersionRepository,
)
from ..engine import RagEngine
from ..ingestion.document_manager import DocumentManager
from ..ingestion.loaders import load_path
from ..ingestion.pipeline import IngestionPipeline
from ..llm_client import LLMClient
from ..models import IngestionReport
from ..storage import FileStorage
from ..store.dense import DenseVectorStore
from ..store.sparse import BM25Store
from .routes import (
    auth_router,
    documents_router,
    query_router,
    usage_router,
)

if TYPE_CHECKING:
    pass


@dataclass
class AppState:
    client: LLMClient
    engine: RagEngine
    ingestion: IngestionPipeline
    dense: DenseVectorStore
    sparse: BM25Store
    settings: Settings | None = None
    db: Database | None = None
    user_repo: UserRepository | None = None
    doc_repo: DocumentRepository | None = None
    ver_repo: VersionRepository | None = None
    usage_repo: UsageRepository | None = None
    history_repo: HistoryRepository | None = None
    doc_manager: DocumentManager | None = None
    storage: FileStorage | None = None

    def __post_init__(self) -> None:
        if self.settings is None:
            self.settings = Settings()


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    document_id: str | None = None


class IngestRequest(BaseModel):
    path: str = Field(min_length=1)


def create_app(state: AppState) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):  # type: ignore[no-untyped-def]
        if state.db:
            await state.db.connect()
            if state.user_repo and state.settings and state.settings.admin_email and state.settings.admin_password:
                try:
                    admin_email = state.settings.admin_email.lower().strip()
                    admin_user = await state.user_repo.get_by_email(admin_email)
                    from ..auth.security import hash_password, verify_password
                    if not admin_user:
                        await state.user_repo.create(admin_email, hash_password(state.settings.admin_password))
                    elif not verify_password(state.settings.admin_password, admin_user.get("password_hash", "")):
                        await state.user_repo.update_password(admin_user["id"], hash_password(state.settings.admin_password))
                except Exception as exc:
                    from ..logging import get_logger
                    get_logger(__name__).error("admin_user_seed_failed", error=str(exc))
        try:
            yield
        finally:
            if state.db:
                await state.db.disconnect()
            await state.client.aclose()

    app = FastAPI(
        title="rag-hybrid-search",
        version="0.2.0",
        description=(
            "Production-grade hybrid-search RAG with multi-user isolation, document "
            "versioning & atomic re-indexing, JWT authentication, and Neon PostgreSQL support."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.app_state = state

    # Register modular route collections
    app.include_router(auth_router)
    app.include_router(documents_router)
    app.include_router(query_router)
    app.include_router(usage_router)

    frontend_candidates = [
        Path.cwd() / "frontend",
        Path("/app/frontend"),
        Path(__file__).resolve().parent.parent.parent.parent / "frontend",
    ]
    frontend_dir = next((p for p in frontend_candidates if p.exists() and p.is_dir()), None)

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/app/" if frontend_dir else "/docs")

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, object]:
        return {
            "status": "ok",
            "database": "postgresql" if state.db and state.db.is_postgres else "sqlite",
            "n_chunks_dense": len(state.dense),
            "n_chunks_sparse": len(state.sparse),
        }

    # Backward compatibility endpoint for CLI & scripts
    @app.post("/v1/ingest", response_model=IngestionReport, tags=["ingest"])
    async def ingest(req: IngestRequest, request: Request) -> IngestionReport:
        s = cast(AppState, request.app.state.app_state)
        docs = list(load_path(Path(req.path)))
        return await s.ingestion.ingest(docs)

    if frontend_dir is not None:
        @app.get("/app", include_in_schema=False)
        async def app_redirect() -> RedirectResponse:
            return RedirectResponse(url="/app/")

        app.mount("/app", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    return app
