from __future__ import annotations

from pathlib import Path
import pytest

from rag.db.database import Database
from rag.db.repository import (
    DocumentRepository,
    HistoryRepository,
    UsageRepository,
    UserRepository,
    VersionRepository,
)


@pytest.fixture
async def test_db(tmp_path: Path) -> Database:
    db_file = tmp_path / "test_rag.db"
    db = Database(url="", environment="development", default_sqlite_path=db_file)
    await db.connect()
    yield db
    await db.disconnect()


@pytest.mark.asyncio
async def test_database_init_and_query_execution(test_db: Database) -> None:
    assert test_db.is_postgres is False
    row = await test_db.fetch_one("SELECT 1 AS num")
    assert row is not None
    assert row["num"] == 1

    rows = await test_db.fetch_all("SELECT 42 AS val")
    assert len(rows) == 1
    assert rows[0]["val"] == 42


@pytest.mark.asyncio
async def test_user_repository(test_db: Database) -> None:
    repo = UserRepository(test_db)

    # Create user
    user = await repo.create("alice@example.com", "hashed_pw_1")
    assert user["email"] == "alice@example.com"
    user_id = user["id"]

    # Get by email (case-insensitive)
    found = await repo.get_by_email("ALICE@EXAMPLE.COM")
    assert found is not None
    assert found["id"] == user_id

    # Get by ID
    by_id = await repo.get_by_id(user_id)
    assert by_id is not None
    assert by_id["email"] == "alice@example.com"

    # Update password
    await repo.update_password(user_id, "new_hashed_pw")
    updated = await repo.get_by_email("alice@example.com")
    assert updated is not None
    assert updated["password_hash"] == "new_hashed_pw"


@pytest.mark.asyncio
async def test_document_repository_crud_and_isolation(test_db: Database) -> None:
    u_repo = UserRepository(test_db)
    doc_repo = DocumentRepository(test_db)

    user_a = await u_repo.create("tenant_a@rag.io", "pass")
    user_b = await u_repo.create("tenant_b@rag.io", "pass")

    # User A creates a document
    doc_a = await doc_repo.create(
        user_id=user_a["id"],
        filename="report_q1.pdf",
        file_hash="hash_a1",
        chunk_count=5,
        size_bytes=1024,
    )
    assert doc_a["filename"] == "report_q1.pdf"
    assert doc_a["version"] == 1

    # User B creates a document with the same filename
    doc_b = await doc_repo.create(
        user_id=user_b["id"],
        filename="report_q1.pdf",
        file_hash="hash_b1",
        chunk_count=8,
        size_bytes=2048,
    )

    # User A lists documents - only gets doc_a
    docs_a = await doc_repo.list_by_user(user_a["id"])
    assert len(docs_a) == 1
    assert docs_a[0]["id"] == doc_a["id"]

    # User B lists documents - only gets doc_b
    docs_b = await doc_repo.list_by_user(user_b["id"])
    assert len(docs_b) == 1
    assert docs_b[0]["id"] == doc_b["id"]

    # User A cannot fetch User B's document
    isolated = await doc_repo.get_by_id(doc_b["id"], user_id=user_a["id"])
    assert isolated is None

    # User A cannot delete User B's document
    del_fail = await doc_repo.delete(doc_b["id"], user_id=user_a["id"])
    assert del_fail is False

    # User B can delete their own document
    del_ok = await doc_repo.delete(doc_b["id"], user_id=user_b["id"])
    assert del_ok is True
    assert await doc_repo.get_by_id(doc_b["id"], user_id=user_b["id"]) is None


@pytest.mark.asyncio
async def test_version_repository(test_db: Database) -> None:
    u_repo = UserRepository(test_db)
    doc_repo = DocumentRepository(test_db)
    ver_repo = VersionRepository(test_db)

    user = await u_repo.create("version_tester@rag.io", "pass")
    doc = await doc_repo.create(
        user_id=user["id"],
        filename="spec.md",
        file_hash="hash_v1",
        chunk_count=3,
        size_bytes=500,
    )

    # Record v1
    v1 = await ver_repo.record_version(
        document_id=doc["id"],
        version_number=1,
        file_hash="hash_v1",
        storage_path="/data/v1_spec.md",
        chunk_count=3,
    )
    assert v1["version_number"] == 1

    # Record v2
    v2 = await ver_repo.record_version(
        document_id=doc["id"],
        version_number=2,
        file_hash="hash_v2",
        storage_path="/data/v2_spec.md",
        chunk_count=6,
    )
    assert v2["version_number"] == 2

    versions = await ver_repo.list_versions(doc["id"])
    assert len(versions) == 2
    assert versions[0]["version_number"] == 2  # DESC order
    assert versions[1]["version_number"] == 1


@pytest.mark.asyncio
async def test_usage_and_history_repository(test_db: Database) -> None:
    u_repo = UserRepository(test_db)
    usage_repo = UsageRepository(test_db)
    hist_repo = HistoryRepository(test_db)

    user = await u_repo.create("usage_tester@rag.io", "pass")
    uid = user["id"]

    # Record usage twice on the same day -> queries incremented, tokens summed
    await usage_repo.record_usage(uid, tokens=150)
    await usage_repo.record_usage(uid, tokens=200)

    summary = await usage_repo.get_summary(uid)
    assert summary["total_queries"] == 2
    assert summary["total_tokens_used"] == 350
    assert len(summary["daily_records"]) == 1

    # Add query history records
    await hist_repo.add(
        user_id=uid,
        question="What is RRF?",
        answer_text="RRF is fusion.",
        composite_confidence=0.88,
        is_idk=False,
        latency_ms=120,
    )
    await hist_repo.add(
        user_id=uid,
        question="Unknown query",
        answer_text="I don't know.",
        composite_confidence=0.15,
        is_idk=True,
        latency_ms=30,
    )

    history = await hist_repo.list_recent(uid, limit=10)
    assert len(history) == 2
    assert history[0]["question"] == "Unknown query"  # DESC order
    assert history[1]["question"] == "What is RRF?"
