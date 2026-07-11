"""Pipeline registry (CONTRACTS.md §4).

The registry is the single dispatch point of the service:
- API routes look up pipelines here instead of importing worker functions,
  so adding a capability = registering one entry (no route changes).
- /v1/models is generated from this dict, so every registered pipeline is
  automatically visible to OpenWebUI as `llm-monitor.<pipeline_id>`.
- Upgrades: register `foo-v2` beside `foo`, A/B them, delete one line to retire.
"""

from dataclasses import dataclass
from typing import Callable

from app.orchestration.contracts import ChatRequest, ChatResponse


class UnknownPipelineError(KeyError):
    """Raised for pipeline ids not in the registry. API layer maps this to 404 / `unknown_pipeline`."""


@dataclass(frozen=True)
class Pipeline:
    id: str
    description: str
    handler: Callable[[ChatRequest], ChatResponse]


PIPELINES: dict[str, Pipeline] = {}


def register(pipeline: Pipeline) -> None:
    if pipeline.id in PIPELINES:
        raise ValueError(f"Duplicate pipeline id '{pipeline.id}' — ids must be unique.")
    PIPELINES[pipeline.id] = pipeline


def get_pipeline(pipeline_id: str) -> Pipeline:
    try:
        return PIPELINES[pipeline_id]
    except KeyError:
        raise UnknownPipelineError(pipeline_id) from None
