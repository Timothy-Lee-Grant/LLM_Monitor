"""Step 4 verification tests (plan 001). Run from langchain_service/:

    LLM_MODE=mock python -m pytest tests/test_registry.py -v

No containers needed: chat-basic never touches the network in mock mode.
chat-rag requires a live pgvector connection, so its test arrives with the
Step 9 suite (integration tier).
"""

import os

# Must be set before app imports: pipelines resolve mode via env at call time,
# and these tests assert mock-specific values.
os.environ["LLM_MODE"] = "mock"

import pytest

import app.orchestration.pipelines  # noqa: F401 — registers the pipelines
from app.orchestration.registry import PIPELINES, get_pipeline, UnknownPipelineError
from app.orchestration.contracts import ChatRequest

EXPECTED_IDS = {"chat-basic", "chat-rag", "graph-basic", "graph-rag"}


def test_registry_contains_exactly_the_contract_pipelines():
    assert set(PIPELINES) == EXPECTED_IDS


def test_unknown_pipeline_raises_registry_error():
    with pytest.raises(UnknownPipelineError):
        get_pipeline("does-not-exist")


def test_chat_basic_returns_contract_shape():
    response = get_pipeline("chat-basic").handler(ChatRequest(user_message="hello")).to_dict()

    assert response["status"] == "success"
    assert isinstance(response["response"], str) and response["response"]

    metadata = response["metadata"]
    assert metadata["pipeline_id"] == "chat-basic"
    assert metadata["model_used"] == "mock-stub-provider"  # CONTRACTS.md §2
    assert metadata["retrieved_sources"] == []
    assert isinstance(metadata["latency_ms"], int)


def test_graph_pipelines_are_honest_placeholders_until_step_5():
    for pipeline_id in ("graph-basic", "graph-rag"):
        with pytest.raises(NotImplementedError):
            get_pipeline(pipeline_id).handler(ChatRequest(user_message="hello"))
