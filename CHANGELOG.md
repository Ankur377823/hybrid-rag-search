# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.2.0] — 2026-10-09

### Added
- **Multi-Tenant Database Isolation**:
  - Production PostgreSQL abstraction via `asyncpg` with connection pooling, SSL negotiation, and automated DDL schema migrations.
  - Zero-config SQLite fallback (`./data/rag.db`) for local development and testing.
  - Strongly typed repositories: `UserRepository`, `DocumentRepository`, `VersionRepository`, `UsageRepository`, and `HistoryRepository`.
  - Strict tenant isolation: document records, vector chunks, version history, query history, and usage metrics are strictly isolated by `user_id`.
- **Document Manager & Atomic Re-indexing**:
  - SHA-256 pre-extraction content hashing: identical uploads skip re-indexing at zero LLM/embedding cost.
  - Atomic index swap: old vector and BM25 chunks remain active until the new version is fully embedded and verified.
  - Full document revision audit log (`/v1/documents/{id}/versions`).
- **JWT Authentication & Security**:
  - Password hashing via SHA-256 with salts, token issuance, and expiration controls (`/v1/auth/login`, `/v1/auth/me`).
  - Per-user token usage metering and rate limiting middleware.
- **Web Studio Frontend**:
  - Responsive, dark-themed Web Studio interface with zero framework bloat (HTML5, Vanilla CSS, modular Vanilla JS).
  - Interactive search bar with confidence gauges, citation inspection modal, and grounded quote highlighting.
  - Document management dashboard with drag-and-drop upload, version timeline, and delete controls.
  - Real-time token quota and query metrics dashboard.
- **Render Cloud Deployment**:
  - Production Infrastructure-as-Code blueprint (`render.yaml`) declaring managed PostgreSQL (`rag-postgres`) and containerized Web Service (`rag-hybrid-search`).
  - Automatic detection and fallback for Render-injected `DATABASE_URL` and `PORT`.
- **Containerization**:
  - Bundled frontend directly into [Dockerfile](Dockerfile) with automatic static mounting at `/app`.
  - Updated `docker-compose.yml` with multi-container orchestration (FastAPI API + Nginx).

### Changed
- Refactored `HybridRetriever` candidate resolution to strictly enforce `user_id` filtering, preventing cross-tenant leakage.
- Updated `pyproject.toml` to include `asyncpg`, `pyjwt`, and `python-multipart`.
- Rewrote `README.md` to document the end-to-end architecture, PostgreSQL isolation, Render deployment, and complete API specifications.
- Expanded `.gitignore` to safely exclude local SQLite databases, uploads, certificates, and runtime artifacts.

---

## [0.1.0] — 2026-05-08

### Added
- Strict Pydantic v2 contracts (`Document`, `Chunk`, `DenseHit`, `SparseHit`, `FusedHit`, `RankedHit`, `Citation`, `Answer`, `EvalCase`).
- Multi-format ingestion loaders: markdown, txt, html (BeautifulSoup), pdf (pypdf).
- Three swappable chunking strategies behind one `Chunker` ABC: fixed-token, recursive-character, semantic (with embedding callback + sync fallback).
- `IngestionPipeline`: chunk → cosine-dedup (≥ 0.95) → dual-index. Incremental and idempotent (content-hash skip).
- Dense store: JSON-backed, NumPy cosine top-K, near-duplicate gate.
- Sparse store: `rank_bm25.BM25Okapi` rebuilt on corpus change, JSON persistence.
- Reciprocal Rank Fusion (`k = 60` default) over the two retrievers.
- Pluggable reranker: `NoOpReranker`, `LLMReranker` (default), `CrossEncoderReranker` (optional `[reranker]` extra).
- Grounded answerer with bracketed citations and hard IDK gate.
- Citation parser + LLM-as-judge verifier returning per-citation `supported` booleans.
- Composite confidence blending retrieval and citation accuracy.
- FastAPI gateway (`POST /v1/ask`, `POST /v1/ingest`, `GET /health`).
- Click CLI: `rag ingest`, `rag ask`, `rag eval`, `rag serve`, `rag config`.
- 50+-test pytest suite (`httpx.MockTransport` + deterministic pseudo-embeddings, no real network).
- mypy strict, ruff lint, GitHub Actions matrix py3.11 / py3.12.
- 5-row sample golden Q&A eval set under `eval/golden_qa.jsonl`.
