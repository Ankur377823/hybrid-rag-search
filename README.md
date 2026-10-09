# rag-hybrid-search

> **Production-grade RAG platform** featuring multi-format document ingestion, three swappable chunking strategies, hybrid retrieval (Dense + BM25) via Reciprocal Rank Fusion (RRF), cross-encoder reranking, bracketed citation verification (LLM-as-judge), multi-tenant PostgreSQL database isolation, and one-click cloud deployment via Render.

[![Tests](https://github.com/Ankur377823/rag-hybrid-search/actions/workflows/test.yml/badge.svg)](https://github.com/Ankur377823/rag-hybrid-search/actions/workflows/test.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![Render](https://img.shields.io/badge/Render-Deploy%20Ready-46E3B7.svg)](https://render.com/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type checked: mypy](https://img.shields.io/badge/typed-mypy%20strict-blueviolet.svg)](https://mypy-lang.org/)

---

## Highlights

- **Hybrid Retrieval (Dense + BM25)**: Combines OpenAI embeddings (`text-embedding-3-small`) with BM25 keyword scoring using rank-based **Reciprocal Rank Fusion (RRF)** ($k=60$) — eliminating fragile cross-query score normalization.
- **Strict Database & Multi-Tenant Isolation**: Built for enterprise multi-tenancy. Every document, vector chunk, query record, and usage quota is strictly bound to a `user_id`. In deployed environments, it runs on **PostgreSQL** with SSL; local development falls back to zero-config SQLite.
- **Atomic Re-indexing & Zero-Cost Deduplication**: Content is hashed via SHA-256 before extraction. Re-uploading an identical document costs 0 LLM tokens and 0 embedding calls. Atomic swap ensures queries never hit half-indexed data.
- **Grounded Generation & Citation Verification**: Every claim must cite an evidence chunk with `[N]` notation. An **LLM-as-judge** asynchronously verifies factual support against retrieved chunks and calculates a calibrated `composite_confidence`.
- **Hard "I Don't Know" Gate**: Rejects hallucinating when retrieval score is below threshold, returning an honest refusal without wasting generation tokens.
- **Web Studio UI & Swagger Docs**: Bundled modern frontend for live testing, document uploads, document version inspection, query audit logs, and token usage analytics.
- **One-Click Render Deployment (`render.yaml`)**: Complete Infrastructure-as-Code blueprint configuring both the containerized web service and managed PostgreSQL.

---

## System Architecture

```
                    ┌──────────────────────────────────────────────┐
                    │            Multi-Tenant Web UI & API         │
                    │      FastAPI  •  JWT Auth  •  Rate Limiting  │
                    └──────────────────────┬───────────────────────┘
                                           │
                       ┌───────────────────┴───────────────────┐
                       ▼                                       ▼
        ┌─────────────────────────────┐        ┌─────────────────────────────┐
        │     Ingestion Pipeline      │        │       Hybrid Retrieval      │
        │  • PDF, HTML, MD, TXT       │        │  • Dense top-20 (Cosine)    │
        │  • Fixed / Recursive / Sem. │        │  • Sparse top-20 (BM25)     │
        │  • SHA-256 Deduplication    │        │  • RRF Fusion (k = 60)      │
        │  • Cosine Dedup (≥ 0.95)    │        │  • Cross-Encoder / LLM Rerank│
        │  • Atomic Vector Swap       │        │  • Tenant user_id Filter    │
        └──────────────┬──────────────┘        └──────────────┬──────────────┘
                       │                                      │
                       ▼                                      ▼
        ┌─────────────────────────────┐        ┌─────────────────────────────┐
        │      Isolated Storage       │        │   Grounded Answer & Judge   │
        │  • PostgreSQL / SQLite      │        │  • Claims cite [1][2]       │
        │  • Document metadata        │        │  • Hard IDK Gate (< 0.35)   │
        │  • Version audit & quotas   │        │  • LLM-as-judge Verification│
        │  • User-scoped vector store │        │  • Composite Confidence     │
        └─────────────────────────────┘        └─────────────────────────────┘
```

---

## Database Isolation & PostgreSQL in Production

When deploying to Render or production environments, data isolation and persistence are enforced:

1. **Foreign-Keyed Relational Model**:
   - `users`: Core identity table with hashed passwords and unique emails.
   - `documents`: Foreign-keyed to `users(id)` with cascading deletes.
   - `document_versions`: Complete audit trail of past file revisions foreign-keyed to `documents(id)`.
   - `usage_records`: Per-user daily token and query counter.
   - `query_history`: Per-user query audit logs with latency, confidence, and IDK tracking.

2. **Tenant Isolation in Vector & Keyword Retrieval**:
   - Every chunk ingested is tagged with `user_id`, `document_id`, and `filename`.
   - During retrieval, the fusion candidates are strictly filtered: chunks not owned by the requesting `user_id` are eliminated before reranking and context synthesis.

3. **Production PostgreSQL Auto-Detection**:
   - Render and cloud environments provide `DATABASE_URL` or `RAG_DATABASE_URL` (starting with `postgresql://` or `postgres://`).
   - The application automatically enables connection pooling via `asyncpg`, initializes the relational schema with `CREATE TABLE IF NOT EXISTS`, and configures SSL context.
   - Local environments seamlessly use SQLite (`./data/rag.db`).

---

## Deploying to Render (`render.yaml`)

This repository includes a [`render.yaml`](render.yaml) Blueprint that provisions:
1. **Managed PostgreSQL Database** (`rag-postgres`): Free/Starter tier with automated backups and private networking.
2. **Docker Web Service** (`rag-hybrid-search`): Houses the FastAPI application, bundled frontend, and hybrid RAG engine.

### Quick Deploy Steps

1. **Push this repository to your GitHub account**:
   ```bash
   git remote add origin https://github.com/Ankur377823/rag-hybrid-search.git
   git branch -M main
   git push -u origin main
   ```

2. **Create Blueprint on Render**:
   - Log into [Render Dashboard](https://dashboard.render.com/).
   - Click **New +** → **Blueprint**.
   - Connect your `rag-hybrid-search` repository.
   - Render will parse `render.yaml` and prompt you for the required secret:
     - `RAG_OPENAI_API_KEY`: Your OpenAI API Key (`sk-...`).
     - `RAG_ADMIN_PASSWORD`: A secure admin password for initial login.

3. **Verify Deployment**:
   - Navigate to your service URL (`https://your-service.onrender.com/`).
   - The Web Studio UI opens directly at `/app`.
   - Swagger REST API documentation is available at `/docs`.
   - Check health endpoint: `https://your-service.onrender.com/health`:
     ```json
     {
       "status": "ok",
       "database": "postgresql",
       "n_chunks_dense": 120,
       "n_chunks_sparse": 120
     }
     ```

---

## Local Development

### 1. Prerequisites
- Python 3.11+
- Git
- OpenAI API Key

### 2. Setup Virtual Environment
```bash
git clone https://github.com/Ankur377823/rag-hybrid-search.git
cd rag-hybrid-search

python -m venv .venv
# Linux / macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

pip install --upgrade pip
pip install -e ".[dev]"
```

### 3. Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Fill in your OpenAI API Key:
```env
RAG_OPENAI_API_KEY=sk-...
RAG_ADMIN_EMAIL=admin@hybridrag.io
RAG_ADMIN_PASSWORD=change-me-admin-pass
```

### 4. Running Locally
```bash
rag serve
# Service starts on http://localhost:8100
# Web Studio: http://localhost:8100/app
# API Docs:   http://localhost:8100/docs
```

---

## Docker & Docker Compose

Run the entire stack locally with Docker Compose:

```bash
docker compose up --build
```

- **Web Studio UI**: [http://localhost:8501](http://localhost:8501)
- **FastAPI Backend**: [http://localhost:8100](http://localhost:8100)
- **API Documentation**: [http://localhost:8100/docs](http://localhost:8100/docs)

---

## API Reference

### Authentication
| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/auth/login` | Authenticate with email/password; returns JWT access token |
| `GET` | `/v1/auth/me` | Fetch authenticated user profile |

### Documents & Re-indexing
| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/documents` | List authenticated user's indexed documents |
| `POST` | `/v1/documents` | Upload & index file (PDF, HTML, MD, TXT) with SHA-256 deduplication |
| `GET` | `/v1/documents/{id}` | Retrieve document details and current version |
| `PUT` | `/v1/documents/{id}` | Atomic re-indexing (bumps version, replaces index upon success) |
| `DELETE` | `/v1/documents/{id}` | Delete document and remove all associated vector chunks |
| `GET` | `/v1/documents/{id}/versions` | Document revision audit history |

### Query & Grounded Generation
| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/ask` | Ask grounded question with citations and LLM-as-judge verification |
| `GET` | `/v1/history` | List user query audit history with confidence and latency |
| `GET` | `/v1/usage` | Inspect daily token and query usage metrics |
| `GET` | `/health` | System health check reporting database and vector store sizes |

### Example Query Request & Response
```bash
curl -X POST http://localhost:8100/v1/ask \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"question": "How does Reciprocal Rank Fusion work?"}'
```

Response:
```json
{
  "request_id": "req_84ef81c2",
  "question": "How does Reciprocal Rank Fusion work?",
  "text": "Reciprocal Rank Fusion (RRF) evaluates multiple ranked retrieval lists by computing a combined score 1 / (k + rank) for each candidate [1]. This ensures robustness against score calibration differences across sparse and dense retrievers [2].",
  "citations": [
    {
      "marker": "[1]",
      "chunk_id": "chunk_9df8a3",
      "source": "docs/fusion.md",
      "title": "Reciprocal Rank Fusion",
      "quote": "RRF assigns 1 / (k + rank) across all retrievers"
    }
  ],
  "retrieval_confidence": 0.88,
  "citation_accuracy": 1.0,
  "composite_confidence": 0.94,
  "is_idk": false,
  "model": "gpt-4o",
  "latency_ms": 1420
}
```

---

## CLI Reference

The CLI tool `rag` allows offline management and automated evaluation:

```bash
# Ingest mixed documents
rag ingest --path ./docs/

# Grounded query with citation printing
rag ask --question "What is the chunking strategy default?"

# Run automated evaluation benchmark
rag eval --cases eval/golden_qa.jsonl

# Start the server
rag serve --host 0.0.0.0 --port 8100

# Dump active configuration JSON
rag config
```

---

## Configuration Reference

All settings can be configured via environment variables prefixed with `RAG_`:

| Environment Variable | Default | Description |
|---|---|---|
| `RAG_OPENAI_API_KEY` | _(required)_ | OpenAI API key |
| `RAG_DATABASE_URL` / `DATABASE_URL` | `""` | PostgreSQL connection URL (e.g. on Render) |
| `RAG_ENV` | `development` | `development` (SQLite) or `production` (PostgreSQL) |
| `RAG_EMBEDDING_MODEL` | `text-embedding-3-small` | Vector embedding model |
| `RAG_GENERATION_MODEL` | `gpt-4o` | Primary answer generation model |
| `RAG_JUDGE_MODEL` | `gpt-4o-mini` | Citation verification judge |
| `RAG_CHUNKING_STRATEGY` | `recursive` | `fixed`, `recursive`, or `semantic` |
| `RAG_CHUNK_SIZE_TOKENS` | `512` | Token limit per chunk |
| `RAG_CHUNK_OVERLAP_TOKENS` | `64` | Overlap between adjacent chunks |
| `RAG_DEDUP_COSINE_THRESHOLD` | `0.95` | Cosine threshold to prune semantic duplicates |
| `RAG_DENSE_TOP_K` | `20` | Number of dense candidates retrieved |
| `RAG_SPARSE_TOP_K` | `20` | Number of BM25 candidates retrieved |
| `RAG_RRF_K` | `60` | Constant parameter for RRF formula |
| `RAG_FINAL_TOP_K` | `5` | Top reranked chunks supplied to LLM context |
| `RAG_IDK_RETRIEVAL_THRESHOLD` | `0.35` | Retrieval threshold below which IDK gate triggers |
| `RAG_JUDGE_WEIGHT` | `0.5` | Weight between retrieval confidence & citation accuracy |
| `RAG_API_PORT` / `PORT` | `8100` | Port for FastAPI server |

---

## Testing & Quality Assurance

Run the comprehensive test suite with coverage:

```bash
pytest -v
```

Run code formatting and type checks:
```bash
ruff check .
ruff format --check .
mypy src
```

---

## License

This project is licensed under the MIT License - see the LICENSE file for details.
