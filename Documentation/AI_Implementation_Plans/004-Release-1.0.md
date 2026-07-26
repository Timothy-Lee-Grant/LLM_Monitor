2026_07_23_23_45-Release-1.0

# Stage 1 (Design Documentation)

**Draft outline** (AI, drafted at Timothy's request — 23 July 2026)

Timothy asked for an outline of this project's first Release Plan, following the format introduced in this session's CLAUDE.md update (`## ImplementationPlans (Release Plan)`). This entry is the Stage 1 draft: a first pass at the three required sections — Release Checklist, Packaging Plan, Presentation — grounded in the project's actual current state, plus the open questions that need Timothy's decision before Stage 2 can resolve into a Stage 3 plan.

**Where the project actually stands right now** (verified against the repo, not memory):

- Branch `ai_dev` is ahead of `main`; `main` still reflects the Phase 1 hand-written system, tagged `v1.0-handwritten`. Everything since — pipeline registry, LangGraph, contract-first API, honest CI, and plan 003 (ToolBox + Azure OpenAI migration) — lives on `ai_dev` and has not been merged.
- Plan 003 looks functionally complete: `.env.example` already documents `LLM_PROVIDER=azure` as the default live provider, cost guards (`LLM_MAX_TOKENS`, `TOOL_RECURSION_LIMIT`, `JUDGE_SAMPLE_RATE`) are wired, and recent commits show Steps 5b–7 (routing, cost guards/observability, tests) implemented. This Release Plan assumes plan 003 is the last feature work before release, not a parallel track.
- CI (`.github/workflows/ci.yml`) runs the real pytest suite, the plumbing-tier retrieval eval (self-arming gate once a baseline is committed), and the judge-parsing eval — plus a separate C# build+test job. No baseline is committed yet, so the retrieval gate is currently running ungated.
- `docker-compose.yaml` profiles: default (mock), `local-live` (Ollama, kept for future hardware), `obs` (Jaeger/Prometheus/Grafana/Langfuse). There is no Azure-hosted deployment profile — everything today runs on a developer's machine via `build.sh`.
- Per `persona.md`, an Azure infrastructure deployment (AKS-leaning, ACA fallback, Key Vault, managed identity, GitHub Actions CD) is envisioned as a **later** plan (referred to there as "004"), separate from the Azure OpenAI *model* integration plan 003 already did. That means this Release Plan and that future infra plan will compete for the same "004" slot in this folder — see Decision 1 below.
- Roadmap items explicitly **not done**: streaming responses on the OpenAI-compatible surface, auth/rate-limiting middleware at the gateway, LangGraph checkpointed conversation memory, and the full (non-plumbing-tier) eval suite wired into CI.

## Release Checklist

### A. Correctness & test coverage
- [ ] `python -m pytest -v` green in `langchain_service` (contract, registry, model factory, idempotent ingestion tests)
- [ ] `dotnet test server.Tests/server.Tests.csproj` green
- [ ] `bash scripts/acceptance_check.sh mock` — full PASS
- [ ] `bash scripts/acceptance_check.sh live` — full PASS against **Groq free tier** (`LLM_PROVIDER=openai_compat`, `OPENAI_COMPAT_BASE_URL=https://api.groq.com/openai/v1`) — this is now this release's verified live path (see Stage 2, 2026_07_24 decision). Azure OpenAI's code path stays in the repo (already implemented and working per plan 003) but is explicitly **not** this release's verification target.
- [x] **Live-mode embeddings for `openai_compat` — implemented 2026_07_25.** `ModelFactory.get_embedding_model` now returns CPU-local embeddings (`fastembed`, model `BAAI/bge-base-en-v1.5`, 768-dim — matches the existing pgvector schema) instead of raising, when `LLM_PROVIDER=openai_compat`. See Stage 4 below for what changed and how it was verified. `chat-rag`/`graph-rag`/`graph-premium` are unblocked in live mode without any Azure account.
- [ ] `bash scripts/observability_check.sh` — PASS with `--obs`
- [ ] Commit a retrieval eval baseline (`eval/baselines/retrieval_plumbing.json`) so the CI gate is armed rather than running ungated

### B. CI/CD honesty
- [ ] CI runs on the branch that will actually ship (confirm `ai_dev` → `main` merge triggers the existing workflow's `main`/`dev` branch filters)
- [ ] No test, gate, or check silently no-ops the way the pre-plan-002 CI did — spot check each CI step actually exercises real code paths

### C. Documentation
- [ ] README's roadmap/milestones sections updated to reflect what shipped in this release (currently lists observability/evals as "in progress on ai_dev" — true once merged?)
- [ ] `CONTRACTS.md` matches the implemented API exactly (no drift between plan 003's routing changes and the documented contract)
- [ ] `observability/README.md` guided tour still walks correctly end to end
- [ ] This Release Plan's Stage 5 verification log filled in before tagging

### D. Security & secrets hygiene
- [ ] `.env` is gitignored and was never committed (`git log --all --full-history -- .env` should show nothing)
- [ ] No API keys or secrets appear anywhere in `docker-compose.yaml` or other tracked files
- [ ] Langfuse's anonymous-admin / no-login-wall config (`observability/`) is explicitly confirmed as local-only and either gated or documented as unsafe outside localhost before any public packaging
- [ ] Default Postgres credentials in `.env.example` (`admin`/`secret_pass`) are clearly marked as dev-only placeholders, not shippable defaults

### E. Deployment readiness
- [ ] Decide and document the release's deployment story (see Packaging Plan below) — local docker-compose only, vs. a real hosted deployment
- [ ] `build.sh --mode live` runs clean against Groq (`LLM_PROVIDER=openai_compat`) on a fresh clone (no leftover local state assumptions, no Azure account required to reach this release's live mode)
- [ ] Startup health-check ordering (pgvector → langchain_service → gateway → OpenWebUI) verified on a cold start, not just a warm re-run

### F. Observability
- [ ] One request traced end-to-end through all four pillars (logs, Jaeger, Prometheus/Grafana, Langfuse) on a clean `--obs` startup, per the observability README's guided tour
- [ ] `llm_requests_total` and token metrics populated and queryable in Grafana

### G. Polish & cleanup
- [ ] Remove or clearly mark any leftover scaffolding from Phase 1 that plan 003 superseded (e.g., anything still referencing the retired policy-gate node)
- [ ] Consistent snake_case wire format spot-checked across all four pipelines' responses
- [ ] `git tag` this release once merged (naming scheme is an open decision — see below)

## Packaging Plan

The project has never been packaged for anyone but Timothy to run. Two materially different packaging targets are on the table, and they lead to very different amounts of work:

**Option 1 — Self-hosted docker-compose release.** Ship the repo as-is: a `git clone` + `./build.sh --mode live` reproduces the whole stack anywhere Docker runs. This is what the project already supports today. Packaging work is mostly documentation: a clear "quickstart" path in the README, confirming the mock-mode path needs zero external accounts, and making sure `.env.example` is the only setup step for live mode.

**Option 2 — Hosted Azure deployment.** Actually stand the stack up on Azure infrastructure (AKS or Container Apps, Key Vault for secrets, managed identity instead of raw API keys in `.env`, GitHub Actions CD). This is the infra work `persona.md` describes as a distinct future plan, motivated by the Microsoft SWE2 resume goal ("zero Azure" gap). It's substantially more work than Option 1 and arguably its own Implementation Plan rather than something to fold into a release checklist.

**Decided (2026_07_24, see Stage 2): Option 1, and Azure is deferred entirely for this release — including as the *model* provider, not just as infrastructure.** Timothy's call: an Azure trial's sign-up credit is time-windowed, and starting that clock now (for light chat-completion testing during this release) would waste most of it before the Azure infra deployment plan — where it can actually be exercised at volume (AKS, sustained load, real cost data) — is ready to happen. So:

- **This release's quickstart path runs on Groq's free tier** (`LLM_PROVIDER=openai_compat`, `OPENAI_COMPAT_BASE_URL=https://api.groq.com/openai/v1`) — no Azure account, no card, no credit-window pressure, and it's already the exact seam plan 003 built (`ModelFactory` provider branch, `.env.example` documents it). A new user can go from `git clone` to a live response with a single free API key.
- **Azure OpenAI's code stays in the repo, untouched** — it was real implementation work (plan 003) and remains a supported provider — but it is not this release's demo path, not the thing `acceptance_check.sh live` verifies, and not something the quickstart docs lead with.
- **The Azure infrastructure deployment plan is now unambiguously later and separate**, resolving the numbering collision from Decision 1 below: it becomes its own future plan (next available slot, likely `005`) started only when Timothy is ready to actually use the trial credit's window for real — deploying and exercising AKS/Container Apps, not just calling a chat endpoint a few times.
- **Open sub-decision this creates:** embeddings. Groq (and `openai_compat` generally) serves no embeddings endpoint, so the RAG pipelines need a different live embeddings story now that Azure isn't in the mix by default — tracked as its own checklist item under Correctness & Test Coverage above (leading option: in-container CPU embeddings via `fastembed`/`sentence-transformers`, which keeps the whole release Azure-free and account-free).

## Presentation

Outline for the YouTube video accompanying this release, to be linked from the resume:

1. **Cold open (30–60s).** One real request going in through OpenWebUI and the finished trace coming out the other side in Jaeger/Grafana/Langfuse — show the payoff before explaining anything.
2. **What this is and why I built it (1–2 min).** Self-hosted LLM orchestration platform; motivation was going deep on AI orchestration and practicing production engineering discipline, not just calling an LLM API from a script.
3. **Architecture walkthrough (3–5 min).** Use the README's mermaid diagram: OpenWebUI → gateway (telemetry middleware → YARP) → langchain_service pipeline registry → Groq/Ollama + pgvector (note Azure OpenAI as a supported-but-not-demoed provider, per the 2026_07_24 scope decision below). Explain the contract-first design and why production lockdown is a config change (deleting one port mapping), not a code change.
4. **Live demo (4–6 min).** `./build.sh --mode live` against Groq's free tier, a request through each pipeline (chat/basic, chat/rag, graph/basic, graph/rag, graph/tools), then the OpenAI-compatible surface (`/v1/chat/completions`) so viewers see it works with any OpenAI client — and that going live cost nothing.
5. **Observability tour (3–4 min).** One request, four pillars: structured log with trace_id → Jaeger trace tree → Grafana RED + token metrics → Langfuse rendered prompt/retrieved chunks. This is the section most directly relevant to the "AI-driven features" and "operational maturity" angle for Microsoft roles.
6. **The process story (2–3 min).** Phase 1 hand-written vs. Phase 2 AI-collaborative with staged review gates (Documentation/AI_Implementation_Plans) — the honest-CI discovery (old workflow installed nothing and still went green) is a strong, concrete interview anecdote and belongs on screen, not just in a doc.
7. **What's next / close (30s).** Point at the roadmap (streaming, auth/rate limiting, memory, full eval suite, Azure infra deployment) so it reads as an active project, not a finished artifact.

**Interview-relevance framing to keep in mind while scripting:** the video should make it easy for a viewer (recruiter or interviewer) to map each section to a resume bullet — contract-first API design, distributed tracing across a polyglot stack, cost-guarded LLM routing, and a disciplined AI-assisted development process with reviewable history.

# Stage 2 (Discussion)

### [AI — 2026_07_23_23_45] Opening entry: decisions needed before Stage 3

1. ~~**Numbering collision.**~~ **Resolved 2026_07_24.** See Timothy's entry below — the Azure infra deployment plan is now clearly a separate, later effort. It takes the next open slot (likely `005`) whenever it starts; this document keeps `004`.
2. ~~**Release scope (Packaging Plan Option 1 vs. 2).**~~ **Resolved 2026_07_24.** Option 1 (self-hosted docker-compose), with the added specificity that the *model provider* for this release is Groq's free tier, not Azure OpenAI — see Packaging Plan above.
3. **Is plan 003 actually done?** This outline assumes yes, based on `.env.example` and recent commit messages ("Implemented Step 7 (tests)," "Step 6 (cost guards/observability)"). Worth an explicit confirmation before the checklist above is treated as accurate, in case there are unmerged loose ends. (Unaffected by the Groq decision — plan 003 built the provider abstraction generally, Azure and Groq alike.)
4. **Versioning scheme.** `main` already carries tag `v1.0-handwritten` for the Phase 1 hand-written milestone. Does this release become `v2.0` (next major version on the same tag sequence) or something like `v1.0-ai-collab` (parallel naming distinguishing the two phases)? Affects the `git tag` checklist item under Deployment Readiness.
5. **Merge plan.** This release implies merging `ai_dev` into `main` for the first time since PR #2. Worth deciding whether that's one release PR or several smaller ones, given how much has landed on `ai_dev` since.
6. ~~**Live-mode embeddings provider.**~~ **Resolved and implemented 2026_07_25.** CPU embeddings via `fastembed`. See Stage 4.
7. ~~**`toolbox` image doesn't support arm64.**~~ **Resolved 2026_07_26** — multi-arch tag `v1.0.1` published and confirmed working (toolbox pulls and reports healthy on Apple Silicon). Detail below kept for the record. Discovered while verifying the embeddings fix: `docker-compose.yaml`'s `toolbox` service pulls `ghcr.io/timothy-lee-grant/tool_box:1.0.0`, which `docker manifest inspect` confirms is amd64-only, so `./build.sh` fails outright on Apple Silicon (Timothy's own machine) with `no matching manifest for linux/arm64/v8 in the manifest list entries`. Timothy was explicit he wants the registry integration kept (not reverted to `build: context: ../Tool_Box`) — the point is professional cross-project integration. Root cause: Tool_Box's `docker_image_release.yml` had no `platforms:` key on its `build-push-action` step, so it only ever built for the runner's own (amd64) platform — a gap in that repo's own prior Stage-3 review of the same file. Fixed directly in `Tool_Box/.github/workflows/docker_image_release.yml` (added `docker/setup-qemu-action@v3` + `platforms: linux/amd64,linux/arm64`), logged in `Tool_Box/Documentation/ImplementationPlans/005-Release-1.0.md`. **Still open, Timothy's call:** which version the multi-arch rebuild lands under (re-cut `1.0.0` vs. a new `1.0.1`/`main`+`latest`) — the existing `1.0.0` tag stays amd64-only forever regardless, since GHCR tags aren't mutated by re-running an old workflow. Once a new tag publishes and `docker manifest inspect` shows both platforms, this project's `docker-compose.yaml` image tag needs updating to match.
8. ~~**Stale `pgdata` volume blocked a full live-mode re-verification.**~~ **False alarm — corrected 2026_07_26.** The real `./build.sh --mode live` run in Stage 5 below connected to the same `pgvector_service`/`pgdata` volume without any auth error. In hindsight the earlier failure was my own ad hoc verification script's fault, not the project's: I hand-guessed Postgres credentials (`admin`/`secret_pass`/`vectordb`, the compose-file *default* values) for a `docker run` outside the normal compose flow, instead of reading what `.env` actually set (`POSTGRES_USER=timothy`, `POSTGRES_DB=my_postgres_db`). Compose substitutes `.env` correctly every time; my manual test just didn't. Leaving this struck rather than deleted so the record is honest about the dead end, per this document's own append-only convention.

---

### [Timothy — 2026_07_24] Deferring Azure for this release

Reasoning: not confident I can fully take advantage of the initial Azure sign-up credit within its time window right now, so for this release I want to integrate with Groq free tier instead of Azure.

### [AI — 2026_07_24] Response

Agree with the call, and it's a clean resolution to two of the open decisions above, not just a provider swap:

- **The reasoning is sound and worth stating explicitly in the checklist/packaging plan (done above), not just acting on silently.** Azure's sign-up credit is time-boxed (a typical new-subscription trial is a fixed dollar amount over a fixed number of days); spending that window now on light chat-completion verification for this release would burn most of it before the Azure *infrastructure* plan — the thing that actually wants sustained Azure usage (AKS/Container Apps, real load, real cost data for the "zero Azure" resume story) — is ready to start. Saving the credit for when it can be used at volume is the higher-value sequencing.
- **One assumption I'm making: "Grok" = Groq**, the free/fast inference provider already wired into this codebase via `LLM_PROVIDER=openai_compat` (`.env.example` literally has `OPENAI_COMPAT_BASE_URL=https://api.groq.com/openai/v1` commented in, from plan 003's D2 decision). xAI's "Grok" model has no integration anywhere in this repo and isn't an OpenAI-protocol free tier the same way Groq is — if that's actually what was meant, that's new work, not the flip-a-config-value swap described below. Proceeding on the Groq assumption since it matches the existing `.env.example`/`factory.py` scaffolding exactly.
- **This resolves Decision 1 (numbering) cleanly**, more cleanly than my original suggestion: the Azure infra plan isn't just deprioritized in ordering, it's now deprioritized in *dependency* — it can't sensibly start until Azure is the deliberate focus again, which now clearly won't be this release.
- **This also sharpens Decision 2 (scope)** beyond "Option 1 vs 2" — the release isn't just "self-hosted docker-compose," it's specifically "self-hosted, zero-paid-account-required docker-compose," since Groq's free tier needs no card. That's a stronger, more demo-friendly release story than one that assumes a reader has (or wants to spend) Azure credit.
- **The one real technical consequence, not just a config change: embeddings.** `factory.py`'s `openai_compat` branch already raises loudly on `get_embedding_model` ("Groq-class chat endpoints don't serve embeddings... RAG under the free tier isn't a thing we pretend to support" — written during plan 003, before this decision). Deferring Azure means that comment's premise is now this release's actual default, not an edge case. Recommend closing it properly rather than leaving `graph-rag`/`graph-premium` live-broken: add CPU in-container embeddings (`fastembed` or `sentence-transformers`, both were already on the table in plan 003's D3 discussion and never adopted). That keeps RAG live-testable with zero external accounts, matching the spirit of "release runs on Groq free tier" rather than quietly re-introducing an Azure dependency through the embeddings side door.

### [AI — 2026_07_25] Verification: Groq works, voxel tools invoke correctly — and the embeddings gap is a confirmed hard blocker, not just a future nice-to-have

Timothy added his Groq API key to `.env` and asked me to verify it works end-to-end and that the voxel-world toolset (Tool_Box's `ToolBox.Voxel` toolset — `world_info`, `list_materials`, `place_block`, `describe_world`, `clear`, etc., per `Tool_Box/docs/TOOL_CATALOG.md`) can actually be invoked through it. Results:

**What I verified works, with evidence:**
- Brought the stack up via `./build.sh --mode mock` (all 5 containers healthy, including `toolbox` built fresh from `../Tool_Box`).
- Exercised the real MCP tool loop in mock mode first via the `TOOLCALL <tool>` deterministic hook already built into `MockChatModel` (`POST /graph/tools {"user_message":"TOOLCALL world_info"}`) — confirmed the ToolNode genuinely round-trips to the live `toolbox` container over MCP and back (not a stub).
- Then ran the **real** verification: inside the running `langchain_service` container, executed the already-registered `graph-free` pipeline handler directly (`PIPELINES["graph-free"].handler(...)`) with `LLM_MODE=live` set for that one process only (see "how I ran this" below — no files were changed to do this). `graph-free` hardcodes `provider="openai_compat"` at graph-build time (plan 003 Step 5b), so it calls Groq regardless of the global `LLM_PROVIDER`, and it never touches `vector_store` (no retrieval), so it doesn't hit the embeddings gap.
  - **Read tool**: asked it to call `world_info` — got back the real tool text ("This is a voxel grid... y = 0 is ground...") via `openai/gpt-oss-120b`, `prompt_tokens=3361`, `completion_tokens=342` (real, non-zero — proof of a genuine paid-API-shaped call, even though Groq's tier is free).
  - **Write tool**: asked it to call `place_block(material=stone, x=0,y=0,z=0)` then `describe_world` — got back `"placed stone"` then `"1 blocks. x 0..0, y 0..0, z 0..0."`, confirming the write tool actually mutated the shared `VoxelWorld` singleton and the read tool observed the mutation.
  - Cleaned up afterward by calling `clear` (`"world cleared"`) so no test data is left in the shared world singleton (per `TOOL_CATALOG.md`'s note that state is a global singleton with no session scoping).
  - **Conclusion: Groq integration works, and the voxel world tools are genuinely invokable — both read and write — through the real `graph-free` pipeline.**

**How I ran this without changing any code or scripts** (per this repo's rule): all containers stayed on the code already in the repo. I ran a throwaway script (`docker cp`'d into the container, never committed) that imports the already-registered pipeline and calls its handler directly, with `LLM_MODE=live` passed only to that one `docker compose exec` invocation — the running container's actual entrypoint/gunicorn process was untouched throughout.

**Why I didn't just run `./build.sh --mode live`, and a confirmed blocker this surfaces:** I also reproduced, concretely, what §Packaging Plan's Decision 6 predicted in the abstract. Exporting `LLM_PROVIDER=openai_compat` and running `./build.sh --mode live` for real:

```
[entrypoint] Running idempotent RAG ingestion...
RuntimeError: openai_compat has no embeddings path (chat-only free tiers).
Use provider='azure' (or 'ollama' with local hardware) for embeddings.
```

`langchain_service` exits 1 and the whole stack fails to come up — **not just for the RAG pipelines, for everything**, because `entrypoint.sh` runs `RunIdempotentRagIngestion()` unconditionally before gunicorn ever starts, and that always resolves an embeddings provider via the global `LLM_PROVIDER` (default `azure`), regardless of which pipeline a request will eventually use. `graph-free`/`graph-tools` don't need embeddings at all, but the container can't boot far enough to serve them, because ingestion isn't scoped to "only if a RAG pipeline exists."

**This escalates Decision 6 from "worth deciding" to "blocks `./build.sh --mode live` entirely for this release" — it needs to be resolved before the release checklist's live-mode items can be checked off for real** (I worked around it for this verification via the direct-handler technique above, which is fine for a one-off check but isn't how an actual user running `./build.sh --mode live` will experience it). My recommendation stands: in-container CPU embeddings (`fastembed`/`sentence-transformers`) so ingestion always succeeds regardless of chat provider — that's a small, contained change (swap what `vector_store.initialize()` resolves for embeddings when `LLM_PROVIDER=openai_compat`) rather than a redesign. **This is implementation work in the main codebase, so per this project's process it should go through its own step in Stage 4 once Timothy decides how he wants to handle it** — I did not implement it.

Restored the stack to `./build.sh --mode mock` afterward (the project's default posture) once verification was done.

# Stage 4 (Implementation)

### [AI — 2026_07_25] Step: CPU embeddings for the `openai_compat` provider

Timothy asked directly: "implement CPU embeddings for the openai_compat provider" — closing Decision 6 above. Scope: make `ModelFactory.get_embedding_model` succeed under `LLM_PROVIDER=openai_compat` instead of raising, without requiring Azure or any paid account, keeping the existing 768-dim pgvector schema intact.

**What changed:**

- `langchain_service/app/models/factory.py` — added `CPU_EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"` (768-dim, matches `DeterministicFakeEmbedding(768)` and the Azure branch's `dimensions=768` — no schema migration across modes/providers) and `from langchain_community.embeddings import FastEmbedEmbeddings`. The `openai_compat` branch of `get_embedding_model` now returns `FastEmbedEmbeddings(model_name=CPU_EMBEDDING_MODEL)` instead of raising `RuntimeError`. Model name is fixed (not `userDesiredModel`) — same reasoning the Azure branch already documents for ignoring that parameter: this is an infra choice, not a per-request one.
- `langchain_service/requirements.txt` — added `fastembed` (ONNX-based; installs clean on `python:3.11-slim`, no compiler/torch needed — verified in-container before writing any code, same "check the installed library before trusting it" discipline as Story C in the project's own war stories).
- `docker-compose.yaml` — added a `fastembed_cache` named volume, mounted at `/tmp/fastembed_cache` (fastembed's actual default cache path, confirmed by inspecting a running container rather than guessing) on `langchain_service`, so the ~100MB model download survives `--force-recreate` instead of re-fetching every restart.
- `.env.example` — corrected the now-stale "Chat only — no embeddings on this path" comment under the `openai_compat` block.
- `langchain_service/tests/test_provider_matrix.py` — replaced `test_live_compat_embeddings_refuse_by_design` (asserted the old `RuntimeError`) with `test_live_compat_embeddings_use_cpu_fastembed`, which monkeypatches `FastEmbedEmbeddings` in the factory module and asserts the routing decision (right class, right model name) without paying for a real ONNX load — real `FastEmbedEmbeddings` construction does real CPU work (and a network fetch on a cold cache), which would violate this test file's own stated invariant ("construction only, offline; no test in this file touches the network").

**How it was verified (all before reporting this done):**

1. Rebuilt the `langchain_service` image (`./build.sh --mode mock`, image build only — the run itself hit the unrelated `toolbox` arm64 issue in Decision 7 above) — confirmed `fastembed` installs without errors.
2. Ran the full suite against the real dependency set (`pip install -r requirements.txt -r requirements-dev.txt` into the project's local `.venv`, then `pytest`, mirroring `ci.yml` exactly): **68 passed, 6 skipped**, no regressions. The new test alone: 15/15 in `test_provider_matrix.py`, 0.56s (confirms the stub kept it fast/offline as intended).
3. Real (non-stubbed) proof the library path works: inside a running container, before writing any code, called `FastEmbedEmbeddings(model_name="BAAI/bge-base-en-v1.5").embed_query(...)` directly — confirmed **768 dimensions**, matching the schema.
4. Real proof the *bug* is fixed: reproduced the exact original crash (`LLM_PROVIDER=openai_compat`, real `RunIdempotentRagIngestion()`, against a real Postgres via a standalone `pgvector-service` container) — ingestion now gets **past** the embeddings step entirely (fetches the model, no `RuntimeError`) and fails later only on an unrelated, pre-existing local issue (Decision 8's stale-volume credential mismatch), which is not something this change touches.

**Left undone, on purpose:** the two environment issues in Decisions 7 and 8 (toolbox arm64 image, stale `pgdata` volume) — both pre-existing, both outside this task's scope, both flagged above for Timothy's call rather than acted on unilaterally (one needs a decision about image publishing/build strategy, the other is a destructive `docker volume rm`). Once those are resolved, `./build.sh --mode live` (with `LLM_PROVIDER=openai_compat`) should be re-verified end-to-end as a single real run, not the decomposed checks used here — that's the honest closing of checklist item A's `acceptance_check.sh live` line.

# Stage 5 (Final Results, Testing, Verification)

### [2026_07_26] `./build.sh --mode live` confirmed working end-to-end on Groq — three problems found and fixed along the way

Getting from "Groq keys added to `.env`" to a genuinely working `./build.sh --mode live` surfaced three real, separate problems — none of them the same problem, even though the first two both first appeared as "the container won't start." Recorded here as the closing verification for this thread of the release checklist, and because this kind of "found it, root-caused it, fixed it, proved it" arc is exactly the material this project's `skill_gap_analysis`/`concepts_documentation` docs value — worth remembering as a unit, not just as scattered Stage-2/4 entries.

**Problem 1 — live mode crashed the whole service at startup, for every pipeline, not just RAG.**
- **Symptom:** `./build.sh --mode live` with `LLM_PROVIDER=openai_compat` set → `langchain_service` exits 1 immediately, before serving a single request.
- **Root cause:** `entrypoint.sh` always runs RAG ingestion before gunicorn starts, and ingestion always resolves an embeddings provider via `ModelFactory.get_embedding_model()` — regardless of which pipeline a request will eventually use. The `openai_compat` branch of that method raised `RuntimeError("openai_compat has no embeddings path...")` by design (Groq-class endpoints are chat-only), which killed the container before `graph-free`/`graph-tools` — pipelines that never touch embeddings — could ever be reached.
- **Fix:** `ModelFactory.get_embedding_model` now returns CPU-local embeddings (`fastembed`, `BAAI/bge-base-en-v1.5`, 768-dim — matches the existing pgvector schema) instead of raising, when the provider is `openai_compat`. Free, account-free, no GPU. Full detail in the Stage 4 entry above.
- **Verified:** full pytest suite (68 passed, 6 skipped, no regressions) plus a real reproduction of the original crash, re-run against the fix, getting past the embeddings step cleanly.

**Problem 2 — the `toolbox` image had no arm64 build, blocking the entire stack on Apple Silicon.**
- **Symptom:** `no matching manifest for linux/arm64/v8 in the manifest list entries` — `toolbox` never pulls, `langchain_service` never even starts (its `depends_on: toolbox: condition: service_healthy` never clears).
- **Root cause:** unrelated to Problem 1 — found incidentally while verifying it. Tool_Box's own `docker_image_release.yml` (a separate repo) had no `platforms:` key on its `build-push-action` step, so its GHCR publish job only ever built for the runner's native platform (amd64). `ghcr.io/timothy-lee-grant/tool_box:1.0.0` was genuinely amd64-only, confirmed via `docker manifest inspect` — not a visibility/permissions problem, which was the first, reasonable guess.
- **Fix:** added `docker/setup-qemu-action@v3` + `platforms: linux/amd64,linux/arm64` to Tool_Box's workflow (`Tool_Box/Documentation/ImplementationPlans/005-Release-1.0.md` has the full writeup, including that this was a gap in that repo's own earlier review of the same file). Timothy cut and pushed tag `v1.0.1`; `docker-compose.yaml`'s `toolbox` image was updated to `ghcr.io/timothy-lee-grant/tool_box:1.0.1` to match.
- **Verified:** `toolbox` now pulls and reports `Healthy` on Timothy's arm64 machine.

**Problem 3 — `LLM_PROVIDER` was never actually set in `.env`, so live mode silently defaulted back to Azure.**
- **Symptom:** after both fixes above, `./build.sh --mode live` still crashed — but with a *different* error: `RuntimeError: AZURE_OPENAI_ENDPOINT is required for LLM_PROVIDER='azure' in live mode but is unset/empty.`
- **Root cause:** not a bug at all — `.env` had `OPENAI_COMPAT_*` keys set but never actually set `LLM_PROVIDER=openai_compat` (only ever discussed/assumed, never written). `docker-compose.yaml`'s `${LLM_PROVIDER:-azure}` correctly fell back to its documented default, and `_require_env` correctly failed loudly on the missing Azure config — exactly the fail-loud behavior plan 003 designed. This is a good example of the project's own error design working as intended: the failure named the exact missing variable and the exact reason, no debugging required.
- **Fix:** added `LLM_PROVIDER=openai_compat` to `.env`.
- **Also answered along the way — why CI never caught any of this:** `ci.yml` runs every Python test with `LLM_MODE: mock` explicitly and never invokes `./build.sh` or Docker Compose at all. Green CI has only ever meant "the mocked unit tests and offline provider-construction tests pass" — it was never scoped to catch a live-mode config or startup problem, consistent with this project's own "CI never spends live tokens" rule. Not a contradiction, just a coverage boundary worth naming explicitly rather than assuming CI proves more than it does.

**Final end-to-end verification (2026_07_26):**

```
$ curl -s localhost:5001/healthz
{"mode":"live","status":"ok"}

$ curl -s -X POST localhost:5001/graph/free -H "Content-Type: application/json" \
  -d '{"user_message":"Say the word verified and nothing else."}'
{"status":"success","response":"verified","metadata":{"pipeline_id":"graph-free",
 "model_used":"openai/gpt-oss-120b","prompt_tokens":1609,"completion_tokens":23,
 "latency_ms":1166,"retrieved_sources":[]}}
```

All five containers (`pgvector_service`, `toolbox`, `langchain_service`, `dotnet_server`, `openwebui`) healthy; real Groq completion through the real MCP-tool-capable pipeline, real non-zero token counts. This closes the live half of checklist item A (`./build.sh --mode live` on Groq, end to end, on Timothy's actual machine) — `scripts/acceptance_check.sh live` itself hasn't been run yet and is still the more formal, scripted version of this same check, left open on the checklist above.
