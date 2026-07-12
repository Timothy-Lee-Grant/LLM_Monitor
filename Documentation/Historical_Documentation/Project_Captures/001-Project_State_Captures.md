2026_07_09_21_00-Project_State_Captures

# Project State Captures — LLM_Monitor

> **Purpose of this file (read this first if you are an LLM):** This is an append-only log of state captures for Timothy Grant's LLM_Monitor project. Each capture is a self-contained snapshot: what the project is, what works, what's hard, and what stories it has generated. Timothy pastes this file into other AI-assisted workflows (career planning, interview prep, project ideation). Timothy is targeting a Software Engineer role at **Microsoft**. Treat every capture as raw material for: (a) resume bullets, (b) behavioral interview stories (STAR format), (c) technical interview talking points, (d) gap analysis. New captures are appended below; never rewrite old ones.

---

# CAPTURE 001 — 2026_07_09 — "First end-to-end LLM responses: live chat + RAG working"

## 1. What this project is

**LLM_Monitor** is a self-built, multi-container AI orchestration platform. It is a learning vehicle deliberately built 100% by hand (AI assistants are prohibited from writing or fixing code; they act only as code reviewers and lecture-writers via markdown docs). The eventual product concept: a monitored LLM chat system where user messages pass through security/policy checking, RAG-augmented generation, and telemetry capture — i.e., the plumbing an enterprise would need to deploy LLM chat responsibly.

### Architecture (4 containers, Docker Compose, single bridge network)

```
user ──► dotnet_server (C#/ASP.NET Core, :5000→8080)     [entry point / router / telemetry middleware]
              │
              ▼
         langchain_service (Python/Flask, :5001→5000)     [AI orchestration: prompts, chains, RAG]
              │                        │
              ▼                        ▼
         ollama_service (:11434)   pgvector_service (pg16)
         [local LLM runtime,       [vector DB; embeddings stored
          llama3.1:8b +             via langchain_postgres PGVector,
          nomic-embed-text]         collection "company_policies"]
```

- **Build orchestration:** `build.sh --mode mock|live [--gpu] [--model X]` — tears down, rebuilds, and recreates containers. Docker Compose **profiles** gate the ollama container to live mode only. Environment variables (`LLM_MODE`, `LLM_MODEL`, `POSTGRES_*`) flow from script → compose → containers.
- **Mock/live duality:** A `ModelFactory` returns either a real `ChatOllama` connection or a custom `MockChatModel` (subclass of LangChain's `BaseChatModel` with overridden `_generate`), so the pipeline can be exercised without GPU/model weights.
- **RAG pipeline:** At container startup, an idempotent ingestion function embeds hardcoded corporate-policy documents (via `nomic-embed-text`, 768-dim) into pgvector. At request time, `similarity_search(query, k=2)` retrieves top-k chunks which are injected into the prompt as `{context}`.
- **Dotnet layer:** ASP.NET Core with a custom telemetry middleware (extension-method registration pattern), controllers, YARP referenced for future reverse-proxying. Multi-stage dockerfile (SDK build stage → slim ASP.NET runtime stage).

## 2. Current state (what demonstrably works as of this capture)

- `./build.sh --mode live` brings up all 4 containers cleanly; pgvector reports healthy via `pg_isready` healthcheck; langchain_service waits on it via `depends_on: condition: service_healthy`.
- **`POST /test/langchain/chatnosecurity`** (Flask, :5001) — returns a real llama3.1:8b completion end-to-end (verified: model told a bacon joke). Model is auto-pulled into Ollama on first request via a hand-written pull-management layer that checks `/api/tags` and calls `/api/pull`.
- **`POST /test/langchain/chatnosecurityrag`** — full RAG flow: embed query → pgvector similarity search → top-k chunks joined into `{context}` → prompt → LLM → response. (Git: "Successfully implemented RAG for user message.")
- Vector ingestion at startup is idempotent-gated and mock-aware (skips embedding when `LLM_MODE=mock`).
- Docs pipeline: 5 AI_Suggestions docs, code reviews, concept lectures, skill-gap archives — the meta-system of AI-as-mentor is functioning.

### Known issues / not yet working
- The plain `chatnosecurity` worker currently uses the **RAG prompt** (which declares `{context}`) but invokes with only `user_message` → LangChain missing-variable error. One-line fix identified (use the non-RAG prompt).
- The langgraph endpoints (`/test/langgraph/chatnosecurity`) are stubbed inside a commented-out block — **LangGraph path is the next build target**. `build_graph.py` exists but references `policy_check_node`, `agent_node`, `respond_node` that are not yet written (only `retrieve_node` exists), and lacks imports.
- Mock mode not yet re-verified end-to-end after the live-mode fixes; `MockChatModel` returns a single hardcoded string (persona-specific mock response lists exist in `MyPromptTemplates.py` but aren't wired in).
- Old/aspirational code (`ProcessNormalChatMessageRequest`) intentionally quarantined in comments — contains the future design: policy check → RAG → tool loop → history injection.
- Tech-debt flags: Python 3.9/slim-buster base image (EOL), unpinned requirements, Flask dev server + `debug=True` in container (Werkzeug debugger exposed — a security no-no worth an interview mention as "what I'd fix for production"), dead `documentToSearchAgainst` param converted to defaulted placeholder pending metadata-filter implementation.

## 3. The debugging war stories (interview gold — STAR-ready)

This week produced a dense debugging arc: first-ever live boot → crash → systematic diagnosis → working RAG. Each story below is true, recent, and demonstrates a named competency.

**Story A — The streaming NDJSON crash (API contract discipline).**
First live boot: langchain container exited(1) in seconds. Root cause chain: the Ollama `/api/pull` payload used key `"streaming": false` instead of the correct `"stream": false`. Ollama ignored the unknown key and streamed NDJSON (many newline-separated JSON objects); `response.json()` expected one JSON document and threw `JSONDecodeError`, uncaught, killing the process at startup. **Lesson articulated:** validate payloads against the API's actual contract, not memory; a silently-ignored request field is worse than a rejected one. Bonus depth: recognized that the pull had actually *completed server-side* (the client read the whole stream before choking), predicted the model would already be in the volume — confirmed via `ollama list`, which changed the next crash site. That prediction-then-confirmation loop is senior-engineer debugging behavior.

**Story B — Lost logs, lost evidence (observability habit formation).**
The first crash's logs were destroyed because `docker compose down` removes containers *and their logs* — teardown ran before anyone read them. Diagnosis had to proceed by static code-path tracing instead. **Lesson:** logs are evidence; capture before teardown (`docker logs <container>` first, `down` second). Directly motivates the project's telemetry middleware concept: systems should externalize their evidence.

**Story C — API drift between library versions (`PGVector` kwargs).**
`PGVector(embedding=..., connection_string=...)` — the argument names from the deprecated `langchain_community` implementation, which most online tutorials still show — vs. the current `langchain_postgres` signature `(embeddings=..., connection=...)`. TypeError at startup. **Lesson:** in fast-moving ecosystems (LangChain especially), the installed package's source is the only truth; used `inspect.signature` inside the container to verify. Strong talking point on dependency hygiene and why unpinned requirements make builds time-bombs.

**Story D — The function that returned None (language-boundary insight).**
`IntializeFlaskEndpoints()` registered all routes but never `return app`; Python silently returns `None`, producing `AttributeError: 'NoneType' object has no attribute 'run'` at boot. **Lesson articulated by Timothy's C#/C background:** a compiled language would reject a non-void function falling off the end; Python needs type annotations + a checker (mypy) to catch the same class of bug. Good story for "tell me about a bug that changed how you write code" — answer: adopting return-type annotations.

**Story E — Compose interpolation and the literal-string password.**
Three `${VAR:-default}` interpolations were written as `{VAR:-default}` (missing `$`), so Postgres was configured with the *literal string* `{POSTGRES_PASSWORD:-secret_pass}` as its password and a database literally named `{POSTGRES_DB:-secret_pass}`. Also `gen_rendom_uuid()` typo in init.sql crashed the DB container on first init — with the subtlety that init scripts only run on an **empty volume**, so the fix required `docker volume rm` to take effect. **Lesson:** infrastructure-as-code fails silently into weird states; `docker compose config` (render the resolved file) is the compile step for YAML.

**Story F — Crossed prompts and silent variable swallowing.**
Two workers had their prompts swapped: the RAG worker used the non-RAG prompt, so LangChain *silently ignored* the retrieved `{context}` — the system "worked" while retrieval had zero effect on output. Detection method: ask a question only the ingested policy docs can answer and check whether the answer echoes them. **Lesson:** silent successes are more dangerous than loud failures; behavioral verification beats status-code verification. Seeds the project's future LLM-judge/evaluation component.

## 4. Design difficulties being wrestled with (honest, current)

1. **Where does mock-awareness live?** Currently `LLM_MODE` checks are scattered (factory, ingestion, instructions). Tension between "mock is a special case checked everywhere" vs. "mock objects satisfy the same contract so downstream code never knows" (dependency inversion). Trending toward the latter — e.g., mock retrieval returning `[]` so the chain flows unchanged.
2. **Module-level side effects vs. explicit initialization.** Original ingestion built DB connections at import time; refactored to an `InitVectorStore()` function after it caused startup fragility. Open question: proper lifecycle management (app factory pattern, DI-style wiring) in Flask vs. what ASP.NET Core gives for free with its DI container — Timothy can compare both because he's building both.
3. **Model lifecycle & the singleton question.** Instantiating a `ChatOllama` per request vs. per-container-lifetime; per-model registry (multiton) sketched but deliberately not adopted yet ("creating a ChatOllama object is not heavy" — knows to measure before optimizing).
4. **Document→collection mapping for RAG.** No design yet for which documents get ingested, how they're identified for idempotency, or how retrieval scopes to a document subset (metadata filtering identified as the mechanism). Currently hardcoded docs.
5. **Where should policy enforcement sit?** The "nosecurity" endpoints exist precisely to defer this. Planned: LangGraph conditional edge (`policy_check` → blocked/ok routing) — the graph skeleton encoding this decision already exists.
6. **Prompt/variable contracts.** LangChain's implicit prompt variables (`{context}`) vs. C#'s explicit DTOs; the crossed-prompt bug came directly from this. Thinking about how to make prompt inputs type-checked or at least validated.

## 5. Skills demonstrated (resume/interview mapping)

- **Containerization & orchestration:** multi-service compose, profiles, healthchecks, dependency conditions, named volumes, env-var layering script→compose→process, multi-stage dotnet builds. *(Microsoft relevance: Azure-adjacent infra literacy.)*
- **Polyglot service design:** C#/ASP.NET Core middleware + controllers alongside Python/Flask; can articulate Kestrel vs. Flask/Werkzeug differences, DI vs. manual wiring.
- **AI engineering:** embeddings, pgvector, similarity search, RAG prompt injection, custom `BaseChatModel` implementation, model-pull lifecycle management against Ollama's REST API, mock/live parity design. *(Microsoft relevance: Copilot-era product plumbing.)*
- **Systematic debugging:** log-first discipline (learned the hard way), static call-path tracing, predicting failure-site migration, verifying library signatures at runtime.
- **Engineering process:** append-only git history discipline, PR merged from a feature branch (`testing-startup`), documentation-driven learning loop with AI reviewer, deliberate quarantine of unfinished code.

## 6. Next milestones (as of this capture)

1. Fix the crossed prompt in the plain worker (1 line); re-verify both langchain endpoints live.
2. Re-verify **mock mode** end-to-end (`./build.sh --mode mock` + both endpoints) — the original goal of the July-5 work session, still unclosed.
3. Un-comment and implement `/test/langgraph/chatnosecurity`: write `agent_node`/`respond_node`, add imports to `build_graph.py`, minimal START→agent→respond→END graph; then grow toward the conditional policy-check edge.
4. Wire the persona-specific mock response lists into `MockChatModel` (currently returns one hardcoded string).
5. Metadata-filtered retrieval (`filter={"source": ...}`) to make `documentToSearchAgainst` real.
6. Longer arc: policy-check chain, chat history/memory, tool use, LLM-judge evaluation, telemetry through the dotnet middleware.

## 7. One-paragraph summary for reuse

*Timothy Grant is hand-building LLM_Monitor, a four-container AI orchestration platform (ASP.NET Core router/telemetry, Flask+LangChain orchestration, Ollama local LLM runtime, pgvector RAG store) with a mock/live dual-mode build system, as a deliberate learning vehicle for a Microsoft SWE role. As of 2026-07-09 the live path works end-to-end: one-command startup, automatic model pulling, and two working endpoints including full RAG (query embedding → pgvector top-k → context-injected generation from llama3.1:8b). The week's debugging arc (six root-caused failures spanning Docker interpolation, Postgres init lifecycle, streaming API contracts, LangChain API drift, and silent prompt-variable swallowing) is documented as interview-ready stories above. Next: mock-mode verification and the LangGraph policy-checking graph.*

--- END CAPTURE 001 ---
