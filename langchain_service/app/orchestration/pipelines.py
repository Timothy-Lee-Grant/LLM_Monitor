"""The four pipelines from CONTRACTS.md §4, registered on import.

Every handler has the uniform signature handle(ChatRequest) -> ChatResponse.
Shared concerns (model resolution, chain assembly, timing) live in private
helpers so the pipeline functions read as intent, not plumbing.

Replaces OrchestrationLogic.py (original preserved in old_implementations/).
"""

import os
import time

from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import StrOutputParser

from app.models.factory import ModelFactory
from app.prompts.MyPromptTemplates import PromptFactory
from app.rag.vector_store import vector_store
from app.graph.build_graph import build_graph
from app.orchestration.contracts import ChatRequest, ChatResponse, ChatMetadata
from app.orchestration.registry import Pipeline, register

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
    chain = PromptFactory.get_assistant_prompt() | model | StrOutputParser()
    answer = chain.invoke({"user_message": request.user_message, "context": context})

    return ChatResponse(
        response=answer,
        metadata=ChatMetadata(
            pipeline_id=pipeline_id,
            model_used=_model_label(model),
            retrieved_sources=sources,
            latency_ms=int((time.perf_counter() - started) * 1000),
        ),
    )


def chat_basic(request: ChatRequest) -> ChatResponse:
    return _run_assistant_chain(request, pipeline_id="chat-basic", k=None)


def chat_rag(request: ChatRequest) -> ChatResponse:
    return _run_assistant_chain(request, pipeline_id="chat-rag", k=2)


def _run_graph(request: ChatRequest, pipeline_id: str, graph) -> ChatResponse:
    """Shared body for the two graph pipelines."""
    started = time.perf_counter()

    final_state = graph.invoke({
        "user_id": request.user_id,
        "desired_model": _resolve_model_name(request),
        "retrieved_chunks": [],
        "messages": [HumanMessage(content=request.user_message)],
        "answer": "",
    })

    sources = [doc.metadata.get("source", "unknown") for doc in final_state.get("retrieved_chunks", [])]

    return ChatResponse(
        response=final_state["answer"],
        metadata=ChatMetadata(
            pipeline_id=pipeline_id,
            model_used=_resolved_model_label(request),
            retrieved_sources=sources,
            latency_ms=int((time.perf_counter() - started) * 1000),
        ),
    )


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
