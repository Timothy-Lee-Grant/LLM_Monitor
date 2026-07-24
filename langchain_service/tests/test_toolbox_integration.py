"""Toolbox integration tests (plan 003 Step 7).

INTEGRATION TIER: these need the real ToolBox reachable on the compose
network, so they self-gate on TOOLBOX_URL — set inside the compose network
(where they run for real), unset in bare/unit CI (where they skip, visibly).
Run them for real with:

    docker compose exec langchain_service python -m pytest tests/test_toolbox_integration.py -v

What's proven here vs the unit suite: the unit tests exercise graph anatomy
with stand-in tools; THESE prove the actual wire — MCP discovery over
streamable HTTP, adapter-built tools executing against the .NET server, and
the full registry -> pipeline -> graph -> toolbox -> answer path.
"""

import json
import os

import pytest

requires_toolbox = pytest.mark.skipif(
    not os.getenv("TOOLBOX_URL"),
    reason="requires the compose network (TOOLBOX_URL unset — unit CI skips this tier)",
)


@requires_toolbox
def test_toolbox_tools_discovered():
    """The walkthrough doc's discovery assertion, verbatim."""
    from app.tools.toolbox_client import discover_tools

    names = {t.name for t in discover_tools()}
    assert {"ping", "server_info", "current_time"} <= names, names


@requires_toolbox
def test_registry_exposes_the_tool_pipelines():
    import app.orchestration.pipelines  # noqa: F401 — registers pipelines
    from app.orchestration.registry import PIPELINES

    assert {"graph-tools", "graph-premium", "graph-free"} <= set(PIPELINES)


@requires_toolbox
def test_agent_can_call_ping():
    """The walkthrough doc's end-to-end assertion: a REAL tool call crosses
    containers and its output survives into the final answer. Mock mode makes
    the model deterministic (TOOLCALL protocol); the tool itself is real."""
    import app.orchestration.pipelines  # noqa: F401
    from app.orchestration.registry import get_pipeline
    from app.orchestration.contracts import ChatRequest

    response = get_pipeline("graph-tools").handler(
        ChatRequest(user_message='TOOLCALL ping {"message": "e2e"}')
    )
    assert "pong: e2e" in response.response
    assert response.metadata.pipeline_id == "graph-tools"


@requires_toolbox
def test_premium_full_path_and_gate():
    import app.orchestration.pipelines  # noqa: F401
    from app.orchestration.registry import get_pipeline
    from app.orchestration.contracts import ChatRequest

    handler = get_pipeline("graph-premium").handler

    ok = handler(ChatRequest(user_message='TOOLCALL ping {"message": "premium-e2e"}'))
    assert "pong: premium-e2e" in ok.response
    assert ok.metadata.retrieved_sources, "premium must retrieve (tier contract)"

    blocked = handler(ChatRequest(user_message="BLOCKME do the forbidden thing"))
    assert "can't help" in blocked.response
    assert blocked.metadata.retrieved_sources == [], "blocked requests must not reach retrieval"


@requires_toolbox
def test_free_tier_runs_and_reports_honest_label():
    import app.orchestration.pipelines  # noqa: F401
    from app.orchestration.registry import get_pipeline
    from app.orchestration.contracts import ChatRequest

    response = get_pipeline("graph-free").handler(
        ChatRequest(user_message='TOOLCALL ping {"message": "free-e2e"}')
    )
    assert "pong: free-e2e" in response.response
    # mock mode: the label contract still holds on the routed pipeline
    assert response.metadata.model_used == "mock-stub-provider"


@requires_toolbox
def test_openai_surface_lists_tool_pipelines():
    from app.api.FlaskServer import create_app

    payload = json.loads(create_app().test_client().get("/v1/models").data)
    ids = {m["id"] for m in payload["data"]}
    assert {"llm-monitor.graph-tools", "llm-monitor.graph-premium", "llm-monitor.graph-free"} <= ids
