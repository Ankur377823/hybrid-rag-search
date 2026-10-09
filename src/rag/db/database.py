"""Database engine and session management.

Supports PostgreSQL (including Neon Serverless with sslmode=require)
and falls back to SQLite for local development and CI testing.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from ..logging import get_logger
from .schema import POSTGRES_SCHEMA, SQLITE_SCHEMA

log = get_logger(__name__)


class Database:
    """Async database abstraction for PostgreSQL and SQLite."""

    def __init__(
        self,
        url: str = "",
        environment: str = "development",
        default_sqlite_path: Path = Path("./data/rag.db"),
    ):
        self.raw_url = url.strip()
        self.environment = environment.lower().strip()
        self.default_sqlite_path = default_sqlite_path

        # Check whether PostgreSQL is configured or requested
        if self.raw_url.startswith(("postgresql://", "postgres://")) or self.environment in ("production", "deployment", "prod"):
            self.is_postgres = True
        else:
            self.is_postgres = False

        self._pool: Any = None
        self._sqlite_conn: Any = None

    async def connect(self) -> None:
        if self.is_postgres:
            if not self.raw_url:
                raise ValueError("RAG_DATABASE_URL or DATABASE_URL must be specified for PostgreSQL in production.")
            try:
                import ssl
                from urllib.parse import urlparse, urlunparse

                import asyncpg  # type: ignore

                parsed = urlparse(self.raw_url)
                # Standardize scheme for asyncpg
                clean_scheme = "postgresql" if parsed.scheme in ("postgres", "postgresql") else parsed.scheme
                clean_url = urlunparse((clean_scheme, parsed.netloc, parsed.path, "", "", ""))

                hostname = parsed.hostname or ""
                requires_ssl = (
                    "sslmode=require" in self.raw_url
                    or "sslmode=no-verify" in self.raw_url
                    or "neon.tech" in hostname
                    or "render.com" in hostname
                    or hostname not in ("localhost", "127.0.0.1", "postgres", "db")
                )

                if requires_ssl:
                    ssl_ctx = ssl.create_default_context()
                    ssl_ctx.check_hostname = False
                    ssl_ctx.verify_mode = ssl.CERT_NONE
                    self._pool = await asyncpg.create_pool(clean_url, ssl=ssl_ctx, min_size=1, max_size=10)
                else:
                    self._pool = await asyncpg.create_pool(clean_url, min_size=1, max_size=10)

                async with self._pool.acquire() as conn:
                    await conn.execute(POSTGRES_SCHEMA)
                log.info("db.connected", kind="postgresql", mode="deployment", host=hostname)
                return
            except Exception as exc:
                log.error("db.postgres_connection_failed", error=str(exc))
                if self.environment in ("production", "deployment", "prod"):
                    raise RuntimeError(f"Database connection to PostgreSQL failed in production mode: {exc}") from exc
                self.is_postgres = False

        # SQLite for local development
        self.default_sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        import sqlite3

        self._sqlite_conn = sqlite3.connect(
            str(self.default_sqlite_path), check_same_thread=False
        )
        self._sqlite_conn.row_factory = sqlite3.Row
        self._sqlite_conn.execute("PRAGMA foreign_keys = ON;")
        self._sqlite_conn.executescript(SQLITE_SCHEMA)
        self._sqlite_conn.commit()
        log.info("db.connected", kind="sqlite", mode="local_development", path=str(self.default_sqlite_path))

    async def disconnect(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
        if self._sqlite_conn is not None:
            self._sqlite_conn.close()
            self._sqlite_conn = None

    async def execute(self, query: str, *args: Any) -> Any:
        if self.is_postgres and self._pool is not None:
            from datetime import datetime as dt_cls
            clean_args = [
                dt_cls.fromisoformat(a) if (isinstance(a, str) and "T" in a and len(a) >= 19 and a[0:4].isdigit()) else a
                for a in args
            ]
            async with self._pool.acquire() as conn:
                return await conn.execute(query, *clean_args)
        else:
            # SQLite uses ? instead of $1, $2
            converted_query = self._to_sqlite_placeholders(query)
            loop = asyncio.get_running_loop()

            def _sync_exec() -> None:
                cur = self._sqlite_conn.cursor()
                cur.execute(converted_query, args)
                self._sqlite_conn.commit()

            return await loop.run_in_executor(None, _sync_exec)

    async def fetch_one(self, query: str, *args: Any) -> dict[str, Any] | None:
        if self.is_postgres and self._pool is not None:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, *args)
                return dict(row) if row else None
        else:
            converted_query = self._to_sqlite_placeholders(query)
            loop = asyncio.get_running_loop()

            def _sync_fetch() -> dict[str, Any] | None:
                cur = self._sqlite_conn.cursor()
                cur.execute(converted_query, args)
                row = cur.fetchone()
                return dict(row) if row else None

            return await loop.run_in_executor(None, _sync_fetch)

    async def fetch_all(self, query: str, *args: Any) -> list[dict[str, Any]]:
        if self.is_postgres and self._pool is not None:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, *args)
                return [dict(r) for r in rows]
        else:
            converted_query = self._to_sqlite_placeholders(query)
            loop = asyncio.get_running_loop()

            def _sync_fetch_all() -> list[dict[str, Any]]:
                cur = self._sqlite_conn.cursor()
                cur.execute(converted_query, args)
                rows = cur.fetchall()
                return [dict(r) for r in rows]

            return await loop.run_in_executor(None, _sync_fetch_all)

    @staticmethod
    def _to_sqlite_placeholders(query: str) -> str:
        """Convert $1, $2, $3 to ? for SQLite compatibility."""
        import re

        return re.sub(r"\$\d+", "?", query)
