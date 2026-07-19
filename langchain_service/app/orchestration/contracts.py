"""Python-side mirror of CONTRACTS.md (§1, §2). One class per wire shape.

If a field changes here, CONTRACTS.md changes first — never the reverse.
Dataclasses (not raw dicts) so typos in field names are AttributeErrors at
development time instead of silent contract violations on the wire.
"""

from dataclasses import dataclass, field


@dataclass
class ChatRequest:
    """CONTRACTS.md §1 — canonical chat request."""
    user_message: str
    user_id: str = "anonymous"
    requested_model: str | None = None  # None -> resolved from LLM_MODEL env by the pipeline


@dataclass
class ChatMetadata:
    pipeline_id: str
    model_used: str
    retrieved_sources: list[str] = field(default_factory=list)
    latency_ms: int = 0
    # Added in plan 002 Step 4 (additive v1 change, recorded in CONTRACTS.md §2).
    # Real counts from the model's usage_metadata in live mode; zeros in mock.
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class ChatResponse:
    """CONTRACTS.md §2 — canonical success response."""
    response: str
    metadata: ChatMetadata
    status: str = "success"

    def to_dict(self) -> dict:
        """Exact wire shape from CONTRACTS.md §2."""
        return {
            "status": self.status,
            "response": self.response,
            "metadata": {
                "pipeline_id": self.metadata.pipeline_id,
                "model_used": self.metadata.model_used,
                "retrieved_sources": self.metadata.retrieved_sources,
                "latency_ms": self.metadata.latency_ms,
                "prompt_tokens": self.metadata.prompt_tokens,
                "completion_tokens": self.metadata.completion_tokens,
            },
        }
