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

Not Gotten To Yet

## Stage 5 (Final Results, Testing, Verficiation)

Not Gotten To Yet