"""Tests for the hardening changes: PyJWT, production secret check, CORS,
semantic chunking for uploads, and real token usage."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from rag.api.app import create_app
from rag.auth.security import create_access_token, decode_access_token
from rag.config import DEFAULT_JWT_SECRET, Settings
from rag.db.database import Database
from rag.db.repository import DocumentRepository, UserRepository, VersionRepository
from rag.ingestion.document_manager import DocumentManager
from rag.llm_client import ChatMessage, LLMClient, track_token_usage
from rag.models import ChunkingStrategy
from rag.storage import FileStorage
from rag.store import BM25Store, DenseVectorStore

from .conftest import chat_response, login_headers

LONG_SECRET = "hardening-test-secret-" + "0123456789abcdef" * 4  # 86 bytes


# ------------------------------------------------------------------- JWT


def test_jwt_only_accepts_the_configured_algorithm() -> None:
    """A token must not be able to pick its own (weaker) algorithm."""
    good = create_access_token({"sub": "usr_1"}, secret_key=LONG_SECRET)
    payload = decode_access_token(good, secret_key=LONG_SECRET)
    assert payload is not None
    assert payload["sub"] == "usr_1"

    unsigned = jwt.encode({"sub": "usr_1"}, key=None, algorithm="none")
    assert decode_access_token(unsigned, secret_key=LONG_SECRET) is None

    other_algorithm = jwt.encode({"sub": "usr_1"}, LONG_SECRET, algorithm="HS512")
    assert decode_access_token(other_algorithm, secret_key=LONG_SECRET) is None


# ---------------------------------------------------------------- settings


def test_production_refuses_the_placeholder_jwt_secret() -> None:
    with pytest.raises(ValueError, match="RAG_JWT_SECRET"):
        Settings(_env_file=None, environment="production", jwt_secret=DEFAULT_JWT_SECRET)

    # A private secret is accepted in production; the placeholder is fine locally.
    Settings(_env_file=None, environment="production", jwt_secret=LONG_SECRET)
    Settings(_env_file=None, environment="development", jwt_secret=DEFAULT_JWT_SECRET)


def test_cors_origins_setting_is_parsed_into_a_list() -> None:
    settings = Settings(
        _env_file=None, cors_allowed_origins=" https://a.example, https://b.example ,"
    )
    assert settings.cors_origins == ["https://a.example", "https://b.example"]
    assert Settings(_env_file=None, cors_allowed_origins="").cors_origins == []


def test_cors_is_closed_by_default_and_opens_only_for_listed_sites(
    full_app_client: TestClient,
) -> None:
    r = full_app_client.get("/health", headers={"Origin": "https://other.example"})
    assert r.status_code == 200
    assert "access-control-allow-origin" not in r.headers

    state = full_app_client.app.state.app_state  # type: ignore[attr-defined]
    state.settings.cors_allowed_origins = "https://ok.example"
    client = TestClient(create_app(state))  # no `with`: startup is not needed here
    allowed = client.get("/health", headers={"Origin": "https://ok.example"})
    assert allowed.headers["access-control-allow-origin"] == "https://ok.example"
    blocked = client.get("/health", headers={"Origin": "https://other.example"})
    assert "access-control-allow-origin" not in blocked.headers


# ------------------------------------------------- semantic chunking (upload)


class _TopicClient:
    """Fake LLM client: 'cat' texts and 'stock' texts get different vectors."""

    def __init__(self) -> None:
        self.batch_sizes: list[int] = []

    async def embed_batch(self, model: str, texts: list[str]) -> list[list[float]]:
        self.batch_sizes.append(len(texts))
        return [[1.0, 0.0] if "cat" in t.lower() else [0.0, 1.0] for t in texts]


async def test_uploads_use_real_semantic_chunking(tmp_path: Path) -> None:
    """Old behaviour: 'semantic' silently fell back to recursive for uploads."""
    db = Database(url="", environment="development", default_sqlite_path=tmp_path / "t.db")
    await db.connect()
    try:
        user = await UserRepository(db).create("semantic@example.com", "not-a-real-hash")
        client: Any = _TopicClient()
        dense = DenseVectorStore(tmp_path / "d.json")
        manager = DocumentManager(
            client=client,
            embedding_model="m",
            dense=dense,
            sparse=BM25Store(tmp_path / "s.json"),
            doc_repo=DocumentRepository(db),
            ver_repo=VersionRepository(db),
            storage=FileStorage(root_dir=tmp_path / "uploads"),
            strategy=ChunkingStrategy.SEMANTIC,
            semantic_min_tokens=3,
            semantic_max_tokens=900,
            embedding_batch_size=3,
        )
        text = (
            b"Cats sleep most of the day. Cats like warm places. "
            b"Stock prices rose today. Stock markets closed higher."
        )
        record, _reindexed, _message = await manager.ingest_or_update(
            user_id=user["id"], filename="mixed.txt", content=text
        )
    finally:
        await db.disconnect()

    chunks = sorted(dense.all_chunks(), key=lambda c: c.position)
    # The topic changes once, so the four sentences become two chunks.
    assert record["chunk_count"] == 2
    assert [c.strategy for c in chunks] == [ChunkingStrategy.SEMANTIC] * 2
    assert "Cats like warm places." in chunks[0].text
    assert chunks[1].text.startswith("Stock prices rose today.")
    # 4 sentences were embedded in batches of at most 3, then the 2 chunks.
    assert client.batch_sizes == [3, 1, 2]


# ------------------------------------------------------------ token usage


def test_usage_records_the_real_token_count(full_app_client: TestClient) -> None:
    """Old behaviour: tokens were estimated by counting words."""
    headers = login_headers(full_app_client)
    r = full_app_client.post(
        "/v1/documents", headers=headers, files={"file": ("a.md", b"# Alpha\nAlpha is a letter.")}
    )
    assert r.status_code == 200

    answer = full_app_client.post(
        "/v1/ask", headers=headers, json={"question": "What is alpha?"}
    ).json()
    # The fake LLM reports 5 prompt + 5 completion tokens for its one answer call.
    assert answer["tokens_used"] == 10

    usage = full_app_client.get("/v1/usage", headers=headers).json()
    assert usage["total_tokens_used"] == 10
    assert usage["total_queries"] == 1


async def test_token_counters_of_parallel_requests_stay_separate(
    make_llm_client: Callable[[Callable[[httpx.Request], httpx.Response]], LLMClient],
) -> None:
    client = make_llm_client(lambda _request: chat_response("ok"))  # 10 tokens per call

    async def one_request(n_calls: int) -> int:
        with track_token_usage() as usage:
            await asyncio.gather(
                *(client.chat("m", [ChatMessage(role="user", content="hi")]) for _ in range(n_calls))
            )
        return usage.total

    try:
        totals = await asyncio.gather(one_request(2), one_request(5))
    finally:
        await client.aclose()
    assert totals == [20, 50]
