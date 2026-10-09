"""Data Access Layer (Repository Pattern) for PostgreSQL and SQLite.

Clean, strongly typed repositories for:
- Users
- Documents
- Document Versions
- Usage Quotas & Metrics
- Query History
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from .database import Database


class UserRepository:
    def __init__(self, db: Database):
        self.db = db

    async def create(self, email: str, password_hash: str) -> dict[str, Any]:
        user_id = f"usr_{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC).isoformat()
        await self.db.execute(
            "INSERT INTO users (id, email, password_hash, created_at) VALUES ($1, $2, $3, $4)",
            user_id,
            email.lower().strip(),
            password_hash,
            now,
        )
        return {
            "id": user_id,
            "email": email.lower().strip(),
            "created_at": now,
        }

    async def get_by_email(self, email: str) -> dict[str, Any] | None:
        return await self.db.fetch_one(
            "SELECT * FROM users WHERE email = $1",
            email.lower().strip(),
        )

    async def get_by_id(self, user_id: str) -> dict[str, Any] | None:
        return await self.db.fetch_one(
            "SELECT id, email, created_at FROM users WHERE id = $1",
            user_id,
        )

    async def update_password(self, user_id: str, password_hash: str) -> None:
        await self.db.execute(
            "UPDATE users SET password_hash = $1 WHERE id = $2",
            password_hash,
            user_id,
        )


class DocumentRepository:
    def __init__(self, db: Database):
        self.db = db

    async def create(
        self,
        *,
        user_id: str,
        filename: str,
        file_hash: str,
        chunk_count: int,
        size_bytes: int,
        doc_id: str | None = None,
    ) -> dict[str, Any]:
        document_id = doc_id or f"doc_{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC).isoformat()
        await self.db.execute(
            """INSERT INTO documents
               (id, user_id, filename, file_hash, version, status, chunk_count, size_bytes, created_at, updated_at)
               VALUES ($1, $2, $3, $4, 1, 'indexed', $5, $6, $7, $8)""",
            document_id,
            user_id,
            filename,
            file_hash,
            chunk_count,
            size_bytes,
            now,
            now,
        )
        return {
            "id": document_id,
            "user_id": user_id,
            "filename": filename,
            "file_hash": file_hash,
            "version": 1,
            "status": "indexed",
            "chunk_count": chunk_count,
            "size_bytes": size_bytes,
            "created_at": now,
            "updated_at": now,
        }

    async def get_by_id(self, document_id: str, user_id: str) -> dict[str, Any] | None:
        return await self.db.fetch_one(
            "SELECT * FROM documents WHERE id = $1 AND user_id = $2",
            document_id,
            user_id,
        )

    async def get_by_hash(self, user_id: str, file_hash: str) -> dict[str, Any] | None:
        return await self.db.fetch_one(
            "SELECT * FROM documents WHERE user_id = $1 AND file_hash = $2",
            user_id,
            file_hash,
        )

    async def get_by_filename(self, user_id: str, filename: str) -> dict[str, Any] | None:
        return await self.db.fetch_one(
            "SELECT * FROM documents WHERE user_id = $1 AND LOWER(filename) = LOWER($2)",
            user_id,
            filename,
        )

    async def list_by_user(self, user_id: str) -> list[dict[str, Any]]:
        return await self.db.fetch_all(
            "SELECT * FROM documents WHERE user_id = $1 ORDER BY updated_at DESC",
            user_id,
        )

    async def update_version(
        self,
        *,
        document_id: str,
        user_id: str,
        file_hash: str,
        chunk_count: int,
        size_bytes: int,
        new_version: int,
    ) -> dict[str, Any] | None:
        now = datetime.now(UTC).isoformat()
        await self.db.execute(
            """UPDATE documents
               SET version = $1, file_hash = $2, chunk_count = $3, size_bytes = $4, updated_at = $5, status = 'indexed'
               WHERE id = $6 AND user_id = $7""",
            new_version,
            file_hash,
            chunk_count,
            size_bytes,
            now,
            document_id,
            user_id,
        )
        return await self.get_by_id(document_id, user_id)

    async def delete(self, document_id: str, user_id: str) -> bool:
        doc = await self.get_by_id(document_id, user_id)
        if not doc:
            return False
        await self.db.execute(
            "DELETE FROM documents WHERE id = $1 AND user_id = $2",
            document_id,
            user_id,
        )
        return True


class VersionRepository:
    def __init__(self, db: Database):
        self.db = db

    async def record_version(
        self,
        *,
        document_id: str,
        version_number: int,
        file_hash: str,
        storage_path: str,
        chunk_count: int,
        status: str = "indexed",
    ) -> dict[str, Any]:
        ver_id = f"ver_{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC).isoformat()
        await self.db.execute(
            """INSERT INTO document_versions
               (id, document_id, version_number, file_hash, storage_path, chunk_count, status, created_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
            ver_id,
            document_id,
            version_number,
            file_hash,
            storage_path,
            chunk_count,
            status,
            now,
        )
        return {
            "id": ver_id,
            "document_id": document_id,
            "version_number": version_number,
            "file_hash": file_hash,
            "storage_path": storage_path,
            "chunk_count": chunk_count,
            "status": status,
            "created_at": now,
        }

    async def list_versions(self, document_id: str) -> list[dict[str, Any]]:
        return await self.db.fetch_all(
            "SELECT * FROM document_versions WHERE document_id = $1 ORDER BY version_number DESC",
            document_id,
        )


class UsageRepository:
    def __init__(self, db: Database):
        self.db = db

    async def record_usage(self, user_id: str, tokens: int = 0) -> None:
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        existing = await self.db.fetch_one(
            "SELECT * FROM usage_records WHERE user_id = $1 AND date = $2",
            user_id,
            today,
        )
        if existing:
            await self.db.execute(
                """UPDATE usage_records
                   SET queries = queries + 1, tokens_used = tokens_used + $1
                   WHERE user_id = $2 AND date = $3""",
                tokens,
                user_id,
                today,
            )
        else:
            rec_id = f"usg_{uuid.uuid4().hex[:12]}"
            await self.db.execute(
                """INSERT INTO usage_records (id, user_id, date, queries, tokens_used)
                   VALUES ($1, $2, $3, 1, $4)""",
                rec_id,
                user_id,
                today,
                tokens,
            )

    async def get_summary(self, user_id: str) -> dict[str, Any]:
        rows = await self.db.fetch_all(
            "SELECT * FROM usage_records WHERE user_id = $1 ORDER BY date DESC LIMIT 30",
            user_id,
        )
        total_queries = sum(r.get("queries", 0) for r in rows)
        total_tokens = sum(r.get("tokens_used", 0) for r in rows)
        return {
            "total_queries": total_queries,
            "total_tokens_used": total_tokens,
            "daily_records": rows,
        }


class HistoryRepository:
    def __init__(self, db: Database):
        self.db = db

    async def add(
        self,
        *,
        user_id: str,
        question: str,
        answer_text: str,
        composite_confidence: float,
        is_idk: bool,
        latency_ms: int,
        document_id: str | None = None,
    ) -> dict[str, Any]:
        qid = f"qry_{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC).isoformat()
        await self.db.execute(
            """INSERT INTO query_history
               (id, user_id, question, document_id, answer_text, composite_confidence, is_idk, latency_ms, created_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
            qid,
            user_id,
            question,
            document_id,
            answer_text,
            composite_confidence,
            bool(is_idk),
            latency_ms,
            now,
        )
        return {
            "id": qid,
            "user_id": user_id,
            "question": question,
            "document_id": document_id,
            "answer_text": answer_text,
            "composite_confidence": composite_confidence,
            "is_idk": is_idk,
            "latency_ms": latency_ms,
            "created_at": now,
        }

    async def list_recent(self, user_id: str, limit: int = 30) -> list[dict[str, Any]]:
        return await self.db.fetch_all(
            "SELECT * FROM query_history WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
            user_id,
            limit,
        )
