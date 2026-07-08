2026_07_08_11_05-Portfolio_Roadmap_OpenWebUI_LangGraph_Observability_And_Evals

# Portfolio Roadmap: OpenWebUI, LangGraph, Observability, and AI Evaluation

This is your step-by-step implementation guide for turning LLM_Monitor into a professional portfolio project. It covers everything you outlined — OpenWebUI as a frontend, LangGraph, local observability, AI testing metrics, verifying your RAG system, tool use, and memory — plus additions that will matter to a Microsoft hiring manager.

**What problem is being solved?** Right now you have proven-out *parts* (Docker skeleton, Flask endpoints, a mock/live model factory, a pgvector container). What you don't yet have is a *system*: no real frontend, no graph orchestration, no visibility into what the AI is doing, and no way to prove any of it works. Hiring managers don't hire people who can call an LLM — they hire people who can operate, observe, evaluate, and defend an AI system in production. That is exactly the gap this roadmap closes.

**How to use this document:** Work through the phases in order. Each phase has numbered steps, code examples to learn from (remember: you type everything yourself), a "Definition of Done," and a "What to say in an interview" note. Phase 0 is mandatory first — everything else builds on a foundation that currently has cracks.

---

## Table of Contents

1. [Target Architecture](#target-architecture)
2. [Phase 0 — Verify and Fix the Foundation (including "is my RAG real?")](#phase-0)
3. [Phase 1 — OpenAI-Compatible API + OpenWebUI Frontend](#phase-1)
4. [Phase 2 — LangGraph: The Real Orchestration Pipeline](#phase-2)
5. [Phase 3 — Tool Use](#phase-3)
6. [Phase 4 — Memory (Short-Term and Long-Term)](#phase-4)
7. [Phase 5 — Local Observability](#phase-5)
8. [Phase 6 — AI Evaluation and Testing Metrics](#phase-6)
9. [Phase 7 — Portfolio Polish (CI, Security, README)](#phase-7)
10. [Milestone Plan and Definition of Done](#milestones)
11. [Common Mistakes to Avoid](#common-mistakes)

---

<a name="target-architecture"></a>
## 1. Target Architecture

Here is where you are going. Study this before writing any code — every phase fills in one region of this picture.

```
                                   ┌──────────────────────────────────────────────┐
                                   │              Docker Network                  │
                                   │                                              │
 Browser ──► ┌────────────┐        │  ┌─────────────────┐      ┌───────────────┐  │
             │ OpenWebUI  │────────┼─►│  dotnet_server  │─────►│ langchain_svc │  │
             │ (frontend) │ OpenAI │  │  (API Gateway,  │ /v1  │ (Flask + Lang │  │
             │ port 3000  │  API   │  │  YARP proxy,    │      │  Graph agent) │  │
             └────────────┘ format │  │  Telemetry MW)  │      └──────┬────────┘  │
                                   │  └────────┬────────┘             │           │
                                   │           │ traces/metrics       │           │
                                   │           ▼                      ▼           │
                                   │  ┌─────────────────┐   ┌──────────────────┐  │
                                   │  │  Observability  │   │ ollama (live)    │  │
                                   │  │  Langfuse +     │   │ port 11434       │  │
                                   │  │  Prometheus +   │   └──────────────────┘  │
                                   │  │  Grafana        │   ┌──────────────────┐  │
                                   │  └─────────────────┘   │ pgvector (pg16)  │  │
                                   │                        │  - RAG vectors   │  │
                                   │                        │  - chat memory   │  │
                                   │                        │  (checkpoints)   │  │
                                   │                        └──────────────────┘  │
                                   └──────────────────────────────────────────────┘

  Offline (not in the request path):
  ┌──────────────────────────────────────────────────────────────┐
  │  Evaluation Harness (pytest + golden dataset + RAGAS +       │
  │  LLM-as-judge) — runs locally and in CI, logs to Langfuse    │
  └──────────────────────────────────────────────────────────────┘
```

**The cast of characters** (since you like personified components):

| Component | Character | Job |
|---|---|---|
| OpenWebUI | The receptionist | Pretty face; speaks only "OpenAI API" — refuses to learn your dialect |
| dotnet_server | The building security guard | Everyone passes through him; he logs who came in, stamps a correlation ID on their forehead, and points them to the right office (YARP) |
| langchain_service | The case worker | Takes the request through a fixed workflow: policy check → gather files (RAG) → maybe call specialists (tools) → write the answer |
| LangGraph | The case worker's checklist on a clipboard | The *explicit* workflow. No step gets skipped, every decision is recorded |
| pgvector | The filing cabinet | Two drawers: one for company knowledge (RAG), one for conversation notes (memory/checkpoints) |
| Langfuse | The security camera system | Watches every LLM call: what went in, what came out, how long, how many tokens |
| Eval harness | The quality inspector | Comes in after hours, runs the same 50 test cases, and writes a scorecard |

**A key architectural decision you should make now:** the dotnet server becomes a real **API gateway** using YARP (you already reference `Yarp.ReverseProxy 2.3.0` in `server.csproj` but never use it — a reviewer *will* notice an unused dependency). OpenWebUI talks OpenAI-format to the gateway; the gateway does telemetry, correlation IDs, and (later) auth/rate limiting, then proxies to the Flask service. This gives you a legitimate reason for the C# tier to exist, which is currently a weak point in the story ("why do you have a .NET server that just forwards JSON?").

---

<a name="phase-0"></a>
## 2. Phase 0 — Verify and Fix the Foundation

**What problem is being solved?** You said you doubt your RAG system actually works. Your doubt is justified — reading the code, there are several reasons it may *appear* to work while doing nothing, or fail silently. Before adding features on top, you must be able to *prove* what the system is doing. This phase teaches you to interrogate a running system, which is itself an interview-grade skill ("how would you debug a vector store that returns nothing?").

### 2.1 Findings from reading your code (verify each yourself)

| # | File | Finding | Severity |
|---|---|---|---|
| F1 | `app/rag/Ingestion.py` | `RunIdempotentRagIngestion` is **not idempotent**: `vector_store.add_documents(raw_docs)` with no `ids` inserts duplicate rows on *every container restart*. After 10 restarts you have 10 copies of each policy document, which skews similarity search. | High |
| F2 | `server/controllers/LlmController.cs` | Posts to `{OLLAMA_BASE_URL}/api/chat` — but (a) `OLLAMA_BASE_URL` is never set for `dotnet_server` in docker-compose, so it is `null`; (b) even if set, it points at **Ollama**, not your langchain service; (c) Flask's `/api/chat` endpoint is commented out. Three independent reasons this path cannot work. | High |
| F3 | `server/controllers/LlmController.cs` | Content type `"/application/json"` has a leading slash — invalid MIME type. Should be `"application/json"`. | Medium |
| F4 | `app/rag/Ingestion.py` | `mode = os.getenv("LLM_MODE")` is read **once at import time** into a module-level variable, while other files call `os.getenv` at call time. If anything ever changes the env var (tests will!), behavior diverges. | Medium |
| F5 | `app/models/factory.py` | `get_embedding_model` ignores `userDesiredModel` when pulling (hardcodes `"nomic-embed-text"` in `TryGetOllamaEmbeddingModel`) but then uses `userDesiredModel` for the actual `OllamaEmbeddings`. If a caller passes anything else, the pull check and the model used disagree. Also the fallback URL here is `http://ollama_service:11434` while everywhere else uses `http://ollama:11434`. Both happen to resolve (service name vs `container_name`) but the inconsistency is a code smell. | Medium |
| F6 | `langchain_service/dockerfile` | Base image `python:3.9.13-slim-buster` — Debian Buster is end-of-life (no security patches) and Python 3.9 is near end-of-life. A portfolio reviewer scanning your Dockerfile sees this immediately. Move to `python:3.12-slim-bookworm`. | Medium |
| F7 | `requirements.txt` | No version pins. Your build is not reproducible — `pip install` today and in three months produce different systems. Pin everything (`flask==3.0.3` style) or use a lock file. | Medium |
| F8 | Root `.env` | Committed to git with `POSTGRES_PASSWORD`. It's a dev password, but the *habit* is what reviewers judge. Add `.env` to `.gitignore`, commit a `.env.example` with placeholder values instead. (Remember your own rule: never rewrite git history — just stop tracking it going forward with `git rm --cached .env`.) | Medium |
| F9 | `app/rag/Ingestion.py` | In mock mode `FindSemanticlyClosestElement` returns `[]` and ingestion is skipped — correct — but there is **no logging** either way. Silence is why you can't tell if RAG works. | Low |

### 2.2 Step-by-step: prove whether RAG works

Do this with the system running in **live** mode (`./build.sh --mode live`).

**Step 1 — Confirm the tables exist.** LangChain's `PGVector` creates its own tables (`langchain_pg_collection`, `langchain_pg_embedding`) on first use. Ask postgres directly:

```bash
docker exec -it pgvector_service psql -U timothy -d my_postgres_db -c "\dt"
```

Expected: `langchain_pg_collection` and `langchain_pg_embedding`. If they're missing, `InitVectorStore` never ran successfully — check `docker logs langchain_service` for a connection error (see F5's URL inconsistency and your connection string host `pgvector_service`).

**Step 2 — Confirm your collection and count the rows.**

```bash
docker exec -it pgvector_service psql -U timothy -d my_postgres_db -c \
 "SELECT c.name, COUNT(e.id) FROM langchain_pg_collection c
  LEFT JOIN langchain_pg_embedding e ON e.collection_id = c.uuid
  GROUP BY c.name;"
```

Expected: `company_policies | 2`. If you see `2 × (number of times you've restarted)`, you have just *observed* finding F1 (non-idempotent ingestion) with your own eyes.

**Step 3 — Inspect an actual embedding.**

```bash
docker exec -it pgvector_service psql -U timothy -d my_postgres_db -c \
 "SELECT document, LEFT(embedding::text, 80) FROM langchain_pg_embedding LIMIT 2;"
```

You should see your policy text and the first numbers of a 768-dimension vector. This answers your old comment in `init.sql` ("TODO: Investigate how this is working") — LangChain bypassed your commented-out `corporate_policies` table entirely and made its own schema. Your `init.sql` only needed to install the extension.

**Step 4 — Run a similarity search with raw SQL (no LangChain).** This is the test that proves the *database* works independent of your Python code. You need a query vector; get one from Ollama:

```bash
curl -s http://localhost:11434/api/embeddings -d \
 '{"model":"nomic-embed-text","prompt":"can I run scripts on my work laptop?"}' \
 | python3 -c "import sys,json; print(json.load(sys.stdin)['embedding'])" > /tmp/vec.txt
```

Then (conceptually — you'll wire the vector into the query):

```sql
SELECT document, embedding <=> '[...vector...]' AS cosine_distance
FROM langchain_pg_embedding
ORDER BY cosine_distance ASC
LIMIT 2;
```

`<=>` is pgvector's cosine-distance operator. The scripting-policy document should come back with a *smaller* distance than the explosives-policy document. When you see that ordering, your RAG storage and search are provably real.

**Step 5 — Test end-to-end through Flask.**

```bash
curl -s -X POST http://localhost:5001/test/langchain/chatnosecurityrag \
  -H "Content-Type: application/json" \
  -d '{"user_requested_model":"qwen2.5:1.5b","user_id":1,"user_message":"Am I allowed to use scripting tools at work?"}'
```

The answer should reference the security policy. If Steps 1–4 pass but Step 5's answer ignores the context, the problem is in prompt assembly (`GetHappyEncouragingAssistentRagPrompt` puts context in a `system` message *after* the user message — see Phase 2 for the fix).

### 2.3 Fixes to implement (in order)

1. **Make ingestion actually idempotent.** `add_documents` accepts an `ids` parameter. Derive deterministic IDs from content so re-running replaces instead of duplicates:

```python
import hashlib

def _doc_id(doc) -> str:
    return hashlib.sha256(
        (doc.metadata["source"] + doc.page_content).encode()
    ).hexdigest()

vector_store.add_documents(raw_docs, ids=[_doc_id(d) for d in raw_docs])
```

Then restart the container twice and re-run Step 2 — the count must stay at 2. *That* is the test for idempotency, and "content-hash as natural key for idempotent writes" is a sentence worth saying in an interview.

2. **Fix the gateway path (F2, F3).** Add a `LANGCHAIN_BASE_URL=http://langchain_service:5000` environment variable to `dotnet_server` in docker-compose, read *that* in the controller, and fix the MIME type. (Phase 1 will replace this controller with YARP anyway, but fix it first so you have a working baseline.)

3. **Unify env reading (F4).** Create one config module that reads env vars once, in one place, with logging:

```python
# app/config.py
import os, logging

log = logging.getLogger(__name__)

class Config:
    LLM_MODE = os.getenv("LLM_MODE", "mock")
    LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:1.5b")
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
    PG_CONN = (
        f"postgresql+psycopg://{os.getenv('POSTGRES_USER','admin')}:"
        f"{os.getenv('POSTGRES_PASSWORD','secret_pass')}"
        f"@pgvector-service:5432/{os.getenv('POSTGRES_DB','vectordb')}"
    )

log.info("Config loaded: mode=%s model=%s", Config.LLM_MODE, Config.LLM_MODEL)
```

Every other file imports `Config` instead of calling `os.getenv`. This is the "single source of truth" pattern and it kills the F5 URL-inconsistency class of bug permanently.

4. **Upgrade the base image and pin dependencies (F6, F7).** `python:3.12-slim-bookworm`, and generate pins with `pip freeze > requirements.txt` from a working environment (or better: adopt `uv` and a `pyproject.toml` — modern and interview-relevant).

5. **Stop tracking `.env` (F8)** and add `.env.example`.

**Definition of Done for Phase 0:** Steps 1–5 of §2.2 all pass; container restarted twice with row count stable; `curl` through the dotnet gateway reaches Flask successfully.

**Interview relevance:** "Tell me about a bug you found" — F1 is a great story: a function *named* Idempotent that wasn't, discovered by querying the database directly, fixed with content-addressed IDs, verified with a restart test.

---

<a name="phase-1"></a>
## 3. Phase 1 — OpenAI-Compatible API + OpenWebUI Frontend

**What problem is being solved?** You need a frontend, and you chose OpenWebUI. The crucial design fact: **OpenWebUI does not speak "your API" — it speaks the OpenAI API dialect.** Instead of seeing this as a constraint, treat it as the feature: you will implement an OpenAI-compatible facade, which is the de-facto industry standard for LLM serving (Ollama, vLLM, Azure OpenAI, LM Studio all expose it). "I implemented an OpenAI-compatible serving layer with SSE streaming" is a strong resume line.

**Why this design:** OpenWebUI → dotnet gateway (YARP) → Flask. You *could* point OpenWebUI directly at Flask, but routing it through the gateway means every conversation flows through your telemetry middleware — which Phase 5 depends on.

### 3.1 Implement the OpenAI facade in Flask

OpenWebUI needs exactly two endpoints:

**Endpoint 1: `GET /v1/models`** — OpenWebUI calls this to populate its model dropdown.

```python
@app.route("/v1/models", methods=["GET"])
def list_models():
    return jsonify({
        "object": "list",
        "data": [
            {"id": "llm-monitor-agent", "object": "model", "owned_by": "timothy"},
            {"id": "llm-monitor-agent-mock", "object": "model", "owned_by": "timothy"},
        ]
    })
```

Note the idea: the "models" you advertise are not raw Ollama models — they are *your pipelines*. Selecting `llm-monitor-agent` in the UI runs your whole LangGraph. This is how products like Copilot expose "models" that are actually agent systems.

**Endpoint 2: `POST /v1/chat/completions`** — the request body you'll receive:

```json
{
  "model": "llm-monitor-agent",
  "messages": [
    {"role": "user", "content": "hello"},
    {"role": "assistant", "content": "hi!"},
    {"role": "user", "content": "am I allowed to use scripts at work?"}
  ],
  "stream": true
}
```

Two response modes. Non-streaming (implement first):

```python
import time, uuid

@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    data = request.get_json()
    user_message = data["messages"][-1]["content"]
    answer = run_agent(user_message, thread_id=_thread_id_from(data))  # your pipeline

    return jsonify({
        "id": f"chatcmpl-{uuid.uuid4()}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": data.get("model", "llm-monitor-agent"),
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": answer},
            "finish_reason": "stop"
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    })
```

Streaming (implement second — OpenWebUI feels dead without it). The OpenAI streaming format is **Server-Sent Events**: each chunk is a line starting with `data: ` containing a JSON "delta", terminated by `data: [DONE]`:

```python
from flask import Response, stream_with_context
import json

def _sse_chunk(chunk_id, model, delta_content=None, finish=None):
    return "data: " + json.dumps({
        "id": chunk_id, "object": "chat.completion.chunk",
        "created": int(time.time()), "model": model,
        "choices": [{"index": 0,
                     "delta": ({"content": delta_content} if delta_content else {}),
                     "finish_reason": finish}]
    }) + "\n\n"

@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    data = request.get_json()
    if not data.get("stream", False):
        return _non_streaming_completion(data)

    chunk_id = f"chatcmpl-{uuid.uuid4()}"
    model = data.get("model", "llm-monitor-agent")

    def generate():
        for token in run_agent_streaming(data):      # yields strings
            yield _sse_chunk(chunk_id, model, delta_content=token)
        yield _sse_chunk(chunk_id, model, finish="stop")
        yield "data: [DONE]\n\n"

    return Response(stream_with_context(generate()),
                    mimetype="text/event-stream")
```

For `run_agent_streaming`, LangChain chains and LangGraph both support `.stream()` — in Phase 2 you'll wire `graph.stream(..., stream_mode="messages")` here.

> **Concept checkpoint (your dockerfile TODO becomes real):** Flask's dev server handles one request at a time; a long streaming response blocks everyone else. This is the moment your "use a production server" TODO stops being optional. Add `gunicorn` with the threaded worker class (`gunicorn -k gthread -w 2 --threads 8 -b 0.0.0.0:5000 main:app`) — or take the stretch goal: migrate Flask → **FastAPI**, which gives you async, automatic OpenAPI docs at `/docs`, and Pydantic request validation (answering your old question about "what is the industry standard to showcase the expected schema" — the answer is *Pydantic models + generated OpenAPI schema*, not comments).

### 3.2 Turn the dotnet server into a real gateway with YARP

Replace the hand-rolled `HttpClient` forwarding in `LlmController` with YARP configuration. In `appsettings.json`:

```json
{
  "ReverseProxy": {
    "Routes": {
      "openai-route": {
        "ClusterId": "langchain",
        "Match": { "Path": "/v1/{**catch-all}" }
      }
    },
    "Clusters": {
      "langchain": {
        "Destinations": {
          "primary": { "Address": "http://langchain_service:5000/" }
        }
      }
    }
  }
}
```

In `Program.cs`:

```csharp
builder.Services.AddReverseProxy()
    .LoadFromConfig(builder.Configuration.GetSection("ReverseProxy"));
// ...
app.UseTelemetryMiddleware();   // still runs on every proxied request
app.MapReverseProxy();
```

Now every OpenWebUI request flows: OpenWebUI → `dotnet_server:5000/v1/...` → telemetry middleware → YARP → Flask. Your middleware sees everything; YARP handles streaming pass-through correctly out of the box (it won't buffer the SSE stream). Keep your `LlmController` around only if you want a non-OpenAI custom API surface; otherwise delete the dead code — reviewers prefer a small clean repo over a museum of attempts (move experiments to `old_implementations/`, which you already do well).

### 3.3 Add OpenWebUI to docker-compose

```yaml
  openwebui:
    image: ghcr.io/open-webui/open-webui:main
    container_name: openwebui
    ports:
      - "3000:8080"
    environment:
      - OPENAI_API_BASE_URL=http://dotnet_server:8080/v1
      - OPENAI_API_KEY=dummy-key-not-checked
      - ENABLE_OLLAMA_API=false        # force it through YOUR stack, not directly to ollama
      - WEBUI_AUTH=false               # single-user local dev; document this choice
    volumes:
      - openwebui_data:/app/backend/data
    depends_on:
      - dotnet_server
```

(And add `openwebui_data:` under `volumes:`.) Note the address: inside the Docker network you target the *container* port `8080`, not the host-mapped `5000`. `ENABLE_OLLAMA_API=false` matters — OpenWebUI will happily bypass your entire system and talk to Ollama directly if you let it, and then none of your telemetry or RAG runs.

**Definition of Done:** open `http://localhost:3000`, pick `llm-monitor-agent`, send a message, watch tokens stream in, and see the request logged by your telemetry middleware in `docker logs dotnet_server`. Send a *second* message and confirm the full history arrives in `messages` (this becomes Phase 4's memory discussion).

**Interview relevance:** "Why did you put a gateway in front?" → cross-cutting concerns (telemetry, auth, rate limiting) belong at the edge, services stay focused; YARP is Microsoft's own reverse proxy, used inside Azure — a very good name to drop with a Microsoft interviewer.

---

<a name="phase-2"></a>
## 4. Phase 2 — LangGraph: The Real Orchestration Pipeline

**What problem is being solved?** Your current pipeline is a linear LCEL chain (`prompt | model | parser`) inside `test_langchain_chatnosecurity_worker`. Linear chains can't express: "if policy violated, stop", "loop calling tools until done", "checkpoint state so a conversation can resume". LangGraph models the pipeline as an explicit state machine, which is both more capable and — critically for you — more *observable and testable*, because each node is a pure-ish function you can unit test.

You already sketched this in `app/graph/` (marked "practice"). This phase makes it real. Your sketch has the right shape; what's missing is real node implementations, wiring to your factory/RAG, the checkpointer, and actually *calling* the graph from the API layer.

### 4.1 Define the state precisely

Your existing `ChatState` is close. Refine it:

```python
# app/graph/state.py
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class ChatState(TypedDict):
    # conversation (the checkpointer persists this; add_messages appends instead of overwrites)
    messages: Annotated[list, add_messages]
    # per-request inputs
    user_id: str
    desired_model: str
    # working data produced by nodes
    policy_verdict: str       # "conformance" | "violated"
    policy_reason: str
    retrieved_chunks: list    # list[Document]
    # output
    answer: str
```

**Why `Annotated[list, add_messages]` matters (a real gap to close):** by default, when a node returns `{"messages": [x]}`, LangGraph *replaces* the state key. The `add_messages` reducer changes the merge rule to *append + dedupe by message ID*. This is the mechanism that makes multi-turn memory work with checkpointing. Be ready to explain reducers — it's the LangGraph question interviewers ask.

### 4.2 Implement the nodes

Each node: read from state → do one thing → return *only the keys you changed* (you already wrote this principle in a comment in `nodes.py` — correct instinct).

```python
# app/graph/nodes.py
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from app.models.factory import ModelFactory
from app.rag.Ingestion import FindSemanticlyClosestElement
from app.prompts.MyPromptTemplates import GetPolicyViolationCheckerPrompt

def policy_check_node(state: ChatState) -> dict:
    user_msg = state["messages"][-1].content
    # RAG over the policy collection to ground the checker (fixes your
    # 'injectedCompanyPolicy is never injected' TODO)
    policy_chunks = FindSemanticlyClosestElement(user_msg, k=2)
    policy_text = "\n\n".join(d.page_content for d in policy_chunks)

    model = ModelFactory.get_chat_model(state["desired_model"])
    chain = GetPolicyViolationCheckerPrompt() | model
    raw = chain.invoke({"injectedCompanyPolicy": policy_text,
                        "user_message": user_msg}).content

    verdict, _, reason = raw.partition(":")
    return {"policy_verdict": verdict.strip().lower(),
            "policy_reason": reason.strip()}

def retrieve_node(state: ChatState) -> dict:
    user_msg = state["messages"][-1].content
    chunks = FindSemanticlyClosestElement(user_msg, k=4)
    return {"retrieved_chunks": chunks}

def blocked_node(state: ChatState) -> dict:
    msg = f"I can't help with that. Policy check result: {state['policy_reason']}"
    return {"answer": msg, "messages": [AIMessage(content=msg)]}
```

Two important upgrades over your current prompts, both fixing real bugs:

1. **Structured output for the policy checker.** Your `MyPromptTemplates.py` TODO already realized free-text `"violated: reason"` is fragile. The professional fix is `model.with_structured_output`:

```python
from pydantic import BaseModel, Field

class PolicyVerdict(BaseModel):
    verdict: str = Field(description="either 'violated' or 'conformance'")
    reason: str
    immediate_action_required: bool = Field(
        description="true only for imminent physical danger")

checker = model.with_structured_output(PolicyVerdict)
result = checker.invoke(prompt_value)   # -> PolicyVerdict object, no string parsing
```

(With Ollama this uses JSON-schema-constrained decoding under the hood. Small local models sometimes fail schema compliance — catch the exception and fail *closed*, i.e., treat parse failure as `violated`. Fail-closed vs fail-open on a safety check: excellent interview material.)

2. **Fix the RAG prompt message ordering.** `GetHappyEncouragingAssistentRagPrompt` puts a `system` message *after* the user message. Models treat late system messages inconsistently; the convention is: one system message up front containing instructions + context, then the conversation:

```python
ChatPromptTemplate.from_messages([
    ("system", "You are a cheerful, encouraging assistant.\n"
               "Use this context if relevant:\n{context}"),
    ("placeholder", "{messages}"),   # the whole running conversation goes here
])
```

The `("placeholder", "{messages}")` slot is how a prompt template accepts LangGraph's message list — this replaces your single `{user_message}` variable and is what makes multi-turn context actually reach the model.

### 4.3 Build and compile the graph

```python
# app/graph/build_graph.py
from langgraph.graph import StateGraph, START, END
from app.graph.state import ChatState
from app.graph.nodes import policy_check_node, retrieve_node, blocked_node, agent_node
from langgraph.prebuilt import ToolNode, tools_condition
from app.tools.registry import ALL_TOOLS   # Phase 3

def build_graph(checkpointer=None):
    g = StateGraph(ChatState)
    g.add_node("policy_check", policy_check_node)
    g.add_node("blocked", blocked_node)
    g.add_node("retrieve", retrieve_node)
    g.add_node("agent", agent_node)
    g.add_node("tools", ToolNode(ALL_TOOLS))

    g.add_edge(START, "policy_check")
    g.add_conditional_edges(
        "policy_check",
        lambda s: "blocked" if s["policy_verdict"] == "violated" else "ok",
        {"blocked": "blocked", "ok": "retrieve"},
    )
    g.add_edge("blocked", END)
    g.add_edge("retrieve", "agent")
    # agent either calls tools (loop back) or finishes
    g.add_conditional_edges("agent", tools_condition,
                            {"tools": "tools", END: END})
    g.add_edge("tools", "agent")
    return g.compile(checkpointer=checkpointer)
```

```
        START ──► policy_check ──violated──► blocked ──► END
                       │ok
                       ▼
                   retrieve ──► agent ◄──────┐
                                  │          │
                            tool calls?   tools
                                  │yes ──────┘
                                  │no
                                  ▼
                                 END
```

Compile the graph **once at startup** (not per request — it's expensive and stateless between requests when using a checkpointer) and store it on the Flask app.

### 4.4 Call it from the OpenAI facade

```python
# inside /v1/chat/completions handler
config = {"configurable": {"thread_id": thread_id}}   # Phase 4 explains thread_id
result = GRAPH.invoke(
    {"messages": [HumanMessage(content=user_message)],
     "user_id": user_id, "desired_model": model_name},
    config=config,
)
answer = result["messages"][-1].content
```

And for streaming, `GRAPH.stream(..., stream_mode="messages")` yields `(message_chunk, metadata)` tuples — filter for chunks from the `agent` node and yield `chunk.content` into your SSE generator.

**Definition of Done:** a policy-violating message gets blocked with a reason; a normal message flows retrieve → agent → answer; `graph.get_graph().draw_ascii()` printed at startup matches the diagram above; each node has at least one unit test (mock mode makes the policy/agent nodes deterministic).

**Interview relevance:** be ready to whiteboard this exact graph and explain: why conditional edges instead of if-statements inside one function (each node independently observable/retryable/testable; state transitions are explicit and checkpointable).

---

<a name="phase-3"></a>
## 5. Phase 3 — Tool Use

**What problem is being solved?** Your `TestToolUseSystem` attempt in `old_implementations/lang_practice.py` tried to hand-roll tool calling with string parsing (`while res[0] != '{'`). You correctly sensed this was wrong. The real mechanism: modern chat models emit **structured tool-call messages** (a JSON block in a dedicated field, not in the text), and the framework routes them. You never parse strings.

### 5.1 Define tools with the `@tool` decorator

```python
# app/tools/registry.py
from langchain_core.tools import tool
import datetime

@tool
def get_current_time() -> str:
    """Returns the current UTC time. Use when the user asks about the current time or date."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

@tool
def search_company_policies(query: str) -> str:
    """Searches internal company policy documents. Use for any question about
    what employees are or are not allowed to do."""
    from app.rag.Ingestion import FindSemanticlyClosestElement
    docs = FindSemanticlyClosestElement(query, k=3)
    return "\n\n".join(d.page_content for d in docs) or "No relevant policy found."

ALL_TOOLS = [get_current_time, search_company_policies]
```

**The docstring is not a comment — it is the API.** It gets serialized into a JSON schema and sent to the model on every request; the model chooses tools by reading these descriptions. Bad docstring = model never calls the tool. This answers your old question "how do I map a string name to a function" — you don't; the framework builds a name→function registry from the decorated objects, and `ToolNode` does the dispatch.

Note `search_company_policies` wraps your RAG as a tool. This gives you two RAG patterns in one project — **pipeline RAG** (Phase 2's `retrieve` node: always runs) and **agentic RAG** (model decides when to search). Interviewers love a compare/contrast: pipeline RAG is predictable and cheap (one retrieval, always), agentic RAG handles "no retrieval needed" and multi-query cases but adds latency and nondeterminism.

### 5.2 Bind tools in the agent node

```python
def agent_node(state: ChatState) -> dict:
    model = ModelFactory.get_chat_model(state["desired_model"])
    model_with_tools = model.bind_tools(ALL_TOOLS)

    context = "\n\n".join(d.page_content for d in state["retrieved_chunks"])
    prompt = GetAssistantPrompt()  # the fixed prompt from Phase 2
    response = model_with_tools.invoke(
        prompt.invoke({"context": context, "messages": state["messages"]})
    )
    return {"messages": [response]}   # may contain .tool_calls
```

The loop you tried to hand-write is now emergent from the graph: if `response.tool_calls` is non-empty, `tools_condition` routes to `ToolNode`, which executes each call and appends `ToolMessage` results to `messages`, then the edge loops back to `agent`, which sees the results and either calls more tools or answers. Add a recursion limit (`config={"recursion_limit": 10}`) so a confused small model can't loop forever — the graph-native version of your old `max_itters`.

**Reality check for your model choice:** `qwen2.5:1.5b` is small; its tool-calling is unreliable. For tool-use demos, use `qwen2.5:7b` or `llama3.1:8b` (both solid at tool calls in Ollama). Document this in the README — "model capability tiers" is a real production concern (and a good reason your `/v1/models` list can advertise an `-agent` and a `-fast` pipeline).

**Definition of Done:** asking "what time is it right now?" produces an answer containing the actual time, and your Langfuse trace (Phase 5) shows: agent → tool_call(get_current_time) → tool result → agent → final answer. A question needing no tools produces zero tool calls.

---

<a name="phase-4"></a>
## 6. Phase 4 — Memory

**What problem is being solved?** Your huge commented-out block in `OrchestrationLogic.py` wrestles with exactly this: "I need to grab the entire history object... store it back into whatever database." Good news: you already installed the answer. LangGraph **checkpointers** persist the graph state (including `messages`) keyed by `thread_id` — and there is a first-class Postgres implementation, so your existing pgvector container does double duty.

Two kinds of memory, and you should implement both because the distinction itself is interview gold:

| | Short-term (thread) memory | Long-term (semantic) memory |
|---|---|---|
| What | The message history of *this* conversation | Facts about the user across *all* conversations |
| Mechanism | `PostgresSaver` checkpointer + `thread_id` | pgvector collection, written/read explicitly |
| Analogy | The case worker's notes for the open case | The filing cabinet's folder on this client |

### 6.1 Short-term memory with PostgresSaver

Install `langgraph-checkpoint-postgres` (add to requirements). At startup:

```python
# main.py
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool

pool = ConnectionPool(Config.PG_CONN_PSYCOPG)  # plain psycopg URL, no '+psycopg'
checkpointer = PostgresSaver(pool)
checkpointer.setup()          # creates checkpoint tables (run once, idempotent)
GRAPH = build_graph(checkpointer=checkpointer)
```

Careful with the connection string: `PostgresSaver` wants a plain `postgresql://...` URL (it's raw psycopg), while the LangChain `PGVector` string uses the SQLAlchemy-style `postgresql+psycopg://...`. Put both in your `Config` with distinct names — this *will* bite you otherwise.

Every invoke with the same `thread_id` now resumes the same conversation — the checkpointer loads state, `add_messages` appends the new turn, and the whole thing persists across container restarts. Prove it with a demo: tell it your name, `docker compose restart langchain_service`, ask "what's my name?" — it remembers. **That's your portfolio demo GIF right there.**

**Where does `thread_id` come from?** OpenWebUI sends `messages` (full history) but you want *your* server to be the source of truth. Practical approach: derive a stable id from the OpenWebUI conversation — OpenWebUI sends a `chat_id` in its request metadata when configured, or simplest robust fallback: hash the first user message + user id. Document whichever you choose; also note the subtlety that since OpenWebUI *already resends full history*, you must pass only the **last** message into the graph (the checkpointer supplies the rest) or you'll get duplicated context. This subtlety — "who owns conversation state, client or server?" — is a genuinely good design discussion for your README.

### 6.2 Long-term memory

Add a second pgvector collection `user_memories`. After each completed conversation turn, run a small extraction step (can be async/background):

```python
MEMORY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "Extract at most one durable fact about the user from this exchange "
               "(preferences, role, recurring needs). Reply NONE if there is none."),
    ("placeholder", "{messages}"),
])
# if fact != "NONE": memory_store.add_documents([Document(fact, metadata={"user_id": ...})],
#                                               ids=[hash(user_id + fact)])
```

And in `retrieve_node`, additionally search `user_memories` filtered by `user_id` and prepend hits to the context. Now the system remembers "Timothy prefers C# examples" *across* conversations. (Same idempotent-ids trick as Phase 0.)

**Definition of Done:** the restart demo works; two different `thread_id`s don't leak into each other; a fact stated in conversation A influences an answer in conversation B (long-term); checkpoint tables visible in psql.

---

<a name="phase-5"></a>
## 7. Phase 5 — Local Observability

**What problem is being solved?** "It works on my machine" is not an engineering claim. You need to *see* every request: the route it took through the graph, every prompt and completion, token counts, latencies. All local (your requirement). Recommended two-layer design — this mirrors how real AI platform teams split it:

| Layer | Tool | What it captures | Why |
|---|---|---|---|
| LLM-level tracing | **Langfuse** (self-hosted) | Full prompt/completion per LLM call, graph spans, token usage, per-trace user/session, eval scores | Purpose-built LLM observability; also stores your eval results (Phase 6) |
| System-level metrics | **OpenTelemetry → Prometheus + Grafana** | Request rate, latency histograms, error rates for dotnet + Flask; dashboards | The industry-standard backbone; .NET's OTel story is first-class (Microsoft relevance) |

If you want to cut scope, do Langfuse first — it gives the most AI-specific value per hour of work. But the OTel layer is what makes a Microsoft interviewer nod, and the **trace-correlation across a polyglot system** (C# → Python in one trace) is the impressive part.

### 7.1 Langfuse, self-hosted

Add to docker-compose (Langfuse needs its own postgres — do *not* share the pgvector instance; separate concerns, separate blast radius):

```yaml
  langfuse-db:
    image: postgres:16
    container_name: langfuse_db
    environment:
      - POSTGRES_USER=langfuse
      - POSTGRES_PASSWORD=langfuse
      - POSTGRES_DB=langfuse
    volumes:
      - langfuse_pgdata:/var/lib/postgresql/data

  langfuse:
    image: langfuse/langfuse:2        # v2: single container; v3 adds clickhouse/redis/minio — overkill here
    container_name: langfuse
    depends_on: [langfuse-db]
    ports:
      - "3001:3000"
    environment:
      - DATABASE_URL=postgresql://langfuse:langfuse@langfuse-db:5432/langfuse
      - NEXTAUTH_URL=http://localhost:3001
      - NEXTAUTH_SECRET=devsecret-change-me
      - SALT=devsalt-change-me
```

(Check the current Langfuse self-hosting docs when you implement — required env vars change between versions.) Create a project in the UI at `localhost:3001`, get the public/secret key pair, add them to the langchain_service environment.

Instrument with the callback handler — one object, passed through the graph config, traces *everything* including nested LLM calls inside nodes:

```python
from langfuse.callback import CallbackHandler

langfuse_handler = CallbackHandler()   # reads LANGFUSE_* env vars

result = GRAPH.invoke(inputs, config={
    "configurable": {"thread_id": thread_id},
    "callbacks": [langfuse_handler],
    "metadata": {"langfuse_user_id": user_id,
                 "langfuse_session_id": thread_id},
})
```

Now open Langfuse after a few chats: you'll see each request as a trace with a span tree — `policy_check` (with its LLM call and the exact policy prompt), `retrieve`, `agent`, tool calls, latencies and token counts per span. **This is also your primary RAG debugging tool from now on** — you can literally read what chunks were retrieved and what prompt the model actually saw.

### 7.2 Metrics: OpenTelemetry → Prometheus → Grafana

On the .NET side (this is where your empty `TelemetryMiddleware` gets a real job):

```csharp
// Program.cs
builder.Services.AddOpenTelemetry()
    .ConfigureResource(r => r.AddService("dotnet-gateway"))
    .WithTracing(t => t.AddAspNetCoreInstrumentation()
                       .AddHttpClientInstrumentation()
                       .AddOtlpExporter(o => o.Endpoint = new Uri("http://otel-collector:4317")))
    .WithMetrics(m => m.AddAspNetCoreInstrumentation()
                       .AddPrometheusExporter());
// ...
app.MapPrometheusScrapingEndpoint();   // exposes /metrics
```

Packages: `OpenTelemetry.Extensions.Hosting`, `OpenTelemetry.Instrumentation.AspNetCore`, `OpenTelemetry.Instrumentation.Http`, `OpenTelemetry.Exporter.Prometheus.AspNetCore`, `OpenTelemetry.Exporter.OpenTelemetryProtocol`.

Your custom middleware then adds the AI-specific dimension OTel doesn't know about:

```csharp
public async Task InvokeAsync(HttpContext context)
{
    var sw = System.Diagnostics.Stopwatch.StartNew();
    await _next(context);
    sw.Stop();
    _logger.LogInformation(
        "route={Route} status={Status} duration_ms={Ms} trace_id={TraceId}",
        context.Request.Path, context.Response.StatusCode,
        sw.ElapsedMilliseconds, System.Diagnostics.Activity.Current?.TraceId);
}
```

On the Flask side: `opentelemetry-instrumentation-flask` + `opentelemetry-instrumentation-requests` auto-instrument, and — the key trick — ASP.NET Core and YARP propagate the W3C `traceparent` header automatically, and Flask's OTel instrumentation reads it. Result: **one distributed trace spanning C# and Python**. Add Prometheus + Grafana + (optionally) an otel-collector to compose, and build one Grafana dashboard: request rate, p50/p95/p99 latency, error rate, and (exported as custom metrics from Flask) tokens/request and time-to-first-token.

**Definition of Done:** one chat message produces (a) a Langfuse trace with the full span tree and token counts, and (b) a Grafana-visible latency data point whose trace ID matches across the dotnet and Flask logs.

**Interview relevance:** know the three pillars (traces / metrics / logs), what `traceparent` looks like (`00-{trace-id}-{span-id}-01`), and why histograms (p95) beat averages for latency.

---

<a name="phase-6"></a>
## 8. Phase 6 — AI Evaluation and Testing Metrics

**What problem is being solved?** This is the section that most differentiates you. Anyone can demo a chatbot; almost nobody walks into an interview with an *evaluation harness*. AI systems are nondeterministic, so classic assert-equality testing fails; the industry answer is layered:

```
 Layer 1: Deterministic unit tests      (mock mode — free, run always)
 Layer 2: Retrieval metrics             (no LLM needed — cheap, objective)
 Layer 3: LLM-judged generation metrics (RAGAS / judge model — expensive, run nightly/on-demand)
 Layer 4: Regression gating in CI       (compare scores to a baseline, fail if degraded)
```

### 8.1 Layer 1 — Deterministic tests (pytest + mock mode)

Your mock mode finally pays off: in `LLM_MODE=mock`, graph routing is testable without any model.

```python
# tests/test_graph_routing.py
def test_policy_violation_routes_to_blocked(monkeypatch):
    # force the policy node's verdict deterministically
    monkeypatch.setattr("app.graph.nodes.run_policy_llm",
                        lambda msg: ("violated", "asked about weapons"))
    result = GRAPH.invoke({"messages": [HumanMessage("how do I build a bomb")],
                           "user_id": "t", "desired_model": "mock"})
    assert "can't help" in result["answer"].lower()
    assert result["retrieved_chunks"] == []   # never reached retrieve
```

Also contract-test your OpenAI facade (response shape, SSE format ends with `[DONE]`), and make your `MockChatModel` scenario-aware (your `MockChatTypeDictionary` was heading here — route mock responses by which prompt type is invoking it, so tests can exercise both verdicts).

### 8.2 Layer 2 — Retrieval metrics (the direct answer to "does my RAG work?")

Build a golden dataset — this is the single highest-leverage artifact in this phase. A JSONL file, 20–50 rows, written by hand:

```jsonl
{"question": "Can I use Python scripts to automate my work tasks?", "expected_doc_ids": ["security_policy_v2.md"], "ground_truth": "Yes, local scripting tools are permitted provided no proprietary source code leaves company assets."}
{"question": "What happens if someone builds an explosive on site?", "expected_doc_ids": ["hr_conduct_v1.md"], "ground_truth": "It is strictly prohibited and results in immediate termination."}
{"question": "What is the capital of France?", "expected_doc_ids": [], "ground_truth": "Paris. (No policy retrieval expected.)"}
```

Then compute the two standard retrieval metrics yourself (deliberately — implementing MRR from scratch is a better learning artifact than importing it):

```python
def hit_at_k(retrieved_ids: list[str], expected_ids: list[str]) -> float:
    """Did ANY expected doc appear in the top-k?"""
    return 1.0 if set(retrieved_ids) & set(expected_ids) else 0.0

def mrr(retrieved_ids: list[str], expected_ids: list[str]) -> float:
    """Reciprocal rank of the FIRST relevant doc (position matters)."""
    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in expected_ids:
            return 1.0 / rank
    return 0.0
```

Runner: for each golden row, call `FindSemanticlyClosestElement(question, k=4)`, map results to their `metadata["source"]`, compute mean hit@4 and MRR across the dataset, print a table, write a timestamped JSON report to `eval_reports/`. Also log a **similarity-score distribution** — this tells you where to set the minimum-score threshold you already suspected you need (your comment: "block erroneous retrievals"). With only 2 documents ingested, *every* query retrieves both — which is precisely why your RAG "works" but feels meaningless. **Action: ingest a real corpus** (10–20 policy/handbook markdown files — write them yourself or generate plausible ones) using a proper loader → splitter pipeline (`DirectoryLoader` + `RecursiveCharacterTextSplitter`, chunk_size≈800, overlap≈100), which also finally implements your "Loader -> chunker" TODO.

### 8.3 Layer 3 — Generation metrics with RAGAS + LLM-as-judge

RAGAS gives you the four canonical RAG metrics; know them cold:

| Metric | Question it answers | Catches |
|---|---|---|
| Faithfulness | Is the answer supported by the retrieved context? | Hallucination |
| Answer relevancy | Does the answer address the question? | Evasive/rambling answers |
| Context precision | Are the retrieved chunks actually relevant? | Noisy retrieval |
| Context recall | Did retrieval find everything the ground truth needs? | Missing retrieval |

RAGAS needs a judge LLM and embeddings — point both at local Ollama (fully local, per your requirement). Use your strongest local model as judge (judge should be ≥ the system under test):

```python
from ragas import evaluate, EvaluationDataset
from ragas.metrics import Faithfulness, AnswerRelevancy, LLMContextPrecisionWithReference, LLMContextRecall
from langchain_ollama import ChatOllama, OllamaEmbeddings

judge = ChatOllama(model="qwen2.5:7b", base_url=..., temperature=0)
emb = OllamaEmbeddings(model="nomic-embed-text", base_url=...)

# rows: {"user_input", "response", "retrieved_contexts", "reference"}
results = evaluate(dataset, metrics=[Faithfulness(), AnswerRelevancy(),
                                     LLMContextPrecisionWithReference(), LLMContextRecall()],
                   llm=judge, embeddings=emb)
```

(API details drift between RAGAS versions — read the current docs when implementing.) Complement with one **custom judge** you write yourself using `GetLlmJudgePrompt` (finally implementing it) + `with_structured_output` returning `{score: 1-5, reasoning: str}` against a rubric like "tone: is the answer encouraging and friendly?". Owning one bespoke judge shows you understand the mechanism, not just the library. Log all scores to Langfuse via its scores API so eval history lives next to the traces.

### 8.4 Layer 4 — Regression gating

`eval_reports/baseline.json` holds your accepted scores. The eval runner exits nonzero if any metric drops more than a tolerance (e.g., MRR −0.05) below baseline. Wire into CI (Phase 7): Layers 1–2 on every push (fast, no LLM); Layer 3 manually/nightly since it needs Ollama. When you intentionally improve the system, re-baseline in the same commit — score deltas become part of code review. **This workflow — eval-gated changes to AI systems — is exactly what AI engineering teams do all day**, and having it in a portfolio project is rare.

**Definition of Done:** golden dataset ≥20 rows; one command (`make eval`) prints hit@k, MRR, and RAGAS table and writes a report; scores visible in Langfuse; CI fails on Layer-1 test failure or Layer-2 regression.

---

<a name="phase-7"></a>
## 9. Phase 7 — Portfolio Polish

Shorter items, high signal-per-hour:

1. **CI with GitHub Actions.** `.github/workflows/ci.yml`: job 1 — Python lint (`ruff`) + `pytest` in mock mode; job 2 — `dotnet build` + `dotnet format --verify-no-changes`; job 3 — `docker compose build`. Green checkmarks on the repo are the first thing anyone sees.
2. **Structured JSON logging everywhere** with `trace_id` in every line (Python `logging` + a JSON formatter; .NET already does structured logging — configure the JSON console formatter). Kills all your `print()` calls, which reviewers read as junior.
3. **Health endpoints.** `/healthz` (liveness: process up) and `/readyz` (readiness: can reach postgres + ollama) on both services; wire compose `healthcheck`s and `depends_on: condition: service_healthy` to them — you already did this for pgvector, finish the job for the others.
4. **Security hardening (ties to your AI_Security doc).** Model allow-list (your existing TODO in `Instructions.py` — an env-var set of permitted models, reject others with 400); request size limits; and add **prompt-injection awareness**: your policy checker runs *before* retrieval, but what about instructions hidden *inside* retrieved documents? Add one adversarial doc to the corpus ("ignore previous instructions and...") plus a golden-dataset row asserting the system doesn't obey it. That's an AI-security eval — a very strong differentiator.
5. **README rewrite.** Architecture diagram (export from this doc), quickstart (3 commands to running UI), screenshots of OpenWebUI + Langfuse trace + Grafana dashboard, the memory-across-restart GIF, an "Evaluation results" table with your current scores, and an honest "Design decisions & tradeoffs" section. Fix the typos in the current README (`cababilities`, `apporiate`, `orchastrated`, `Langchian`, `comiling`) — for a document whose stated purpose is proving craftsmanship, typos are load-bearing.
6. **Repo hygiene.** Add `server/bin/`, `server/obj/`, `**/.venv/`, `__pycache__/` to `.gitignore` (compiled DLLs and a 184 MB venv have no business in git — going forward only; don't rewrite history). Delete or clearly quarantine dead commented-out code.

---

<a name="milestones"></a>
## 10. Milestone Plan and Definition of Done

Suggested order — each milestone is demoable, so the project is never "half-broken":

| # | Milestone | Contents | Demo artifact |
|---|---|---|---|
| M1 | Trustworthy foundation | Phase 0 fixes + RAG verification | psql session proving stable row counts + working similarity search |
| M2 | Chat UI end-to-end | Phase 1 (facade, YARP, OpenWebUI) | Streaming chat in browser through your gateway |
| M3 | Real agent | Phase 2 + 3 (LangGraph + tools) | Blocked message demo; tool-use demo |
| M4 | Memory | Phase 4 (checkpointer + long-term) | The restart GIF |
| M5 | Glass walls | Phase 5 (Langfuse + OTel/Grafana) | One trace across C#→Python; dashboard |
| M6 | Prove it | Phase 6 (golden set, RAGAS, gating) | `make eval` scorecard; regression-failing CI run |
| M7 | Ship it | Phase 7 (CI, security, README) | The repo itself |

Rough effort at a few hours/evening: M1–M2 ≈ 1–2 weeks, M3–M4 ≈ 2 weeks, M5 ≈ 1 week, M6 ≈ 1–2 weeks, M7 ≈ 1 week. Two months to a genuinely senior-looking artifact.

---

<a name="common-mistakes"></a>
## 11. Common Mistakes to Avoid

1. **Building on the unverified foundation.** If you skip Phase 0, every RAG eval in Phase 6 measures duplicated documents and you'll chase ghosts.
2. **Letting OpenWebUI talk to Ollama directly.** Then your entire backend is decorative. `ENABLE_OLLAMA_API=false` and verify traffic in the gateway logs.
3. **Passing full client history into a checkpointed graph.** Double context, growing prompts, weird answers. One owner of history: the checkpointer.
4. **Testing generation before retrieval.** If retrieval is bad, generation metrics are noise. Layers 2 before 3, always.
5. **Trusting a 1.5B model with tool calling or judging.** Match model size to job; document the tiers.
6. **Sharing one postgres for app data and observability data.** Separate failure domains — your monitoring must survive your app's database dying (and vice versa).
7. **Perfect being the enemy of demoable.** Every milestone above ends in a demo. If a phase stalls, cut scope inside the phase, not the demo.

---

## What I'd add that you didn't ask for (summary)

Already woven in above, but explicitly: the **OpenAI-compatible facade** (industry-standard interface, makes OpenWebUI trivial), **YARP as a real gateway** (justifies the .NET tier, Microsoft-relevant), **structured output for the policy checker** (kills string parsing), **golden dataset + regression gating** (the rarest, most impressive piece), **prompt-injection eval row** (bridges to your AI_Security track), and **FastAPI migration as a stretch goal** (async + Pydantic + OpenAPI docs). If you only have energy for one "extra," make it the golden dataset — everything else in Phase 6 hangs off it, and it's the artifact interviewers ask to see.
