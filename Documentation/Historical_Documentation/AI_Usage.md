2026_07_10_15_52-(AI_Usage)

# AI Usage: The Hand-Written Foundation and the Road Forward

This document serves two purposes:

1. **A provenance record.** It documents, in detail, everything Timothy Grant accomplished by hand before AI-assisted development began (commit `50a2757`, July 10, 2026: *"Everything up to this point was hand written (not AI developed)"*). This section is the source of truth for the README's "Built By Hand" section.
2. **A strategy.** A detailed recommendation for how to introduce AI development into this project in a way that *increases* learning velocity and portfolio credibility instead of destroying them.

---

# Part 1: What Was Accomplished By Hand

Everything below was designed, written, debugged, and shipped by Timothy between **June 24 and July 10, 2026** (133 commits on `main`). During this period, AI (Claude) was explicitly prohibited from writing or modifying any code. Its role was limited to producing documentation: code reviews, concept lectures, skill-gap analyses, and troubleshooting guides that Timothy then implemented himself.

## 1.1 System Architecture (Microservices, Docker)

A five-service microservice system, fully containerized and orchestrated via Docker Compose:

| Service | Technology | Role |
|---|---|---|
| `dotnet_server` | C# / ASP.NET Core | API gateway; routes user requests, hosts telemetry middleware |
| `langchain_service` | Python / Flask / LangChain | AI orchestration: prompts, models, RAG, agent logic |
| `pgvector-service` | Postgres 16 + pgvector | Vector database for semantic search |
| `ollama` | Ollama | Local LLM inference (live mode only) |
| `openwebui` | OpenWebUI | Chat frontend speaking the OpenAI API contract |

Architectural features implemented by hand:

- **Mock/live dual-mode design.** The entire system runs without GPU compute via a `LLM_MODE=mock` environment variable. Compose **profiles** (`["live"]`) gate the Ollama container so mock mode doesn't pay its startup cost. This was a deliberate design decision to enable development on hardware without inference capability.
- **Container health-checking.** `pgvector-service` has a `pg_isready` healthcheck, and `langchain_service` uses `depends_on: condition: service_healthy` — correct startup ordering, not sleep-based hacks.
- **Environment variable configuration with defaults** (`${LLM_MODE:-mock}`, `${POSTGRES_USER:-admin}`) flowing from `build.sh` → compose → containers.
- **Named volumes** for Ollama model cache, Postgres data, and OpenWebUI state, so expensive artifacts (multi-GB models) survive container teardown.
- **`build.sh` orchestration script**: bash argument parsing (`--mode`, `--gpu`, `--model`), `set -euo pipefail` fail-fast semantics, full teardown of orphaned containers, profile-aware rebuild, image pruning, and a hook for a GPU compose-file override.

## 1.2 The .NET Gateway

- ASP.NET Core Web API with attribute-routed controllers (`[ApiController]`, `[Route]`).
- **Custom middleware** (`TelemetryMiddleware`) implementing the `RequestDelegate` pipeline pattern, plus an **extension method** (`UseTelemetryMiddleware()`) following the framework's registration idiom.
- Dependency injection of `IHttpClientFactory` for outbound service-to-service HTTP calls.
- DTO classes for the incoming user contract and the outgoing langchain-service contract, with JSON serialization via `System.Text.Json`.
- An **xUnit test project** (`server.Tests`) wired into a solution file at the repo root.

## 1.3 The Python / LangChain Service

- **Flask API** exposing test chat endpoints and, critically, an **OpenAI-compatible API facade** (`/v1/models`, `/v1/chat/completions`) — reverse-engineered from the OpenAI contract so that OpenWebUI connects to the custom agent as if it were an OpenAI backend. OpenWebUI integration confirmed working July 9 (`cf5379c "Openwebui is working."`).
- **LCEL chains**: `prompt | model | StrOutputParser()` composition for both plain chat and RAG-augmented chat paths.
- **Model factory pattern** (`ModelFactory`): returns either a live `ChatOllama` connection or a **custom mock model** — `MockChatModel`, a hand-written subclass of LangChain's `BaseChatModel` implementing `_generate()` with `ChatGeneration`/`ChatResult` internals. This demonstrates understanding of LangChain's model abstraction beneath the convenience APIs, not just usage of it.
- **Dynamic Ollama model management** (`Instructions.py`): queries Ollama's `/api/tags` REST endpoint, handles the `:latest` tag-normalization edge case, POSTs to `/api/pull` with `stream: false` to block until download completes, caches known-pulled models in module-level sets, and degrades gracefully to the mock model on failure.
- **RAG pipeline with pgvector**: `PGVector` vector store initialization over a psycopg connection string, idempotent document ingestion at startup, and top-k `similarity_search` retrieval injected into prompt context.
- **Prompt engineering** (`PromptFactory`): a unified assistant prompt with optional RAG context slot; a **few-shot policy-violation checker** with a constrained output contract (`violated:`/`conformance:` prefix parsing); and an **LLM-as-judge prompt** for future evaluation work. Mock response fixtures organized per prompt type.
- **LangGraph agent (in progress)**: a typed `ChatState` (`TypedDict` with `Annotated[list, add_messages]` reducer), implemented nodes for policy checking (RAG-grounded), retrieval, and blocked-response handling, and a practice graph wiring **conditional edges** (policy verdict routes to END or to retrieval → agent → respond).

## 1.4 Data Layer

- Postgres 16 with the pgvector extension, initialized via a mounted `scripts/init.sql` (`CREATE EXTENSION IF NOT EXISTS vector`).
- Studied (visible in init.sql comments and lecture requests) the raw-SQL alternative: HNSW indexes, `VECTOR(768)` columns, cosine ops — deliberately learning what LangChain's `PGVector` abstracts away.

## 1.5 Engineering Process

- **CI pipeline**: GitHub Actions workflow running pytest on push/PR, with pip caching; a .NET test job drafted and consciously parked.
- **Git discipline**: 133 commits over 17 days, feature branch + pull-request merge (`testing-startup` → PR #1), no history rewriting, and a clean, git-verifiable boundary commit marking the end of the hand-written era.
- **A self-built AI mentorship system**: the `CLAUDE.md` contract restricting AI to documentation-only, plus 40+ generated documents across code reviews, concept lectures, skill-gap tracking, and troubleshooting guides — every fix in those guides was implemented by hand.
- **Working-notes habit**: `timeline_implementation_notes.md` captures dated design deliberations (stateful vs. stateless chat, HTTP vs. gRPC, vector DB ownership questions) — evidence of thinking, not just typing.

## 1.6 Honest Current State (as of the boundary commit)

For integrity, the hand-written system also has known incomplete edges — worth acknowledging because it makes the provenance claim credible rather than inflated:

- `/v1/chat/completions` currently returns a hardcoded response; the agent pipeline is not yet wired behind it.
- `build_graph()` is mid-construction (the practice graph is complete; the real one is being assembled).
- A prompt refactor (functions → `PromptFactory`) landed in the final hand-written commits but `OrchestrationLogic.py` and `nodes.py` still import the old function names — an in-flight refactor.
- Test suites are placeholders (`assert True`) — infrastructure proven, coverage not yet written.

---

# Part 2: Strategy for Moving Forward with AI

## 2.1 The Core Reframe

The fear is: *"If AI writes code, hiring managers will discount everything."* That fear is based on a binary model — either you wrote it or AI did — and that binary is not how strong engineering organizations think in 2026. Microsoft ships Copilot; they don't want engineers who avoid AI, and they don't want engineers who paste whatever AI emits. They want engineers who can **direct, review, and own** AI-produced work — the same skills as a senior engineer directing junior engineers.

So the goal is not "hide the AI" or "hand-write forever." The goal is to make this project demonstrate **three distinct competencies, in sequence**:

1. **Phase 1 (done): I can build it myself.** The hand-written foundation proves baseline competence.
2. **Phase 2 (starting now): I can direct AI like a tech lead.** Specs, plans, reviews, and rejections — all visible in the repo.
3. **The meta-skill: I engineered the collaboration itself.** The CLAUDE.md contract, the documentation system, the provenance discipline — this project is *already* an AI-workflow-engineering artifact. That story is rare and valuable.

Done this way, AI usage doesn't invalidate Phase 1 — Phase 1 is what makes Phase 2 credible.

## 2.2 Protect the Provenance (do this first)

1. **Tag the boundary**: `git tag v1.0-handwritten 50a2757` and push the tag. An immutable, verifiable line: everything before this was hand-written.
2. **Branch separation**: continue AI-assisted work on `ai_dev`; merge to `main` via pull requests you review. The branch history itself becomes evidence of the workflow.
3. **Commit attribution convention**: adopt trailers so provenance is queryable forever:
   - `[hand]` — written entirely by Timothy
   - `[ai-assisted]` — AI drafted, Timothy reviewed/modified line-by-line
   - `[ai-generated]` — AI wrote it, Timothy reviewed and accepted
   Optionally add `Co-Authored-By: Claude` trailers on AI commits. A hiring manager who checks will find honesty — which upgrades trust in the `[hand]` commits too.
4. **README provenance section** (suggested structure):
   - *"Phase 1 — Hand-Written Foundation (June 24 – July 10, 2026)"*: summarize Part 1 of this document; link the `v1.0-handwritten` tag.
   - *"Phase 2 — AI-Accelerated Development (July 10, 2026 – )"*: state the workflow (spec → plan → implement → review), what AI builds, what remains hand-written, and link to this document.
   - Frame it as a deliberate methodology, not a confession.

## 2.3 The Tiered Ownership Model

Not all code is equal learning material. Divide every piece of future work into three tiers *before* starting it:

| Tier | What | Who writes it | Why |
|---|---|---|---|
| **Tier 1: Hand-written** | New concepts you're learning for interviews: LangGraph checkpointer/memory wiring, the eval harness scoring logic, SSE streaming internals, distributed trace propagation C#→Python | Timothy, with AI as tutor only (current CLAUDE.md rules) | These are exactly the topics you'll be interrogated on. Typing them is how they stick. |
| **Tier 2: AI-drafted, deeply reviewed** | Well-understood patterns applied at scale: additional endpoints repeating a pattern you've built once, refactors of code you wrote, real test suites for your code | AI drafts; Timothy reviews every line, requests changes, and must be able to re-derive it | You already proved you can write a Flask endpoint and a factory. Writing the fifth one by hand teaches nothing. |
| **Tier 3: AI-generated** | Boilerplate with near-zero learning value: Grafana dashboard JSON, docker-compose plumbing for a new observability container, CI YAML tweaks, DTO piles | AI writes; Timothy skims and accepts | Velocity. This is where the "bogged down in minutia" time was going. |

**The rule that keeps this honest — the Explain-Back Gate:** nothing merges to `main` unless you can explain every line to an imaginary interviewer. If you can't, either study it until you can (AI writes you a lecture in `concepts_documentation/`, as it always has) or reject the code. This single rule preserves the entire learning value of the project.

## 2.4 The Workflow (per feature)

You already built the folder for this: `AI_Implementation_Plans/`. Use it as designed.

1. **You write the spec** (interfaces, contracts, acceptance criteria — a few paragraphs). Design stays yours. This is also exactly what senior engineers do.
2. **AI writes an implementation plan** into `AI_Implementation_Plans/` (numbered per convention). You review and approve/modify it. *Reviewing plans is a system-design rep — you're now the reviewer instead of the reviewed.*
3. **AI implements on `ai_dev`** per the approved plan, in Tier-2/3 scope only.
4. **You review the diff as the senior engineer.** Leave real review comments; make AI revise. This inverts your old dynamic — until now the AI reviewed your code, now you review its code. That is *precisely* the skill Microsoft interviews for in an AI-native engineer.
5. **Explain-Back Gate**, then merge with the attribution trailer.
6. **Concept extraction**: anything you couldn't explain becomes a new lecture doc, keeping the `skill_gap_analysis` loop alive.

## 2.5 Applying the Tiers to the Existing Roadmap

Your roadmap (Documentation/AI_Suggestions/006 and persona.md) mapped to tiers:

| Roadmap item | Tier | Notes |
|---|---|---|
| Wire the real LangGraph agent behind `/v1/chat/completions` | **1** | The heart of the project. Hand-write the graph, nodes, and routing. AI reviews. |
| Postgres checkpointer / conversation memory | **1** | Core AI-engineering interview material (state, persistence, reducers). |
| Finish the in-flight PromptFactory refactor (fix stale imports) | **2** | You designed it; let AI complete mechanical renames, you review. |
| SSE streaming for OpenAI facade | **1 → 2** | Hand-write the first streaming endpoint (learn generators/chunked transfer); AI replicates the pattern elsewhere. |
| YARP gateway in the .NET server | **2** | You've done the middleware learning; YARP config is mostly plumbing. Study the concepts from the diff. |
| Real test suites (pytest + xUnit) | **2** | AI drafts tests for *your* code; reviewing tests teaches your own edge cases. Hand-write a few first so you can judge quality. |
| Langfuse + OTel + Prometheus + Grafana stack | **3 for plumbing, 1 for concepts** | AI does compose files and dashboard JSON. You hand-write the instrumentation calls and trace-propagation code — that's the interview story ("I traced a request across C# and Python services"). |
| Eval harness (golden dataset, hit@k/MRR, RAGAS, LLM-judge, CI gate) | **1 for scoring logic, 3 for harness scaffolding** | Metrics math and judge prompts by hand; runner/reporting boilerplate by AI. |

Velocity estimate: this roughly triples throughput while keeping ~100% of the interview-relevant learning, because the learning was never in the compose files and DTOs where the time was going.

## 2.6 The Interview Story This Produces

When a hiring manager asks "did AI build this?", the answer becomes a strength:

> "Phase 1 I wrote entirely by hand — there's a git tag proving it — because I wanted the fundamentals in my fingers. Then I deliberately transitioned to directing AI: I write specs, review implementation plans, gate every merge on being able to explain every line, and tag commit provenance. I got a 3x velocity increase and I can defend any file in this repo. Ask me about any of them."

That answer demonstrates: baseline competence, senior-style delegation and review, engineering judgment about *when* to use AI, process design, and honesty. No purely-hand-written portfolio project demonstrates all five.

## 2.7 Risks and Mitigations

- **Risk: Tier creep.** Tier-2 quietly becomes "AI writes everything." *Mitigation:* the tier is declared in the implementation plan doc before work starts; the Explain-Back Gate is non-negotiable.
- **Risk: Review theater.** Skimming diffs and approving. *Mitigation:* write at least one substantive review comment or requested change per AI PR. If you can't find one, you're not reading it.
- **Risk: Losing hand-coding fluency for interviews.** Coding rounds are still hand-written. *Mitigation:* Tier-1 work is regular hand-coding; supplement with LeetCode-style practice outside this project — that need existed regardless of AI.
- **Risk: The README oversells.** *Mitigation:* keep §1.6-style honesty. Credibility comes from the verifiable tag plus acknowledged rough edges, not from polish claims.

## 2.8 Immediate Next Actions

1. `git tag v1.0-handwritten 50a2757 && git push origin v1.0-handwritten`
2. Rewrite the README provenance section per §2.2 (hand-write this — it's your voice).
3. Update `CLAUDE.md` rules for the `ai_dev` era: encode the tier system, the plan-first workflow, and commit attribution so every future AI session follows it automatically.
4. First AI-directed feature: finish the PromptFactory refactor (Tier 2, small, mechanical) — a low-risk trial run of the full spec → plan → implement → review → explain-back loop.
5. Then take on the LangGraph agent wiring as your first big Phase-2 mixed-tier feature.
