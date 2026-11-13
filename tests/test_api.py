from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import login_headers


def test_health(full_app_client: TestClient) -> None:
    r = full_app_client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "n_chunks_dense" in body


def test_upload_then_ask(full_app_client: TestClient) -> None:
    headers = login_headers(full_app_client)
    r = full_app_client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("alpha.md", b"# Alpha\nAlpha is a Greek letter.\n")},
    )
    assert r.status_code == 200
    assert r.json()["document"]["chunk_count"] >= 1

    r2 = full_app_client.post("/v1/ask", headers=headers, json={"question": "What is alpha?"})
    assert r2.status_code == 200
    answer = r2.json()
    assert "text" in answer
    assert len(answer["used_chunks"]) >= 1


def test_ask_rejects_empty_and_blank_question(full_app_client: TestClient) -> None:
    headers = login_headers(full_app_client)
    for question in ["", "   ", "\n\t"]:
        r = full_app_client.post("/v1/ask", headers=headers, json={"question": question})
        assert r.status_code == 422


def test_root_redirect_and_frontend(full_app_client: TestClient) -> None:
    r = full_app_client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"] in ("/app/", "/docs")

    r_app = full_app_client.get("/app/")
    assert r_app.status_code == 200
    assert "HybridRAG" in r_app.text
