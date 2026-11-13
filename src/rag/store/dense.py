"""Dense (embedding) vector store.

JSON-backed flat-file index. Cosine top-K with NumPy is sub-millisecond up to
~50K rows; the spec calls for 10K-100K chunks which fits comfortably. ChromaDB /
Qdrant migration path is documented in ADR-002.

Public surface:

    store.upsert(chunks, embeddings)
    store.search(query_embedding, top_k=20) -> list[DenseHit]
    store.is_near_duplicate(embedding, threshold=0.95) -> bool
    store.get(chunk_id) -> Chunk | None
    store.save() / store.load()
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import numpy as np

from ..models import Chunk, DenseHit
from .files import load_json, save_json


class DenseVectorStore:
    """Flat-file embedding index. Persists on `save()`."""

    def __init__(self, path: Path):
        self._path = path
        self._chunks: dict[str, Chunk] = {}
        self._embeddings: dict[str, list[float]] = {}
        self._matrix: np.ndarray | None = None
        self._ids_in_matrix: list[str] = []
        self._load()

    def _load(self) -> None:
        data = load_json(self._path)
        if data is None:
            return
        for raw in data.get("entries", []):
            chunk = Chunk.model_validate(raw["chunk"])
            self._chunks[chunk.chunk_id] = chunk
            self._embeddings[chunk.chunk_id] = list(raw["embedding"])
        self._rebuild_matrix()

    def save(self) -> None:
        payload = {
            "version": 1,
            "entries": [
                {"chunk": chunk.model_dump(), "embedding": self._embeddings[cid]}
                for cid, chunk in self._chunks.items()
            ],
        }
        save_json(self._path, payload)

    def known_ids(self) -> set[str]:
        return set(self._chunks)

    def get(self, chunk_id: str) -> Chunk | None:
        return self._chunks.get(chunk_id)

    def all_chunks(self) -> list[Chunk]:
        return list(self._chunks.values())

    def __len__(self) -> int:
        return len(self._chunks)

    def upsert(
        self,
        chunks: Iterable[Chunk],
        embeddings: Iterable[list[float]],
    ) -> None:
        chunks_list = list(chunks)
        embeddings_list = list(embeddings)
        if len(chunks_list) != len(embeddings_list):
            raise ValueError("chunks and embeddings length mismatch")
        for chunk, emb in zip(chunks_list, embeddings_list, strict=True):
            self._chunks[chunk.chunk_id] = chunk
            self._embeddings[chunk.chunk_id] = list(emb)
        self._rebuild_matrix()

    def delete(self, chunk_ids: Iterable[str]) -> None:
        for cid in chunk_ids:
            self._chunks.pop(cid, None)
            self._embeddings.pop(cid, None)
        self._rebuild_matrix()

    def atomic_replace(
        self,
        old_chunk_ids: Iterable[str],
        new_chunks: Iterable[Chunk],
        new_embeddings: Iterable[list[float]],
    ) -> None:
        chunks_list = list(new_chunks)
        embeddings_list = list(new_embeddings)
        if len(chunks_list) != len(embeddings_list):
            raise ValueError("chunks and embeddings length mismatch")
        for cid in old_chunk_ids:
            self._chunks.pop(cid, None)
            self._embeddings.pop(cid, None)
        for chunk, emb in zip(chunks_list, embeddings_list, strict=True):
            self._chunks[chunk.chunk_id] = chunk
            self._embeddings[chunk.chunk_id] = list(emb)
        self._rebuild_matrix()
        self.save()

    def search(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 20,
        allowed_ids: set[str] | None = None,
    ) -> list[DenseHit]:
        """Return the `top_k` most similar chunks.

        `allowed_ids` limits the search to those chunks (used for per-user and
        per-document search). The filter is applied BEFORE picking the top K,
        so another user's chunks can never push the caller's chunks out.
        """
        if self._matrix is None or len(self._ids_in_matrix) == 0:
            return []
        ids = self._ids_in_matrix
        matrix = self._matrix
        if allowed_ids is not None:
            keep = [i for i, cid in enumerate(ids) if cid in allowed_ids]
            if not keep:
                return []
            ids = [ids[i] for i in keep]
            matrix = matrix[keep]

        q = _normalize(np.asarray(query_embedding, dtype=np.float64))
        sims = matrix @ q
        if top_k >= sims.size:
            order = np.argsort(-sims)
        else:
            order = np.argpartition(-sims, top_k)[:top_k]
            order = order[np.argsort(-sims[order])]
        out: list[DenseHit] = []
        for rank, idx in enumerate(order, start=1):
            out.append(
                DenseHit(
                    chunk_id=ids[int(idx)],
                    # Clip: float rounding can give 1.0000000002, which the model rejects.
                    score=float(np.clip(sims[idx], -1.0, 1.0)),
                    rank=rank,
                )
            )
        return out

    def is_near_duplicate(
        self, embedding: list[float], *, threshold: float = 0.95
    ) -> bool:
        if self._matrix is None or len(self._ids_in_matrix) == 0:
            return False
        q = _normalize(np.asarray(embedding, dtype=np.float64))
        sims = self._matrix @ q
        return bool(sims.max() >= threshold)

    def _rebuild_matrix(self) -> None:
        if not self._embeddings:
            self._matrix = None
            self._ids_in_matrix = []
            return
        ids = list(self._embeddings.keys())
        rows = np.asarray([self._embeddings[i] for i in ids], dtype=np.float64)
        norms = np.linalg.norm(rows, axis=1, keepdims=True)
        norms = np.where(norms == 0.0, 1.0, norms)
        self._matrix = rows / norms
        self._ids_in_matrix = ids


def _normalize(vec: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(vec)) or 1.0
    return vec / n
