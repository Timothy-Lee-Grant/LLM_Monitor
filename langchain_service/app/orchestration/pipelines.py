"""The four pipelines from CONTRACTS.md §4, registered on import.

Every handler has the uniform signature handle(ChatRequest) -> ChatResponse.
Shared concerns (model resolution, chain assembly, timing) live in private
helpers so the pipeline functions read as intent, not plumbing.

Replaces OrchestrationLogic.py (original preserved in old_implementations/).
"""

import os
import time

from langchain_core.output_parsers import StrOutputParser

from app.models.factory import ModelFactory
from app.prompts.MyPromptTemplates import PromptFactory
from app.rag.vector_store import vector_store
from app.orchestration.contracts import ChatRequest, ChatResponse, ChatMetadata
from app.orchestration.registry import Pipeline, register


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


def _graph_not_ready(request: ChatRequest) -> ChatResponse:
    # Honest placeholder: registered so the registry is complete (4 ids, /v1/models
    # correct), but loudly unfinished. Swapped for compiled graphs in plan 001 Step 5.
    raise NotImplementedError("Graph pipelines are wired in plan 001 Step 5.")


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
    description="LangGraph path, retrieve node skipped. (Step 5)",
    handler=_graph_not_ready,
))
register(Pipeline(
    id="graph-rag",
    description="LangGraph path with retrieve node (k=4). (Step 5)",
    handler=_graph_not_ready,
))
