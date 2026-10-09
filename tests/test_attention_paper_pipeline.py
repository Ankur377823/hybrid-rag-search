from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from rag.engine import RagEngine
from rag.generation import GroundedAnswerer
from rag.ingestion import IngestionPipeline, load_path
from rag.llm_client import LLMClient
from rag.models import ChunkingStrategy
from rag.retrieval import HybridRetriever, NoOpReranker
from rag.store import BM25Store, DenseVectorStore
from tests.conftest import chat_json, chat_response, embed_response


@pytest.mark.asyncio
async def test_attention_paper_full_pipeline(
    make_llm_client: Callable[[Callable[[httpx.Request], httpx.Response]], LLMClient],
    tmp_path: Path,
) -> None:
    pdf_path = Path("docs/attention-is-all-you-need-Paper.pdf")
    assert pdf_path.exists(), "attention-is-all-you-need-Paper.pdf must exist in docs/"

    # Step 1: Ingestion & parsing of PDF
    docs = list(load_path(pdf_path))
    assert len(docs) == 1
    doc = docs[0]
    assert doc.format.value == "pdf"
    assert len(doc.text) > 20000
    assert "Vaswani" in doc.text
    assert "Adam optimizer" in doc.text or "Adam" in doc.text

    # Step 2: Setup stores and mock LLM client
    dense_path = tmp_path / "dense.json"
    sparse_path = tmp_path / "sparse.json"
    dense_store = DenseVectorStore(dense_path)
    sparse_store = BM25Store(sparse_path)

    def handler(request: httpx.Request) -> httpx.Response:
        url_path = request.url.path
        if url_path.endswith("/embeddings"):
            body = json.loads(request.content)
            return embed_response(body["input"])
        
        # Chat responses for reranking / answering / verification
        body = json.loads(request.content)
        msgs = body.get("messages", [])
        last_msg = msgs[-1]["content"] if msgs else ""
        
        # Reranker scoring request
        if "score the relevance" in (msgs[0]["content"] if msgs else "").lower():
            query_part = last_msg.split("QUERY:\n")[-1].split("\n\nPASSAGE:")[0].lower() if "QUERY:\n" in last_msg else ""
            passage_text = last_msg.split("PASSAGE:\n")[-1].lower() if "PASSAGE:\n" in last_msg else last_msg.lower()
            if "author" in query_part:
                if any(k in passage_text for k in ["vaswani", "shazeer", "parmar", "uszkoreit", "equal contribution"]):
                    return chat_json({"score": 0.95})
            elif "optimizer" in query_part:
                if any(k in passage_text for k in ["adam", "warmup_steps", "beta1"]):
                    return chat_json({"score": 0.95})
            return chat_json({"score": 0.05})
        
        # Grounded answer request
        if "answer the user question" in (msgs[0]["content"] if msgs else "").lower():
            if "author" in last_msg.lower():
                return chat_response("The authors include Ashish Vaswani, Noam Shazeer, Niki Parmar, and Jakob Uszkoreit [1].")
            if "optimizer" in last_msg.lower():
                return chat_response("The authors used the Adam optimizer with beta1=0.9 and beta2=0.98 [1].")
            return chat_response("The Transformer relies entirely on attention [1].")

        # Judge citation verification request
        return chat_json({"supported": True, "reason": "Claim directly verified against passage."})

    client = make_llm_client(handler)

    pipeline = IngestionPipeline(
        client=client,
        embedding_model="text-embedding-3-small",
        dense=dense_store,
        sparse=sparse_store,
        strategy=ChunkingStrategy.RECURSIVE,
        chunk_size_tokens=512,
        overlap_tokens=64,
    )

    report = await pipeline.ingest(docs)
    assert report.n_documents == 1
    assert report.n_chunks_added > 10
    assert len(dense_store) == report.n_chunks_added
    assert len(sparse_store) == report.n_chunks_added

    # Step 3: Retrieval testing (Hybrid search: dense + BM25 + RRF)
    from rag.retrieval.reranker import LLMReranker

    reranker = LLMReranker(client=client, model="gpt-4o-mini")
    retriever = HybridRetriever(
        client=client,
        embedding_model="text-embedding-3-small",
        dense=dense_store,
        sparse=sparse_store,
        reranker=reranker,
        dense_top_k=10,
        sparse_top_k=10,
        rrf_k=60,
        final_top_k=5,
    )

    # Test Query 1: Authors
    query_authors = "Who are the authors of Attention Is All You Need?"
    hits_authors = await retriever.retrieve(query_authors)
    assert len(hits_authors) > 0
    # Top hit should contain author information
    top_author_chunk = hits_authors[0].chunk.text
    assert any(name in top_author_chunk for name in ["Vaswani", "Shazeer", "Parmar", "Uszkoreit"])

    conf_authors = HybridRetriever.aggregate_confidence(hits_authors)
    assert conf_authors >= 0.50, f"Expected confidence >= 0.50, got {conf_authors}"

    # Test Query 2: Optimizer
    query_optimizer = "Which optimizer was used to train the Transformer?"
    hits_opt = await retriever.retrieve(query_optimizer)
    assert len(hits_opt) > 0
    top_opt_chunk = hits_opt[0].chunk.text
    assert "Adam" in top_opt_chunk

    conf_opt = HybridRetriever.aggregate_confidence(hits_opt)
    assert conf_opt >= 0.50, f"Expected confidence >= 0.50, got {conf_opt}"

    # Step 4: End-to-End RagEngine Answer Generation & Verification
    answerer = GroundedAnswerer(
        client=client,
        model="gpt-4o",
        idk_retrieval_threshold=0.35,
    )
    engine = RagEngine(
        client=client,
        retriever=retriever,
        answerer=answerer,
        judge_model="gpt-4o-mini",
        judge_weight=0.5,
    )

    answer_authors = await engine.answer(query_authors)
    assert answer_authors.is_idk is False
    assert "Ashish Vaswani" in answer_authors.text
    assert len(answer_authors.citations) >= 1
    assert answer_authors.composite_confidence >= 0.60
    assert answer_authors.citation_accuracy >= 0.90

    answer_opt = await engine.answer(query_optimizer)
    assert answer_opt.is_idk is False
    assert "Adam optimizer" in answer_opt.text
    assert len(answer_opt.citations) >= 1
    assert answer_opt.composite_confidence >= 0.60

    await client.aclose()
