"""HTTP layer (plan 001 Step 6). Thin by design:

    validate -> build ChatRequest -> registry dispatch -> jsonify contract shape

All shapes come from CONTRACTS.md. No business logic lives here — routes are
shims over the pipeline registry, so adding a pipeline requires ZERO changes
in this file (it appears in /v1/models automatically, and the OpenAI surface
reaches it via its model id).

Uses the Flask application-factory pattern (create_app), the standard shape
for testability (tests build a fresh app) and for WSGI servers (wsgi.py).
"""

import time
import uuid
import os

from flask import Flask, jsonify, request

import app.orchestration.pipelines  # noqa: F401 — importing registers all pipelines
from app.metrics import metrics_payload
from app.orchestration.registry import PIPELINES, get_pipeline, UnknownPipelineError
from app.orchestration.contracts import ChatRequest

# CONTRACTS.md §4: OpenAI-visible model id = "llm-monitor." + pipeline_id
MODEL_ID_PREFIX = "llm-monitor."

# CONTRACTS.md §6: canonical route -> pipeline id
PIPELINE_ROUTES = {
    "/chat/basic": "chat-basic",
    "/chat/rag": "chat-rag",
    "/graph/basic": "graph-basic",
    "/graph/rag": "graph-rag",
    # plan 003 Step 3. Registration is conditional on TOOLBOX_URL (see
    # pipelines.py) but this map is static — when the pipeline isn't
    # registered, this route 404s with the contract's unknown_pipeline
    # error, which is exactly the right answer for "capability not
    # configured in this deployment".
    "/graph/tools": "graph-tools",
}


def _error(http_status: int, code: str, message: str):
    """CONTRACTS.md §3 error shape."""
    return jsonify({"status": "error", "error": {"code": code, "message": message}}), http_status


def _parse_chat_request(data: dict) -> ChatRequest | None:
    """Returns None when user_message is missing/invalid (caller sends the 400)."""
    user_message = data.get("user_message")
    if not isinstance(user_message, str) or not user_message.strip():
        return None
    return ChatRequest(
        user_message=user_message,
        user_id=str(data.get("user_id", "anonymous")),
        requested_model=data.get("requested_model"),
    )


def create_app() -> Flask:
    app = Flask(__name__)

    # ---- canonical pipeline routes (CONTRACTS.md §1/§2) ----

    def _dispatch(pipeline_id: str):
        data = request.get_json(silent=True)
        if data is None:
            return _error(400, "invalid_request", "Body must be valid JSON.")
        chat_request = _parse_chat_request(data)
        if chat_request is None:
            return _error(400, "invalid_request", "'user_message' is required and must be a non-empty string.")
        chat_response = get_pipeline(pipeline_id).handler(chat_request)
        return jsonify(chat_response.to_dict())

    for route, pipeline_id in PIPELINE_ROUTES.items():
        # default-arg binding (pid=pipeline_id) freezes the loop variable per closure
        app.add_url_rule(
            route,
            endpoint=f"pipeline_{pipeline_id}",
            view_func=lambda pid=pipeline_id: _dispatch(pid),
            methods=["POST"],
        )

    # ---- health (CONTRACTS.md §6; compose healthcheck target) ----

    @app.route("/healthz", methods=["GET"])
    def healthz():
        return jsonify({"status": "ok", "mode": os.getenv("LLM_MODE", "mock")})

    # ---- Prometheus scrape target (plan 002 Step 4) ----
    # Always exposed, never gated: PULL model means this costs nothing unless
    # someone scrapes it (and only the obs profile runs a scraper).

    @app.route("/metrics", methods=["GET"])
    def metrics():
        payload, content_type = metrics_payload()
        return payload, 200, {"Content-Type": content_type}

    # ---- OpenAI-compatible surface (CONTRACTS.md §5) ----

    @app.route("/v1/models", methods=["GET"])
    def list_models():
        # Generated from the registry: a new pipeline is instantly visible to OpenWebUI.
        return jsonify({
            "object": "list",
            "data": [
                {"id": f"{MODEL_ID_PREFIX}{pipeline_id}", "object": "model", "owned_by": "llm-monitor"}
                for pipeline_id in PIPELINES
            ],
        })

    @app.route("/v1/chat/completions", methods=["POST"])
    def chat_completions():
        data = request.get_json(silent=True)
        if data is None:
            return _error(400, "invalid_request", "Body must be valid JSON.")

        model_id = data.get("model", "")
        pipeline_id = model_id.removeprefix(MODEL_ID_PREFIX)

        messages = data.get("messages") or []
        user_message = next(
            (m.get("content") for m in reversed(messages) if m.get("role") == "user"),
            None,
        )
        if not user_message:
            return _error(400, "invalid_request", "messages[] must contain at least one 'user' role entry.")

        chat_request = ChatRequest(user_message=user_message, user_id=str(data.get("user", "anonymous")))
        chat_response = get_pipeline(pipeline_id).handler(chat_request)

        # Non-streaming only (CONTRACTS.md §5): a `stream: true` request still gets
        # a complete JSON body. SSE streaming is on the roadmap, not in this cleanup.
        return jsonify({
            "id": f"chatcmpl-{uuid.uuid4()}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_id,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": chat_response.response},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        })

    # ---- error mapping (CONTRACTS.md §3) ----

    @app.errorhandler(UnknownPipelineError)
    def handle_unknown_pipeline(exc):
        return _error(404, "unknown_pipeline", f"No pipeline registered for id '{exc.args[0]}'.")

    @app.errorhandler(RuntimeError)
    def handle_upstream_failure(exc):
        # ModelFactory raises RuntimeError when Ollama can't supply a model.
        app.logger.exception("Upstream model failure")
        return _error(502, "upstream_model_error", str(exc))

    @app.errorhandler(Exception)
    def handle_internal_error(exc):
        # Generic message on the wire, full traceback in the logs — never leak internals.
        app.logger.exception("Unhandled error")
        return _error(500, "internal_error", "An internal error occurred.")

    return app
