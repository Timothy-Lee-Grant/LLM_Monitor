"""Pipeline registry (CONTRACTS.md §4).

The registry is the single dispatch point of the service:
- API routes look up pipelines here instead of importing worker functions,
  so adding a capability = registering one entry (no route changes).
- /v1/models is generated from this dict, so every registered pipeline is
  automatically visible to OpenWebUI as `llm-monitor.<pipeline_id>`.
- Upgrades: register `foo-v2` beside `foo`, A/B them, delete one line to retire.
"""

import time
from dataclasses import dataclass, replace
from typing import Callable

from app.observability import get_tracer
from app.metrics import LLM_REQUESTS, LLM_DURATION, LLM_TOKENS
from app.orchestration.contracts import ChatRequest, ChatResponse


class UnknownPipelineError(KeyError):
    """Raised for pipeline ids not in the registry. API layer maps this to 404 / `unknown_pipeline`."""


@dataclass(frozen=True)
class Pipeline:
    id: str
    description: str
    handler: Callable[[ChatRequest], ChatResponse]


PIPELINES: dict[str, Pipeline] = {}


def _instrumented(pipeline_id: str, handler: Callable[[ChatRequest], ChatResponse]):
    """Wrap a handler in a `pipeline.dispatch` span (plan 002 Step 3).

    This is the "instrumentation attaches at the registry boundary" decision
    made concrete: EVERY pipeline — current and future — is traced because
    registration itself does the wrapping. No pipeline author ever thinks
    about spans. When observability is disabled the span is a no-op
    (see app/observability.py on the API/SDK split), so this wrapper is
    always safe and always on.
    """
    def dispatch_with_span(request: ChatRequest) -> ChatResponse:
        started = time.perf_counter()
        with get_tracer().start_as_current_span("pipeline.dispatch") as span:
            span.set_attribute("llm.pipeline_id", pipeline_id)
            span.set_attribute("llm.request.user_id", request.user_id)
            try:
                response = handler(request)
            except Exception as exc:
                # Metrics count the failure; the span records it; the API
                # layer still owns the HTTP mapping (CONTRACTS.md §3).
                LLM_REQUESTS.labels(pipeline_id=pipeline_id, status="error").inc()
                span.record_exception(exc)
                raise
            finally:
                LLM_DURATION.labels(pipeline_id=pipeline_id).observe(time.perf_counter() - started)

            LLM_REQUESTS.labels(pipeline_id=pipeline_id, status="success").inc()
            LLM_TOKENS.labels(pipeline_id=pipeline_id, direction="prompt").inc(response.metadata.prompt_tokens)
            LLM_TOKENS.labels(pipeline_id=pipeline_id, direction="completion").inc(response.metadata.completion_tokens)

            span.set_attribute("llm.model_used", response.metadata.model_used)
            span.set_attribute("llm.latency_ms", response.metadata.latency_ms)
            span.set_attribute("llm.tokens.prompt", response.metadata.prompt_tokens)
            span.set_attribute("llm.tokens.completion", response.metadata.completion_tokens)
            span.set_attribute("rag.sources_count", len(response.metadata.retrieved_sources))
            return response
    return dispatch_with_span


def register(pipeline: Pipeline) -> None:
    if pipeline.id in PIPELINES:
        raise ValueError(f"Duplicate pipeline id '{pipeline.id}' — ids must be unique.")
    PIPELINES[pipeline.id] = replace(pipeline, handler=_instrumented(pipeline.id, pipeline.handler))


def get_pipeline(pipeline_id: str) -> Pipeline:
    try:
        return PIPELINES[pipeline_id]
    except KeyError:
        raise UnknownPipelineError(pipeline_id) from None
