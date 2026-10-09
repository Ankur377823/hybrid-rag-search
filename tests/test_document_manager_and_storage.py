from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import pytest

from rag.db.database import Database
from rag.db.repository import DocumentRepository, UserRepository, VersionRepository
from rag.ingestion.document_manager import DocumentManager, _extract_text
from rag.llm_client import LLMClient
from rag.models import DocumentFormat
from rag.storage import FileStorage
from rag.store.dense import DenseVectorStore
from rag.store.sparse import BM25Store
from tests.conftest import embed_response


@pytest.fixture
def file_storage(tmp_path: Path) -> FileStorage:
    return FileStorage(root_dir=tmp_path / "uploads")


def test_file_storage_save_read_delete(file_storage: FileStorage) -> None:
    user_id = "user_abc"
    filename = "document.txt"
    content = b"Hello world storage testing!"

    path, f_hash, size = file_storage.save_file(
        user_id=user_id,
        filename=filename,
        content=content,
        version=1,
    )
    assert Path(path).exists()
    assert size == len(content)

    # Read back
    read_data = file_storage.read_file(path)
    assert read_data == content

    # Delete
    deleted = file_storage.delete_file(path)
    assert deleted is True
    assert not Path(path).exists()

    # Deleting non-existent returns False
    assert file_storage.delete_file(path) is False


def test_extract_text_formats() -> None:
    # TXT
    txt, fmt = _extract_text("notes.txt", b"Plain text content.")
    assert txt == "Plain text content."
    assert fmt == DocumentFormat.TEXT

    # Markdown
    md, fmt_md = _extract_text("readme.md", b"# Header\nMarkdown body text.")
    assert "# Header" in md
    assert fmt_md == DocumentFormat.MARKDOWN

    # HTML
    html_raw = b"<html><head><script>var x=1;</script></head><body><h1>Title</h1><p>Paragraph content</p></body></html>"
    html_txt, fmt_html = _extract_text("page.html", html_raw)
    assert "Title" in html_txt
    assert "Paragraph content" in html_txt
    assert "var x=1" not in html_txt
    assert fmt_html == DocumentFormat.HTML


@pytest.mark.asyncio
async def test_document_manager_ingest_dedup_and_reindex(
    tmp_path: Path,
    make_llm_client: Any,
) -> None:
    # Setup LLM client with mocked embeddings
    def handler(request: Any) -> Any:
        body = json.loads(request.content)
        return embed_response(body["input"])

    client: LLMClient = make_llm_client(handler)

    # Setup database
    db = Database(url="", environment="development", default_sqlite_path=tmp_path / "rag.db")
    await db.connect()
    try:
        user_repo = UserRepository(db)
        doc_repo = DocumentRepository(db)
        ver_repo = VersionRepository(db)
        storage = FileStorage(root_dir=tmp_path / "uploads")
        dense = DenseVectorStore(tmp_path / "dense.json")
        sparse = BM25Store(tmp_path / "sparse.json")

        user = await user_repo.create("doc_manager_test@rag.io", "pass")
        uid = user["id"]

        manager = DocumentManager(
            client=client,
            embedding_model="text-embedding-3-small",
            dense=dense,
            sparse=sparse,
            doc_repo=doc_repo,
            ver_repo=ver_repo,
            storage=storage,
        )

        doc_content = b"# Document Content\nThis is a sample document for RAG indexing."

        # 1. First Ingestion: creates v1
        doc_rec, reindexed, msg = await manager.ingest_or_update(
            user_id=uid,
            filename="sample.md",
            content=doc_content,
        )
        assert reindexed is True
        assert doc_rec["version"] == 1
        assert len(dense) > 0
        assert len(sparse) > 0

        # 2. Duplicate Content Ingestion: Content-hash skips (0-cost)
        dup_rec, dup_reindexed, dup_msg = await manager.ingest_or_update(
            user_id=uid,
            filename="sample.md",
            content=doc_content,
        )
        assert dup_reindexed is False
        assert "identical" in dup_msg.lower()
        assert dup_rec["version"] == 1

        # 3. Updated Content Ingestion: Atomic re-indexing bumps to v2
        new_content = b"# Document Content Updated\nThis is an amended text with additional valuable details."
        updated_rec, updated_reindexed, updated_msg = await manager.ingest_or_update(
            user_id=uid,
            filename="sample.md",
            content=new_content,
            doc_id=doc_rec["id"],
        )
        assert updated_reindexed is True
        assert updated_rec["version"] == 2
        assert "v2" in updated_msg

        # 4. Deleting Document cleans vector stores and database
        doc_id = doc_rec["id"]
        del_ok = await manager.delete_document(document_id=doc_id, user_id=uid)
        assert del_ok is True
        assert len(dense) == 0
        assert len(sparse) == 0
        assert await doc_repo.get_by_id(doc_id, uid) is None
    finally:
        await db.disconnect()
        await client.aclose()
