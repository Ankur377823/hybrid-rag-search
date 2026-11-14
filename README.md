# hybrid-rag-search

> A **retrieval-augmented generation (RAG) system**: multi-format document ingestion, three swappable chunking strategies, hybrid retrieval (dense + BM25) fused with Reciprocal Rank Fusion (RRF), LLM reranking, cited answers checked by an LLM judge, per-user data isolation, and a Render deployment blueprint.

[![Tests](https://github.com/Ankur377823/hybrid-rag-search/actions/workflows/test.yml/badge.svg)](https://github.com/Ankur377823/hybrid-rag-search/actions/workflows/test.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![Render](https://img.shields.io/badge/Render-Deploy%20Ready-46E3B7.svg)](https://render.com/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type checked: mypy](https://img.shields.io/badge/typed-mypy%20strict-blueviolet.svg)](https://mypy-lang.org/)

---

## Highlights

- **Hybrid Retrieval (Dense + BM25)**: Combines OpenAI embeddings (`text-embedding-3-small`) with BM25 keyword scoring using rank-based **Reciprocal Rank Fusion (RRF)** ($k=60$) — eliminating fragile cross-query score normalization.
- **Per-User Isolation**: Every document, chunk, query record and usage counter belongs to a `user_id`. Search is limited to the caller's own chunks *before* the top-K is taken, and every API route except login requires a token. Relational data lives in **PostgreSQL** when deployed (SQLite locally); chunk text and embeddings live in JSON index files on the server's disk.
- **Versioned Re-indexing & Zero-Cost Deduplication**: Content is hashed with SHA-256 before extraction, so re-uploading an identical document costs 0 LLM tokens and 0 embedding calls. On an update, the old chunks are replaced only after the new version is fully embedded.
- **Grounded Generation & Citation Verification**: Every claim must cite an evidence chunk with `[N]` notation. An **LLM-as-judge** then checks each citation against its chunk, and the result is combined with retrieval confidence into one `composite_confidence` score.
- **Hard "I Don't Know" Gate**: Rejects hallucinating when retrieval score is below threshold, returning an honest refusal without wasting generation tokens.
- **Web Studio UI & Swagger Docs**: Bundled modern frontend for live testing, document uploads, document version inspection, query audit logs, and token usage analytics.
- **One-Click Render Deployment (`render.yaml`)**: Complete Infrastructure-as-Code blueprint configuring both the containerized web service and managed PostgreSQL.
- **Tested**: automated test suite (unit, API and regression tests) with an 80% coverage gate, `ruff` and strict `mypy`, run in CI on Python 3.11 and 3.12.

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
        │  • Cosine Dedup (≥ 0.95)    │        │  • LLM Rerank (cross-enc opt)│
        │  • Atomic Vector Swap       │        │  • Tenant user_id Filter    │
        └──────────────┬──────────────┘        └──────────────┬──────────────┘
                       │                                      │
                       ▼                                      ▼
        ┌─────────────────────────────┐        ┌─────────────────────────────┐
        │      Isolated Storage       │        │   Grounded Answer & Judge   │
        │  • PostgreSQL / SQLite      │        │  • Claims cite [1][2]       │
        │  • Document metadata        │        │  • Hard IDK Gate (< 0.35)   │
        │  • Version audit & quotas   │        │  • LLM-as-judge Verification│
        │  • JSON vector + BM25 index │        │  • Composite Confidence     │
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
   - During retrieval, the caller's allowed chunk ids are worked out first, and both the dense and the BM25 search run only inside that set (filter before top-K). Chunks with no owner are hidden from logged-in users.

   - The chunk text and embeddings are **not** stored in PostgreSQL. They are kept in memory and saved to `dense.json` / `sparse.json` under `RAG_INDEX_DIR` (written atomically). On Render this folder is on the persistent disk mounted at `/data`.

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
   git remote add origin https://github.com/Ankur377823/hybrid-rag-search.git
   git branch -M main
   git push -u origin main
   ```

2. **Create Blueprint on Render**:
   - Log into [Render Dashboard](https://dashboard.render.com/).
   - Click **New +** → **Blueprint**.
   - Connect your `hybrid-rag-search` repository.
   - Render will parse `render.yaml` and prompt you for the required secret:
     - `RAG_OPENAI_API_KEY`: Your OpenAI API Key (`sk-...`).
     - `RAG_ADMIN_PASSWORD`: A secure admin password for initial login.

   - `RAG_JWT_SECRET` is generated automatically by the Blueprint. If you create the service by hand, set it yourself: with `RAG_ENV=production` the app refuses to start while the secret is still the public placeholder.
   - The service needs the persistent disk from `render.yaml` (mounted at `/data`). Without it, the search index and uploaded files are lost on every restart or deploy.

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
git clone https://github.com/Ankur377823/hybrid-rag-search.git
cd hybrid-rag-search

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

If the `rag` command is blocked or not found on your machine, start it through Python instead:
```bash
python -m rag.cli serve
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

Every `/v1` endpoint except `POST /v1/auth/login` requires an `Authorization: Bearer <token>` header. Requests are rate limited to 60 per minute per user (or per IP address when not logged in).

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
| `POST` | `/v1/ask` | Ask grounded question with citations and LLM-as-judge verification (login required) |
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
  "latency_ms": 1420,
  "tokens_used": 3127
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
| `RAG_JWT_SECRET` | _(placeholder)_ | Secret used to sign login tokens. **Required in production**: the app refuses to start with the placeholder |
| `RAG_JWT_EXPIRE_MINUTES` | `1440` | Login token lifetime |
| `RAG_CORS_ALLOWED_ORIGINS` | `""` | Comma-separated list of other websites allowed to call the API from a browser. Empty = none (the bundled UI needs no entry) |

---

## Testing & Quality Assurance

Run the test suite with coverage:

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

## Known Limitations

This is a learning and portfolio project, not a hardened production system. The main limits:

- **The vector index is a JSON file, not a vector database.** Embeddings are held in memory and searched by exact (brute-force) cosine similarity. That suits thousands of chunks, not millions, and the index is rebuilt and rewritten on every upload.
- **Single server instance.** The index and the rate limiter live in one process's memory, so the service cannot be scaled horizontally as it is.
- **Two stores.** PostgreSQL holds document records while the index file holds the chunks; they are updated one after another, not in one transaction.
- **The default reranker is an LLM** (`gpt-4o-mini`, one call per candidate). A local cross-encoder is available with `RAG_RERANK_KIND=cross-encoder` and the `[reranker]` extra.
- **Confidence scores are heuristics**, not calibrated probabilities. The weights and the `0.35` threshold have not been tuned on labelled data.
- **Evaluation is minimal.** `rag eval` runs a small golden set and reports confidence and citation counts; it does not score answer correctness.
- **Documents ingested with the CLI have no owner**, so they are visible to `rag ask` but not to users of the web app.
- **No sign-up flow.** One admin user is created from `RAG_ADMIN_EMAIL` / `RAG_ADMIN_PASSWORD` at start-up.
- **Text only.** No OCR for scanned PDFs, no table or image understanding, no streaming responses, no multi-turn chat memory.
- **Security notes.** The UI keeps the login token in `localStorage`; database TLS is enabled without certificate verification; uploaded document text is passed to the model without a dedicated prompt-injection defence.

---

## License

This project is licensed under the MIT License - see the LICENSE file for details.
