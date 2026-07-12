10 July, 2026

## Stage 1 (Design Documentation)

1. Context:

**Current State**:

This is the first collaborative AI feature implementation. Previously everything had been done 100% by hand. I wrote all the code, and completely developed this project myself. But now we are changing the implemention strategy which we will be using to develop this project. Now we will be taking on a collaborative development with AI as outlined in the CLAUDE.md file for AI_Implementation_Plans. 

This project currently has many different docker components. All of them are started up within the docker compose file. A build script is able to perform the docker compose calls to build and inject environment variables into the system. The two main dynamic environment variables are 'live' and 'mock'. 'live' is for when we want to start our system up with the real LLM and Ollama service. 'mock' is when we want to start up our project, but don't want to have the heavy system of Ollama and interacting with those LLMs.

The system currently operates as follows. The langchain_service gets an HTTP request from outside the docker network. It will recieve a POST request and that POST request will have the user's message. This user's message is then sent to our internal langchain_logic. The internal logic will process the users message by getting a standardized prompt, getting a standardized model, and invoking the chain with the user's message. I then tried to implement a RAG that would allow for functionality of comparing the user's message to documents in the vector database to give extra context.

I then attempted to get langgraph operating (but this is very much not working right now).

**Current Problems**:

- The system was under active development. It was working in parts, but every day there were many new changes, logic taken out, endpoints removed, classes modified, etc. So the current state of the system is very much unstable.

- I don't think that my RAG system actually works.

- I am unsure of the architecture which this project is using. I attempted to use my best judgement to create a scalable, distributed, asyncronous system; but I am lacking in experience in this realm, so I don't know if I did it in a good way or not.

- There is no standard interface and agreements between the different docker services for how these HTTP requests will be sent.

- The system is not connected correctly. The langchain_service should not be recieving any communications from outside the docker network. (I want to have API endpoint enabled in my langchain_service which are able to be reached by outside for testing reasons, but in the actual system all requests should be going through my YARP dotnet server.)

**Direction For This Implementation**

- Refactor code within each of the docker services to be professional, scalable, and clean.
- Ensure RAG actually saves documents corrently into our vector database
- Ensure RAG successfully retrieves those documents based on user message
- Create a standardized interface and contract between all of the services in the project.
- Have multiple API endpoints inside the langchain_service such that a user can send messages to be processed in the following ways in both base langchain (no langgraph) and in langgraph (but remember that we want scalablility so the implementation you use to implement these two endpoints with langgraph should allow for easy growth of new features within the langgraph system):

A simple POST request that gets sent to the llm with that message and given response.

A POST request that has extra context injected into it from the RAG.

So in total, there will be 4 working valid (testing) API endpoints which I can hit from outside docker network, and 4 other (real) API endpoints that I can hit by routing through my dotnet YARP sever.

- Ensure Openwebui is working and compatable with our system and can call as required.

2. Interfaces & contracts

I don't know

3. Acceptance criteria

(1) `./build.sh --mode mock` responds with all containers healthy, all 4 test endpoints return 200 with valid contract JSON; 
(2) same via dotnet gateway routes; 
(3) live mode: RAG endpoint response demonstrably uses ingested document content; 
(4) re-running ingestion twice yields no duplicate rows in pgvector; 
(5) OpenWebUI chat round-trips through the real pipeline (no hardcoded stub); 
(6) pytest suite covering contract shapes passes in CI.

4. Non-goals

- We do not need to attempt to implement features and functionality which does not currently exist in the project. For example, tool usage.
- Don't need to implement policy checking and blocking


## Stage 2 (Discussion)

---

### [AI — 2026_07_10_19_50] Opening entry: current-state findings and discussion questions

Timothy, I investigated the full codebase before writing this. First, concrete facts about the current state so our discussion is grounded in reality rather than memory. Then, the decisions I need from you.

#### A. Verified breakages (why the service is unstable)

These are not opinions — the refactor of prompts into `PromptFactory` left the rest of the codebase pointing at symbols that no longer exist:

1. **`app/models/factory.py` cannot import.** Line: `from app.prompts.MyPromptTemplates import MockChatTypeDictionary, number_of_chat_types`. Neither name exists anymore (the mock data moved to `mock_prompts.py` as `MOCK_RESPONSES` etc.). Since everything imports the factory, the entire service fails at startup. This is the root "nothing works" bug.
2. **`OrchestrationLogic.py` calls `GetHappyEncouragingAssistentRagPrompt()`** — replaced by `PromptFactory.get_assistant_prompt()`. NameError at request time.
3. **`graph/nodes.py` imports `GetPolicyViolationCheckerPrompt`** — same problem. Also, it's used as `GetPolicyViolationCheckerPrompt | model` without being called (it was a function; now it needs to be `PromptFactory.get_policy_checker_prompt() | model`).
4. **`graph/build_graph.py`**: `from langgraph.prebuilt import ToolNode, tool_condition` — the real name is `tools_condition`. Also `build_graph()` is incomplete (adds 2 nodes, no edges, no compile, returns `None`); only `build_graph_old()` is complete.
5. **Prompt variable mismatch**: `get_assistant_prompt()` requires `{context}`, but the non-RAG worker invokes with only `{"user_message": ...}` → KeyError. Also the template has `("placeholder", "{message}")` but nothing ever passes `message`.
6. **`/v1/chat/completions` is a hardcoded stub** — OpenWebUI "works" only in the sense that it receives a fake canned string. It never touches the orchestration layer.
7. **Dotnet `LlmController`**: reads `OLLAMA_BASE_URL` (never set for `dotnet_server` in compose → null), posts to `/api/chat` (doesn't exist on Flask), media type is `"/application/json"` (invalid — leading slash), and returns the raw `HttpResponseMessage` object serialized instead of reading the body. Four independent bugs; this path has never worked end-to-end.
8. **There is no YARP.** The plan says "my YARP dotnet server," but `Program.cs` is a plain controller app — no YARP package, no reverse-proxy config. This matters for question 1 below.
9. **`RunIdempotentRagIngestion` is not idempotent.** `add_documents` with no IDs inserts duplicates on every startup. Your pgvector collection is accumulating copies of the same two documents. Fix: deterministic IDs (e.g., hash of content) so re-ingestion upserts.
10. Minor but worth fixing while we're in there: `ChatState.disired_model` typo (it's load-bearing — nodes read `state["disired_model"]`), `main.py` runs ingestion *after* creating the app with `debug=True` (the Flask reloader imports the module twice → double ingestion), and Flask's dev server isn't a production server (gunicorn is the standard fix).

#### B. My read on the architecture (answering your "is my architecture good?" worry)

The overall shape is sound and industry-standard: gateway → orchestration service → model runtime + vector DB, with mock/live profiles. That's genuinely the right decomposition. Your instability isn't an architecture problem — it's the absence of two things professionals lean on: **contracts** (so a rename in one file can't silently break five others) and **tests/CI that run the service** (so breakage is caught at commit time, not demo time). This implementation should prioritize those two, because they're what makes the refactor *stay* fixed.

#### C. Decisions I need from you before Stage 3

**Q1 — What is the dotnet server, really?** Two different products:
   - (a) **True YARP reverse proxy**: transparent forwarding, routes defined in `appsettings.json`, no DTOs, no controller for the chat path. Telemetry middleware still works. Less code, matches "API gateway" on a resume.
   - (b) **Controller-based orchestrator** (what exists now): receives, validates, transforms, forwards via HttpClient. More code, more control, but it duplicates the contract and is where 4 of your bugs live.
   - My recommendation: (a) for the chat routes, keeping a controller only where the gateway adds real logic later (auth, policy). But it's your call and it changes the plan significantly.

**Q2 — The contract.** I propose one canonical JSON shape at every HTTP boundary, snake_case on the wire (configure `System.Text.Json` naming policy in C# rather than renaming C# properties — this answers the comment-question in your controller about naming conventions across languages). Request: `{user_id, user_message, requested_model}`. Response: `{status, response, metadata{...}}`. Documented in one markdown file that both services link to. Agree, or do you want to design it together in more detail first?

**Q3 — Endpoint layout.** Plan says 4 test endpoints. I propose: `/test/chat/basic`, `/test/chat/rag`, `/test/graph/basic`, `/test/graph/rag`, plus the real `/v1/chat/completions` for OpenWebUI. For scalable dispatch, your own commented-out idea in `FlaskServer.py` (dict of model-id → orchestration function) is the right pattern — OpenWebUI's model picker then selects the pipeline. Confirm?

**Q4 — Mock mode and RAG.** Currently mock mode makes `FindSemanticlyClosestElement` return `[]`, so the RAG path is untestable without Ollama. Do you want a mock embedding model (deterministic fake vectors) so the *full* RAG path — pgvector included — runs in mock mode? I'd argue yes: it makes the RAG contract testable in CI. Cost: a bit more mock code.

**Q5 — LangGraph scope.** For "scalable growth," I'd structure the graph as: entry → (rag?) → agent → respond, with the policy-check node deferred (your non-goals exclude policy blocking). The graph and plain-chain paths would share the same `ModelFactory`/`PromptFactory`/retriever components. The checkpointer stays out of scope for this cleanup. Agree?

**Q6 — Acceptance criteria** (you left this open; here's a strawman): (1) `./build.sh --mode mock` → all containers healthy, all 4 test endpoints return 200 with valid contract JSON; (2) same via dotnet gateway routes; (3) live mode: RAG endpoint response demonstrably uses ingested document content; (4) re-running ingestion twice yields no duplicate rows in pgvector; (5) OpenWebUI chat round-trips through the real pipeline (no hardcoded stub); (6) pytest suite covering contract shapes passes in CI.

Answer inline or in chat and I'll fold your decisions into the next entry.

---

Yes, I read over your assessment and it sounds correct. 

**Q1** I wanted to put YARP into this project to be able to signal to Microsoft that I would be a good canditate and have experience working with their systems. I was thinking that YARP could be a rate limiter, authentication, etc. I don't know if this is the right way to think about it, but this was my logic.

**Q2** I like your idea.

**q3** Sounds good, but does this assume that all of those will be going to the langchain_service? Will we have 4 (or I guess 5) more that correspond to going to the dotnet server to be routed though the authentication and telemetry gathering in the future?

**q4** Yes, I definately want to be able to have a fully mock path, as you described and suggested.

**q5** How will we handle the situations in the future where we have multiple users attempting to connect to the same pipeline? Or we need to upgrade a pipeline to add a new feature? Or if I want to add something like photo parsing? Is your idea scalable in these dimensions?

**q6** I like it and have updated my acceptance criteria section.

---

### [AI — 2026_07_10_23_13] Reply: YARP confirmed, endpoint topology, pipeline scalability

**Q1 (YARP) — your logic is exactly right.** YARP is Microsoft's own reverse-proxy library, built as ASP.NET Core middleware, which means the gateway becomes: `request → telemetry middleware → (future: auth middleware) → (future: rate-limiter middleware) → YARP forwarder → langchain_service`. Rate limiting and auth aren't *inside* YARP — they're standard ASP.NET middleware (`AddRateLimiter`, `AddAuthentication`) that sit in front of the proxy step, which is precisely the mental model you described. This is also the honest resume story: "built an API gateway with YARP, custom telemetry middleware, with extension points for auth and rate limiting." **Decision: option (a), true YARP proxy.** Your existing `TelemetryMiddleware` survives unchanged. `LlmController` gets retired (or kept only as a non-routed reference).

**Q3 (endpoint topology) — good catch, and here's the cleaner framing: the 4 "test" and 4 "real" endpoints are the same 4 endpoints, reached via two network paths.** We do not write 8 handlers. The langchain_service defines 4 canonical routes (+ the OpenWebUI ones):

```
langchain_service (port 5000 internal):
  POST /chat/basic          POST /graph/basic
  POST /chat/rag            POST /graph/rag
  GET  /v1/models           POST /v1/chat/completions

Test path (dev only):   host:5001 → langchain_service directly
                        (works because compose maps 5001:5000)
Real path:              host:5000 → dotnet gateway → telemetry middleware
                        → YARP forwards /api/llm/{**rest} → langchain_service/{rest}
```

So `POST host:5000/api/llm/chat/rag` and `POST host:5001/chat/rag` hit the identical handler — one goes through the gateway (telemetry, future auth), one bypasses it. When you eventually want to lock the system down, you delete the `5001:5000` port mapping from compose and the "test path" ceases to exist without touching any code. This satisfies your Stage 1 requirement ("langchain_service should not receive outside communications... except for testing") as a *configuration* choice, not a code fork.

**Q5 (pipeline scalability) — three separate concerns, three separate mechanisms:**

1. *Multiple users, same pipeline.* Compiled chains and graphs are **stateless, reusable objects** — we build each pipeline once at startup, and every request is an independent `.invoke()` carrying its own state dict. Two users invoking the same graph concurrently never touch each other's data, the same way two calls to a pure function don't. Per-request concurrency is handled by the server layer (gunicorn workers). Later, when you add memory, per-user state lives in the checkpointer keyed by `thread_id` — the pipeline object itself still stays shared and stateless. This is the standard production pattern.
2. *Upgrading a pipeline.* This is what the **registry pattern** (your model-id → pipeline dict) buys us. Each pipeline has a string id (`"chat-basic"`, `"agent-rag"`). Upgrading = registering `"agent-rag-v2"` alongside v1; OpenWebUI's model list exposes both; you A/B them; you retire v1 by deleting one registry line. No endpoint changes, no client changes.
3. *New capabilities (e.g., photo parsing).* Two insertion points, both already planned: a new **node** in an existing graph (if it's a step in a flow — e.g., "if message contains image, parse it, put description in state, continue"), or a new **registry entry** (if it's a new flow entirely). The contract is the only thing that needs future-proofing: we'll define `user_message` today but keep the request shape extensible (a future `attachments` field is additive, not breaking). Designing the v1 contract so additions don't break existing clients is the real scalability discipline here — and it's a non-goal to *implement* photo parsing now.

**Where we stand:** Q1 decided (YARP proxy), Q2 agreed (snake_case contract, single doc), Q3 clarified above (confirm you're happy with "same endpoints, two paths"), Q4 decided (full mock RAG path), Q5 answered above, Q6 locked into Stage 1. If Q3's topology and Q5's answers sit right with you, I consider Stage 2 converged and I'll write the full Stage 3 implementation plan on your go.

---

## Stage 3 (Implementation Planning)

### [AI — 2026_07_10_23_17] Implementation Plan v1

Design decisions carried in from Stage 2: true YARP proxy gateway; snake_case wire contract in one doc; 4 canonical endpoints reachable via two network paths; full mock RAG path (fake embeddings + real pgvector); pipeline registry for dispatch and growth; LangGraph without policy node or checkpointer; acceptance criteria per Stage 1 §3.

**Ordering principle:** each step leaves the repo in a runnable state and is independently verifiable, so you can grant permission one step at a time in Stage 4 and check my work after each.

Extra findings folded in (discovered while preparing this plan): `Yarp.ReverseProxy 2.3.0` is *already referenced* in `server.csproj` — Step 7 is wiring, not adding. The Python dockerfile uses `python:3.9.13-slim-buster` while CI uses 3.11 (and current langchain releases have dropped 3.9). `requirements.txt` is fully unpinned. CI's `if [ -f requirements.txt ]` looks at repo root where no such file exists, so CI has never installed the service's dependencies — the green pipeline was only running `test_fake.py` with no real imports.

---

#### Step 1 — Contract document (no code changes)

Create `CONTRACTS.md` at repo root (it's an engineering artifact both services implement, not learning documentation, so it lives with the code).

Contents:
- **Canonical chat request** (all langchain_service pipeline endpoints): `{"user_id": str, "user_message": str, "requested_model": str}` — `requested_model` optional, defaults per LLM_MODE. Shape is additive-extensible (future `attachments`, `thread_id` are new optional fields, never renames).
- **Canonical success response**: `{"status": "success", "response": str, "metadata": {"pipeline_id": str, "model_used": str, "retrieved_sources": [str], "latency_ms": int}}`.
- **Canonical error response**: `{"status": "error", "error": {"code": str, "message": str}}` with HTTP status matching (400 malformed, 502 upstream model failure, 500 internal).
- **OpenAI-compatible surface** (`/v1/models`, `/v1/chat/completions`): follows OpenAI schema verbatim; documents the model-id → pipeline-id mapping rule.
- **Network topology table**: which ports exist, which are dev-only, gateway route prefixes.

Verification: you read and approve the document. Every later step cites it.

#### Step 2 — langchain_service boots again (minimal fixes, no restructuring)

Smallest set of changes to get the service importable and serving in mock mode:

2a. `app/models/factory.py`: replace dead import with `from app.prompts.mock_prompts import MOCK_RESPONSES`; `MockChatModel` gains an optional `response_pool` (defaults to friendly-assistant pool) and returns a random element — restoring your original commented-out intent.
2b. `app/orchestration/OrchestrationLogic.py`: call `PromptFactory.get_assistant_prompt()`; non-RAG worker passes `context=""` (the design already anticipated this in the docstring).
2c. `app/prompts/MyPromptTemplates.py`: remove the unused `("placeholder", "{message}")` line (it's for chat-history injection we aren't doing yet; reintroduced later with memory).
2d. `app/graph/nodes.py` + `build_graph.py`: fix the `PromptFactory` usage, remove `ToolNode, tool_condition` import (tools are a non-goal), fix `disired_model` → `desired_model` in `state.py` and all readers.
2e. `main.py`: run ingestion *before* `app.run`, drop `debug=True` (the reloader double-executes module-level code; we lose hot reload, gain determinism).

Verification: `./build.sh --mode mock` → container starts, `GET :5001/` returns the hello JSON, existing two POST endpoints return mock responses.

#### Step 3 — RAG layer: real in mock mode, idempotent, no import-time side effects

3a. New `app/rag/vector_store.py`: a `VectorStoreManager` class — connection string built from env, explicit `initialize()` called from `main.py`, no module-level globals executing at import (current `Ingestion.py` computes `mode` at import time, which is why mock-checks are scattered).
3b. **Mock embeddings**: `ModelFactory.get_embedding_model` returns `DeterministicFakeEmbeddings` (from `langchain_core.embeddings.fake` — deterministic per input text) when `LLM_MODE=mock`. pgvector now runs identically in both modes; only the embedding source differs. The mock-mode early-returns in retrieval/ingestion are deleted.
3c. **Idempotent ingestion**: compute `id = sha256(page_content)` per document and pass `ids=` to `add_documents` — langchain-postgres upserts on ID, so re-running ingestion N times yields exactly one row per document. Seed docs move to `app/rag/seed_documents.py`.
3d. Retrieval: `find_similar(message, k, score_threshold=None)` using `similarity_search_with_score`, threshold unused for now but present per your erroneous-retrieval concern (answering the question in your `Ingestion.py` comment).

Verification: mock build; `docker exec` into pgvector, `SELECT count(*) FROM langchain_pg_embedding;` — run ingestion twice (restart container), count unchanged (acceptance criterion 4). Retrieval returns the seeded docs for an on-topic query.

#### Step 4 — Pipeline registry + orchestration refactor

4a. New `app/orchestration/registry.py`: `PIPELINES: dict[str, Pipeline]` where a `Pipeline` is `(id, description, handler)` and every handler has the uniform signature `handle(request: ChatRequest) -> ChatResponse` (dataclasses mirroring CONTRACTS.md).
4b. `OrchestrationLogic.py` becomes `app/orchestration/pipelines.py` with four registered entries: `chat-basic`, `chat-rag`, `graph-basic`, `graph-rag`. The two chain pipelines are your existing workers refactored to the uniform signature; prompt/model/retriever acquisition is shared, not duplicated.
4c. Old files move to `old_implementations/` (matching your existing convention) rather than being deleted.

Verification: pytest unit tests — registry contains exactly 4 ids; each handler returns a contract-shaped response in mock mode (no containers needed).

#### Step 5 — LangGraph completion

5a. `build_graph(with_rag: bool)` — single builder, compiled twice at startup into the two graph pipelines: `START → retrieve (skipped/no-op when with_rag=False) → agent → respond → END`. State: `desired_model`, `retrieved_chunks`, `messages` (with `add_messages` reducer), `answer`.
5b. `graph-basic` / `graph-rag` registry entries invoke the pre-compiled graphs — compiled once at startup, shared statelessly across requests (the Q5 concurrency model, now in code).
5c. `build_graph_old` and the policy/blocked nodes move to `old_implementations/` (policy checking is a non-goal; the prompt stays in `PromptFactory` for the future).
5d. Growth path documented in module docstring: new capability = new node + edge in the builder, or new registry entry; memory later = checkpointer param already threaded through `build_graph`.

Verification: pytest — both graph pipelines return contract-shaped responses in mock mode; `retrieved_sources` empty for basic, populated for rag.

#### Step 6 — Flask API layer rebuilt on the registry

6a. `FlaskServer.py`: routes per CONTRACTS.md — `POST /chat/basic`, `/chat/rag`, `/graph/basic`, `/graph/rag`, each a thin shim: validate → build `ChatRequest` → `PIPELINES[id].handler(req)` → jsonify. Request validation returns contract-shaped 400s. Unhandled exceptions → contract-shaped 500s via a Flask error handler (no stack traces on the wire).
6b. `GET /v1/models`: generated from the registry (each pipeline id becomes a model id, e.g. `llm-monitor.graph-rag`). `POST /v1/chat/completions`: parses OpenAI shape, maps model id → pipeline, invokes, wraps the pipeline response in an OpenAI completion object. The hardcoded stub dies. (Streaming/SSE: deliberately deferred, OpenWebUI works without it.)
6c. `GET /healthz`: returns 200 + mode; used by compose healthcheck in Step 8.
6d. Dockerfile: base image → `python:3.11-slim`, run under `gunicorn` (2 workers) instead of the Flask dev server; ingestion runs in an entrypoint before gunicorn starts so it executes exactly once, not per-worker.

Verification: mock build; curl all 4 endpoints on :5001 → 200 + contract JSON (acceptance criterion 1); curl `/v1/models` and `/v1/chat/completions` → OpenAI-shaped responses containing real pipeline output.

#### Step 7 — dotnet gateway becomes a real YARP proxy

7a. `Program.cs`: `builder.Services.AddReverseProxy().LoadFromConfig(builder.Configuration.GetSection("ReverseProxy"))` and `app.MapReverseProxy()`. Package already referenced. `TelemetryMiddleware` stays exactly where it is in the pipeline — it now observes proxied traffic.
7b. `appsettings.json` ReverseProxy config: route `/api/llm/{**catch-all}` → cluster `langchain` (path transform strips the `/api/llm` prefix); route `/v1/{**catch-all}` → same cluster (for OpenWebUI). Cluster destination from env var `LANGCHAIN_BASE_URL` (set in compose) so nothing is hardcoded.
7c. `LlmController.cs` and `TestController.cs` retired to a `server/old_implementations/` folder (excluded from compilation) — same convention as Python.
7d. Extension points documented as comments where auth/rate-limiting middleware will slot in (explicit non-goals now).

Verification: mock build; curl `host:5000/api/llm/chat/rag` → identical response to `host:5001/chat/rag` (acceptance criterion 2); dotnet_server logs show telemetry entries for the proxied request.

#### Step 8 — docker-compose alignment

8a. `openwebui.OPENAI_API_BASE_URL` → `http://dotnet_server:8080/v1` (the commented-out line comes back to life — OpenWebUI now goes through the gateway, acceptance criterion 5).
8b. `dotnet_server`: add `LANGCHAIN_BASE_URL=http://langchain_service:5000`, `depends_on: langchain_service: condition: service_healthy`.
8c. `langchain_service`: healthcheck hitting `/healthz`.
8d. Note (no action): port `5001:5000` mapping is the dev/test path per Stage 2; removing it later is the lockdown switch.

Verification: full mock stack up; open OpenWebUI at :3000, pick a pipeline model, send a message, receive a mock-pipeline response that transited the gateway (confirmed via dotnet telemetry logs).

#### Step 9 — Tests + CI made honest

9a. Pin `requirements.txt` versions; add `requirements-dev.txt` (pytest).
9b. pytest suite replacing `test_fake.py`: contract-shape tests for all 4 pipelines (mock mode, Flask test client — no containers), registry integrity, ingestion ID determinism (pure function), OpenAI endpoint shape tests.
9c. `ci.yml`: fix the working directory so dependencies actually install (`langchain_service/requirements.txt`), run pytest with `LLM_MODE=mock`; re-enable the C# job (fixing the `setup-detnet` typo) to at least `dotnet build`.

Verification: `pytest` green locally; push to a branch → CI green with tests demonstrably importing real app code (acceptance criterion 6).

#### Step 10 — Live-mode verification & Stage 5 handoff

No new features — a scripted acceptance pass:
10a. `./build.sh --mode live` (small model, e.g. `qwen2.5:1.5b`); ingestion runs with real `nomic-embed-text` embeddings.
10b. Criterion 3: POST a question answerable only from a seed doc to `/chat/rag` and `/graph/rag`; response must contain the doc's content; same question to `/chat/basic` must not.
10c. Criterion 4 re-check under live embeddings (restart, count rows).
10d. Full criteria matrix results written into Stage 5 of this document.

---

#### Risks / open items I want you aware of before approving

1. **langchain-postgres upsert semantics** (Step 3c): I'm relying on `add_documents(ids=...)` overwriting on conflict. If the installed version inserts-only, fallback is delete-by-id-then-add. Verified during Step 3, flagged in Stage 4 notes if behavior differs.
2. **Python 3.9 → 3.11 + pinning** may surface dependency resolution changes; Step 2 verification catches this early since it rebuilds the image.
3. **OpenWebUI without streaming** (Step 6b): responses appear all-at-once. Acceptable for this cleanup; SSE is on your roadmap already.
4. **`/v1` routed through gateway** (Step 7b) means OpenWebUI traffic appears in telemetry — intended, but telemetry volume grows.
5. **Ollama URL inconsistency** noticed in passing: factory default is `http://ollama:11434` (service name) but `get_embedding_model` defaults to `http://ollama_service:11434` (container name). Compose sets the env var so it works today; Step 2 normalizes both fallbacks to the env-var-first pattern.

### Stage 3 Discussion Subsection

Awaiting Timothy's review of Implementation Plan v1.

### Stage 3 Discussion Subsection

Not Gotten To Yet

## Stage 4 (Implementation)

### [AI — 2026_07_10_23_25] Step 1 complete — CONTRACTS.md created

Created `CONTRACTS.md` at repo root. Contents as planned: snake_case wire convention (with the C# `JsonNamingPolicy.SnakeCaseLower` mapping rule, answering the naming-convention question from your old controller comments), canonical request/success/error shapes, an error-code table mapped to HTTP statuses, the 4 pipeline registry ids plus the `llm-monitor.<pipeline_id>` OpenAI model-id mapping rule, the OpenAI-compatible surface (streaming explicitly deferred), and the two-access-path topology table including the "delete the 5001 mapping = production lockdown" note.

Additions beyond the plan sketch (flagging for transparency): a reserved-future-fields list (`attachments`, `thread_id`, `options`) so v1 extensibility is explicit, and a `/healthz` contract since Step 8's compose healthcheck depends on it.

No code touched. Awaiting your review of CONTRACTS.md and permission for Step 2.

### [AI — 2026_07_10_23_35] Step 2 complete — langchain_service boots again

All sub-steps executed as planned:

- **2a** `factory.py`: dead import replaced with `from app.prompts.mock_prompts import MOCK_RESPONSES`. `MockChatModel` now has a `response_pool: list` pydantic field defaulting to the friendly-assistant pool, and `_generate` returns `random.choice(self.response_pool)` — your original commented-out intent, restored. Also normalized the embedding-model fallback URL from `ollama_service` to `ollama` (risk item 5 from the plan).
- **2b** `OrchestrationLogic.py`: both workers use `PromptFactory.get_assistant_prompt()`; the non-RAG worker passes `context=""`. Removed the `import *` (it was how the dead-symbol breakage propagated silently — explicit imports make the next rename a loud ImportError at startup instead of a quiet request-time NameError).
- **2c** `MyPromptTemplates.py`: unused `("placeholder", "{message}")` removed, comment marks where the chat-history slot returns with memory.
- **2d** `nodes.py`: `PromptFactory.get_policy_checker_prompt()` called correctly, invoke keys fixed to match the template (`injected_company_policies` — the old code passed `injectedCompanyPolicy`, a third bug in that line beyond the two we knew about). `state.py`: `disired_model` → `desired_model`. `build_graph.py`: bad `tool_condition` import removed, TODO left pointing at Step 5. Answered your `partition(":")` comment question inline: it splits on the *first* colon only, returning `(before, ":", after)`, so reasons containing colons survive intact.
- **2e** `main.py`: ingestion now runs before the server accepts traffic; `debug=True` removed (reloader double-imports the module).

**Noted, not fixed (out of Step 2 scope):** `build_graph_old` references `agent_node`/`respond_node` which don't exist in `nodes.py` — it would NameError if called. Nothing calls it; Step 5 retires it to `old_implementations/`.

**Verification status:** `py_compile` passes on all 11 service files; grep confirms zero remaining references to any dead symbol (`disired_model`, `MockChatTypeDictionary`, `tool_condition`, etc.). My sandbox has no PyPI/Docker access, so the runtime check is yours: run `./build.sh --mode mock`, then `curl :5001/` (hello JSON) and POST the two existing `/test/langchain/...` endpoints — both should now return random mock-pool responses instead of crashing.

### [AI — 2026_07_10_23_48] Step 2 addendum — dead-code remnants retired (Timothy's request)

Per your request, all `*_old`/practice remnants moved out of active code into `old_implementations/` (nothing deleted — your notes are preserved verbatim, each with a header explaining provenance):

- `app/graph/build_graph.py` → `build_graph_old` moved to `langchain_service/old_implementations/build_graph_old.py`. Header notes it references `agent_node`/`respond_node` that were never written — it would NameError if called.
- `app/api/FlaskServer.py` → the commented `t1()` dispatch-dict draft moved to `langchain_service/old_implementations/notes_v1_dispatch_draft.py`. Its header credits the idea as the origin of the registry pattern in CONTRACTS.md §4.
- `server/controllers/LlmController.cs` → 100-line commented `LlmController_old` block moved to `server/old_implementations/LlmController_old.cs`.
- `server/controllers/TestController.cs` → the 113-line `/* ... */` practice block (serialization experiments, from-memory `LlmChatCall` attempt) moved to `server/old_implementations/TestController_practice_notes.cs`.

One thing to be aware of: SDK-style csproj files auto-compile every `.cs` under the project folder, so `server/old_implementations/*.cs` WILL be picked up by the compiler. Both files are 100% comments, so this is harmless today — but Step 7 adds an explicit `<Compile Remove="old_implementations/**" />` so future retirements there can contain real (uncommented) code safely.

Verification: `py_compile` passes on the touched Python files; grep shows zero `_old` references left in `langchain_service/app/` or `server/controllers/`.

### [AI — 2026_07_11_00_02] Step 3 complete — RAG layer rebuilt

**What changed:**

- **3a** New `app/rag/vector_store.py`: `VectorStoreManager` with explicit `initialize()` (no module-level side effects — importing it never touches the network; the old file computed `mode` and the connection string at import time, which is why mock-checks were scattered everywhere). Module-level singleton `vector_store` shared statelessly across requests. Misuse before init raises a clear RuntimeError. Host now env-configurable (`POSTGRES_HOST`, default = compose service name `pgvector-service`).
- **3b** `ModelFactory.get_embedding_model` returns `DeterministicFakeEmbeddings(size=768)` in mock mode — `768` deliberately matches nomic-embed-text's dimension so mock and live rows share one pgvector column schema. All mock-mode early-returns in the RAG path are gone: **pgvector now runs for real in mock mode**. Also fixed two latent bugs in the live path: the method ignored its own parameter (hardcoded `"nomic-embed-text"`), and a failed model pull was silently ignored (now raises at startup rather than corrupting the store mid-request).
- **3c** `app/rag/seed_documents.py` holds the seed docs (data only; fixed the `testingexplosive` typo). `Ingestion.py` is now a thin orchestrator: `initialize()` + `add_documents_idempotent(SEED_DOCUMENTS)`. IDs are `sha256(page_content)` passed to `add_documents(ids=...)` — langchain-postgres upserts on ID conflict, so N restarts = one row per document (risk item 1 from the plan: your row-count verification below is the empirical check on this).
- **3d** `find_similar(message, k, score_threshold=None)` built on `similarity_search_with_score`. Threshold is opt-in and off by default (behavior unchanged) — it exists because a nearest neighbor *always* exists, even for garbage queries; "nearest" ≠ "near".
- **Design addition beyond plan sketch:** per-mode collections (`company_policies_mock` / `company_policies_live`) — both modes share the pgdata volume, and fake-embedding rows must never be candidates in a live similarity search.
- Callers updated: `OrchestrationLogic.py` and `nodes.py` now use `vector_store.find_similar(...)`. Original `Ingestion.py` (with your comment-questions) preserved at `old_implementations/Ingestion_v1.py`.

**Answers to the questions in your old Ingestion.py comments:**

1. *"I need to investigate what PGVector is doing"* — `PGVector(...)` builds a SQLAlchemy engine for the connection string, ensures two tables exist (`langchain_pg_collection` — one row per collection name; `langchain_pg_embedding` — one row per document: id, embedding vector, document text, JSONB metadata, collection FK), and registers your embedding model so `add_documents` embeds text before INSERT and `similarity_search` embeds the query before the distance query.
2. *"we need to block erroneous retrievals... minimum matching closeness"* — that's exactly `score_threshold`. PGVector scores are cosine *distance* (lower = closer), so the guard keeps `distance <= threshold`.
3. *"how would we do this outside the LC ecosystem... talk to pgvector itself"* — yes, directly in SQL. pgvector adds a `vector` column type and distance operators; the whole retrieval is: `SELECT document FROM langchain_pg_embedding ORDER BY embedding <=> '[...query vector...]' LIMIT 4;` where `<=>` is cosine distance (`<->` L2, `<#>` negative inner product). LangChain's contribution is only: embed the query, build this SQL, map rows to `Document` objects. Worth doing once by hand from the pgvector container to demystify it — good interview material.

**Verification:** `py_compile` clean on all touched files; grep confirms no `FindSemanticlyClosestElement` or `pgvector_service` references remain. Runtime checks for you (acceptance criterion 4):

```
./build.sh --mode mock
docker exec -it pgvector_service psql -U admin -d vectordb -c "SELECT count(*) FROM langchain_pg_embedding;"   # expect 2
docker restart langchain_service   # re-runs ingestion
docker exec -it pgvector_service psql -U admin -d vectordb -c "SELECT count(*) FROM langchain_pg_embedding;"   # STILL 2 = idempotent
curl -X POST localhost:5001/test/langchain/chatnosecurityrag -H "Content-Type: application/json" -d '{"user_message":"can I use scripting tools?"}'   # mock: should now execute a REAL pgvector similarity search
```

If the second count differs from the first, risk item 1 fired (add_documents not upserting on this version) — report the number and I'll switch to delete-then-add in a follow-up.

### [AI — 2026_07_11_00_18] Step 4 complete — pipeline registry + orchestration refactor

**What changed:**

- **4a** Three new modules in `app/orchestration/`:
  - `contracts.py` — dataclasses mirroring CONTRACTS.md §1/§2 (`ChatRequest`, `ChatResponse`, `ChatMetadata`, with `to_dict()` producing the exact wire shape). Dataclasses instead of raw dicts so a typo'd field name is an AttributeError at dev time, not a silent contract violation on the wire.
  - `registry.py` — `PIPELINES` dict, `register()` (rejects duplicate ids), `get_pipeline()` raising `UnknownPipelineError` (the API layer maps it to 404/`unknown_pipeline` in Step 6).
  - `pipelines.py` — registers all 4 CONTRACTS.md §4 ids on import. `chat-basic` and `chat-rag` share one `_run_assistant_chain(request, pipeline_id, k)` body (k=None means no retrieval) — your old workers had ~80% duplicated code; now the diff between the two pipelines is literally one argument. Metadata is fully populated: pipeline_id, model_used, retrieved_sources, latency_ms.
- **Deviation from plan, flagged:** `graph-basic`/`graph-rag` are registered as *honest placeholders* that raise `NotImplementedError` rather than silently delegating to the chain implementations. Registry is complete (4 ids, so `/v1/models` generation in Step 6 is correct), but nothing pretends to be a graph that isn't one. Step 5 swaps in the compiled graphs.
- **4b** `FlaskServer.py`: the two existing routes now dispatch through `get_pipeline(...)` and return the CONTRACTS.md §2 shape. **Breaking change to note:** response body changed from `{"status", "message_response"}` to the contract shape — if you had anything scripted against the old shape, it needs the new field names. Route *paths* are unchanged until Step 6. The request parser accepts both `requested_model` (contract name) and your old `user_requested_model` (transitional; dropped in Step 6).
- **4c** `OrchestrationLogic.py` retired to `old_implementations/OrchestrationLogic_v1.py` and removed from `app/` (file deletion approved by Timothy via Cowork permission prompt).
- **Verification artifact:** `tests/test_registry.py` — registry integrity (exactly 4 ids), unknown-id error path, chat-basic full contract-shape assertions, graph placeholders raise. Run: `cd langchain_service && LLM_MODE=mock python -m pytest tests/test_registry.py -v`.

**Housekeeping observation (no action taken):** `__pycache__/` directories with stale compiled bytecode (including the deleted `OrchestrationLogic`) exist inside the repo tree — worth adding `__pycache__/` to `.gitignore` if not already covered, and untracking any committed `.pyc` files. Flagging rather than fixing since it touches git state.

**Verification status:** `py_compile` clean on all new/touched files; grep shows no remaining `OrchestrationLogic` or worker-function references in `app/` (only the stale `__pycache__` noted above). Runtime: the same two curl commands from Step 2/3 now return the full contract JSON (status/response/metadata) — plus `tests/test_registry.py` above.

### [AI — 2026_07_11_00_31] Step 5 complete — LangGraph pipelines live

**What changed:**

- **5a** `build_graph(with_rag: bool, checkpointer=None)` — one builder, two shapes: `START → agent → respond → END` and `START → retrieve → agent → respond → END`. Design choice worth understanding: RAG is decided by **conditional wiring at build time**, not a no-op node checking a flag per request — the compiled graph contains only the steps it actually runs. The checkpointer parameter is threaded through now (unused), so adding memory later is an argument, not a refactor.
- `state.py`: `ChatState` slimmed to `user_id`, `desired_model`, `retrieved_chunks`, `messages`, `answer` (policy fields and the redundant `user_msg` dropped). Your old *"Investigate this"* comment on `add_messages` is answered in the docstring: it's a **reducer** — a node returning `{"messages": [x]}` gets *appended* (deduped by message id) instead of overwriting the list; every other field is last-write-wins. That's the mechanism multi-turn memory will ride on.
- `nodes.py`: `retrieve_node` (k=4), new `agent_node` (context from state → shared PromptFactory/ModelFactory chain → `answer`), new `respond_node` (commits `answer` to history as an `AIMessage`; deliberately separate — it's the future seam for citation formatting/output grading without touching model invocation). Nodes use the *same* components as the chain pipelines: one set of building blocks, two execution engines.
- **5b** `pipelines.py`: graphs compiled **once at import** into `_GRAPH_BASIC`/`_GRAPH_RAG` (compilation is pure assembly — no network/DB), then shared statelessly; every `.invoke()` carries its own state dict, so concurrent users never interact (the Q5 concurrency answer, now literally in the code comments). Placeholders replaced by `graph_basic`/`graph_rag` handlers via a shared `_run_graph` body; `retrieved_sources` extracted from final state.
- **5c** Old policy/blocked nodes preserved at `old_implementations/graph_policy_nodes_v1.py`; the policy-checker prompt remains live in `PromptFactory` for when that feature is scheduled.
- **5d** Growth path documented in the `build_graph.py` module docstring (new step = node+edge; new flow = builder variant + registry entry; memory = checkpointer + thread_id).
- Test updated: the Step 4 placeholder test is replaced by `test_graph_basic_returns_contract_shape` — graph-basic is fully unit-testable in mock mode since it has no retrieve node. graph-rag joins the Step 9 integration tier (needs pgvector).

**Verification:** `py_compile` clean; grep confirms no `policy_check_node`/`blocked_node`/`NotImplementedError` remnants in `app/` (stale `__pycache__` aside). For you:

```
cd langchain_service && LLM_MODE=mock python -m pytest tests/test_registry.py -v   # 4 tests, all green
```

All four registry pipelines are now real. Flask routes for the graph pipelines don't exist yet — that's Step 6, which is also where `/v1/chat/completions` stops being a stub.

### [AI — 2026_07_11_00_49] Step 6 complete — API layer rebuilt on the registry

**What changed:**

- **6a** `FlaskServer.py` fully rewritten (v1 preserved at `old_implementations/FlaskServer_v1.py`). The four canonical routes (`/chat/basic`, `/chat/rag`, `/graph/basic`, `/graph/rag`) are generated from one `PIPELINE_ROUTES` mapping — each is a shim: validate → `ChatRequest` → registry dispatch → contract JSON. Error mapping per CONTRACTS.md §3 via Flask errorhandlers: `UnknownPipelineError`→404, `RuntimeError` (ModelFactory upstream failures)→502, anything else→500 with a generic message on the wire and the full traceback in logs only.
- Adopted the Flask **application-factory pattern**: `IntializeFlaskEndpoints()` → `create_app()`. This is the standard Flask shape — tests construct a fresh app per test, and WSGI servers import it from `wsgi.py`. (Also quietly retires the `Intialize` typo.)
- **6b** `/v1/models` is now generated from the registry (`llm-monitor.<pipeline_id>` × 4). `/v1/chat/completions` is real: model id → pipeline, last user-role message → `user_message`, pipeline response wrapped in a proper `chat.completion` object. **The hardcoded stub is dead.**
- **6c** `/healthz` returns `{"status": "ok", "mode": ...}`. The old `/` hello route is gone (healthz is its professional replacement).
- **6d** Runtime rebuilt: `python:3.11-slim`, gunicorn (2 workers). Process model worth understanding — `entrypoint.sh` runs ingestion exactly ONCE before gunicorn forks; then each worker imports `wsgi.py`, which calls `vector_store.initialize()` per worker (each forked process needs its OWN connection pool — pools must never be shared across forks). `create_app()` itself never touches the DB, so unit tests need no containers. `main.py` remains as the documented local-dev entry. Also: answered the old dockerfile TODO (uvicorn is ASGI, for async frameworks; Flask is WSGI → gunicorn is its production server), and added `.dockerignore` (`.venv/` alone was silently bloating every image build via `COPY . .`).
- `requirements.txt`: + gunicorn (pinning happens in Step 9).

**Breaking changes to note:**
1. Old routes `/test/langchain/chatnosecurity[rag]` are GONE — replaced by the CONTRACTS.md §6 routes. Update any saved curls.
2. The transitional `user_requested_model` field is dropped; the contract name is `requested_model`.

**Known risk (flagged in plan, now concrete):** OpenWebUI sends `stream: true` by default; we return a complete JSON body regardless. If OpenWebUI's UI won't render non-streamed completions, the quick fix is wrapping the same response as a single SSE chunk — say the word if chat output doesn't appear in Step 8 testing.

**Verification (for you):**

```
./build.sh --mode mock
curl localhost:5001/healthz
for p in chat/basic chat/rag graph/basic graph/rag; do
  curl -s -X POST localhost:5001/$p -H "Content-Type: application/json" -d '{"user_message":"can I use scripting tools?"}'; echo; done
curl localhost:5001/v1/models
curl -s -X POST localhost:5001/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"llm-monitor.graph-rag","messages":[{"role":"user","content":"hello"}]}'
curl -s -X POST localhost:5001/chat/basic -H "Content-Type: application/json" -d '{}'            # expect contract-shaped 400
curl -s -X POST localhost:5001/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"llm-monitor.nope","messages":[{"role":"user","content":"hi"}]}'                   # expect contract-shaped 404
```

This is acceptance criterion 1 in full (all 4 endpoints, 200 + contract JSON, mock mode). Next: Step 7 (YARP) unlocks criterion 2.

### [AI — 2026_07_11_01_02] Step 7 complete — the dotnet server is now a real YARP gateway

**What changed:**

- **7a** `Program.cs` rewritten: `AddReverseProxy().LoadFromConfig(...)` + `app.MapReverseProxy()`. Pipeline order is documented in the code because the order IS the architecture: `telemetry → [future auth] → [future rate limiter] → YARP forwarder`. Controllers-related services (`AddControllers`, `AddHttpClient`, `MapControllers`) are gone — the gateway forwards, it doesn't orchestrate. Added `GET /healthz` (minimal API) as the gateway's own liveness probe. Your two old comment-questions are answered inline: `UseTelemetryMiddleware` works on `app` because it's an *extension method* (`this IApplicationBuilder` makes it callable on the receiver) and it registers into the request *pipeline*, not DI; no `using` is needed because the extension class shares the `LLM_MONITOR.server` namespace.
- **7b** `appsettings.json` gains the `ReverseProxy` section: route `llm-pipelines` matches `/api/llm/{**catch-all}` with a `PathRemovePrefix` transform (so `/api/llm/chat/rag` → `/chat/rag` upstream); route `openai-surface` matches `/v1/{**catch-all}` unchanged (for OpenWebUI). One cluster, `langchain`, default destination `http://langchain_service:5000/`. **Deviation from plan, flagged:** instead of a custom `LANGCHAIN_BASE_URL` variable parsed in code, the destination is overridable via ASP.NET's built-in config-from-env mechanism (`ReverseProxy__Clusters__langchain__Destinations__primary__Address`) — zero custom code, and it's the idiomatic pattern (double underscore = config path separator). Step 8's compose note reflects this.
- **Necessary addition:** `TelemetryMiddleware` was an empty skeleton (comments only) — it now logs `method / path / status / elapsed_ms` per request via structured logging, with a Stopwatch around `await _next(...)`. Without this, the step's own verification ("telemetry entries for proxied requests") was unfalsifiable. The in/out halves of the middleware are commented; a TODO points at the OpenTelemetry future from your roadmap.
- **7c** Both controllers retired to `server/old_implementations/{LlmController_v1.cs, TestController_v1.cs}` and the `controllers/` folder removed. `server.csproj` now has `<Compile Remove="old_implementations/**" />` — the archive folder is officially invisible to the compiler (closing the caveat from the Step 2 addendum; real uncommented code can live there safely now). `server.Tests` has no reference to the retired controllers (placeholder test only).
- **7d** Auth/rate-limiter extension points are explicit commented lines in the pipeline with the service registrations they'd need.

**Verification (for you — my sandbox has no dotnet SDK, so compile check is yours):**

```
cd server && dotnet build            # first: confirms YARP config-by-code compiles
./build.sh --mode mock               # then the real test through the gateway:
curl localhost:5000/healthz                                          # gateway itself
curl -s -X POST localhost:5000/api/llm/chat/rag -H "Content-Type: application/json" \
  -d '{"user_message":"can I use scripting tools?"}'                 # should EXACTLY match localhost:5001/chat/rag
curl localhost:5000/v1/models                                        # OpenAI surface via gateway
docker logs dotnet_server | grep telemetry                           # entries for the proxied calls
```

That's acceptance criterion 2 (same responses via gateway routes). Step 8 rewires OpenWebUI through this gateway and adds healthchecks.

### [AI — 2026_07_11_01_12] Step 8 complete — compose topology aligned

**What changed (docker-compose.yaml only):**

- **8a** `openwebui.OPENAI_API_BASE_URL` → `http://dotnet_server:8080/v1` — your commented-out line from months ago, resurrected. Every OpenWebUI chat now transits telemetry → YARP → langchain_service. `depends_on` switched from langchain_service to dotnet_server accordingly.
- **8b** `dotnet_server.depends_on` upgraded from plain list to `langchain_service: condition: service_healthy` — the gateway doesn't start until its upstream can actually serve. No env var needed for the YARP destination (appsettings default already matches the compose service name); a commented override using the `ReverseProxy__...` double-underscore form is in place for when you want to retarget without a rebuild.
- **8c** `langchain_service` healthcheck hits `/healthz`. Implementation detail that matters: `python:3.11-slim` ships neither curl nor wget, so the probe is stdlib `urllib.request` via `python -c`. `start_period: 20s` covers image boot + the one-time RAG ingestion in the entrypoint (probe failures during start_period don't count against retries).
- **8d** The `5001:5000` dev mapping stays, now with the CONTRACTS.md §6 comment marking it as the production lockdown switch.

**Startup chain now encoded in compose:** pgvector healthy → langchain ingests + serves → healthy → gateway starts → OpenWebUI starts. A half-initialized system can no longer accept traffic in the wrong order.

**Verification (for you — full-stack, acceptance criterion 5):**

```
./build.sh --mode mock
docker compose -p llm_monitor ps        # langchain_service should show (healthy)
# open http://localhost:3000 — model dropdown should list all four llm-monitor.* pipelines
# pick llm-monitor.chat-rag, send a message, get a mock-pool response back
docker logs dotnet_server | grep telemetry   # the OpenWebUI traffic, proxied
```

Watch-item from Step 6 applies here: if the model list appears but chat responses never render, that's the `stream: true` issue — tell me and I'll add the single-chunk SSE wrapper. Remaining: Step 9 (tests/CI) and Step 10 (live-mode acceptance pass).

### [AI — 2026_07_11_01_28] Step 9 complete — tests and CI made honest

**What changed:**

- **9b** Test suite (`test_fake.py` deleted — it was `assert True`, the ghost that kept your pipeline green while testing nothing):
  - `conftest.py` at the service root — sets `LLM_MODE=mock` before any app import and provides a fresh Flask test client per test (the application-factory payoff from Step 6). Placed at the root, not in `tests/`, deliberately: pytest adds a conftest's directory to `sys.path`, which is what makes `import app...` resolve regardless of invocation directory.
  - `tests/test_api_contract.py` — 10 tests over the HTTP surface: `/healthz`, all four pipeline routes (parametrized, field-by-field §2 assertions), missing/malformed-body 400s, `/v1/models` registry generation, `/v1/chat/completions` round-trip, unknown-model 404, missing-user-turn 400. **Key technique:** retrieval is monkeypatched on the `vector_store` singleton — pipelines, graph nodes, and routes all share that one object, so `/chat/rag` and `/graph/rag` are fully testable with zero containers, including asserting `retrieved_sources` comes back populated.
  - `tests/test_ingestion_ids.py` — pins the idempotency guarantee at its root: id is a pure function of content (same content → same id even with different metadata; matches `sha256` exactly; seed docs unique). The docker row-count check verifies the *database* behavior; these verify the *invariant* that makes it work.
  - `tests/test_registry.py` — unchanged from Steps 4/5.
- **9c** `ci.yml` rewritten. The confession-worthy fix: `working-directory: langchain_service` — the old workflow's `if [ -f requirements.txt ]` looked at the repo root, found nothing, installed nothing, and passed vacuously. Now: Python 3.11 (matching the runtime image), real dependency install (+ `requirements-dev.txt`), `LLM_MODE=mock python -m pytest -v`. C# job re-enabled with the `setup-detnet` typo fixed: `dotnet build` on the gateway + `dotnet test` on server.Tests.
- **9a — deviation from plan, flagged:** requirements are NOT exact-pinned in this step. Reason: my sandbox has no PyPI access, so any exact versions I wrote would be guesses — and a guessed pin that's wrong breaks your build *immediately* (worse than floating). The honest path: pin from a **resolved, working environment**. After your next successful `./build.sh --mode mock`, run:

  ```
  docker compose -p llm_monitor exec langchain_service pip freeze > langchain_service/requirements.lock
  ```

  and I'll switch the dockerfile and CI to install from the lock (one-line changes each) in a follow-up. `requirements-dev.txt` (pytest) added as planned.

**Verification (for you):**

```
cd langchain_service && python -m pytest -v        # expect 18 tests, all green, no containers running
git push origin <branch>                            # CI: both jobs green, python job visibly installing real deps
```

That's acceptance criterion 6 modulo the lock-file follow-up. Step 10 (live-mode acceptance pass) closes out the plan.

### [AI — 2026_07_11_01_44] Step 10 complete — scripted acceptance pass delivered; execution is yours

No new features, as planned. The deliverable is `scripts/acceptance_check.sh` — one script, run once per mode:

```
./build.sh --mode mock && bash scripts/acceptance_check.sh mock
./build.sh --mode live && bash scripts/acceptance_check.sh live      # uses your small-model default (qwen2.5:1.5b via build.sh)
```

What it automates, mapped to the Stage 1 criteria: **[1]** all four pipeline endpoints direct on :5001, field-level contract assertions; **[2]** the same four via the gateway `/api/llm/*` plus `/v1/models` through YARP; **§3 error paths** (400 missing message, 404 unknown model); **[3]** `retrieved_sources` contains the seed doc for RAG routes and is empty for basic — in live mode it also prints the RAG vs basic answers side-by-side for your human judgment on whether the model *visibly used* the policy text; **[4]** row count in the mode's collection before and after a `docker restart` (expects 2 → 2). Criteria **[5]** (OpenWebUI round-trip + gateway telemetry) and **[6]** (pytest/CI) are printed as manual steps at the end.

Design notes: no `set -e` — an acceptance pass runs *every* check and reports, rather than dying at the first failure; JSON assertions are python3 one-liners (no jq dependency); `wait_healthy` polls `/healthz` so the restart check can't race ingestion; row counts are scoped to `company_policies_<mode>` via the collection join, so mock and live runs don't contaminate each other's criterion 4.

Verified here: bash syntax, the JSON-assert helper against a real contract body, and the route-substitution idiom. Network execution is on your machine.

**This closes Stage 4.** Run both passes and paste the two summary blocks (plus criteria 5/6 results) into Stage 5 below — the matrix is scaffolded and waiting. If anything FAILs, we handle it as a Stage 5 finding, not a silent re-edit: the plan stays an honest record.

## Stage 5 (Final Results, Testing, Verficiation)

### Acceptance criteria matrix (fill from acceptance_check.sh output)

| # | Criterion (Stage 1 §3) | Mock | Live | Evidence / notes |
|---|---|---|---|---|
| 1 | 4 test endpoints return 200 + contract JSON | ☐ | n/a | `acceptance_check.sh mock` criterion-1 block |
| 2 | Same via dotnet gateway routes | ☐ | n/a | criterion-2 block + telemetry log lines |
| 3 | Live RAG response demonstrably uses ingested content | n/a | ☐ | criterion-3 block + side-by-side answers |
| 4 | Re-running ingestion yields no duplicate rows | ☐ | ☐ | criterion-4 block (2 → 2) |
| 5 | OpenWebUI round-trips through the real pipeline | ☐ | ☐ | manual: chat at :3000 + `docker logs dotnet_server \| grep telemetry` |
| 6 | pytest suite passes in CI | ☐ | n/a | local `pytest -v` (18 tests) + CI run link |

### Results log (chronological — paste script output and observations below)

*(awaiting Timothy's mock and live runs)*

### Known deferred items (carried out of plan 001, not failures)

- `requirements.lock` generation + dockerfile/CI switch to it (Step 9a deviation — needs Timothy's one `pip freeze` command from a working build).
- OpenWebUI `stream: true`: if chat renders no output despite 200s, add the single-chunk SSE wrapper (Step 6 watch-item).
- pgvector upsert semantics (plan risk 1): confirmed or refuted by criterion 4's 2 → 2 check.
- Score threshold for retrieval quality is implemented but disabled (`score_threshold=None`) — tuning belongs to the evaluation-harness roadmap item, with real metrics instead of guesses.

### Found Issues and Discussion

#### Timothy's Response

1. The build was failing the unit testing.
```
Run python -m pytest -v
ImportError while loading conftest '/home/runner/work/LLM_Monitor/LLM_Monitor/langchain_service/conftest.py'.
conftest.py:15: in <module>
    from app.api.FlaskServer import create_app
app/api/FlaskServer.py:20: in <module>
    import app.orchestration.pipelines  # noqa: F401 — importing registers all pipelines
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
app/orchestration/pipelines.py:16: in <module>
    from app.models.factory import ModelFactory
app/models/factory.py:5: in <module>
    from langchain_core.embeddings import DeterministicFakeEmbeddings
E   ImportError: cannot import name 'DeterministicFakeEmbeddings' from 'langchain_core.embeddings' (/opt/hostedtoolcache/Python/3.11.15/x64/lib/python3.11/site-packages/langchain_core/embeddings/__init__.py)
Error: Process completed with exit code 4.
```

I looked at the documentation online and saw that the correct way to call it is

```
from langchain_core.embeddings import DeterministicFakeEmbedding

embed = DeterministicFakeEmbedding(size=100)
```

So I changed the names in langchain_service/app/models/factory.py to conform to this.

This is actually quite a confusing thing and I am not sure that it will even compile (or run I guess in Python's case) because I am attempting to call DeterministicFakeEmbedding but importing DeterministicFakeEmbeddings. (but I tested it, and making this change does now cause my python-tests in github actions to pass).

2. Within the add_documents_idempotent method, I noticed that it seems this way of doing the operations will look at all of the documents which are currently needing to be within the vector database, it will then calculate a hash based on the document itself (and all the content), then it will add all those documents. This imples to me that we will be needing to go through all documents, vectorizing them, putting them into our vector database (overwriting the exact same old ones that are already there). This seems like a very wasteful operation. I am wondering if a different approach might be that we check if that id is within our database and if so, we will not attempt to add that document.

As of right now, we only have two sample Document objects, but eventually we will have long pdf and other documents which we will want to store within the database, so in the future it might grow to be more of a problem.

#### [AI — 2026_07_11_20_17] Response to both found issues

**Issue 1 (DeterministicFakeEmbedding import) — your suspicion was CORRECT, and the fix was incomplete.** I checked `factory.py`: your commit fixed the *import* (line 5, singular) but line 60 still *called* the plural `DeterministicFakeEmbeddings(size=768)`. Three things worth understanding here:

1. *Why it "compiled" anyway:* Python has no compile-time name resolution. `py_compile` only checks syntax; names are looked up **at call time**. So the module imports fine, and the NameError only fires when `get_embedding_model` actually executes in mock mode — i.e., the first real mock-mode ingestion after your change would have crashed the container at startup.
2. *Why CI stayed green:* none of the 18 tests ever calls `get_embedding_model` — the API tests monkeypatch retrieval, and the ingestion tests only exercise the pure `deterministic_id` function. A green suite is only as honest as its coverage. This is the plan-001 CI lesson recurring one level deeper: last time the pipeline installed nothing; this time it installed everything and still couldn't see this bug.
3. *Why the typo happened at all (my error, for the record):* langchain_core's own naming is inconsistent — the base class is `Embeddings` (plural), the sibling fake is `FakeEmbeddings` (plural), but this one is `DeterministicFakeEmbedding` (singular). I pattern-matched to the plural convention instead of verifying the symbol. Your instinct to check the documentation was exactly the right move.

*Actions taken:* fixed the call site (line 60 → singular, with a comment memorializing the naming trap), and added `tests/test_factory.py` — a test that CALLS the mock embedding path (asserts constructible, 768-dim, deterministic same-text→same-vector, different-text→different-vector) plus a mock chat-model label test. That closes the specific coverage gap that let your CI pass with a live NameError in the tree. Suite is now 20 tests.

**Issue 2 (re-embedding every startup) — your analysis is right, and it's a real scaling concern.** Current behavior: every startup re-embeds every seed doc and upserts it, even when the row is already there and identical. With 2 docs that's milliseconds; with chunked PDFs it's real compute (embedding is the expensive step — the DB write is cheap). Your proposed fix — check existence first, skip what's already there — is the correct first optimization, and content-hash ids make it *safe*: if the id exists, the content is by definition identical, so skipping loses nothing.

Proposed change to `add_documents_idempotent` (~4 lines, one extra round-trip):

```python
ids = [self.deterministic_id(d) for d in docs]
existing = {doc.id for doc in self._require_initialized().get_by_ids(ids)}
missing = [(i, d) for i, d in zip(ids, docs) if i not in existing]
if missing:
    self._store.add_documents([d for _, d in missing], ids=[i for i, _ in missing])
```

One `get_by_ids` SELECT replaces N embedding computations — embedding cost is now paid only for genuinely new content.

Two things you should know are *deliberately not solved* by this (so we scope them consciously rather than discover them later):

1. **Orphans on edit.** Because id = sha256(content), an *edited* document gets a NEW id — the old version stays behind as a stale row that retrieval can still surface. True synchronization needs a delete side ("rows in DB whose ids are no longer in the source set"). LangChain has purpose-built machinery for exactly this delta-sync problem (the indexing API / `RecordManager`, with `incremental` and `full` cleanup modes) — worth adopting when documents become editable, rather than reinventing it.
2. **Startup ingestion doesn't scale past a small corpus.** When the PDFs arrive, ingestion should become its own job (loader → chunker → embedder → delta-sync), triggered on demand or on a schedule — not something that blocks container startup. That's a proper future implementation plan ("document ingestion pipeline"), and it's also where your loader/chunker TODO from the original `Ingestion.py` naturally lands.

*Recommendation:* I implement the skip-existing optimization now as a plan-001 addendum (small, in scope for "ensure RAG saves documents correctly", immediately testable — ingestion twice, second run embeds zero docs), and we log orphan-cleanup + offline ingestion as the seed of a future plan. Your call — say go and it's a 15-minute change with a test.