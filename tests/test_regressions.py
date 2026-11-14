"""One test per bug that was found and fixed, so none of them can come back.

Each test name says what must be true. Read the docstring for the old bug.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient

from rag.auth.security import create_access_token, decode_access_token
from rag.generation.answerer import is_idk_text
from rag.ingestion import IngestionPipeline
from rag.middleware.rate_limit import RateLimiter, client_key
from rag.models import Chunk, ChunkingStrategy, Document, DocumentFormat
from rag.retrieval import HybridRetriever, NoOpReranker
from rag.store import BM25Store, DenseVectorStore

from .conftest import ADMIN_EMAIL, ADMIN_PASSWORD, login_headers

TEST_SECRET = "regression-test-secret-0123456789-abcdef"
SECRET_FACT = b"# Private notes\nThe launch code for project Heron is 7421.\n"


def _chunk(chunk_id: str, text: str, user_id: str | None, document_id: str = "doc") -> Chunk:
    metadata = {"document_id": document_id}
    if user_id:
        metadata["user_id"] = user_id
    return Chunk(
        chunk_id=chunk_id,
        source="test",
        text=text,
        strategy=ChunkingStrategy.FIXED,
        position=0,
        char_start=0,
        char_end=len(text),
        metadata=metadata,
    )


class _SameVectorClient:
    """Fake LLM client: every text gets the same embedding."""

    def __init__(self, vector: list[float]):
        self._vector = vector

    async def embed_batch(self, model: str, texts: list[str]) -> list[list[float]]:
        return [list(self._vector) for _ in texts]


def _retriever(dense: DenseVectorStore, sparse: BM25Store, vector: list[float]) -> HybridRetriever:
    client: Any = _SameVectorClient(vector)
    return HybridRetriever(
        client=client,
        embedding_model="m",
        dense=dense,
        sparse=sparse,
        reranker=NoOpReranker(),
    )


# --------------------------------------------------------------- security


def test_ask_requires_login(full_app_client: TestClient) -> None:
    """Old bug: /v1/ask answered anonymous callers from every user's documents."""
    headers = login_headers(full_app_client)
    r = full_app_client.post(
        "/v1/documents", headers=headers, files={"file": ("private.md", SECRET_FACT)}
    )
    assert r.status_code == 200

    question = {"question": "What is the launch code for project Heron?"}
    assert full_app_client.post("/v1/ask", json=question).status_code == 401
    bad_token = {"Authorization": "Bearer not-a-real-token"}
    assert full_app_client.post("/v1/ask", headers=bad_token, json=question).status_code == 401
    assert full_app_client.post("/v1/ask", headers=headers, json=question).status_code == 200


def test_server_path_ingest_endpoint_is_gone(full_app_client: TestClient, tmp_path: Path) -> None:
    """Old bug: POST /v1/ingest let anyone index (and then read) any server file."""
    secret = tmp_path / "secret.txt"
    secret.write_text("top secret", encoding="utf-8")
    r = full_app_client.post("/v1/ingest", json={"path": str(secret)})
    assert r.status_code in (404, 405)
    assert full_app_client.get("/health").json()["n_chunks_dense"] == 0


def test_rate_limit_key_ignores_fake_authorization_headers() -> None:
    """Old bug: the raw header was the key, so a new fake header each time was never limited."""
    settings = SimpleNamespace(jwt_secret=TEST_SECRET, jwt_algorithm="HS256")
    app = SimpleNamespace(state=SimpleNamespace(app_state=SimpleNamespace(settings=settings)))

    def request_with(header: str) -> Any:
        return SimpleNamespace(
            headers={"Authorization": header}, app=app, client=SimpleNamespace(host="9.9.9.9")
        )

    assert client_key(request_with("Bearer fake-1")) == "ip:9.9.9.9"
    assert client_key(request_with("Bearer fake-2")) == "ip:9.9.9.9"
    assert client_key(request_with("")) == "ip:9.9.9.9"

    real = create_access_token({"sub": "usr_1"}, secret_key=TEST_SECRET)
    assert client_key(request_with(f"Bearer {real}")) == "user:usr_1"


def test_rate_limiter_forgets_idle_clients() -> None:
    """Old bug: one entry per client was kept forever."""
    limiter = RateLimiter(requests_per_minute=5)
    limiter.MAX_TRACKED_KEYS = 3
    limiter._history = {f"ip:{i}": [0.0] for i in range(3)}  # very old requests
    limiter.check("ip:new")
    assert list(limiter._history) == ["ip:new"]


def test_login_token_uses_configured_expiry(full_app_client: TestClient) -> None:
    """Old bug: RAG_JWT_EXPIRE_MINUTES was ignored (always 24 hours)."""
    settings = full_app_client.app.state.app_state.settings  # type: ignore[attr-defined]
    settings.jwt_expire_minutes = 5
    r = full_app_client.post(
        "/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    payload = decode_access_token(r.json()["access_token"], secret_key=settings.jwt_secret)
    assert payload is not None
    assert payload["exp"] - payload["iat"] == 5 * 60


# ----------------------------------------------------------------- search


def test_other_users_chunks_cannot_crowd_out_my_results(tmp_path: Path) -> None:
    """Old bug: top-20 was taken across all users first, then filtered -> 0 results."""
    dense = DenseVectorStore(tmp_path / "d.json")
    sparse = BM25Store(tmp_path / "s.json")
    chunks = [_chunk(f"b{i}", f"zorblatt port guide {i}", "userB", "docB") for i in range(30)]
    vectors = [[1.0, 0.001 * i] for i in range(30)]
    chunks.append(_chunk("a1", "zorblatt port is 7421", "userA", "docA"))
    vectors.append([0.9, 0.4])
    dense.upsert(chunks, vectors)
    sparse.upsert(chunks)
    retriever = _retriever(dense, sparse, [1.0, 0.0])

    hits = asyncio.run(retriever.retrieve("zorblatt port guide", user_id="userA"))
    assert [h.chunk.chunk_id for h in hits] == ["a1"]

    hits = asyncio.run(
        retriever.retrieve("zorblatt port guide", user_id="userA", document_id="docA")
    )
    assert [h.chunk.chunk_id for h in hits] == ["a1"]


def test_chunks_without_an_owner_are_hidden_from_logged_in_users(tmp_path: Path) -> None:
    """Old bug: a chunk with no user_id was visible to every user."""
    dense = DenseVectorStore(tmp_path / "d.json")
    sparse = BM25Store(tmp_path / "s.json")
    chunks = [_chunk("shared", "alpha beta", None), _chunk("mine", "alpha gamma", "userA")]
    dense.upsert(chunks, [[1.0, 0.0], [1.0, 0.1]])
    sparse.upsert(chunks)
    retriever = _retriever(dense, sparse, [1.0, 0.0])

    hits = asyncio.run(retriever.retrieve("alpha", user_id="userA"))
    assert [h.chunk.chunk_id for h in hits] == ["mine"]

    # The local CLI passes no user and may search everything.
    hits = asyncio.run(retriever.retrieve("alpha"))
    assert {h.chunk.chunk_id for h in hits} == {"shared", "mine"}


def test_no_reranker_still_gives_usable_confidence(tmp_path: Path) -> None:
    """Old bug: with rerank 'none' the score was the raw RRF value (~0.03) -> always IDK."""
    dense = DenseVectorStore(tmp_path / "d.json")
    sparse = BM25Store(tmp_path / "s.json")
    chunks = [_chunk("c1", "alpha beta gamma", "u1")]
    dense.upsert(chunks, [[1.0, 0.0]])
    sparse.upsert(chunks)
    retriever = _retriever(dense, sparse, [1.0, 0.0])

    hits = asyncio.run(retriever.retrieve("alpha beta gamma", user_id="u1"))
    assert hits[0].score == 1.0  # rank 1 in both lists = best possible
    assert 0.0 < hits[0].rrf_score < 0.05  # the raw value is still reported
    assert HybridRetriever.aggregate_confidence(hits) >= 0.35


def test_idk_detection_handles_curly_apostrophe() -> None:
    """Old bug: a refusal written with a curly apostrophe was not recognised."""
    assert is_idk_text("I don't know.")
    assert is_idk_text("I don" + chr(0x2019) + "t know.")
    assert is_idk_text("  i dont know")
    assert not is_idk_text("The port is 7421 [1].")


# ---------------------------------------------------------------- storage


def test_corrupt_index_file_is_kept_as_backup(tmp_path: Path) -> None:
    """Old bug: a half-written index loaded as empty and was then overwritten."""
    path = tmp_path / "dense.json"
    store = DenseVectorStore(path)
    store.upsert([_chunk("c1", "hello", "u1")], [[1.0, 0.0]])
    store.save()
    assert not (tmp_path / "dense.json.tmp").exists()  # the temp file was swapped in

    path.write_text(path.read_text(encoding="utf-8")[:40], encoding="utf-8")  # simulate damage
    reloaded = DenseVectorStore(path)
    assert len(reloaded) == 0
    assert (tmp_path / "dense.json.corrupt").exists()  # nothing was thrown away


def test_cli_ingest_removes_duplicates_inside_one_run(tmp_path: Path) -> None:
    """Old bug: duplicates were only checked against earlier runs, not within a run."""
    client: Any = _SameVectorClient([0.5, 0.5])
    pipeline = IngestionPipeline(
        client=client,
        embedding_model="m",
        dense=DenseVectorStore(tmp_path / "d.json"),
        sparse=BM25Store(tmp_path / "s.json"),
    )
    docs = [
        Document(source=f"f{i}.txt", format=DocumentFormat.TEXT, text="identical paragraph")
        for i in range(3)
    ]
    report = asyncio.run(pipeline.ingest(docs))
    assert report.n_chunks_added == 1
    assert report.n_chunks_deduplicated == 2


# -------------------------------------------------------------- documents


def test_unreadable_upload_returns_400(full_app_client: TestClient) -> None:
    """Old bug: a file with only spaces returned a 500 server error."""
    headers = login_headers(full_app_client)
    r = full_app_client.post(
        "/v1/documents", headers=headers, files={"file": ("blank.txt", b"   \n  ")}
    )
    assert r.status_code == 400


def test_update_with_new_filename_and_delete_cleans_up(
    full_app_client: TestClient, tmp_path: Path
) -> None:
    """Old bugs: a renamed update kept the old name; delete left raw files on disk."""
    headers = login_headers(full_app_client)
    r = full_app_client.post(
        "/v1/documents", headers=headers, files={"file": ("old-name.md", b"# One\nFirst text.")}
    )
    doc_id = r.json()["document"]["id"]

    r = full_app_client.put(
        f"/v1/documents/{doc_id}",
        headers=headers,
        files={"file": ("new-name.md", b"# Two\nSecond text.")},
    )
    assert r.status_code == 200
    assert r.json()["document"]["filename"] == "new-name.md"
    assert r.json()["document"]["version"] == 2

    uploads = tmp_path / "uploads"
    assert len(list(uploads.rglob("*.md"))) == 2

    assert full_app_client.delete(f"/v1/documents/{doc_id}", headers=headers).status_code == 204
    assert list(uploads.rglob("*.md")) == []
    assert full_app_client.get("/health").json()["n_chunks_dense"] == 0
