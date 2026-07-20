2026_07_19_15_35-ToolBox_Integration_And_Hosted_LLM_Migration

# Stage 1 (Design Documentation)

**Direction For This Implementation** (Timothy, 19 July 2026)

Two goals, which interact:

1. **Introduce tools into the system.** The Tool_Box repo (https://github.com/Timothy-Lee-Grant/Tool_Box/tree/feature/002-streamable-http) is a separate project exposing MCP tools over streamable HTTP. Integrate it into LLM_Monitor so the LangGraph agent's tool loop becomes real: discover tools from the ToolBox at startup, call them over the compose network. The walkthrough document generated in the Tool_Box repo (`LLM_MONITOR_INTEGRATION.md`) is the Stage 1 input for the integration mechanics — it specifies the compose wiring, the `langchain-mcp-adapters` client, the `graph-tools` registry entry, and the tests.

2. **Migrate off local AI inference.** Timothy no longer has access to a computer that can run local model inference. Live mode can no longer mean "Ollama on my machine" — it must mean a hosted model API. This introduces **price sensitivity**: every live-mode LLM call now costs real money. Consequences Timothy has stated up front:
   - For pipelines that hit the external API, he does NOT want per-request LLM overhead (e.g. an LLM-judge policy gate checking whether the request broke the rules). The live request path should be as close to one model call per user message as possible.
   - Mock mode remains the default development posture; the external API is for deliberate, verifying runs.

Key Stage 1 constraints carried over from the walkthrough doc:

- Toolbox service is internal-only (no `ports:`), host-header allowlist must include `toolbox`, healthcheck-gated startup ordering.
- Toolbox is NOT profile-gated: tools are real and free in both mock and live modes. Only models are mocked/paid.
- Adding toolsets to Tool_Box later must add agent capabilities with zero LLM_Monitor code changes.
- New capability lands as a new registry entry (`graph-tools`), additive — existing pipelines untouched.

# Stage 2 (Discussion)

### [AI — 2026_07_19_15_35] Opening entry: review of Stage 1 and decisions needed

#### A. Observations on the ToolBox integration

The walkthrough doc is a solid Stage 1 — it already made the important calls (internal-only exposure, healthcheck ordering, additive registry entry, pinned adapters). Three things I verified against this repo before planning:

1. **The graph is ready for this.** `build_graph.py` was explicitly designed with this growth path ("new flow entirely → new builder variant + one registry entry"). A tool-loop variant needs one new concept the current graph doesn't have: a *conditional* edge (agent → tool_node when the model emitted tool calls, agent → respond when it didn't). Everything else is the established pattern.

2. **One real async/sync friction point.** `client.get_tools()` is async; pipelines and the Flask API layer are synchronous. Startup-time discovery can wrap with `asyncio.run(...)` once at module import (same place `_GRAPH_BASIC`/`_GRAPH_RAG` are compiled). But tool *execution* inside `ToolNode` is also async under the hood — LangChain's `BaseTool` from the MCP adapters exposes async `_arun`, and calling it from a sync `graph.invoke()` will raise unless the adapter provides sync fallbacks. We need to decide: run the `graph-tools` pipeline via `graph.ainvoke` inside `asyncio.run(...)`, or verify the adapter tools work under sync invoke. This is the kind of thing that looks fine in the doc and bites during Step 3 — flagged now so it lands in the plan as an explicit sub-step with a test.

3. **Startup coupling risk.** Discovery at pipeline-construction time means langchain_service now cannot boot if toolbox is down, even for pipelines that don't use tools. The `depends_on: service_healthy` gate makes this consistent with how we treat pgvector, so I think it's acceptable — but it's a real availability coupling and worth stating: toolbox joins the "must be healthy before the service exists" set. Alternative (lazy discovery on first `graph-tools` request) adds complexity for little gain in a compose-local system. My recommendation: eager discovery, matching pgvector discipline.

#### B. The hosted-model migration — decisions needed

This is the part Stage 1 leaves open. The architecture question and the cost question are separable.

**D1 — Provider abstraction (architecture).** Recommendation: do NOT code against any one vendor SDK. Nearly every cheap provider (Groq, OpenRouter, Gemini via its OpenAI-compat endpoint, DeepSeek, Together) speaks the OpenAI chat-completions protocol. `langchain-openai`'s `ChatOpenAI(base_url=..., api_key=..., model=...)` therefore covers all of them; switching providers becomes a config change, exactly like the YARP retarget comment in docker-compose. `ModelFactory` grows a third branch keyed by a new env var:

```
LLM_MODE=mock            → MockChatModel (unchanged, still default)
LLM_MODE=live + LLM_PROVIDER=ollama   → ChatOllama (kept for the day you have hardware again)
LLM_MODE=live + LLM_PROVIDER=openai_compat → ChatOpenAI(base_url=OPENAI_COMPAT_BASE_URL, ...)
```

**D2 — Which provider to start with (money).** Current landscape (verify limits at implementation time — free tiers move): Groq free tier (no card, ~30 req/min, tool calling, $0), Google Gemini free tier ($0, verify quotas), OpenRouter (aggregator, free models rotate), cheapest paid fallbacks (DeepSeek / Gemini Flash-Lite class, ≤$0.30/M input). Initial recommendation: Groq free tier first. **Timothy to decide.**

**D3 — Embeddings.** Options: (1) CPU embedding in-container (fastembed/sentence-transformers — works if "no local AI" means "no GPU-class hardware"); (2) hosted embeddings (Gemini free tier, or OpenAI-class `text-embedding-3-small` at ~$0.02/M — effectively free at our volume); (3) keep DeterministicFakeEmbedding in live — rejected, live RAG would retrieve on noise. Initial recommendation: option 2. **Timothy to decide.**

**D4 — Cost posture for the live request path.** Concretely what "no extra overhead" means in this codebase:

- The live chat path is already one model call per request — the policy LLM gate was retired in plan 001 (`old_implementations/graph_policy_nodes_v1.py`) and the LLM judge lives only in `eval/eval_judge.py`, run on-demand. So the main work here is *keeping* it that way and writing it down: **rule — nothing on the live request path may add an LLM call beyond the agent loop itself.** Tool-loop iterations are model calls too: a runaway agent loop is the new cost risk, so the graph gets a **recursion/iteration cap** (LangGraph `recursion_limit`, plus `max_tokens` on the model).
- Evals (retrieval, judge) run only in mock mode or on explicit demand, never in CI-against-paid-API.
- `max_tokens` set on the hosted model config; default model is the cheap/free one, never a premium model by default.

**D5 — Secrets.** API keys enter via `.env` (already gitignored — verify) → compose `environment:` → factory reads env var, fails loudly if `LLM_MODE=live` and key unset. Keys never appear in compose file or git history.

**D6 — What happens to the `live` profile / ollama service.** `live` now means "external API" — the profile no longer needs to start the ollama container. Options: (a) remove ollama from compose, (b) keep it under a new `local-live` profile for the future-hardware day. I lean (b) — it costs nothing and preserves the earlier work's runnability. **Timothy to decide.**

#### C. Decisions needed before Stage 3 goes final

1. Provider choice (D2) — recommend Groq first + Gemini second.
2. Embeddings strategy (D3) — and how strict "no local inference" is.
3. Ollama's fate in compose (D6) — remove vs. `local-live` profile.
4. Async execution strategy for graph-tools (A2) — I'll investigate both options in Step 3 and present findings, unless you have a preference now.
5. Confirm: eager tool discovery at startup (A3), `graph-tools` as the new registry id, and the walkthrough doc's compose wiring adopted as-is.

---

### [Timothy — 2026_07_19_15_46, via conversation] Strategic reframe: optimize for Microsoft SWE2

Timothy brought in advice from another conversation reviewing his resume against Microsoft job descriptions. Key points:

1. **"Zero Azure" is the single biggest screener ding.** His resume shows AWS (RDS/EC2) and the word Azure appears nowhere, while he is applying to Microsoft. The cheapest fix: build or redeploy the flagship project on Azure.
2. **The CoreAI JD's preferred quals map directly onto this plan:** "Azure development," "AI-driven features: prompt design, tool calling, eval harnesses," "data pipelines." Recommendation from that conversation: make the flagship cover all three — Azure OpenAI embeddings, an LLM-powered feature with tool/function calling, and an eval harness for relevance scoring.
3. **Budget clarified:** "cost sensitive" means "don't waste money," not "$0 only." $40–50/month is acceptable spend toward the goal.
4. **Cost-lean clarified:** the earlier "no LLM judge overhead" requirement means *at least one pipeline* must be optimized for cost. Other pipelines absolutely can carry per-request LLM overhead (judges, policy gates) when there's a compelling reason.
5. **Explicit goal statement: get hired at Microsoft as a Software Engineer 2. Optimize the plan for this.**

### [AI — 2026_07_19_15_46] Response: revised decisions and the SWE2-optimized shape

This reframe resolves most of the open decisions, and it changes one big one. Taking them in order:

**D2 RESOLVED — the provider is Azure OpenAI, and it's not close.** With the SWE2-at-Microsoft goal stated explicitly, provider choice stops being a cost question and becomes a resume question. Every live token this project burns should also be buying the keyword "Azure OpenAI" and real experience with the Azure portal, resource provisioning, model deployments (Azure AI Foundry), key management, and Azure cost controls — the exact surface a Microsoft interviewer can probe. Cost check against the budget: GPT-4o-mini-class models run roughly $0.15/M input, $0.60/M output on Azure pay-as-you-go — a heavy dev month (say 5M in / 1M out) is under $2. `text-embedding-3-small` is $0.02/M — pennies. The entire Azure OpenAI side of this plan fits in single-digit dollars per month, leaving nearly all of the $40–50 budget for infrastructure (see plan 004 preview below). Also note: new Azure accounts typically get ~$200 of 30-day credit — verify at signup and use it deliberately.

Architecturally D1 survives intact: `langchain-openai` ships `AzureChatOpenAI` and `AzureOpenAIEmbeddings`, so the factory branch becomes `LLM_PROVIDER=azure` alongside the kept `ollama` branch. Config via `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_API_VERSION`, and *deployment names* (Azure's extra indirection over raw model names — worth understanding, and worth being able to explain in an interview).

**D3 RESOLVED — Azure OpenAI embeddings (`text-embedding-3-small`).** This is precisely what the JD advice named ("swap raw local embeddings for Azure OpenAI embeddings"). Bonus that kills the migration risk from v1: text-embedding-3 models accept a `dimensions` parameter, so we can request 768-dim vectors and **keep the existing pgvector column schema unchanged**. (We still re-ingest, since mock vectors and real vectors don't share a space — but no schema migration.)

**D4 REVISED — tiered pipelines instead of a blanket rule.** Timothy's clarification turns the cost rule into a *design feature*, which is honestly a better interview story than the blanket rule was:

- **`graph-tools` (lean tier):** agent + tool loop only. Hard caps (`recursion_limit`, `max_tokens`), no auxiliary LLM calls, cheapest deployed model. Explicitly documented as the cost-optimized tier.
- **`graph-premium` (full tier):** policy gate (single cheap-model classification call — this revives the plan-001-retired policy node with a now-compelling reason) → RAG → tool loop → **sampled async LLM-judge scoring** (judge a configurable fraction of responses *after* the response is returned, logging scores to Langfuse — no user-facing latency, bounded cost).

The pair demonstrates: prompt design, tool calling, eval harness woven into production traffic (not just offline), cost-tier product thinking, and per-pipeline cost observability in Grafana. That covers the JD's "AI-driven features" line end to end, and "designing a cost-tiered LLM serving architecture" is a strong SWE2 behavioral/design answer.

**D6 RESOLVED per my lean:** ollama moves to a `local-live` profile, kept for the future-hardware day. `live` now means Azure.

**NEW — plan 004 preview (Azure deployment).** Redeploying the stack *on* Azure is the other half of closing the "zero Azure" gap, but it is deliberately **out of scope for 003** — this plan keeps its shape (tools + hosted models), and deployment gets its own staged plan. Direction to react to now, since it affects 003's choices at the margins:

- Compute: **AKS** (free-tier control plane + one B2s-class node, ~$30/month, deallocate when not demoing) is my lean over Azure Container Apps (~$0 with scale-to-zero) — because Kubernetes/AKS is a heavyweight keyword in Microsoft infra-adjacent JDs, and compose→k8s migration was already identified as a learning goal in `targeted_implementations/002-Containers_And_Orchestration_Skills_For_Microsoft.md`. ACA remains the budget fallback.
- Around it: Azure Database for PostgreSQL flexible server (pgvector extension) or in-cluster pgvector, Azure Key Vault + managed identity for the secrets story, GitHub Actions CI/CD to Azure, and an Azure **budget alert** capping spend — itself a cost-engineering story.
- Rough monthly bill either way: Azure OpenAI usage (<$5) + AKS node (~$30, stoppable) or ACA (~$0) — inside the $40–50 envelope with headroom.

**Remaining open before Stage 3 v2 is final:** (1) confirm Azure OpenAI + the tiered-pipeline design; (2) A2 async strategy — still an implementation-time spike; (3) whether `graph-premium` lands in 003 or is deferred to its own step gate (it's in v2 as Step 5, permissioned separately like every step, so deferring is just "don't grant Step 5 yet").

---

### [Timothy — 2026_07_19_16_48, via conversation] Confirming understanding before formalizing

Timothy restated the design to verify it before agreeing: (1) local functionality is preserved — `LLM_PROVIDER=ollama` keeps the Ollama path alive, because the lack of local hardware is *temporary* and that capability must not be lost; (2) two external pipelines, both on Azure pay-as-you-go: `graph-tools` with only the base agent-loop + tools functionality, and `graph-premium` with the full feature set; (3) he likes this because the project should showcase many feature sets. New question: should we also utilize the free-tier models discussed earlier (Groq/Gemini) — possibly as another pipeline? Asked for the AI's thoughts, in the documentation.

### [AI — 2026_07_19_16_48] Confirmation, and yes to the free-tier pipeline — as a *routing* feature

**Your understanding is correct on all three points**, with one precision worth stating because it affects how we build it:

1. **Ollama preserved — yes.** The `ollama` branch of `ModelFactory` stays, the ollama compose service moves to a `local-live` profile, and when you have hardware again it's an env-var flip. Nothing from plans 001–002 is discarded.
2. **Two Azure pipelines — yes.** Both `graph-tools` and `graph-premium` call Azure OpenAI pay-as-you-go. `graph-tools` is deliberately minimal (agent loop + tools, hard caps, no auxiliary LLM calls — the documented cost-lean tier). `graph-premium` is the showcase tier (policy gate → RAG → tool loop → sampled async judge).
3. **The precision:** today, provider selection is *global* (one `LLM_MODE`/`LLM_PROVIDER` env pair controls every pipeline). Your description — different pipelines, same provider now, but potentially different providers later — implies provider becomes a **per-pipeline binding** with the env vars as the default. That's a small factory change (a `provider` parameter on `get_chat_model`, defaulting to the env) but an important architectural shift, and it's exactly what makes your free-tier question easy to say yes to.

**On the free-tier pipeline: yes — and I'd frame it as "model routing," because that reframe is what makes it portfolio-gold rather than clutter.** Reasoning:

- *The feature it showcases is real and named in industry:* multi-provider model routing. With per-pipeline provider binding, the registry becomes a routing table: `graph-free` → Groq free tier (llama-3.3-70b class, tool-calling capable, $0), `graph-tools` → Azure mini-class, `graph-premium` → Azure full path. Same question through three tiers, compared live in Grafana (cost panel) and Langfuse (quality scores) — that is a *demo you can run in an interview*: "here's the same query at $0, at a tenth of a cent, and at premium with eval scoring; here's the observed cost/quality/latency tradeoff." Very few SWE2 candidates can show that.
- *It has a practical dev benefit:* `graph-free` gives you a **$0 real-model loop for daily development**. Mock mode stays the default for tests, but when you want to exercise genuine tool-calling behavior repeatedly while iterating, you burn Groq's free quota instead of Azure dollars. The Azure pipelines then get exercised deliberately (demos, verification, eval runs) — which is exactly your "don't waste money" posture, engineered into the system instead of relying on discipline.
- *Guardrails so it stays a supporting act:* the headline of this project is Azure — the resume line is "Azure OpenAI–based tiered pipelines *with multi-provider routing (Groq free-tier) and per-tier cost observability*," not "a Groq project with Azure on the side." Concretely: `graph-free` reuses the same `openai_compat` factory branch from Stage 2 D1 (`ChatOpenAI(base_url=...)` — Groq speaks the OpenAI protocol), so it costs us one registry entry, one env-var pair, and zero new architecture beyond the per-pipeline binding we already need. If Groq's free tier rotates models or rate-limits during a demo, that's survivable — and even *that* is a talking point (why free tiers can't be your production dependency).
- *What I'd say no to:* a Gemini pipeline as well. Three providers is a routing story; four is maintenance. Gemini stays what it was in D2 — the named fallback if Groq's free tier degrades.

This lands in the plan as **Step 5b** (after the Azure provider exists, before/alongside premium), separately permissioned like everything else — skipping it never blocks the Azure work. Plan below bumped to v3: per-pipeline provider binding added to Step 4, Step 5b added, acceptance criteria and risks updated.

# Stage 3 (Implementation Planning)

### [AI — 2026_07_19_16_48] Implementation Plan v3 (v2 + per-pipeline provider binding and the `graph-free` routing pipeline, per Stage 2 discussion of 16_48; v1 assumed Groq-only — superseded)

Ordering rationale: compose plumbing first (everything else needs a reachable toolbox), then discovery, then the lean graph, then the Azure model migration, then the premium tier (separately permissioned), then cost guards/observability, then tests/verification.

#### Step 1 — Compose: toolbox service + wiring

- Add `toolbox` service per the walkthrough doc: `build: ../Tool_Box`, `AllowedHosts: "localhost;127.0.0.1;toolbox"`, curl healthcheck, **no ports**, not profile-gated.
- `langchain_service`: add `depends_on: toolbox: condition: service_healthy` and `TOOLBOX_URL=http://toolbox:8080/mcp`.
- Proof: `docker compose up` shows toolbox healthy before langchain_service starts; `docker compose exec langchain_service python -c "import urllib.request; urllib.request.urlopen('http://toolbox:8080/health')"` succeeds.

#### Step 2 — Tool discovery client

- Pin `langchain-mcp-adapters==<resolved>` in requirements.
- New module `app/tools/toolbox_client.py`: `build_toolbox_client()` reading `TOOLBOX_URL` (KeyError if unset — no silent default), `discover_tools()` wrapping the async `get_tools()` for startup use.
- Proof: inside compose, a one-liner discovery script lists `ping`, `server_info`, `current_time`.

#### Step 3 — `graph-tools` pipeline (lean tier)

- `build_graph` gains a tool-loop variant: `agent → (conditional: tool_calls?) → tool_node → agent`, `agent → respond` otherwise. `ToolNode(tools)` from `langgraph.prebuilt`; model bound with `.bind_tools(tools)`.
- Resolve the async question (Stage 2 A2): spike both `graph.ainvoke` under `asyncio.run` and sync invoke with adapter tools; adopt whichever is cleaner, document why.
- Hard caps: `recursion_limit` on invocation, `max_tokens` on the model — this pipeline is the documented cost-optimized tier.
- Register `graph-tools` in `pipelines.py` — additive; appears in `/v1/models` automatically; instrumented for free by the registry wrapper.
- Mock-mode behavior: mock model must be able to emit a scripted tool call (extend `MockChatModel`, or test the tool node directly — decide during implementation).

#### Step 4 — Azure OpenAI provider (the Ollama exit)

- Azure side (Timothy, in portal — resume-relevant experience, not automated away): create the Azure OpenAI resource, deploy a cheap chat model (GPT-4o-mini class) and `text-embedding-3-small`, note endpoint + deployment names, set an Azure **budget alert** (e.g. $40/month with email at 50/90%).
- `ModelFactory.get_chat_model`: add a `provider` parameter (defaults to `LLM_PROVIDER` env — existing callers unchanged) with branches: `azure` → `AzureChatOpenAI(azure_deployment=..., temperature=0, max_tokens=LLM_MAX_TOKENS)`; `openai_compat` → `ChatOpenAI(base_url=..., api_key=..., model=...)` (used by Step 5b); `ollama` branch kept verbatim (hardware-return path). `LLM_MODE=mock` still overrides everything to mocks regardless of provider — mock remains the global dev default. Add pinned `langchain-openai` to requirements.
- Per-pipeline binding: pipeline construction passes its provider explicitly (`graph-tools`/`graph-premium` → `azure`), making the registry a visible routing table.
- `get_embedding_model`: `azure` → `AzureOpenAIEmbeddings(azure_deployment=..., dimensions=768)` — pgvector schema unchanged; re-ingestion required (document why: mock and real vectors don't share a space).
- Compose: ollama moves to `local-live` profile; `live` requires the Azure env vars; `.env.example` documents names; startup fails loudly if `LLM_MODE=live` with missing key.
- Proof: `LLM_MODE=live LLM_PROVIDER=azure` chat through OpenWebUI returns a real Azure OpenAI answer through the full gateway path.

#### Step 5 — `graph-premium` pipeline (full tier; separately permissioned — may be deferred without touching other steps)

- New builder variant: policy-gate node (single cheap-model classification: allowed/blocked, reviving the retired plan-001 policy prompt) → retrieve → agent/tool loop → respond → **async sampled judge** (configurable sample rate; judge call happens after the response is committed; score written to Langfuse via the existing SDK wiring from plan 002).
- Register `graph-premium`; document the tier contract next to the registry: lean = no auxiliary LLM calls; premium = policy gate + sampled judge, each with a stated reason.
- Proof: premium request shows policy-gate span + (when sampled) a judge score attached to the trace in Langfuse; lean request shows neither.

#### Step 5b — `graph-free` pipeline (model routing; separately permissioned)

- One registry entry binding the lean tool-loop graph to `openai_compat` with Groq's endpoint (`GROQ_BASE_URL`, `GROQ_API_KEY`, tool-calling-capable free model, e.g. llama-3.3-70b class — verify current free-tier models/limits at implementation time).
- Purpose (documented in the registry description): $0 real-model development loop + the multi-provider routing demonstration. Same hard caps as `graph-tools`.
- Explicit non-goal: no fourth provider. Gemini remains the named fallback if Groq's free tier degrades.
- Proof: the same tool-demo question answered by `graph-free` (Groq) and `graph-tools` (Azure), both visible with per-pipeline token/cost metrics in Grafana.

#### Step 6 — Cost guards and cost observability

- Unit-assert the caps (`max_tokens`, `recursion_limit`) and the tier contract (lean pipeline makes exactly N model calls for a no-tool request).
- Write the tier rule into CONTRACTS.md: every pipeline declares its tier; nothing joins the lean tier's request path that adds an LLM call.
- Grafana: token metrics already exist per pipeline (plan 002) — add a cost panel converting tokens → $ using the Azure per-token prices, so spend per pipeline is *observable*. Pair with the Azure budget alert from Step 4.
- Evals (`eval/`) never run against the paid API in CI — mock or explicit-manual only.

#### Step 7 — Tests

- Integration pytest (compose, mock mode, marked so unit CI skips): `test_toolbox_tools_discovered` (`{ping, server_info, current_time} ⊆ names`), `test_agent_can_call_ping` (`pong: e2e` reaches the final answer).
- Unit tests: factory matrix (`LLM_MODE` × `LLM_PROVIDER` → model class), loud failure when live without a key, tier-contract assertions from Step 6.
- `scripts/acceptance_check.sh`: add toolbox health curl.

#### Step 8 — Live verification (the demo moments)

- Through OpenWebUI on `graph-tools`, live mode: "what time is it on the server?" → agent calls `current_time` and answers with real server time — an answer the model cannot know without the tool.
- On `graph-premium`: a blocked-policy request refuses; a sampled request shows a judge score in Langfuse.
- Record the session's actual dollar spend from the token metrics + Azure cost view; log it here (expected: cents).

#### Acceptance criteria

1. `docker compose up` (default/mock): toolbox healthy before langchain_service; existing pipelines unaffected; new pipelines listed in `/v1/models`.
2. Mock-mode pytest green, including both toolbox integration tests and the tier-contract tests.
3. Live mode runs with zero local inference against **Azure OpenAI**; ollama container not running.
4. The `current_time` demo succeeds end-to-end through the gateway; premium demos succeed if Step 5 was granted.
5. No secret in git; live mode without a key fails loudly at startup; Azure budget alert configured.
6. Adding a toolset to Tool_Box requires zero LLM_Monitor code changes to appear in the agent.
7. Resume delta is real: the project now truthfully supports "Azure OpenAI (chat + embeddings), LLM tool calling via MCP, cost-tiered pipeline design with eval scoring on production traffic, and multi-provider model routing with per-tier cost observability" (routing claim contingent on Step 5b being granted).
8. The Ollama path still works: `LLM_PROVIDER=ollama` under the `local-live` profile remains runnable (verifiable by inspection/unit test now, end-to-end when hardware returns).

#### Risks

- **Azure onboarding friction**: resource creation, model deployment quotas, and API versioning are their own learning curve (that's partly the point); budget a session for it before Step 4 coding.
- **Tool-calling quality**: mini-class models occasionally emit malformed tool calls; the loop cap bounds the damage; escalate the deployed model only if demos actually suffer.
- **Async/sync integration** (Stage 2 A2): the known unknown; explicitly spiked in Step 3 before deep wiring.
- **Judge/policy cost creep** (premium tier): bounded by sample rate + cheap judge model; the Step 6 cost panel makes any creep visible immediately.
- **Sibling-checkout build**: `build: ../Tool_Box` requires both repos side by side on the right branch; documented in README as a prerequisite.
- **Price/quota drift**: Azure prices, free-credit terms, and Groq's free-tier models/limits all change; verify at implementation time; the provider abstraction keeps exit costs low.
- **Free-tier reliability** (`graph-free`): rate limits or model rotation can break it without notice — acceptable for a dev/demo tier, never a dependency for the Azure pipelines; its failure modes are themselves a talking point about free tiers in production.

### [AI — 2026_07_19_17_24] Plan re-review + Timothy-Side Prerequisites Per Step

**Re-review before we start:** I walked the v3 steps once more against the codebase and I still endorse the ordering and content. Two confirmations from that pass: (1) `.env` handling is already correct — the repo's `.gitignore` ignores `.env` and `.env.*` while allowing `.env.example`, so the secrets flow in D5 works with zero gitignore changes; (2) the one step with a hard external dependency on you is Step 1 (Tool_Box must be buildable as a sibling checkout) and Step 4 (Azure resources must exist) — everything else is internal. Your account/signup work can happen in parallel at any time; nothing blocks until the step that consumes it.

The division of labor below is deliberate: everything involving accounts, money, credentials, and the Azure portal is yours — partly because I shouldn't hold your keys, and mostly because *this portal experience is part of the resume value*. Do these yourself, slowly, reading the screens.

#### Prerequisites checklist (do-ahead work, roughly in the order the steps consume it)

**Step 1 (toolbox in compose) — YOUR WORK:**
- Ensure `Tool_Box` is checked out as a **sibling directory** of `LLM_Monitor` (i.e. `../Tool_Box` resolves from this repo), on the branch containing the streamable-HTTP server (`feature/002-streamable-http` — or merge it to main first if you consider it done; your call, just tell me which branch is authoritative).
- Verify it builds standalone before we wire it in: `docker build -t toolbox-test ../Tool_Box` succeeds, and a manually-run container answers `GET /health` on 8080. If its Dockerfile lives in a subdirectory or needs build args, note that here in the discussion — Step 1's compose stanza needs to match.

**Step 2 (discovery client) — No work on your end needed.**

**Step 3 (`graph-tools` pipeline) — No work on your end needed.**

**Step 4 (Azure OpenAI provider) — YOUR WORK (the big one; budget an unhurried session):**
1. Create an Azure account at portal.azure.com (verify the ~$200/30-day new-account credit at signup and note its expiry date — use it deliberately).
2. Set up spend protection **first, before deploying any model**: Cost Management → create a budget (e.g. $40/month) with email alerts at 50% and 90%.
3. Create an Azure OpenAI resource (portal will route you through Azure AI Foundry). Region matters for model availability — pick a major US region and check the chat model you want is listed there.
4. Create two model **deployments** (Azure's indirection layer — a deployment is your named instance of a model): one cheap chat model (GPT-4o-mini class), one `text-embedding-3-small`. Write down the *deployment names you chose* — the code addresses deployments, not model names.
5. Collect into `LLM_Monitor/.env` (already gitignored — verified 2026_07_19): `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_API_VERSION`, `AZURE_OPENAI_CHAT_DEPLOYMENT`, `AZURE_OPENAI_EMBED_DEPLOYMENT`. (I'll create the matching `.env.example` with these names, no values, during Step 4.)
6. Sanity-check with one raw curl to the chat completions endpoint before we integrate — proves keys/endpoint/deployment names independently of our code, and shows you the wire format YARP-style debugging will need later.

**Step 5 (`graph-premium`) — No work on your end needed** (reuses the Step 4 resource and deployments; the policy gate and judge use the same cheap chat deployment).

**Step 5b (`graph-free` routing) — YOUR WORK (5 minutes):**
- Create a free Groq account at console.groq.com (no credit card), generate an API key, add to `.env`: `GROQ_API_KEY`, plus `GROQ_BASE_URL` (their OpenAI-compatible endpoint) and the tool-calling-capable free model name we settle on at implementation time.

**Step 6 (cost guards/observability) — YOUR WORK (2 minutes, during the step):**
- Confirm the two per-token prices (input/output) for your chosen Azure chat deployment from your own Azure pricing page, so the Grafana cost panel uses *your* real rates rather than my researched ones.

**Step 7 (tests) — No work on your end needed.**

**Step 8 (live verification) — YOUR WORK (participation, not setup):**
- Run the demo prompts yourself through OpenWebUI (login: existing admin account) for both tiers, and afterwards open Azure's Cost analysis view to see the actual spend of the session — we log the number here as part of Stage 5 evidence.

**Cross-cutting, before Stage 4 begins:**
- Confirm which Tool_Box branch is authoritative (Step 1 above).
- Never paste API keys into our chat or into any file other than `.env`. If a key ever leaks into a tracked file, we rotate it in the portal — history is never rewritten (project rule), so the only safe response to a committed secret is revocation.

### Stage 3 Discussion Subsection

*(v1 → v2 changes are recorded in the Stage 2 entries of 2026_07_19_15_46. Discussion of Plan v2 goes here; the plan above will be revised in place as this conversation proceeds.)*

# Stage 4 (Implementation)

### [Timothy — 2026_07_19_17_45] Step 1 prerequisite complete; permission granted for Step 1

Verified on his machine: `Tool_Box` is a sibling checkout at `/Users/timothygrant/Desktop/projects/Tool_Box`, on branch `feature/002-streamable-http` (branches present: 002, 003-extra-tools, main — 002 is authoritative for this plan). `docker build -t toolbox-test ../Tool_Box` succeeded (multi-stage .NET 10 build, Dockerfile at repo root, curl installed in the runtime stage — the healthcheck's dependency confirmed). The standalone `/health` curl was skipped; compose's healthcheck will prove it in verification. Granted Step 1.

### [AI — 2026_07_19_17_45] Step 1 complete — toolbox service wired into compose

**Changed:** `docker-compose.yaml` only. Three edits, matching the plan and the walkthrough doc exactly:

1. New `toolbox` service: `build.context: ../Tool_Box`, `AllowedHosts=localhost;127.0.0.1;toolbox`, curl healthcheck (10s/3s/5 retries/10s start), **no `ports:`** (internal-only, ADR-008 posture), **not profile-gated** (tools real in mock and live). Commented in the file's house style with the plan-003 reasoning.
2. `langchain_service.environment` += `TOOLBOX_URL=http://toolbox:8080/mcp` (consumed from Step 2 on; comment flags the `/mcp`-not-`/` trap).
3. `langchain_service.depends_on` += `toolbox: condition: service_healthy` (toolbox joins pgvector in the must-be-healthy-first set, per Stage 2 A3).

**Notes/deviations:** one addition beyond the walkthrough stanza — `container_name: toolbox`, matching this file's existing convention (every service pins a container_name). Environment written in list form (`- KEY=value`) rather than the walkthrough's map form, again matching the file's existing style. No other deviations.

**Verified by AI:** YAML parses; toolbox has no ports; healthcheck/env/depends_on all present as specified. (Docker itself isn't runnable in my sandbox — runtime proof is yours below.)

**Timothy's verification commands (from LLM_Monitor root):**

```bash
docker compose up -d --build          # watch: toolbox reaches healthy BEFORE langchain_service starts
docker compose ps                     # toolbox: (healthy); no published ports on it
docker compose exec langchain_service python -c "import urllib.request; print(urllib.request.urlopen('http://toolbox:8080/health').status)"   # expect: 200
curl -sf http://localhost:8080/health || echo "not reachable from host (EXPECTED — internal only)"
```

Paste results here; if the four behaviors hold (ordering, healthy, 200 from inside, unreachable from host), Step 1 is verified and Step 2 (discovery client) awaits your go.

# Stage 5 (Final Results, Testing, Verification)

*(Populated at completion.)*
