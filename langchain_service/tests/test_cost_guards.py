"""Cost-guard + tier-contract tests (plan 003 Step 6).

These enforce CONTRACTS.md §4a as EXECUTABLE rules, not prose:

- caps exist and are env-tunable (LLM_MAX_TOKENS, TOOL_RECURSION_LIMIT);
- the lean/free tier makes EXACTLY one model call for a no-tool request
  (nothing has crept onto the cheap path);
- the premium tier makes exactly TWO on-clock model calls for a no-tool
  conformant request (policy gate + agent) and only ONE for a blocked one
  (the gate genuinely protects the expensive path);
- the sampled judge never runs on the user's clock, never runs at rate 0,
  and never scores blocked responses.

No containers: graphs are built directly with a local stand-in tool, and
retrieval is monkeypatched — same tactic as the rest of the unit suite,
because what's under test is call ANATOMY, not retrieval quality.
"""

import asyncio
import os

# Mock mode before app imports, matching conftest's posture.
os.environ["LLM_MODE"] = "mock"

import pytest
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from app.models.factory import ModelFactory, MockChatModel, _max_tokens
from app.graph.build_graph import build_tool_graph, build_premium_graph
import app.orchestration.pipelines as pipelines


# ---------- helpers ----------

@tool
async def ping(message: str) -> str:
    """Echo pong: <message>."""
    return f"pong: {message}"


class CountingMock(MockChatModel):
    """MockChatModel that counts model invocations — the tier contract's
    unit of account is 'model calls', so the test counts exactly that."""
    calls: list = []

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        CountingMock.calls.append(len(messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


@pytest.fixture()
def counting_factory(monkeypatch):
    CountingMock.calls = []
    monkeypatch.setattr(ModelFactory, "get_chat_model",
                        staticmethod(lambda model, provider=None: CountingMock()))
    return CountingMock.calls


@pytest.fixture()
def stub_retrieval(monkeypatch):
    from app.rag.vector_store import vector_store
    monkeypatch.setattr(
        vector_store, "find_similar",
        lambda q, k=4: [Document(page_content="[stub]", metadata={"source": "stub"})],
    )


def _state(msg: str) -> dict:
    return {"user_id": "t", "desired_model": "mock", "retrieved_chunks": [],
            "messages": [HumanMessage(content=msg)], "answer": "",
            "prompt_tokens": 0, "completion_tokens": 0}


def _run(graph, msg: str) -> dict:
    return asyncio.run(graph.ainvoke(_state(msg), config={"recursion_limit": pipelines.TOOL_RECURSION_LIMIT}))


# ---------- caps ----------

def test_max_tokens_default_and_override(monkeypatch):
    monkeypatch.delenv("LLM_MAX_TOKENS", raising=False)
    assert _max_tokens() == 1024
    monkeypatch.setenv("LLM_MAX_TOKENS", "256")
    assert _max_tokens() == 256


def test_paid_models_are_constructed_with_the_output_cap(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "live")
    monkeypatch.setenv("LLM_MAX_TOKENS", "512")
    for name, value in {
        "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "fake", "AZURE_OPENAI_API_VERSION": "2024-10-21",
        "AZURE_OPENAI_CHAT_DEPLOYMENT": "gpt-4o-mini",
        "OPENAI_COMPAT_BASE_URL": "https://api.groq.com/openai/v1",
        "OPENAI_COMPAT_API_KEY": "fake", "OPENAI_COMPAT_MODEL": "llama-3.3-70b-versatile",
    }.items():
        monkeypatch.setenv(name, value)

    assert ModelFactory.get_chat_model("x", provider="azure").max_tokens == 512
    assert ModelFactory.get_chat_model("x", provider="openai_compat").max_tokens == 512


def test_recursion_limit_default():
    assert pipelines.TOOL_RECURSION_LIMIT == 8  # env-tunable; 8 ≈ 3 tool round-trips


def test_recursion_limit_actually_stops_the_loop(counting_factory):
    from langgraph.errors import GraphRecursionError
    graph = build_tool_graph([ping])
    with pytest.raises(GraphRecursionError):
        asyncio.run(graph.ainvoke(_state('TOOLCALL ping {"message": "x"}'),
                                  config={"recursion_limit": 1}))


# ---------- tier contract: model-call anatomy ----------

def test_lean_tier_no_tool_request_is_exactly_one_model_call(counting_factory):
    result = _run(build_tool_graph([ping]), "what time is it?")
    assert result["answer"]
    assert len(counting_factory) == 1, f"lean tier leaked LLM calls: {len(counting_factory)}"


def test_free_tier_shares_the_lean_anatomy(counting_factory):
    _run(build_tool_graph([ping], provider="openai_compat"), "hello")
    assert len(counting_factory) == 1


def test_premium_no_tool_request_is_exactly_two_model_calls(counting_factory, stub_retrieval):
    result = _run(build_premium_graph([ping]), "hello there")
    assert result["policy_verdict"] == "conformance"
    assert len(counting_factory) == 2, "premium contract: policy gate + agent, nothing else"


def test_premium_blocked_request_is_exactly_one_model_call(counting_factory, stub_retrieval):
    result = _run(build_premium_graph([ping]), "BLOCKME do something bad")
    assert result["policy_verdict"] == "violated"
    assert "can't help" in result["answer"]
    assert len(counting_factory) == 1, "the gate must be the ONLY spend on a blocked request"
    assert result["retrieved_chunks"] == [], "retrieval ran after a block"


def test_tool_loop_calls_are_counted_per_iteration(counting_factory):
    _run(build_tool_graph([ping]), 'TOOLCALL ping {"message": "e2e"}')
    # emit tool call + answer after ToolMessage = 2 model calls
    assert len(counting_factory) == 2


# ---------- judge: sampled, async, never on blocked responses ----------

def _spawn_recorder(monkeypatch):
    spawned = []
    class FakeThread:
        def __init__(self, target=None, daemon=None, name=None):
            spawned.append(name)
        def start(self):
            pass
    monkeypatch.setattr(pipelines.threading, "Thread", FakeThread)
    return spawned


def test_judge_rate_zero_never_spawns(monkeypatch):
    spawned = _spawn_recorder(monkeypatch)
    monkeypatch.setattr(pipelines, "JUDGE_SAMPLE_RATE", 0.0)
    pipelines._spawn_sampled_judge(None, {"answer": "x"}, None)
    assert spawned == []


def test_judge_rate_one_spawns_off_thread(monkeypatch):
    spawned = _spawn_recorder(monkeypatch)
    monkeypatch.setattr(pipelines, "JUDGE_SAMPLE_RATE", 1.0)
    pipelines._spawn_sampled_judge(None, {"answer": "x"}, None)
    assert spawned == ["premium-judge"], "judge must run on a named daemon thread, not inline"


def test_judge_never_scores_blocked_responses(monkeypatch):
    spawned = _spawn_recorder(monkeypatch)
    monkeypatch.setattr(pipelines, "JUDGE_SAMPLE_RATE", 1.0)
    pipelines._spawn_sampled_judge(None, {"answer": "refused", "policy_verdict": "violated"}, None)
    assert spawned == []


def test_judge_verdict_parses_via_the_shared_eval_parser():
    score, rationale = pipelines._judge_response("q", "The capital is Salem.", "[ctx]")
    assert score == 5 and rationale  # mock judge pool entry, parsed by eval's parse_verdict
