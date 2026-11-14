"""Shared fixtures: deterministic embedding model + httpx-mocked LLMClient."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from rag.api.app import AppState, create_app
from rag.config import Settings
from rag.db.database import Database
from rag.db.repository import (
    DocumentRepository,
    HistoryRepository,
    UsageRepository,
    UserRepository,
    VersionRepository,
)
from rag.engine import RagEngine
from rag.generation import GroundedAnswerer
from rag.ingestion import IngestionPipeline
from rag.ingestion.document_manager import DocumentManager
from rag.llm_client import LLMClient
from rag.middleware.rate_limit import _default_limiter
from rag.models import ChunkingStrategy
from rag.retrieval import HybridRetriever, NoOpReranker
from rag.storage import FileStorage
from rag.store import BM25Store, DenseVectorStore

ADMIN_EMAIL = "admin@hybridrag.io"
ADMIN_PASSWORD = "AdminTestPassword123!"


def deterministic_embedding(text: str, dim: int = 32) -> list[float]:
    """Hash-derived pseudo-embedding. Stable across runs, no model needed."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    seeds = [b for b in digest]
    out: list[float] = []
    for i in range(dim):
        # Use sin of a hashed seed so values are smooth and reproducible.
        out.append(math.sin(seeds[i % len(seeds)] * (i + 1) / 11.0))
    return out


def chat_response(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5},
        },
    )


def chat_json(payload: dict[str, object]) -> httpx.Response:
    return chat_response(json.dumps(payload))


def embed_response(texts: list[str]) -> httpx.Response:
    return httpx.Response(
        200,
        json={"data": [{"embedding": deterministic_embedding(t)} for t in texts]},
    )


@pytest.fixture
def make_llm_client() -> Callable[[Callable[[httpx.Request], httpx.Response]], LLMClient]:
    """Factory yields LLMClients that own their underlying httpx transport.

    `LLMClient.__init__` defaults `_owns_client=False` when a transport is
    passed in; flipping it to True here means `await client.aclose()` actually
    frees the AsyncClient. Without this, pytest's strict-warning mode raises
    PytestUnraisableExceptionWarning when the loop is GC'd and tests fail
    non-deterministically depending on ordering.
    """

    def make(handler: Callable[[httpx.Request], httpx.Response]) -> LLMClient:
        transport = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = LLMClient(api_key="test", client=transport, max_retries=0)
        client._owns_client = True  # type: ignore[attr-defined]
        return client

    return make


def write_file(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def parse_json_input(body: bytes) -> dict[str, object]:
    return json.loads(body)


@pytest.fixture(autouse=True)
def _fresh_rate_limiter() -> None:
    """The limiter is one shared object; start every test with empty counters."""
    _default_limiter.reset()


@pytest.fixture
def full_app_client(
    make_llm_client: Callable[[Callable[[httpx.Request], httpx.Response]], LLMClient],
    tmp_path: Path,
) -> Iterator[TestClient]:
    """The complete app (auth + database + stores) with a fake LLM behind it."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/embeddings"):
            body = json.loads(request.content)
            return embed_response(body["input"])
        return chat_response("Stubbed answer.")

    client = make_llm_client(handler)
    dense = DenseVectorStore(tmp_path / "d.json")
    sparse = BM25Store(tmp_path / "s.json")
    pipeline = IngestionPipeline(
        client=client,
        embedding_model="text-embedding-3-small",
        dense=dense,
        sparse=sparse,
        strategy=ChunkingStrategy.FIXED,
    )
    retriever = HybridRetriever(
        client=client,
        embedding_model="text-embedding-3-small",
        dense=dense,
        sparse=sparse,
        reranker=NoOpReranker(),
        final_top_k=3,
    )
    answerer = GroundedAnswerer(client=client, model="gpt-4o", idk_retrieval_threshold=0.0)
    engine = RagEngine(
        client=client, retriever=retriever, answerer=answerer, judge_model="gpt-4o-mini"
    )
    settings = Settings(
        admin_email=ADMIN_EMAIL,
        admin_password=ADMIN_PASSWORD,
        jwt_secret="testing-jwt-secret-key-0123456789-abcdef",
    )
    db = Database(url="", environment="development", default_sqlite_path=tmp_path / "test.db")
    doc_repo = DocumentRepository(db)
    ver_repo = VersionRepository(db)
    storage = FileStorage(root_dir=tmp_path / "uploads")
    doc_manager = DocumentManager(
        client=client,
        embedding_model="text-embedding-3-small",
        dense=dense,
        sparse=sparse,
        doc_repo=doc_repo,
        ver_repo=ver_repo,
        storage=storage,
    )
    state = AppState(
        client=client,
        engine=engine,
        ingestion=pipeline,
        dense=dense,
        sparse=sparse,
        settings=settings,
        db=db,
        user_repo=UserRepository(db),
        doc_repo=doc_repo,
        ver_repo=ver_repo,
        usage_repo=UsageRepository(db),
        history_repo=HistoryRepository(db),
        doc_manager=doc_manager,
        storage=storage,
    )
    # The context manager runs startup (connect DB, create the admin user).
    with TestClient(create_app(state)) as test_client:
        yield test_client


def login_headers(client: TestClient) -> dict[str, str]:
    """Log in as the test admin and return the Authorization header."""
    r = client.post("/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
