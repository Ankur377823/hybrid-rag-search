"""End-to-end hybrid retriever: dense + sparse → RRF → rerank → top-K."""

from __future__ import annotations

from ..llm_client import LLMClient
from ..logging import get_logger
from ..models import Chunk, RankedHit
from ..store.dense import DenseVectorStore
from ..store.sparse import BM25Store
from .fusion import reciprocal_rank_fusion
from .reranker import Reranker

log = get_logger(__name__)


def _is_visible(chunk: Chunk, user_id: str | None, document_id: str | None) -> bool:
    """A chunk is visible only to its owner, and only inside the chosen document.

    Strict rule: when a `user_id` is given, a chunk with a different owner OR
    with no owner at all is hidden.
    """
    if user_id and chunk.metadata.get("user_id") != user_id:
        return False
    return not (document_id and chunk.metadata.get("document_id") != document_id)


class HybridRetriever:
    def __init__(
        self,
        *,
        client: LLMClient,
        embedding_model: str,
        dense: DenseVectorStore,
        sparse: BM25Store,
        reranker: Reranker,
        dense_top_k: int = 20,
        sparse_top_k: int = 20,
        rrf_k: int = 60,
        final_top_k: int = 5,
    ):
        self._client = client
        self._embedding_model = embedding_model
        self._dense = dense
        self._sparse = sparse
        self._reranker = reranker
        self._dense_top_k = dense_top_k
        self._sparse_top_k = sparse_top_k
        self._rrf_k = rrf_k
        self._final_top_k = final_top_k

    async def retrieve(
        self,
        query: str,
        *,
        user_id: str | None = None,
        document_id: str | None = None,
    ) -> list[RankedHit]:
        if not query.strip():
            return []

        # Tenant isolation: work out which chunks this caller may see FIRST,
        # then search only inside that set. (user_id=None is the local CLI,
        # which may search everything.)
        allowed_ids: set[str] | None = None
        if user_id or document_id:
            allowed_ids = {
                c.chunk_id
                for c in self._dense.all_chunks()
                if _is_visible(c, user_id, document_id)
            }
            if not allowed_ids:
                return []

        embedding = (await self._client.embed_batch(self._embedding_model, [query]))[0]
        dense_hits = self._dense.search(
            embedding, top_k=self._dense_top_k, allowed_ids=allowed_ids
        )
        sparse_hits = self._sparse.search(
            query, top_k=self._sparse_top_k, allowed_ids=allowed_ids
        )
        fused = reciprocal_rank_fusion(dense_hits, sparse_hits, k=self._rrf_k)

        # Best possible RRF score = rank 1 in BOTH lists. Dividing by it turns
        # the tiny raw RRF score (about 0.03) into a 0-1 score, so the
        # "I don't know" threshold also works when no reranker is used.
        best_possible_rrf = 2.0 / (self._rrf_k + 1)

        candidates: list[RankedHit] = []
        target_count = max(self._final_top_k * 4, self._dense_top_k)
        for hit in fused:
            chunk = self._dense.get(hit.chunk_id) or self._sparse.get(hit.chunk_id)
            if chunk is None or not _is_visible(chunk, user_id, document_id):
                continue
            candidates.append(
                RankedHit(
                    chunk=chunk,
                    score=min(1.0, hit.rrf_score / best_possible_rrf),
                    dense_rank=hit.dense_rank,
                    sparse_rank=hit.sparse_rank,
                    rrf_score=hit.rrf_score,
                )
            )
            if len(candidates) >= target_count:
                break

        ranked = await self._reranker.rerank(
            query=query, candidates=candidates, top_k=self._final_top_k
        )
        log.info(
            "retrieval.done",
            n_dense=len(dense_hits),
            n_sparse=len(sparse_hits),
            n_fused=len(fused),
            n_final=len(ranked),
        )
        return ranked

    @staticmethod
    def aggregate_confidence(hits: list[RankedHit]) -> float:
        """Aggregate post-rerank confidence.

        The confidence that the corpus contains the requested fact is primarily
        determined by the best-matching passage, reinforced by secondary passages.
        Using a naive arithmetic mean severely punishes answers where exactly one
        chunk holds the key fact (e.g. [1.0, 0.0, 0.0, 0.0, 0.0] averages to 0.20,
        erroneously triggering the low-confidence IDK gate).
        """
        if not hits:
            return 0.0
        scores = sorted([h.score for h in hits], reverse=True)
        top = scores[0]
        if len(scores) == 1:
            return max(0.0, min(1.0, top))
        mean_score = sum(scores) / len(scores)
        blended = 0.7 * top + 0.3 * mean_score
        return max(0.0, min(1.0, max(top * 0.75, blended)))

    @staticmethod
    def chunks(hits: list[RankedHit]) -> list[Chunk]:
        return [h.chunk for h in hits]
