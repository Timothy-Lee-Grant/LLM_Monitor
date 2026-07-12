"""HTTP-layer contract tests (CONTRACTS.md §1-§6) via the Flask test client.

No containers: mock mode never touches Ollama, and retrieval is monkeypatched
at the vector_store singleton — pipelines, graph nodes, and routes all share
that one object, so patching it covers every path. Real pgvector round-trips
are Step 10 (live acceptance), not unit territory.
"""

import pytest
from langchain_core.documents import Document

from app.rag.vector_store import vector_store

FAKE_DOCS = [
    Document(
        page_content="Employees are permitted to use local scripting tools.",
        metadata={"source": "security_policy_v2.md", "category": "it_safety"},
    ),
]

PIPELINE_ROUTES = ["/chat/basic", "/chat/rag", "/graph/basic", "/graph/rag"]
RAG_ROUTES = {"/chat/rag", "/graph/rag"}


@pytest.fixture()
def fake_retrieval(monkeypatch):
    monkeypatch.setattr(
        vector_store,
        "find_similar",
        lambda message, k=4, score_threshold=None: FAKE_DOCS,
    )


def _assert_contract_success(body: dict, pipeline_id: str):
    """CONTRACTS.md §2, field by field."""
    assert body["status"] == "success"
    assert isinstance(body["response"], str) and body["response"]
    metadata = body["metadata"]
    assert metadata["pipeline_id"] == pipeline_id
    assert metadata["model_used"] == "mock-stub-provider"
    assert isinstance(metadata["retrieved_sources"], list)
    assert isinstance(metadata["latency_ms"], int)


def _assert_contract_error(body: dict, code: str):
    """CONTRACTS.md §3."""
    assert body["status"] == "error"
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]


# ---- health ----

def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "mode": "mock"}


# ---- canonical pipeline routes ----

@pytest.mark.parametrize("route", PIPELINE_ROUTES)
def test_pipeline_routes_return_contract_shape(client, fake_retrieval, route):
    response = client.post(route, json={"user_message": "can I use scripting tools?"})
    assert response.status_code == 200

    pipeline_id = route.lstrip("/").replace("/", "-")
    body = response.get_json()
    _assert_contract_success(body, pipeline_id)

    expected_sources = ["security_policy_v2.md"] if route in RAG_ROUTES else []
    assert body["metadata"]["retrieved_sources"] == expected_sources


def test_missing_user_message_is_contract_400(client):
    response = client.post("/chat/basic", json={})
    assert response.status_code == 400
    _assert_contract_error(response.get_json(), "invalid_request")


def test_non_json_body_is_contract_400(client):
    response = client.post("/chat/basic", data="definitely not json", content_type="application/json")
    assert response.status_code == 400
    _assert_contract_error(response.get_json(), "invalid_request")


# ---- OpenAI-compatible surface ----

def test_v1_models_generated_from_registry(client):
    body = client.get("/v1/models").get_json()
    assert body["object"] == "list"
    model_ids = {m["id"] for m in body["data"]}
    assert model_ids == {
        "llm-monitor.chat-basic",
        "llm-monitor.chat-rag",
        "llm-monitor.graph-basic",
        "llm-monitor.graph-rag",
    }


def test_v1_chat_completions_round_trip(client):
    response = client.post("/v1/chat/completions", json={
        "model": "llm-monitor.chat-basic",
        "messages": [{"role": "user", "content": "hello"}],
    })
    assert response.status_code == 200

    body = response.get_json()
    assert body["object"] == "chat.completion"
    assert body["model"] == "llm-monitor.chat-basic"
    choice = body["choices"][0]
    assert choice["message"]["role"] == "assistant"
    assert choice["message"]["content"]
    assert choice["finish_reason"] == "stop"


def test_v1_unknown_model_is_contract_404(client):
    response = client.post("/v1/chat/completions", json={
        "model": "llm-monitor.does-not-exist",
        "messages": [{"role": "user", "content": "hello"}],
    })
    assert response.status_code == 404
    _assert_contract_error(response.get_json(), "unknown_pipeline")


def test_v1_missing_user_message_is_contract_400(client):
    response = client.post("/v1/chat/completions", json={
        "model": "llm-monitor.chat-basic",
        "messages": [{"role": "system", "content": "no user turn here"}],
    })
    assert response.status_code == 400
    _assert_contract_error(response.get_json(), "invalid_request")
