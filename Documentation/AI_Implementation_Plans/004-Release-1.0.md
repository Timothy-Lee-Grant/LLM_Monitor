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
- [ ] `bash scripts/acceptance_check.sh live` — full PASS against the real Azure OpenAI deployment (confirms the cost-guarded live path actually works, not just mock)
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
- [ ] `build.sh --mode live` runs clean against Azure OpenAI on a fresh clone (no leftover local state assumptions)
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

**Option 1 — Self-hosted docker-compose release.** Ship the repo as-is: a `git clone` + `./build.sh --mode live` (with the user supplying their own Azure OpenAI keys in `.env`) reproduces the whole stack anywhere Docker runs. This is what the project already supports today. Packaging work is mostly documentation: a clear "quickstart" path in the README, confirming the mock-mode path needs zero external accounts, and making sure `.env.example` is the only setup step for live mode.

**Option 2 — Hosted Azure deployment.** Actually stand the stack up on Azure infrastructure (AKS or Container Apps, Key Vault for secrets, managed identity instead of raw API keys in `.env`, GitHub Actions CD). This is the infra work `persona.md` describes as a distinct future plan, motivated by the Microsoft SWE2 resume goal ("zero Azure" gap). It's substantially more work than Option 1 and arguably its own Implementation Plan rather than something to fold into a release checklist.

**Recommendation:** treat this Release ("Release-1.0") as Option 1 — the self-hosted docker-compose package, capping the AI-collaborative Phase 2 work (registry, LangGraph, contracts, honest CI, Azure OpenAI model integration) with a clean, documented, reproducible release. Reserve the Azure infrastructure deployment as its own follow-on Implementation Plan (which would then need a different numeric slot than this document, since both are competing for "004" — see Decision 1). This keeps the release scoped to "is the AI-collaborative system I built actually done and reproducible," rather than blocking it on a large, separate infra project.

## Presentation

Outline for the YouTube video accompanying this release, to be linked from the resume:

1. **Cold open (30–60s).** One real request going in through OpenWebUI and the finished trace coming out the other side in Jaeger/Grafana/Langfuse — show the payoff before explaining anything.
2. **What this is and why I built it (1–2 min).** Self-hosted LLM orchestration platform; motivation was going deep on AI orchestration and practicing production engineering discipline, not just calling an LLM API from a script.
3. **Architecture walkthrough (3–5 min).** Use the README's mermaid diagram: OpenWebUI → gateway (telemetry middleware → YARP) → langchain_service pipeline registry → Ollama/Azure OpenAI + pgvector. Explain the contract-first design and why production lockdown is a config change (deleting one port mapping), not a code change.
4. **Live demo (4–6 min).** `./build.sh --mode live`, a request through each of the four pipelines (chat/basic, chat/rag, graph/basic, graph/rag), then the OpenAI-compatible surface (`/v1/chat/completions`) so viewers see it works with any OpenAI client.
5. **Observability tour (3–4 min).** One request, four pillars: structured log with trace_id → Jaeger trace tree → Grafana RED + token metrics → Langfuse rendered prompt/retrieved chunks. This is the section most directly relevant to the "AI-driven features" and "operational maturity" angle for Microsoft roles.
6. **The process story (2–3 min).** Phase 1 hand-written vs. Phase 2 AI-collaborative with staged review gates (Documentation/AI_Implementation_Plans) — the honest-CI discovery (old workflow installed nothing and still went green) is a strong, concrete interview anecdote and belongs on screen, not just in a doc.
7. **What's next / close (30s).** Point at the roadmap (streaming, auth/rate limiting, memory, full eval suite, Azure infra deployment) so it reads as an active project, not a finished artifact.

**Interview-relevance framing to keep in mind while scripting:** the video should make it easy for a viewer (recruiter or interviewer) to map each section to a resume bullet — contract-first API design, distributed tracing across a polyglot stack, cost-guarded LLM routing, and a disciplined AI-assisted development process with reviewable history.

# Stage 2 (Discussion)

### [AI — 2026_07_23_23_45] Opening entry: decisions needed before Stage 3

1. **Numbering collision.** `persona.md` refers to a future Azure infrastructure deployment plan as "004." This document has also taken the "004" slot in `Documentation/AI_Implementation_Plans/` (per CLAUDE.md's release-doc rule: same folder, same numbering sequence as regular Implementation Plans). Only one document can be `004`. Suggest this Release Plan keeps `004` (it was requested now) and the Azure infra plan becomes `005` whenever Timothy starts it — but confirm.
2. **Release scope (Packaging Plan Option 1 vs. 2).** Confirmed as Option 1 above (self-hosted docker-compose), pending Timothy's agreement — this is the single biggest scope decision in this document and changes the size of the Release Checklist substantially if reversed.
3. **Is plan 003 actually done?** This outline assumes yes, based on `.env.example` and recent commit messages ("Implemented Step 7 (tests)," "Step 6 (cost guards/observability)"). Worth an explicit confirmation before the checklist above is treated as accurate, in case there are unmerged loose ends.
4. **Versioning scheme.** `main` already carries tag `v1.0-handwritten` for the Phase 1 hand-written milestone. Does this release become `v2.0` (next major version on the same tag sequence) or something like `v1.0-ai-collab` (parallel naming distinguishing the two phases)? Affects the `git tag` checklist item under Deployment Readiness.
5. **Merge plan.** This release implies merging `ai_dev` into `main` for the first time since PR #2. Worth deciding whether that's one release PR or several smaller ones, given how much has landed on `ai_dev` since.
