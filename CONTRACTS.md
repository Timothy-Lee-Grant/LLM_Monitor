# LLM_Monitor Service Contracts (v1)

This document is the single source of truth for every HTTP boundary in the system.
Both the dotnet gateway and the langchain_service implement these shapes exactly.
Any change to a wire shape MUST be made here first, and MUST be additive
(new optional fields only — never rename or remove a field within v1).

Wire convention: **snake_case** for all JSON field names, at every boundary.
(C# uses PascalCase properties internally and maps via `JsonNamingPolicy.SnakeCaseLower`;
Python uses snake_case natively. No service ever hand-renames fields.)

---

## 1. Canonical Chat Request

Sent to every pipeline endpoint (`/chat/*`, `/graph/*`).

```json
{
  "user_id": "string",
  "user_message": "string",
  "requested_model": "string"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `user_id` | string | no (default `"anonymous"`) | Opaque caller identifier. Future: derived from gateway auth, not client-supplied. |
| `user_message` | string | **yes** | Non-empty. The raw user message. |
| `requested_model` | string | no | Ollama model tag (e.g. `qwen2.5:1.5b`). Ignored when `LLM_MODE=mock`. Defaults to `LLM_MODEL` env. |

Reserved future fields (additive, do not reuse these names for anything else):
`attachments` (list), `thread_id` (string, for checkpointer memory), `options` (object).

## 2. Canonical Success Response

```json
{
  "status": "success",
  "response": "string",
  "metadata": {
    "pipeline_id": "string",
    "model_used": "string",
    "retrieved_sources": ["string"],
    "latency_ms": 0
  }
}
```

| Field | Type | Notes |
|---|---|---|
| `status` | `"success"` | Literal. |
| `response` | string | The assistant's final answer text. |
| `metadata.pipeline_id` | string | Registry id that served the request (see §4). |
| `metadata.model_used` | string | Actual model invoked (`mock-stub-provider` in mock mode). |
| `metadata.retrieved_sources` | list of string | `source` metadata values of retrieved chunks. Empty list for non-RAG pipelines. |
| `metadata.latency_ms` | int | End-to-end pipeline execution time. |
| `metadata.prompt_tokens` | int | *Added 2026_07_12 (plan 002, additive).* Model-reported prompt token count; 0 in mock mode. |
| `metadata.completion_tokens` | int | *Added 2026_07_12 (plan 002, additive).* Model-reported completion token count; 0 in mock mode. |

## 3. Canonical Error Response

```json
{
  "status": "error",
  "error": {
    "code": "string",
    "message": "string"
  }
}
```

| HTTP status | `error.code` | When |
|---|---|---|
| 400 | `invalid_request` | Missing/empty `user_message`, malformed JSON, wrong types. |
| 404 | `unknown_pipeline` | Model id / pipeline id not in registry. |
| 502 | `upstream_model_error` | Ollama unreachable, model pull failed, model invocation raised. |
| 500 | `internal_error` | Anything unhandled. Message is generic; details go to logs, never the wire. |

## 4. Pipeline Registry IDs

| Pipeline id | Engine | RAG | Description |
|---|---|---|---|
| `chat-basic` | LangChain chain | no | Prompt → model → parser. |
| `chat-rag` | LangChain chain | yes | Retrieval context injected into prompt. |
| `graph-basic` | LangGraph | no | Graph path, retrieve node skipped. |
| `graph-rag` | LangGraph | yes | Graph path with retrieve node. |

OpenAI model-id mapping rule: model id = `llm-monitor.<pipeline_id>`
(e.g. `llm-monitor.graph-rag`). `/v1/models` is generated from the registry —
adding a registry entry automatically exposes a new model to OpenWebUI.

## 5. OpenAI-Compatible Surface

For OpenWebUI (and any OpenAI-SDK client). Follows the OpenAI schema verbatim;
only the subset below is implemented.

- `GET /v1/models` → `{"object": "list", "data": [{"id": "llm-monitor.chat-basic", "object": "model", "owned_by": "llm-monitor"}, ...]}`
- `POST /v1/chat/completions` → request: standard OpenAI shape; `model` selects the pipeline per §4;
  the last `messages[]` entry with role `user` becomes `user_message`.
  Response: standard `chat.completion` object, `choices[0].message.content` = pipeline `response`.
  `stream: true` is NOT yet supported (deferred; responses are non-streaming).

## 6. Endpoint & Network Topology

langchain_service routes (Flask, port 5000 in-container):

| Route | Method | Contract |
|---|---|---|
| `/healthz` | GET | `{"status": "ok", "mode": "mock"\|"live"}` |
| `/chat/basic`, `/chat/rag`, `/graph/basic`, `/graph/rag` | POST | §1 → §2/§3 |
| `/v1/models`, `/v1/chat/completions` | GET / POST | §5 |

Access paths:

| Path | URL | Purpose |
|---|---|---|
| Test (dev only) | `host:5001/<route>` | Direct to langchain_service. Exists only while compose maps `5001:5000`; deleting that mapping is the production lockdown switch. No code change involved. |
| Real | `host:5000/api/llm/<route>` | dotnet gateway → telemetry middleware → YARP → langchain_service `/<route>` (prefix `/api/llm` stripped by YARP transform). |
| Real (OpenAI) | `host:5000/v1/<route>` | Gateway-proxied OpenAI surface; what OpenWebUI uses. |

Both access paths hit the identical handler. Gateway adds telemetry today;
auth and rate limiting are future middleware in front of the YARP forwarder.

---

*v1 — 2026_07_10. Changes require a new entry in the relevant AI_Implementation_Plans document.*
