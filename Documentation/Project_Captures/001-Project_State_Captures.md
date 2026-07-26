2026_07_24_10_00-Project_State_Captures

# Project State Captures — LLM_Monitor

> **Purpose of this file (read this first if you are an LLM agent):** This is an append-only log of state captures for Timothy Grant's `LLM_Monitor` project. Each capture is a **self-contained snapshot** — do not assume the reader has any other context about Timothy or this repo. Timothy pastes this file into other AI-assisted workflows (career/job-search planning, resume tailoring, interview prep, project ideation). **Treat every capture as raw material for:** (a) resume bullets, (b) behavioral interview stories (STAR format), (c) technical interview talking points, (d) gap analysis, (e) deciding what Timothy should build/study/practice next in service of his job search. New captures are appended below in chronological order; **never rewrite or delete old captures** — if something changed, say so in the new capture and let the diff speak.
>
> **Timothy's explicit goal: land a Software Engineer role at Microsoft (targeting SWE2-level).** Every recommendation you make from this document should be filtered through "does this help that goal."
>
> A prior, much shorter project-overview document (`Documentation/Historical_Documentation/001-Project_Overview_For_Resume_Agent.md`, written 2026-07-03) and an earlier capture log (`Documentation/Historical_Documentation/Project_Captures/001-Project_State_Captures.md`, first entry 2026-07-09) exist from very early in the project (day ~10, hand-written phase only, before RAG/LangGraph/observability/evals/Azure existed). They are archived, not deleted, and are still useful for "how did this start" narrative — but this file is the current source of truth for project state.

---

# CAPTURE 001 — 2026_07_24 — "AI-collaborative phase (plans 001–003) complete; full observability + eval stack; Azure OpenAI live; pre-release"

## 1. Structured metadata (quick-parse block)

```yaml
project_name: LLM_Monitor
owner: Timothy Grant
type: personal_learning_project
domain: [backend_engineering, ai_engineering, distributed_systems, observability, devops, mlops]
status: in_progress            # pre-release; feature-complete for a v1, not yet packaged/tagged
maturity: mid_to_late          # architecture fully realized end-to-end; hardening/release phase next
started: 2026-06-23
capture_date: 2026-07-24
elapsed: ~1 month
primary_languages: [Python, C#, SQL, Bash]
architecture_style: microservices (5-7 containers depending on profile), contract-first HTTP boundaries
repo_scale: ~209 commits on the active branch (ai_dev), ~164 on main
one_line: >
  A self-hosted LLM serving platform: a C#/.NET gateway routes traffic through telemetry
  middleware and YARP to a Python LangChain/LangGraph service, which runs four+ chat/RAG/
  agentic pipelines against Azure OpenAI (or local Ollama / free-tier OpenAI-compatible
  providers) with a pgvector RAG store, an MCP tool-calling loop, full four-pillar
  observability (logs/traces/metrics/LLM-traces), and a CI-gated eval harness.
learning_goal: >
  Build the backend, distributed-systems, AI-integration, and operational-maturity skills
  required for a software engineering role at a large technology company — explicit target:
  Microsoft, Software Engineer 2 level.
```

## 2. One-paragraph description (reusable verbatim)

LLM_Monitor is a self-hosted LLM serving platform built by Timothy Grant as a deliberate, disciplined learning vehicle for a Microsoft SWE2 application. A C#/.NET gateway (custom telemetry middleware + YARP reverse proxy) fronts a Python/Flask service that owns a **pipeline registry** of seven LLM workflows — plain chat, RAG, a LangGraph agent loop with MCP tool-calling, and a "premium" tier combining a policy gate, RAG, and tools — running against **Azure OpenAI** in live mode (with free-tier OpenAI-compatible and local-Ollama fallbacks) and pgvector for retrieval. OpenWebUI sits on top as the chat frontend via an OpenAI-compatible API Timothy implemented himself. The project has **full four-pillar observability** (structured logs with trace-id correlation, OpenTelemetry distributed tracing to Jaeger across the C#→Python boundary, Prometheus/Grafana RED+token metrics, and Langfuse LLM-trace capture) and a **CI-gated eval harness** (retrieval hit@k/MRR + LLM-as-judge, self-arming regression gate). It was built in two deliberate phases — 100% hand-written scaffolding first, then a staged, reviewed, AI-collaborative process for everything since — with every design discussion, decision, and step-by-step implementation log preserved in-repo (`Documentation/AI_Implementation_Plans/`).

## 3. Architecture (current, verified against repo 2026-07-24)

Request flow: `OpenWebUI → dotnet gateway (telemetry middleware → YARP) → langchain_service (Flask, pipeline registry) → Ollama / Azure OpenAI / OpenAI-compat provider + pgvector`

```
                                   ┌───────────────────────────────┐
 user ──▶ OpenWebUI (:3000) ──▶   │  dotnet_server (gateway,:5000) │
          OpenAI-compatible API   │  TelemetryMiddleware → YARP    │
                                   └───────────────┬────────────────┘
                                                    │ forwards + injects traceparent
                                                    ▼
                                   ┌────────────────────────────────────┐
                                   │  langchain_service (Flask, :5001)  │
                                   │  pipeline REGISTRY (7 pipelines)   │
                                   └───┬────────┬────────┬─────────────┘
                                       │        │        │
                          RAG retrieval│        │tool loop│ model calls
                                       ▼        ▼        ▼
                              pgvector-service   toolbox (MCP,    Azure OpenAI /
                              (Postgres+pgvector) internal-only)   Ollama / openai_compat
                                                                    (profile/env gated)

  obs profile (optional, --obs flag): otel-collector → Jaeger (traces)
                                       Prometheus → Grafana (RED + token metrics)
                                       Langfuse (web+worker+pg+clickhouse+redis+minio) (LLM traces)
```

**Service inventory:**

| Service | Tech | Responsibility | Profile |
|---|---|---|---|
| `dotnet_server` | C# / ASP.NET Core, YARP | Edge gateway: custom telemetry middleware (method/path/status/latency + trace_id), reverse-proxies to langchain_service; OpenAI-compat surface proxy | always on |
| `langchain_service` | Python / Flask (gunicorn) / LangChain / LangGraph | Owns the pipeline registry, model factory, RAG, MCP tool client, cost guards, eval harness | always on |
| `pgvector-service` | PostgreSQL + pgvector | Vector store for RAG; idempotent (content-hash) ingestion — never re-embeds unchanged docs | always on |
| `toolbox` | separate repo (`Tool_Box`), MCP over streamable HTTP | Exposes callable tools to the agent loop; internal-only (no host ports), healthcheck-gated | always on (not profile-gated — tools are free in both mock/live) |
| `openwebui` | OpenWebUI | Chat frontend, enters through the gateway so every chat is telemetered | always on |
| `ollama` | Ollama | Local model serving (kept for the "hardware returns" day) | `local-live` only |
| `otel-collector`, `jaeger` | OpenTelemetry Collector, Jaeger | Distributed tracing sink/UI | `obs` only |
| `prometheus`, `grafana` | Prometheus, Grafana | Metrics scrape + dashboards (anonymous admin — local-only, explicitly documented as unsafe outside localhost) | `obs` only |
| `langfuse-web/worker` + `langfuse-postgres` + `clickhouse` + `langfuse-redis` + `minio` | Langfuse v3 self-hosted | Full LLM observability: rendered prompts, retrieved chunks, per-node traces | `obs` only |

**Build orchestration:** `./build.sh --mode mock|live [--gpu] [--obs]`. Mock mode (default dev posture, $0, no external calls) exists because Timothy's current machine cannot run GPU-class local inference — the entire pipeline (registry, RAG, contracts, tool loop) runs identically in mock and live; only the model/embedding provider is swapped via a factory. Startup is healthcheck-ordered (pgvector → langchain_service → toolbox → gateway → OpenWebUI), never sleep-based.

### 3a. Pipeline registry (the system's core abstraction — `CONTRACTS.md` §4)

| Pipeline id | Engine | RAG | Tools | Cost tier | Notes |
|---|---|---|---|---|---|
| `chat-basic` | LangChain chain | no | no | — | Prompt → model → parser |
| `chat-rag` | LangChain chain | yes | no | — | Retrieval context injected into prompt |
| `graph-basic` | LangGraph | no | no | — | Compiled graph, retrieve node omitted at build time (not skipped at runtime — genuinely absent from the topology) |
| `graph-rag` | LangGraph | yes | no | — | Graph path with retrieve node |
| `graph-tools` | LangGraph | no | MCP | **lean** | Agent ⇄ toolbox conditional loop (`tools_condition` inspects the last AIMessage for tool_calls) |
| `graph-premium` | LangGraph | yes | MCP | **premium** | policy gate → retrieve → agent⇄tools → respond; sampled async LLM-judge runs *after* the response, off the request's clock |
| `graph-free` | LangGraph | no | MCP | **free** | Same topology as `graph-tools`, bound to a free `openai_compat` endpoint (Groq et al.) at graph-build time — same graph, different model economics |

Registering a pipeline is the **only** thing needed to expose it: `/v1/models` is generated from the registry dict, so a new entry becomes a new OpenWebUI-selectable model with zero route changes. Every pipeline is auto-instrumented at registration (a `pipeline.dispatch` OpenTelemetry span + Prometheus counters wrap every handler) — pipeline authors never write telemetry code themselves.

**Cost-tier contract (CONTRACTS.md §4a, a real engineering constraint, not aspirational docs):** lean/free tiers may contain **zero** LLM calls beyond the agent loop itself — no policy gates, judges, or rerankers — enforced by convention + a recursion cap (`TOOL_RECURSION_LIMIT`, default 8) and output cap (`LLM_MAX_TOKENS`, default 1024) applied at model construction. Premium tier gets exactly one policy-gate call ahead of the loop plus a *sampled* (`JUDGE_SAMPLE_RATE`, default 0.1), async, post-response judge call. CI never spends live tokens (`LLM_MODE=mock` always). This exists because Timothy lost local GPU access mid-project and live mode now means *paying per token* — the tier contract is the direct engineering response to that constraint.

## 4. Technology stack (for skill-tagging)

```yaml
languages: [Python, C#, SQL, Bash]
backend_frameworks: [ASP.NET Core, YARP, Flask, gunicorn]
ai_frameworks: [LangChain, LangGraph, langchain-mcp-adapters, Ollama]
model_providers: [Azure OpenAI (chat + embeddings), OpenAI-compatible free tiers (Groq-class), Ollama (local)]
ai_concepts: [RAG, embeddings, pgvector similarity search, agentic tool-calling (MCP), conditional
              graph routing, structured/parseable LLM output, prompt-role contracts, LLM-as-judge
              evaluation, retrieval eval (hit@k/MRR), cost-tiered model routing, prompt-injection-
              style test hooks]
data: [PostgreSQL, pgvector, idempotent content-hash ingestion]
infrastructure: [Docker, docker-compose profiles, healthchecks, service_discovery, multi-stage builds]
observability: [OpenTelemetry (traces), Prometheus + Grafana (metrics), Jaeger, Langfuse v3
                (self-hosted, LLM-trace capture), structured logging w/ trace_id correlation]
patterns: [microservices, API gateway (YARP), registry pattern, factory pattern, mock/live seam,
           contract-first API design, dependency injection, idempotent initialization,
           conditional-edge state machines (LangGraph)]
testing: [pytest (Python: contract/registry/factory/ingestion/cost-guard/eval tests), xUnit (C#),
          bash-scripted end-to-end acceptance checks, honest CI (installs real deps, runs real tests)]
cloud_alignment: [Azure_OpenAI (IN USE, not aspirational), AKS/Azure_Container_Apps + Key_Vault +
                  managed_identity + GitHub_Actions_CD (planned, not yet built)]
```

## 5. Engineering decisions worth citing verbatim in an interview

- **Contract-first API design.** Every HTTP boundary is defined in `CONTRACTS.md` before implementation; snake_case wire format everywhere; changes must be additive within a version; C# maps PascalCase→wire via `JsonNamingPolicy` rather than hand-renaming fields.
- **Production lockdown is a config change, not a code change.** langchain_service is directly reachable on :5001 for dev/test; deleting that one port mapping in compose is the entire lockdown procedure.
- **Startup ordering via health checks, never sleeps.** langchain_service's healthcheck is stdlib Python (the slim base image ships neither curl nor wget); its `start_period` budgets for one-time RAG ingestion.
- **Honest CI (a real discovery, strong interview story).** The original GitHub Actions workflow "passed" by looking for `requirements.txt` at the repo root (found nothing), installing nothing, and running a test that imported no application code — a green build meaning nothing. Timothy found and root-caused this, then rebuilt the workflow so it installs real deps from `langchain_service/` and runs the real pytest suite, plus a separate C# build+test job.
- **Instrumentation attaches at the registry boundary, not per-pipeline.** Every pipeline handler is wrapped in a `pipeline.dispatch` span and metrics counters at *registration* time (`app/orchestration/registry.py`) — new pipelines get tracing for free; no author ever writes telemetry code.
- **Mock/live is a provider-swap seam, not an if/else scattered through business logic.** `ModelFactory.get_chat_model` / `get_embedding_model` centralize mode+provider resolution (mock / azure / openai_compat / ollama); `MockChatModel` implements a genuine deterministic protocol (a `"TOOLCALL <tool> <json>"` trigger and prompt-aware routing by inspecting the system message) so the *entire* tool loop, policy gate, and judge are testable without spending a token.
- **Fail loud, not silent, on config.** `_require_env` in `factory.py` treats compose's `${VAR:-}`-interpolated empty strings as missing (not just unset), because an empty string passes a naive `KeyError` check but is useless as config — this is a direct lesson from an earlier bug class (see §7, Story E).
- **Graph topology encodes decisions at compile time, not request time.** `build_graph(with_rag=True/False)` compiles a *different* graph shape rather than a runtime `if rag: ...` inside one graph — "the compiled graph only contains the steps it actually runs."
- **Judges/policy gates are contract-tiered, and judges never sit on the user's clock.** The sampled LLM-judge in `graph-premium` runs *after* the response is returned, on a background thread — "in the graph would mean on the clock," so it's deliberately kept out of the graph.
- **Idempotent RAG ingestion.** Documents are content-hashed; only new/changed documents get (re-)embedded, so restarting the stack never silently re-vectorizes everything.

## 6. Skills demonstrated (resume/interview mapping, honest)

**Backend & distributed systems**
- Multi-service HTTP architecture: gateway + orchestrator + data plane, mirroring commercial LLM-application shape.
- ASP.NET Core: custom middleware pipeline (extension-method registration), YARP reverse proxy configured as a real forwarder (not a stub), ASP.NET DI.
- Docker Compose at real complexity: 5 profiles (default/live/local-live/obs + gpu override), healthchecks, `depends_on: condition: service_healthy`, private bridge networking, named volumes, multi-stage builds.
- Contract-first, versioned HTTP API design across a language boundary (C# ⇄ Python), with an explicit error-code contract and additive-only versioning discipline.

**AI / LLM engineering**
- Built and shipped a **pipeline registry** — the central "adding a capability = one dict entry" abstraction — across 7 distinct chat/RAG/agentic workflows.
- LangGraph state machines with **conditional edges** decided by model output (`tools_condition`) and by application logic (policy gate) — not just linear chains.
- Real MCP tool-calling integration (`langchain-mcp-adapters`) against a separate self-built tool server, with startup-time tool discovery and an async/sync execution boundary solved deliberately.
- Provider abstraction over Azure OpenAI / OpenAI-compatible free tiers / local Ollama via the OpenAI chat-completions protocol as a lowest-common-denominator — "switching providers is a config change."
- Cost-engineering discipline for a paid API: per-tier LLM-call budgeting written into the API contract itself, recursion/token caps enforced at construction, sampled+async judging.
- Full eval harness: golden-dataset retrieval eval (hit@k/MRR) and LLM-as-judge faithfulness scoring, with a **self-arming CI regression gate** (ungated until a baseline is committed, then enforced at zero tolerance).
- pgvector RAG with idempotent content-hash ingestion and a mock-embeddings seam (`DeterministicFakeEmbedding`) for fully offline, deterministic testing.

**Observability (the project's operational-maturity thesis)**
- Four-pillar setup, wired for real: structured logs carrying `trace_id` → OpenTelemetry distributed traces spanning the C#→Python boundary in Jaeger → Prometheus/Grafana RED + token metrics per pipeline → Langfuse rendered prompt/retrieved-chunk capture. One request is traceable through all four.
- Registry-boundary auto-instrumentation pattern (see §5) — a reusable architectural idea, not just "we added some logging."

**Software engineering process & discipline**
- Directed a staged, reviewable AI-collaborative development process (design doc → discussion → AI-authored implementation plan → step-by-step permissioned implementation → verification), with the full back-and-forth preserved in git and in `Documentation/AI_Implementation_Plans/`.
- Found and fixed a CI pipeline that was "green" while testing nothing — a concrete, provable process-quality story.
- Deliberate quarantine discipline: superseded code moved to `old_implementations/`, never silently deleted, so history stays legible.
- Skill-gap self-tracking over time (`Documentation/skill_gap_analysis/`, 8 snapshots so far) — evidence of a structured self-improvement loop, not just shipping features.

## 7. The development process itself (a differentiator worth explaining in interviews)

Built in two deliberate phases:

1. **Phase 1 — 100% hand-written (2026-06-23 → 2026-07-09/10).** Every line — Docker system, C# gateway, Flask/LangChain service — written personally, AI used *only* as a code reviewer and lecture-writer, specifically so Timothy understood every piece before any AI touched code. Produced a dense, real debugging arc (see war stories below).
2. **Phase 2 — AI-collaborative, with review gates (2026-07-10 → present).** For larger features, a 5-stage process: (1) Timothy writes design goals, (2) dynamic discussion with the AI on architecture/tradeoffs, (3) AI produces a step-by-step implementation plan which Timothy reviews and negotiates, (4) AI implements one step at a time with explicit per-step permission, narrating what changed and what broke, (5) verification. Three plans completed this way so far:
   - **001 — Initial Project Cleanup:** pipeline registry, LangGraph completion, real YARP proxy, Flask API rebuilt on the registry, honest CI, live-mode verification.
   - **002 — Metrics and Observability:** the full four-pillar stack (steps 1–9: infra skeleton → gateway instrumentation → langchain_service tracing → metrics/Grafana → Langfuse → golden dataset → retrieval eval → judge eval → CI wiring/self-arming gate).
   - **003 — ToolBox Integration and Hosted LLM Migration:** MCP tool integration (`graph-tools`), the Azure OpenAI / provider-abstraction migration forced by losing local GPU access, cost-tier contract, `graph-premium` (policy+RAG+tools+sampled judge), `graph-free` (free-tier routing).

Every plan document contains the *actual negotiation* — Timothy pushing back, the AI presenting tradeoffs and open decisions explicitly rather than silently picking one, and a running Stage-2 discussion log. This is itself interview material: "tell me about directing AI tools in your workflow" has a real, specific, three-plan-deep answer here, not a generic one.

## 8. Debugging war stories (STAR-ready, spanning both phases)

**From Phase 1 (hand-written, full detail in the historical capture, summarized here):**
- **Streaming NDJSON crash:** an Ollama pull payload used `"streaming": false` instead of `"stream": false`; the unknown key was silently ignored, Ollama streamed NDJSON, `response.json()` choked on multi-document input and crashed the container at startup. Lesson: validate against the API's actual contract, not memory.
- **Lost logs, lost evidence:** `docker compose down` destroys container logs; the first crash's evidence was gone before it could be read. Lesson: capture before teardown — this directly motivated the project's telemetry-first design.
- **API drift across LangChain versions:** `PGVector(embedding=..., connection_string=...)` (deprecated `langchain_community` signature, still shown in most tutorials) vs. the actual installed `langchain_postgres` signature `(embeddings=..., connection=...)`. Verified via `inspect.signature` inside the running container. Strong talking point on dependency hygiene in fast-moving ecosystems.
- **Compose interpolation typo:** `{VAR:-default}` (missing `$`) meant Postgres was configured with the *literal string* `{POSTGRES_PASSWORD:-secret_pass}` as its password. Lesson: `docker compose config` is the "compile step" for YAML — always render before trusting it.
- **Crossed prompts, silent variable swallowing:** the RAG worker used the non-RAG prompt, so LangChain silently ignored the retrieved `{context}` — the system "worked" while retrieval had zero effect on output. Detected by asking a question only the ingested docs could answer. Lesson: silent successes are more dangerous than loud failures; behavioral verification beats status-code verification. This is the direct ancestor of the project's later eval harness.

**From Phase 2 (AI-collaborative, newly surfaced):**
- **The CI that tested nothing:** documented above in §5/§6 — arguably the single strongest "quality/process" story in the whole project, because it's provable from the diff (`ci.yml` before/after) and shows Timothy auditing generated/inherited infrastructure rather than trusting a green checkmark.
- **Missing `langfuse` extra pulling in a version-incompatible `langchain` package** (`Documentation/AI_Suggestions/001`): adding Langfuse's `CallbackHandler` required a `langchain` dependency whose version had to be compatible with the already-pinned `langchain-core`/`langgraph`; the fix required understanding the dependency's own version-branch check (`langchain.__version__.startswith("1")`) rather than just installing latest. Also surfaced a secondary, non-blocking observation: Langfuse's internal housekeeping queues (retention/PostHog/Slack integrations) log chatty Redis timeout errors that are cosmetic, distinguished from an actual ingestion-path problem by checking *which* queue is erroring — a diagnostic habit (don't treat all red log lines as equally severe) worth narrating.
- **Async/sync boundary in the tool loop (plan 003):** `client.get_tools()` (MCP discovery) is async while the rest of the Flask layer is sync; tool *execution* inside `ToolNode` is also async under the hood. Resolved by wrapping discovery in `asyncio.run(...)` once at module import time, alongside the existing compiled-graph-at-import pattern — an explicit, planned-for architectural decision rather than a reactive patch.

## 9. Design difficulties actively being wrestled with (honest, current)

1. **Where does "mock-awareness" live?** Ongoing tension between mock as a special case checked in many places vs. mock objects satisfying the same interface so downstream code is oblivious (dependency inversion) — trending toward the latter (e.g., `MockChatModel.bind_tools` as accept-and-ignore, prompt-aware deterministic routing).
2. **Model/graph lifecycle.** Graphs are compiled once at import time and shared; per-request state flows through `thread_id`/checkpointer (checkpointer parameter already threaded through `build_graph`, not yet wired to persistent memory).
3. **Conversation memory is designed but not built.** `thread_id` is reserved in the contract; LangGraph checkpointing is roadmap, not implemented.
4. **Streaming is designed but not built.** The OpenAI-compatible surface explicitly does not yet support `stream: true` — a known, documented gap, not an oversight.
5. **Auth/rate-limiting is a known gap.** The gateway's YARP forwarder has no auth or rate-limiting middleware yet; documented as "future middleware in front of the same forwarder."
6. **Release/deployment story is undecided.** No Azure infrastructure deployment exists yet — everything runs via `docker-compose` on a developer machine. A Release Plan (`Documentation/AI_Implementation_Plans/004-Release-1.0.md`) was drafted 2026-07-23 specifically to resolve scope: ship as a polished self-hosted docker-compose release first, vs. build the full Azure (AKS/Container Apps + Key Vault + managed identity + GitHub Actions CD) deployment as a separate, later plan. **Undecided as of this capture — flag this as an open, live decision if asked about deployment.**

## 10. Current status (accurate as of 2026-07-24)

```yaml
completed:
  - Full microservice architecture: gateway (C#/YARP) + orchestrator (Flask) + pgvector + toolbox + OpenWebUI
  - Pipeline registry with 7 registered pipelines (chat-basic/rag, graph-basic/rag/tools/premium/free)
  - Contract-first API (CONTRACTS.md v1), snake_case wire convention, OpenAI-compatible surface
  - Mock/live dual mode with a real provider factory (mock, Azure OpenAI, openai_compat, Ollama)
  - MCP tool-calling loop (langchain-mcp-adapters) against a self-built external toolbox
  - Cost-tier contract (lean/premium/free) with enforced recursion + token caps
  - Idempotent, content-hashed pgvector RAG ingestion
  - Full four-pillar observability stack (logs+trace_id, OpenTelemetry/Jaeger, Prometheus/Grafana, Langfuse v3)
  - Eval harness: retrieval hit@k/MRR + LLM-as-judge, wired into CI with a self-arming regression gate
  - Honest CI: real pytest suite (11 test files) + real xUnit build/test, both installing real dependencies
  - Staged AI-collaborative development process, 3 plans complete (001, 002, 003), fully documented
in_progress:
  - Release Plan (004) — Stage 1 draft outline exists; scope decision (self-hosted package vs. Azure
    infra deployment) not yet finalized
  - ai_dev branch not yet merged to main (main still reflects pre-plan-002/003 state, tag v1.0-handwritten)
not_started:
  - Streaming responses on the OpenAI-compatible surface
  - Auth / rate-limiting middleware at the gateway
  - LangGraph checkpointed conversation memory (thread_id reserved, not wired)
  - Azure infrastructure deployment (AKS/ACA, Key Vault, managed identity, GitHub Actions CD)
honest_note: >
  This is no longer an early-stage scaffold — the AI-orchestration architecture, observability
  stack, and eval harness are real and working, verified against Azure OpenAI in live mode, not
  just mock mode. What remains before a true "v1 release" is packaging/deployment decisions and
  the roadmap items above (streaming, auth, memory) — those are honestly incomplete, not overstated.
```

## 11. Strategic / career context (why this project exists, and current framing)

```yaml
target_role: Microsoft Software Engineer, level SWE2
resume_gap_found: >
  A resume/JD-alignment review found "zero Azure" as the single biggest screener risk (existing
  resume showed AWS RDS/EC2, no Azure anywhere). This directly motivated migrating the "live" LLM
  provider to Azure OpenAI (plan 003) rather than, e.g., staying on Ollama-only or picking a
  non-Microsoft cloud provider — a deliberate, resume-aware technical decision, not an accident.
budget_posture: "cost sensitive, not zero-budget" — up to ~$40-50/month acceptable toward this goal.
target_JD_language_this_project_truthfully_covers: >
  "Azure development" (Azure OpenAI in active use), "AI-driven features: prompt design, tool
  calling, eval harnesses" (all three literally implemented), "data pipelines" (RAG ingestion).
constraint_that_shaped_architecture: >
  Timothy lost access to GPU-class local hardware mid-project (~mid-July 2026), forcing the
  Ollama -> hosted-API migration and the accompanying cost-tier contract. This is a good example
  of "engineering under a real constraint change," not a hypothetical exercise.
planned_next_infra_move: >
  A separate, later Implementation Plan (referred to informally as "004" in persona.md, but
  numerically conflicting with the Release Plan doc — unresolved as of this capture, see §9.6)
  to actually deploy the stack to Azure (AKS leaning, ACA fallback), with Key Vault, managed
  identity, and GitHub Actions CD.
presentation_plan: >
  Timothy makes YouTube videos and intends to record a walkthrough/demo of this project once
  released, linked from his resume. An outline for that video exists in the draft Release Plan
  (004-Release-1.0.md): cold-open live demo, architecture walkthrough, four-pipeline demo,
  observability tour, and the hand-written-vs-AI-collaborative process story.
```

## 12. Milestones (dated)

- 2026-06-23 — project start.
- 2026-07-02 — Docker system: build script, compose file, all core services spinning up with env injection.
- 2026-07-08 — full LangChain pipeline connected end to end (live Ollama chat + RAG).
- 2026-07-09/10 — hand-written phase declared complete; switched to the staged AI-collaborative process; OpenWebUI talking to the service through the gateway.
- 2026-07-11 — plan 001 merged (PR #2): pipeline registry, LangGraph completion, real YARP proxy, OpenAI-compatible surface, honest CI, idempotent ingestion.
- mid-July 2026 — plan 002: full observability stack + eval harness, step by step (infra → gateway instrumentation → service tracing → metrics/Grafana → Langfuse → golden dataset → retrieval eval → judge eval → CI gate).
- 2026-07-19 onward — plan 003: MCP toolbox integration + forced migration off local Ollama to Azure OpenAI, driven by losing GPU-class hardware access; cost-tier contract; `graph-premium`/`graph-free`.
- 2026-07-23 — Release Plan (004) Stage-1 outline drafted; CLAUDE.md updated with the Release-Plan documentation format.
- 2026-07-24 — this capture written.

## 13. Resume-agent usage hints

- **Best framed as:** a production-shaped AI-infrastructure project — API gateway + LLM orchestration service + RAG + agentic tool-calling + full observability + CI-gated evals — built with the same rigor as professional code review, on a real (not toy) polyglot stack.
- **Strongest talking points, ranked:** (1) the honest-CI discovery — provable, concrete, shows auditing instinct; (2) four-pillar observability with registry-boundary auto-instrumentation — architecturally reusable idea, not "added some logs"; (3) the cost-tier contract forced by a real hardware-access constraint — shows engineering judgment under real limits, not hypothetical ones; (4) the staged AI-collaborative process itself, with three fully-documented plans as evidence — directly answers "how do you use AI tools in your workflow" with specifics; (5) MCP tool-calling agent loop with a genuine conditional-edge state machine.
- **Avoid overstating:** no production/cloud deployment exists yet (docker-compose on a dev machine only); no streaming, auth, or persistent conversation memory yet — describe these as designed/roadmapped, not shipped.
- **Keywords for JD matching:** microservices, API gateway, YARP, ASP.NET Core, LangChain, LangGraph, agentic tool-calling, MCP, RAG, pgvector, Azure OpenAI, embeddings, OpenTelemetry, distributed tracing, Prometheus, Grafana, Langfuse, LLM-as-judge, eval harness, CI/CD, Docker, contract-first API design, cost-aware LLM routing.
- **Deeper evidence available on request** (do not dump these into a resume, but cite them if asked to substantiate a claim): `Documentation/AI_Implementation_Plans/` (001-003 full design+discussion+implementation logs, 004 draft release plan), `Documentation/concepts_documentation/` (21 lecture-style docs Timothy used to close knowledge gaps as they were found), `Documentation/skill_gap_analysis/` (8 dated self-assessment snapshots showing gap-closure over time), `CONTRACTS.md` (the API contract itself), `README.md` (current human-facing overview).

---
*This document is a summary/reuse artifact. No project source code is included or modified here. Append new captures below a new `# CAPTURE 00N — ...` heading; never edit this capture in place.*
