from __future__ import annotations

import io

from fastapi.testclient import TestClient


def test_auth_login_success_and_failure(full_app_client: TestClient) -> None:
    # 1. Invalid login
    r_bad = full_app_client.post(
        "/v1/auth/login",
        json={"email": "admin@hybridrag.io", "password": "WrongPassword"},
    )
    assert r_bad.status_code == 401

    # 2. Valid admin login
    r_ok = full_app_client.post(
        "/v1/auth/login",
        json={"email": "admin@hybridrag.io", "password": "AdminTestPassword123!"},
    )
    assert r_ok.status_code == 200
    body = r_ok.json()
    assert "access_token" in body
    token = body["access_token"]

    # 3. Get profile with token
    r_me = full_app_client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_me.status_code == 200
    assert r_me.json()["email"] == "admin@hybridrag.io"


def test_document_routes_flow_and_tenant_isolation(full_app_client: TestClient) -> None:
    # Login as admin
    r_login = full_app_client.post(
        "/v1/auth/login",
        json={"email": "admin@hybridrag.io", "password": "AdminTestPassword123!"},
    )
    token = r_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Upload Document
    file_bytes = b"# Architecture Overview\nHybrid RAG blends dense vector search with BM25."
    r_upload = full_app_client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("architecture.md", io.BytesIO(file_bytes), "text/markdown")},
    )
    assert r_upload.status_code == 200
    upload_res = r_upload.json()
    doc_id = upload_res["document"]["id"]
    assert upload_res["document"]["filename"] == "architecture.md"
    assert upload_res["document"]["version"] == 1

    # 2. List Documents
    r_list = full_app_client.get("/v1/documents", headers=headers)
    assert r_list.status_code == 200
    docs = r_list.json()
    assert len(docs) >= 1
    assert any(d["id"] == doc_id for d in docs)

    # 3. Get Document by ID
    r_get = full_app_client.get(f"/v1/documents/{doc_id}", headers=headers)
    assert r_get.status_code == 200
    assert r_get.json()["id"] == doc_id

    # 4. View Document Versions
    r_vers = full_app_client.get(f"/v1/documents/{doc_id}/versions", headers=headers)
    assert r_vers.status_code == 200
    assert len(r_vers.json()) >= 1

    # 5. Delete Document
    r_del = full_app_client.delete(f"/v1/documents/{doc_id}", headers=headers)
    assert r_del.status_code == 204

    # 6. Verify Deleted
    r_get_after = full_app_client.get(f"/v1/documents/{doc_id}", headers=headers)
    assert r_get_after.status_code == 404


def test_usage_and_history_routes(full_app_client: TestClient) -> None:
    r_login = full_app_client.post(
        "/v1/auth/login",
        json={"email": "admin@hybridrag.io", "password": "AdminTestPassword123!"},
    )
    token = r_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Ask a question to trigger usage & history tracking
    r_ask = full_app_client.post(
        "/v1/ask",
        headers=headers,
        json={"question": "What is hybrid search?"},
    )
    assert r_ask.status_code == 200

    # Get Usage Summary
    r_usage = full_app_client.get("/v1/usage", headers=headers)
    assert r_usage.status_code == 200
    usage_data = r_usage.json()
    assert usage_data["total_queries"] >= 1

    # Get History
    r_hist = full_app_client.get("/v1/history", headers=headers)
    assert r_hist.status_code == 200
    history_records = r_hist.json()
    assert len(history_records) >= 1
    assert history_records[0]["question"] == "What is hybrid search?"
