"""Multi-user Document Manager with Atomic Re-indexing and Content-Hash Deduplication.

Handles:
- Upload validation and storage
- SHA-256 hash comparison for zero-cost duplicate skips
- Text extraction across PDF, HTML, Markdown, and TXT
- Chunking & embedding generation
- Atomic index swap (old version replaced ONLY after new version is fully verified)
- Multi-user isolation via user_id metadata
"""

from __future__ import annotations

import hashlib
import io
import uuid
from pathlib import Path
from typing import Any

from ..db.repository import DocumentRepository, VersionRepository
from ..ingestion.chunkers import chunker_for
from ..llm_client import LLMClient
from ..logging import get_logger
from ..models import Chunk, ChunkingStrategy, Document, DocumentFormat
from ..storage import FileStorage
from ..store.dense import DenseVectorStore
from ..store.sparse import BM25Store

log = get_logger(__name__)


def _extract_text(filename: str, content: bytes) -> tuple[str, DocumentFormat]:
    suffix = filename.lower()
    if suffix.endswith(".pdf"):
        import io
        import re
        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(content))
        raw = "\n\n".join((p.extract_text() or "").strip() for p in reader.pages)
        cleaned = re.sub(
            r"[\U0001f56e\U0001f56f\U0001f4d6\ub6b1\uf020-\uf0ff\u25aa\u25cf\u25cb\u25e6\u2043\u2219]+",
            "\n• ",
            raw,
        )
        cleaned = re.sub(r"(•\s*){2,}", "• ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip(), DocumentFormat.PDF
    elif suffix.endswith((".html", ".htm")):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(content.decode("utf-8", errors="replace"), "html.parser")
        for s in soup(["script", "style", "noscript"]):
            s.decompose()
        lines = [ln.strip() for ln in soup.get_text(separator="\n").splitlines()]
        return "\n".join(ln for ln in lines if ln).strip(), DocumentFormat.HTML
    elif suffix.endswith((".md", ".markdown")):
        return content.decode("utf-8", errors="replace").strip(), DocumentFormat.MARKDOWN
    else:
        return content.decode("utf-8", errors="replace").strip(), DocumentFormat.TEXT


class DocumentManager:
    """Coordinates storage, database metadata, and vector index consistency."""

    def __init__(
        self,
        *,
        client: LLMClient,
        embedding_model: str,
        dense: DenseVectorStore,
        sparse: BM25Store,
        doc_repo: DocumentRepository,
        ver_repo: VersionRepository,
        storage: FileStorage,
        strategy: ChunkingStrategy = ChunkingStrategy.RECURSIVE,
        chunk_size_tokens: int = 512,
        overlap_tokens: int = 64,
    ):
        self.client = client
        self.embedding_model = embedding_model
        self.dense = dense
        self.sparse = sparse
        self.doc_repo = doc_repo
        self.ver_repo = ver_repo
        self.storage = storage
        self.strategy = strategy
        self.chunk_size_tokens = chunk_size_tokens
        self.overlap_tokens = overlap_tokens

    async def ingest_or_update(
        self,
        *,
        user_id: str,
        filename: str,
        content: bytes,
        existing_doc_id: str | None = None,
        doc_id: str | None = None,
    ) -> tuple[dict[str, Any], bool, str]:
        """Ingest or atomically re-index a document.

        Returns (document_record, was_reindexed, status_message).
        """
        if not content:
            raise ValueError("Uploaded file is empty.")

        file_hash = hashlib.sha256(content).hexdigest()

        # Check existing document
        effective_doc_id = existing_doc_id or doc_id
        existing = None
        if effective_doc_id:
            existing = await self.doc_repo.get_by_id(effective_doc_id, user_id)
        if not existing:
            existing = await self.doc_repo.get_by_filename(user_id, filename)

        # 1. Content Hash Check: If exact same hash, skip re-indexing (0 cost!)
        if existing and existing.get("file_hash") == file_hash:
            log.info("doc.hash_match_skip", filename=filename, hash=file_hash[:12])
            return (
                existing,
                False,
                "Document content is identical to the current indexed version. No re-indexing needed.",
            )

        # 2. Text Extraction
        extracted_text, doc_format = _extract_text(filename, content)
        if not extracted_text:
            raise ValueError(f"Could not extract any readable text from '{filename}'.")

        # 3. Chunking
        doc_source = f"{user_id}/{filename}"
        doc_model = Document(
            source=doc_source,
            format=doc_format,
            title=Path(filename).stem,
            text=extracted_text,
            metadata={"user_id": user_id, "filename": filename},
        )
        chunker = chunker_for(
            self.strategy,
            chunk_size_tokens=self.chunk_size_tokens,
            overlap_tokens=self.overlap_tokens,
        )
        new_chunks = chunker.chunk(doc_model)
        if not new_chunks:
            raise ValueError(f"Failed to generate chunks for '{filename}'.")

        # Associate document_id and user_id into chunk metadata
        target_doc_id = existing["id"] if existing else f"doc_{uuid.uuid4().hex[:12]}"
        tagged_chunks = [
            c.model_copy(
                update={
                    "metadata": {
                        "user_id": user_id,
                        "document_id": target_doc_id,
                        "filename": filename,
                    }
                }
            )
            for c in new_chunks
        ]

        # 4. Generate Embeddings (Staging phase)
        texts = [c.text for c in tagged_chunks]
        new_embeddings = await self.client.embed_batch(self.embedding_model, texts)
        if len(new_embeddings) != len(tagged_chunks):
            raise RuntimeError("Embedding count mismatch from API.")

        # 5. Save File to Object Storage
        target_version = (existing.get("version", 0) + 1) if existing else 1
        storage_path, _, size_bytes = self.storage.save_file(
            user_id=user_id,
            filename=filename,
            content=content,
            version=target_version,
        )

        # 6. Atomic Store Swap: Find old chunk IDs associated with this document
        old_chunk_ids: list[str] = []
        if existing:
            for c in self.dense.all_chunks():
                if c.metadata.get("document_id") == target_doc_id:
                    old_chunk_ids.append(c.chunk_id)

        # Atomically replace chunks in Dense and Sparse stores
        self.dense.atomic_replace(old_chunk_ids, tagged_chunks, new_embeddings)
        self.sparse.atomic_replace(old_chunk_ids, tagged_chunks)

        # 7. Update Database Metadata
        if existing:
            updated_doc = await self.doc_repo.update_version(
                document_id=target_doc_id,
                user_id=user_id,
                file_hash=file_hash,
                chunk_count=len(tagged_chunks),
                size_bytes=size_bytes,
                new_version=target_version,
            )
            doc_record = updated_doc or existing
        else:
            doc_record = await self.doc_repo.create(
                user_id=user_id,
                filename=filename,
                file_hash=file_hash,
                chunk_count=len(tagged_chunks),
                size_bytes=size_bytes,
                doc_id=target_doc_id,
            )

        # Record version history
        await self.ver_repo.record_version(
            document_id=target_doc_id,
            version_number=target_version,
            file_hash=file_hash,
            storage_path=storage_path,
            chunk_count=len(tagged_chunks),
            status="indexed",
        )

        msg = (
            f"Successfully re-indexed '{filename}' to v{target_version} ({len(tagged_chunks)} chunks)."
            if existing
            else f"Successfully indexed '{filename}' as v1 ({len(tagged_chunks)} chunks)."
        )
        return doc_record, True, msg

    async def delete_document(self, document_id: str = "", user_id: str = "") -> bool:
        doc = await self.doc_repo.get_by_id(document_id, user_id)
        if not doc:
            return False

        # Find and purge chunks from vector stores
        chunk_ids_to_remove = [
            c.chunk_id
            for c in self.dense.all_chunks()
            if c.metadata.get("document_id") == document_id
        ]
        self.dense.delete(chunk_ids_to_remove)
        self.sparse.delete(chunk_ids_to_remove)
        self.dense.save()
        self.sparse.save()

        # Delete database record (cascades versions)
        await self.doc_repo.delete(document_id, user_id)
        return True
