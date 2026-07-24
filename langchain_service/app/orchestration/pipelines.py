"""The four pipelines from CONTRACTS.md §4, registered on import.

Every handler has the uniform signature handle(ChatRequest) -> ChatResponse.
Shared concerns (model resolution, chain assembly, timing) live in private
helpers so the pipeline functions read as intent, not plumbing.

Replaces OrchestrationLogic.py (original preserved in old_implementations/).
"""

import asyncio
import os
import random
import threading
import time

from langchain_core.messages import HumanMessage

from app.models.factory import ModelFactory
from app.observability import get_langchain_callbacks, observability_enabled
from app.prompts.MyPromptTemplates import PromptFactory, ASSISTANT_PROMPT_VERSION, TOOL_AGENT_PROMPT_VERSION
from app.rag.vector_store import vector_store
from app.graph.build_graph import build_graph, build_tool_graph, build_premium_graph
from app.orchestration.contracts import ChatRequest, ChatResponse, ChatMetadata
from app.orchestration.registry import Pipeline, register


def _invoke_config(request: ChatRequest, pipeline_id: str, prompt_version: str = ASSISTANT_PROMPT_VERSION) -> dict:
    """LangChain RunnableConfig shared by chains and graphs: Langfuse callbacks
    (empty list = no-op when observability is off) + trace metadata.

    langfuse_user_id / langfuse_tags are recognized by the Langfuse handler.
    thread_id is the B3 future-proofing: reserved in CONTRACTS.md, recorded on
    every generation NOW so multi-turn implicit-feedback mining can link
    consecutive turns the day memory lands. None until then — that's fine,
    the FIELD existing is what matters.
    """
    return {
        "callbacks": get_langchain_callbacks(),
        "metadata": {
            "langfuse_user_id": request.user_id,
            "langfuse_tags": [pipeline_id],
            "pipeline_id": pipeline_id,
            "prompt_version": prompt_version,
            "thread_id": None,  # populated when memory (checkpointer) arrives
        },
    }

# Compiled ONCE at import (startup), then shared statelessly across all requests:
# every .invoke() carries its own state dict, so concurrent users never interact.
# Compilation is pure graph assembly — no network, no DB.
_GRAPH_BASIC = build_graph(with_rag=False)
_GRAPH_RAG = build_graph(with_rag=True)


def _resolve_model_name(request: ChatRequest) -> str:
    return request.requested_model or os.getenv("LLM_MODEL", "mock")


def _model_label(model) -> str:
    # ChatOllama exposes .model (the tag); MockChatModel falls back to its _llm_type
    # ("mock-stub-provider"), which is what CONTRACTS.md §2 specifies for mock mode.
    return getattr(model, "model", None) or model._llm_type


def extract_usage(message) -> tuple[int, int]:
    """(prompt_tokens, completion_tokens) from an AIMessage.

    Live: ChatOllama populates usage_metadata. Mock: absent -> (0, 0), honest
    zeros rather than estimates (plan 002 risk 4). Shared by chain pipelines
    and the graph's agent node — one definition of "token count" everywhere.
    """
    usage = getattr(message, "usage_metadata", None) or {}
    return int(usage.get("input_tokens") or 0), int(usage.get("output_tokens") or 0)


def _run_assistant_chain(request: ChatRequest, pipeline_id: str, k: int | None) -> ChatResponse:
    """Shared body for the two chain pipelines. k=None means no retrieval."""
    started = time.perf_counter()

    if k is None:
        documents = []
    else:
        documents = vector_store.find_similar(request.user_message, k=k)

    context = "\n\n".join(doc.page_content for doc in documents)
    sources = [doc.metadata.get("source", "unknown") for doc in documents]

    model = ModelFactory.get_chat_model(_resolve_model_name(request))
    # Chain stops at the model (no StrOutputParser): the raw AIMessage carries
    # usage_metadata, which the parser would have thrown away. answer = .content.
    message = (PromptFactory.get_assistant_prompt() | model).invoke(
        {"user_message": request.user_message, "context": context},
        config=_invoke_config(request, pipeline_id),
    )
    prompt_tokens, completion_tokens = extract_usage(message)

    return ChatResponse(
        response=message.content,
        metadata=ChatMetadata(
            pipeline_id=pipeline_id,
            model_used=_model_label(model),
            retrieved_sources=sources,
            latency_ms=int((time.perf_counter() - started) * 1000),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        ),
    )


def chat_basic(request: ChatRequest) -> ChatResponse:
    return _run_assistant_chain(request, pipeline_id="chat-basic", k=None)


def chat_rag(request: ChatRequest) -> ChatResponse:
    return _run_assistant_chain(request, pipeline_id="chat-rag", k=2)


def _initial_state(request: ChatRequest) -> dict:
    """Fresh per-request graph state — shared by sync and tool graphs."""
    return {
        "user_id": request.user_id,
        "desired_model": _resolve_model_name(request),
        "retrieved_chunks": [],
        "messages": [HumanMessage(content=request.user_message)],
        "answer": "",
        "prompt_tokens": 0,
        "completion_tokens": 0,
    }


def _graph_response(request: ChatRequest, pipeline_id: str, final_state: dict, started: float,
                    model_label: str | None = None) -> ChatResponse:
    """Final-state -> ChatResponse assembly — shared by sync and tool graphs.

    model_label override (plan 003 Step 5b): pipelines bound to a non-default
    provider (graph-free) report THEIR model, not LLM_MODEL's — the metadata
    must tell the truth about which model actually answered."""
    sources = [doc.metadata.get("source", "unknown") for doc in final_state.get("retrieved_chunks", [])]

    return ChatResponse(
        response=final_state["answer"],
        metadata=ChatMetadata(
            pipeline_id=pipeline_id,
            model_used=model_label or _resolved_model_label(request),
            retrieved_sources=sources,
            latency_ms=int((time.perf_counter() - started) * 1000),
            prompt_tokens=final_state.get("prompt_tokens", 0),
            completion_tokens=final_state.get("completion_tokens", 0),
        ),
    )


def _run_graph(request: ChatRequest, pipeline_id: str, graph) -> ChatResponse:
    """Shared body for the two graph pipelines."""
    started = time.perf_counter()

    # config propagates to every node invocation inside the graph — the Langfuse
    # handler therefore sees retrieve/agent/respond as nested observations (D5).
    final_state = graph.invoke(_initial_state(request), config=_invoke_config(request, pipeline_id))

    return _graph_response(request, pipeline_id, final_state, started)


# Lean-tier runaway guard (plan 003 Step 3): each trip around the tool loop is
# a model call = money in live mode. 8 allows ~3 tool round-trips (each is
# agent + tools = 2 graph steps, plus START/respond overhead) — generous for
# real use, cheap as a failure ceiling. Env-tunable, no rebuild.
TOOL_RECURSION_LIMIT = int(os.getenv("TOOL_RECURSION_LIMIT", "8"))


def _run_tool_graph(request: ChatRequest, pipeline_id: str, graph, model_label: str | None = None) -> ChatResponse:
    """Tool-loop twin of _run_graph — async because the MCP adapter tools are
    async-only (Step 2 finding): sync graph.invoke() would raise on the first
    tool execution. asyncio.run() is safe here: gunicorn's sync workers have
    no running event loop, so each request gets a private loop for the graph's
    duration (same reasoning as discover_tools, inverted for request time)."""
    started = time.perf_counter()

    config = _invoke_config(request, pipeline_id, prompt_version=TOOL_AGENT_PROMPT_VERSION)
    # recursion_limit rides in the SAME config dict as callbacks/metadata —
    # LangGraph reads it per-invocation, so the cap needs no graph recompile.
    config["recursion_limit"] = TOOL_RECURSION_LIMIT

    final_state = asyncio.run(graph.ainvoke(_initial_state(request), config=config))

    return _graph_response(request, pipeline_id, final_state, started, model_label=model_label)


# ---- premium tier: runner + sampled async judge (plan 003 Step 5) ----------

# Fraction of premium responses scored by the LLM judge, post-response.
# 0.0 = never, 1.0 = every response (useful in tests). Cost is bounded by
# rate x one cheap judge call; the user's latency is bounded by ZERO because
# the judge runs on a daemon thread after the response is already returned.
JUDGE_SAMPLE_RATE = float(os.getenv("JUDGE_SAMPLE_RATE", "0.1"))


def _judge_response(user_message: str, answer: str, context: str) -> tuple[int | None, str]:
    """One judge call: rubric + judged material -> (score 1-5 | None, rationale).

    Reuses the plan-002 eval assets wholesale — same rubric file, same prompt,
    same first-colon parser — so 'the judge that scores production traffic'
    and 'the judge in the offline eval harness' are provably the same judge
    (a calibration story, not just a reuse convenience). Imported lazily:
    the eval package is not otherwise a runtime dependency."""
    from eval.eval_judge import parse_verdict, RUBRIC_PATH

    rubric = RUBRIC_PATH.read_text()
    model = ModelFactory.get_chat_model(os.getenv("LLM_MODEL", "mock"))
    message = (PromptFactory.get_llm_judge_prompt() | model).invoke(
        {"rubric": rubric, "context": context, "model_response": answer}
    )
    return parse_verdict(message.content)


def _push_judge_score(trace_id: str | None, score: int, rationale: str) -> None:
    """Best-effort Langfuse push, same posture as eval_judge's: never raises
    past this function, tolerates SDK drift, skips silently when obs is off
    or the trace id wasn't captured."""
    if not (observability_enabled() and trace_id):
        return
    try:
        from langfuse import get_client
        get_client().create_score(
            name="faithfulness.live",
            value=float(score),
            trace_id=trace_id,
            comment=rationale[:500],
        )
    except Exception as exc:  # noqa: BLE001 — observability must never break serving
        print(f"(judge score push skipped: {type(exc).__name__}: {exc})")


def _spawn_sampled_judge(request: ChatRequest, final_state: dict, trace_id: str | None) -> None:
    """Fire-and-forget judge on a daemon thread for a JUDGE_SAMPLE_RATE
    fraction of premium responses. Split from _judge_response so tests can
    call the judge synchronously and assert on it without thread timing."""
    if random.random() >= JUDGE_SAMPLE_RATE:
        return
    if final_state.get("policy_verdict") == "violated":
        return  # blocked answers are refusals; faithfulness-judging them is noise

    def run() -> None:
        try:
            context = "\n\n".join(d.page_content for d in final_state.get("retrieved_chunks", []))
            score, rationale = _judge_response(request.user_message, final_state.get("answer", ""), context)
            if score is not None:
                _push_judge_score(trace_id, score, rationale)
                print(f"(sampled judge: faithfulness={score} — {rationale[:80]})")
        except Exception as exc:  # noqa: BLE001 — the judge must NEVER take down serving
            print(f"(sampled judge skipped: {type(exc).__name__}: {exc})")

    threading.Thread(target=run, daemon=True, name="premium-judge").start()


def _run_premium_graph(request: ChatRequest, pipeline_id: str, graph) -> ChatResponse:
    """Premium twin of _run_tool_graph, two additions:

    1. When observability is on, the whole graph run is wrapped in an
       explicit Langfuse span so we hold a TRACE ID after the run — the
       post-hoc judge score needs something to attach to, and the callback
       handler's own trace context is gone by the time the judge runs.
    2. After the response is assembled (user's clock stopped), the sampled
       judge is spawned off-thread.
    """
    started = time.perf_counter()

    config = _invoke_config(request, pipeline_id, prompt_version=TOOL_AGENT_PROMPT_VERSION)
    config["recursion_limit"] = TOOL_RECURSION_LIMIT

    trace_id = None
    if observability_enabled():
        try:
            from langfuse import get_client
            with get_client().start_as_current_span(name=f"{pipeline_id}.request") as lf_span:
                trace_id = lf_span.trace_id
                final_state = asyncio.run(graph.ainvoke(_initial_state(request), config=config))
        except ImportError:
            final_state = asyncio.run(graph.ainvoke(_initial_state(request), config=config))
    else:
        final_state = asyncio.run(graph.ainvoke(_initial_state(request), config=config))

    response = _graph_response(request, pipeline_id, final_state, started)
    _spawn_sampled_judge(request, final_state, trace_id)
    return response


def _resolved_model_label(request: ChatRequest) -> str:
    # Graph nodes construct their model internally, so the pipeline layer derives
    # the label the same way the factory will: mock mode -> the contract's
    # "mock-stub-provider", otherwise the resolved model tag.
    if os.getenv("LLM_MODE") == "mock":
        return "mock-stub-provider"
    return _resolve_model_name(request)


def graph_basic(request: ChatRequest) -> ChatResponse:
    return _run_graph(request, pipeline_id="graph-basic", graph=_GRAPH_BASIC)


def graph_rag(request: ChatRequest) -> ChatResponse:
    return _run_graph(request, pipeline_id="graph-rag", graph=_GRAPH_RAG)


register(Pipeline(
    id="chat-basic",
    description="LangChain chain: prompt -> model -> parser. No retrieval.",
    handler=chat_basic,
))
register(Pipeline(
    id="chat-rag",
    description="LangChain chain with pgvector retrieval context (k=2).",
    handler=chat_rag,
))
register(Pipeline(
    id="graph-basic",
    description="LangGraph: START -> agent -> respond. No retrieval.",
    handler=graph_basic,
))
register(Pipeline(
    id="graph-rag",
    description="LangGraph: START -> retrieve (k=4) -> agent -> respond.",
    handler=graph_rag,
))


# ---- graph-tools (plan 003 Step 3) ----------------------------------------
# CONDITIONAL registration — the Stage 4 decision reconciling two rules that
# collided here:
#   * Eager discovery (Stage 2 A3): tool problems must surface at STARTUP,
#     not mid-request. So when a toolbox is configured, we discover at import
#     and a dead toolbox kills the boot — loudly, like pgvector.
#   * Honest CI: the unit suite runs with no containers at all. Import-time
#     network discovery would fail every test file that touches pipelines.
# Resolution: TOOLBOX_URL is the switch. Compose ALWAYS sets it -> in any
# real deployment the pipeline exists and discovery is eager/fail-loud.
# Unset (bare pytest) -> the capability honestly does not exist: absent from
# the registry and /v1/models, not silently mocked. The registry pattern
# makes this a non-event for every other pipeline.
if os.getenv("TOOLBOX_URL"):
    from app.tools.toolbox_client import discover_tools

    _TOOLBOX_TOOLS = discover_tools()
    _GRAPH_TOOLS = build_tool_graph(_TOOLBOX_TOOLS)

    def graph_tools(request: ChatRequest) -> ChatResponse:
        return _run_tool_graph(request, pipeline_id="graph-tools", graph=_GRAPH_TOOLS)

    register(Pipeline(
        id="graph-tools",
        description=(
            "LangGraph MCP tool loop (LEAN/cost-optimized tier): agent <-> toolbox, "
            f"{len(_TOOLBOX_TOOLS)} tools discovered at startup; no auxiliary LLM calls; "
            f"recursion-capped at {TOOL_RECURSION_LIMIT}."
        ),
        handler=graph_tools,
    ))

    # graph-premium (plan 003 Step 5) shares the toolbox dependency, so it
    # lives under the same conditional: no toolbox configured -> no premium.
    _GRAPH_PREMIUM = build_premium_graph(_TOOLBOX_TOOLS)

    def graph_premium(request: ChatRequest) -> ChatResponse:
        return _run_premium_graph(request, pipeline_id="graph-premium", graph=_GRAPH_PREMIUM)

    register(Pipeline(
        id="graph-premium",
        description=(
            "LangGraph PREMIUM/full tier: policy gate -> retrieve (k=4) -> MCP tool loop "
            "-> respond, plus sampled async LLM-judge scoring to Langfuse "
            f"(rate={JUDGE_SAMPLE_RATE}). Cost anatomy: 1 policy call + capped agent loop "
            "+ zero judge calls on the user's clock."
        ),
        handler=graph_premium,
    ))

    # graph-free (plan 003 Step 5b): SAME topology as graph-tools, compiled
    # with the per-pipeline binding provider="openai_compat" — the registry
    # as a routing table, made concrete. $0 real-model dev loop (Groq free
    # tier) + the multi-provider routing demo. Registered whenever the
    # toolbox exists; in live mode without OPENAI_COMPAT_* keys a request
    # fails with _require_env's message naming the missing variable (same
    # honest posture as the Azure pipelines — note: at REQUEST time, since
    # that's when nodes construct models; startup can't check per-pipeline
    # keys without breaking the mock-first default).
    _GRAPH_FREE = build_tool_graph(_TOOLBOX_TOOLS, provider="openai_compat")

    def _free_model_label(request: ChatRequest) -> str:
        if os.getenv("LLM_MODE") == "mock":
            return "mock-stub-provider"
        return os.getenv("OPENAI_COMPAT_MODEL") or "openai-compat"

    def graph_free(request: ChatRequest) -> ChatResponse:
        return _run_tool_graph(request, pipeline_id="graph-free", graph=_GRAPH_FREE,
                               model_label=_free_model_label(request))

    register(Pipeline(
        id="graph-free",
        description=(
            "LangGraph MCP tool loop (FREE tier): identical topology to graph-tools, "
            "bound to an OpenAI-compatible free endpoint (Groq) instead of Azure — "
            "multi-provider routing via per-pipeline model binding. Same caps as lean; "
            "no embeddings/RAG on this path (chat-only free tiers)."
        ),
        handler=graph_free,
    ))
