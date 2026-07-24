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

### [Timothy — 2026_07_19_18_05] Step 1 VERIFIED; Step 2 granted

All four behaviors held on his machine: `toolbox` container `Up (healthy)` with `8080/tcp` and **no published ports**; `langchain_service` healthy and started after it; in-network probe returned `200`; host curl failed as expected ("not reachable from host — EXPECTED — internal only"). Full `docker compose ps` shows the toolbox coexisting with the obs stack (22h uptime on those) without disturbance. Said "start next step."

### [AI — 2026_07_19_18_05] Step 2 complete — tool discovery client

**Changed:**

1. `langchain_service/requirements.txt`: added `langchain-mcp-adapters==0.3.0` (pinned — the only pin in the file, see debt note below), with a comment explaining why this one is pinned.
2. New `langchain_service/app/tools/toolbox_client.py` (first inhabitant of the empty `app/tools/` package): `build_toolbox_client()` — `MultiServerMCPClient` with `transport="streamable_http"` and `os.environ["TOOLBOX_URL"]` (KeyError if unset, fail-loudly per D5 style); `discover_tools()` — sync startup-time wrapper via `asyncio.run()`, with a docstring explaining exactly why that's safe at startup and unsafe inside a request path. No `__init__.py`, matching the repo's namespace-package convention.

**Version verification done before pinning (not just "latest"):** downloaded the 0.3.0 wheel and inspected it — (a) `transport: Literal["streamable_http"]` confirmed in `sessions.py`, so the walkthrough's config key is valid for this exact version; (b) dependency constraint is `langchain-core>=1.0,<2.0`, compatible with this repo's (unpinned) resolution.

**Finding — Stage 2 question A2 is now pre-answered.** The 0.3.0 adapter constructs `StructuredTool` with only `coroutine=` (no sync `func=`): the discovered tools are **async-only**. Therefore sync `graph.invoke()` through a `ToolNode` would raise, and the Step 3 spike collapses to a decision: the `graph-tools` pipeline runs via `graph.ainvoke` wrapped in `asyncio.run(...)` at the pipeline boundary. Will still be proven by test in Step 3, but we now know the answer before writing the graph.

**Debt noted (not acted on — out of 003 scope):** `requirements.txt` is otherwise entirely unpinned, which contradicts the repo's own honest-CI lesson. Candidate for a small future plan: pin the full file from a `pip freeze` of a known-good build.

**Timothy's verification commands (rebuild required — requirements changed):**

```bash
docker compose up -d --build langchain_service
docker compose exec langchain_service python -c "from app.tools.toolbox_client import discover_tools; print(sorted(t.name for t in discover_tools()))"
# expect a list including: 'current_time', 'ping', 'server_info'
```

Paste the tool list here; if the three names appear, Step 2 is verified and Step 3 (`graph-tools` pipeline) awaits your go.

### [Timothy — 2026_07_19_19_10] Step 3 granted

Granted with just "Step 3" — the Step 2 discovery one-liner's output was not pasted. Bookkeeping decision (AI): Step 2's proof is folded into Step 3's verification below, which exercises discovery end-to-end anyway (the service cannot even boot `graph-tools` without a successful discovery). Noted rather than hidden.

### [AI — 2026_07_19_19_10] Step 3 complete — `graph-tools` pipeline (lean tier)

**Changed (6 files):**

1. **`app/models/factory.py`** — `MockChatModel` gains the deterministic **TOOLCALL protocol**: user message `TOOLCALL <tool_name> <json_args?>` → the mock emits exactly that tool call; last message a `ToolMessage` → the mock answers `[mock] tool result: <content>` so tests can assert the *real tool output* survived the loop. Plus `bind_tools()` as identity (the Base default raises `NotImplementedError`, which would crash mock mode at bind time). Neither trigger can fire on existing chat/RAG paths — prior behavior unchanged. This is the "extend MockChatModel" option from the plan, chosen over test-only stubs because it makes the tool loop *demoable* in mock mode through OpenWebUI, not just testable.
2. **`app/prompts/MyPromptTemplates.py`** — `get_tool_agent_system()` (a concrete `SystemMessage`, not a template — the loop's growing history can't fit fixed template slots) + `TOOL_AGENT_PROMPT_VERSION = "agent.tools@1"` per the prompt-versioning discipline.
3. **`app/graph/nodes.py`** — `make_tool_agent_node(tools)` (factory closure, async per the Step 2 finding; **accumulates** `prompt_tokens`/`completion_tokens` across loop iterations — the lean tier's cost claim depends on counting every trip, and the default reducer is last-write-wins) and `tool_respond_node` (extract-only twin of `respond_node` — the final AIMessage is already in messages).
4. **`app/graph/build_graph.py`** — `build_tool_graph(tools)`: `START → agent → (tools_condition) → tools → agent ... → respond → END`. First conditional edge in the codebase; `ToolNode`/`tools_condition` verified present in the resolved langgraph (they live in the `langgraph-prebuilt` dependency — the main wheel doesn't contain them, worth knowing). Separate builder, not a `with_tools` flag: the agent node, wiring, and sync/async model all differ.
5. **`app/orchestration/pipelines.py`** — small refactor extracting `_initial_state`/`_graph_response` (shared by sync and tool graphs); `_run_tool_graph` via `asyncio.run(graph.ainvoke(...))` (safe: gunicorn sync workers have no running loop); `TOOL_RECURSION_LIMIT` env-tunable, default 8, passed per-invocation in config; `_invoke_config` gains a `prompt_version` parameter so graph-tools traces tag `agent.tools@1` instead of the assistant version; **conditional registration** (see decision below).
6. **`app/api/FlaskServer.py`** — `/graph/tools` added to the canonical route map. The map is static, so with no toolbox configured the route 404s with the contract's `unknown_pipeline` error — the correct answer for "capability not configured".

**DECISION made during implementation (deviation-level, flagged):** eager discovery at import (Stage 2 A3) collided with honest CI — the unit suite imports `pipelines` with no containers, and `test_registry` asserts the exact pipeline set. Resolution: **registration is conditional on `TOOLBOX_URL` being set.** Compose always sets it → every real deployment discovers eagerly and fails loudly at boot (verified below). Unset (bare pytest) → the capability honestly doesn't exist: absent from registry and `/v1/models`, not silently mocked. All 40 existing unit tests pass untouched because of this.

**DEFERRED to Step 4 (noted, not forgotten):** `max_tokens` is a model-config cap; it lands with the Azure model config where it matters financially. The lean tier's cap in this step is `recursion_limit`.

**Verified by AI (in sandbox, real langgraph + mock model + stand-in async MCP-style tool):**

- Full loop: `TOOLCALL ping {"message": "e2e"}` → message trail `Human → AI(tool_calls) → Tool → AI` → final answer contains `pong: e2e`.
- No-tool path: plain question routes agent → respond directly, normal mock answer.
- Recursion cap: `recursion_limit=1` on a tool request raises `GraphRecursionError` — the runaway guard is real.
- Fail-loud: import with `TOOLBOX_URL` set to a dead endpoint → boot fails with a connection error, per A3.
- Full unit suite: **40/40 pass** with `TOOLBOX_URL` unset; unregistered `/graph/tools` returns contract-shaped `404 unknown_pipeline`.

**Timothy's verification commands (covers Step 2 + Step 3; rebuild picks up all code):**

```bash
docker compose up -d --build langchain_service
curl -s http://localhost:5001/v1/models | python3 -m json.tool | grep -B1 -A2 graph-tools
# expect: "llm-monitor.graph-tools" listed

curl -s -X POST http://localhost:5001/graph/tools -H 'Content-Type: application/json' \
  -d '{"user_message": "TOOLCALL ping {\"message\": \"e2e\"}"}' | python3 -m json.tool
# expect: response contains "pong: e2e" — the REAL toolbox executed over the compose network

curl -s -X POST http://localhost:5001/graph/tools -H 'Content-Type: application/json' \
  -d '{"user_message": "hello"}' | python3 -m json.tool
# expect: a normal mock answer (no tool call) — conditional edge's other branch
```

The middle command is the demo moment in miniature: mock model, but a **real MCP tool call across containers**. If both curls behave, Steps 2+3 are verified; Step 4 (Azure provider) then needs your portal prerequisites from the Stage 3 checklist.

### [Timothy — 2026_07_19_20_02] Step 4 granted, with a sequencing change

Rather than doing the Azure portal session now, Timothy asked: implement the Step 4 code first, do the portal work AFTER all steps are complete — and at that point have the AI produce a **concepts document** he can use to walk through the external-account creation with full understanding. Agreed arrangement:

- Code lands now against env-var *names*; `.env` values arrive later.
- Mock mode (the default) is unaffected throughout; live-without-keys fails loudly by design — so nothing is in a broken state while the portal work waits.
- Step 8 (live verification) and the acceptance criteria that require real Azure calls are **deferred until the portal session**; everything verifiable offline is verified now.
- NEW deliverable added to this plan's close-out: `Documentation/concepts_documentation/021-*` covering the Azure onboarding walkthrough (account → budget → resource → deployments → keys) plus the Step 4 concepts (provider abstraction, deployments-vs-models indirection, fail-loud config, cost guards).

### [AI — 2026_07_19_20_02] Step 4 complete (code) — Azure provider + hosted-model migration; live verification deferred

**Changed (4 files):**

1. **`langchain_service/requirements.txt`** — `langchain-openai==1.3.5` (was a commented-out stub from the project's past). Same pin discipline as Step 2: the wheel was downloaded and inspected first — `AzureChatOpenAI` reads `AZURE_OPENAI_ENDPOINT`/`AZURE_OPENAI_API_KEY`/`OPENAI_API_VERSION`, takes `azure_deployment`/`api_version`/`max_tokens`; embeddings accept `dimensions`. Requires `langchain-core>=1.4.9,<2` — compatible.
2. **`app/models/factory.py`** — the provider matrix (Stage 2 D1, revised 16_48):
   - `get_chat_model(userDesiredModel, provider=None)`: mock overrides everything; else `provider` arg (per-pipeline binding for Step 5b) → `LLM_PROVIDER` env → **default `azure`**. Branches: `azure` → `AzureChatOpenAI` (deployment-addressed; `userDesiredModel` deliberately ignored — the deployment IS the model choice, documented in-code); `openai_compat` → `ChatOpenAI(base_url=..)` for Groq/any OpenAI-protocol endpoint; `ollama` → original path **kept verbatim**; unknown → `ValueError` naming the valid set.
   - `get_embedding_model(...)`: `azure` → `AzureOpenAIEmbeddings(dimensions=768)` — **pgvector schema unchanged** (the v1 migration risk closed as designed); `openai_compat` → refuses with an explanatory error (chat-only free tiers; we don't pretend); `ollama` kept.
   - `_require_env()` — fail-loud with a subtlety found during implementation: compose's `${VAR:-}` interpolation turns unset host vars into **empty strings**, which pass a `KeyError` check while being useless. Empty counts as missing; the error names the variable and points at `.env.example`.
   - `_max_tokens()` — `LLM_MAX_TOKENS` (default 1024) applied at construction on BOTH paid branches, so no pipeline can forget the cap (the Step 3 deferral, landed).
3. **`docker-compose.yaml`** — ollama moved to `profiles: ["local-live"]` (D6 as agreed: `--profile local-live` + `LLM_PROVIDER=ollama` on the hardware-return day); langchain_service gains the 10 provider env lines (`LLM_PROVIDER` default azure, `LLM_MAX_TOKENS`, 5× `AZURE_*`, 3× `OPENAI_COMPAT_*`), all `${VAR:-}` pass-throughs from `.env`.
4. **New `.env.example`** (root) — every name, no values, portal-sourced guidance per entry, and the rotation-not-rewrite rule restated.

**Deviations/notes:**
- `build.sh` untouched (scripts out of scope): its live-mode echo "Ollama active" is now stale. Logged as debt; one-line fix whenever scripts are next opened.
- `LLM_PROVIDER` defaults to `azure` (not `ollama`): "live means hosted" is the new posture, and defaulting to ollama would silently fall back to mock when no local model answers — the exact quiet degradation this plan is against.

**Verified by AI (offline — everything not requiring a real key):**
- Full unit suite still **40/40**.
- `LLM_MODE=live` + azure + no keys → `RuntimeError: AZURE_OPENAI_ENDPOINT is required...` (fail-loud proven).
- Azure branches construct offline with fake keys: `AzureChatOpenAI` (max_tokens=1024, deployment threaded), `AzureOpenAIEmbeddings` (dimensions=768). No network at construction.
- `openai_compat` chat constructs (Groq-shaped config); embeddings refuse with the designed message; unknown provider → `ValueError`; mock override intact.
- Compose YAML parses; ollama under `local-live`; 10 env lines wired.

**Deferred to the portal session (tracked, not lost):** real Azure chat/embedding calls, OpenWebUI live demo, cost-observation — all parked in Step 8. **Re-ingestion note for that day:** switching embeddings mock→Azure requires re-ingesting RAG content (same 768-dim schema, different semantic space) — e.g. recreate the pgvector volume or force the idempotent ingestion to re-run by content-hash reset.

**Timothy's verification commands (mock mode — proves the migration didn't disturb anything):**

```bash
docker compose up -d --build langchain_service
curl -s -X POST http://localhost:5001/graph/tools -H 'Content-Type: application/json' \
  -d '{"user_message": "TOOLCALL ping {\"message\": \"still-works\"}"}' | python3 -m json.tool
# expect: "pong: still-works" — Steps 1-3 behavior unchanged under the new factory

docker compose exec langchain_service python -c "
import os; os.environ['LLM_MODE']='live'; os.environ['LLM_PROVIDER']='azure'
from app.models.factory import ModelFactory
try: ModelFactory.get_chat_model('x')
except RuntimeError as e: print('fail-loud OK:', e)"
# expect: the AZURE_OPENAI_ENDPOINT-is-required message — live stays honest until .env is filled
```

If both behave, Step 4 (code) is verified. Next: Step 5 (`graph-premium`) or Step 5b (`graph-free`) — 5b's code can also land now (env-name-only, same arrangement), with its 5-minute Groq signup joining the deferred portal batch.

### [Timothy — 2026_07_19_20_40] Step 5 granted

### [AI — 2026_07_19_20_40] Step 5 complete — `graph-premium` (full tier): policy gate + RAG + tool loop + sampled async judge

**Changed (7 files):**

1. **`app/graph/state.py`** — `policy_verdict` / `policy_reason` added to `ChatState` (only the premium graph writes them; readers use `.get()`).
2. **`app/models/factory.py`** — `MockChatModel` gains PROMPT-AWARE routing: it detects the policy-checker prompt (by its system text) and answers deterministically — `violated:` iff the user message contains the **BLOCKME** marker (the test/demo hook), else `conformance:` — and detects the judge prompt, returning a fixed parseable `5: ...` verdict from the existing `MOCK_LLM_JUDGE` pool. Deterministic on purpose: the random pool would make policy/judge tests flaky. Existing paths untouched (they never carry those system texts).
3. **`app/graph/nodes.py`** — `policy_check_node` and `blocked_node` **revived from `old_implementations/graph_policy_nodes_v1.py`** (retired plan 001; the premium tier is the compelling reason the retirement note anticipated). Kept: k=2 retrieved policy context, first-colon-only verdict parse. New: explicit **fail-open** posture on unparseable verdicts (raw text preserved in `policy_reason`; the fail-closed alternative is documented in-code as the higher-stakes choice). Also: `make_tool_agent_node` gains `include_context` — the premium agent appends retrieved chunks to its system message; the lean graph's compiled agent contains no context branch at all (build-time wiring, as always).
4. **`app/graph/build_graph.py`** — `build_premium_graph(tools)`: `START → policy → (violated?) → blocked → END | → retrieve → agent ⇄ tools → respond → END`. The judge is deliberately NOT a node — "in the graph" would mean "on the user's clock." Cost anatomy documented in the docstring: 1 policy call + capped agent loop + 0 judge calls on the clock.
5. **`app/orchestration/pipelines.py`** — `JUDGE_SAMPLE_RATE` (env, default 0.1); `_judge_response()` **reusing the plan-002 eval assets wholesale** (same `rubric.md`, same judge prompt, same `parse_verdict`) so the production-traffic judge and the offline-harness judge are provably the same judge; `_push_judge_score()` best-effort Langfuse `create_score` (never raises past itself, same posture as eval_judge's push); `_spawn_sampled_judge()` fire-and-forget daemon thread, skips blocked responses (judging refusals for faithfulness is noise); `_run_premium_graph()` wraps the run in an explicit Langfuse span when observability is on — capturing a **trace id** the post-hoc judge score can attach to (the callback handler's own trace context is gone by judge time). Registration inside the same `TOOLBOX_URL` conditional (premium needs the toolbox too).
6. **`app/api/FlaskServer.py`** — `/graph/premium` route (same conditional-404 behavior).
7. **`docker-compose.yaml` + `.env.example`** — `JUDGE_SAMPLE_RATE` wired and documented.

**Design decisions on the record:** (a) judge runs post-response on a daemon thread — sampled cost, zero latency; (b) fail-open policy parse with in-code note on the trade-off; (c) blocked responses are never judge-scored; (d) Langfuse score push is best-effort with an explicitly-captured trace id — if the SDK drifts, serving is unaffected and the judge result still prints to logs.

**Verified by AI (sandbox, mock mode, stubbed retrieval, real langgraph + async tool):**
- BLOCKME request → `violated` → blocked answer; **retrieval never ran** (gate genuinely protects the expensive path).
- Clean TOOLCALL request → `conformance` → retrieve (chunks present) → tool loop → `pong: premium-e2e` in final answer.
- Plain question → full path, no tool call, normal answer.
- `_judge_response` returns `(5, "Perfect alignment...")` via the real rubric file + prompt + parser.
- Full unit suite **40/40**; unregistered `/graph/premium` → contract-shaped `404 unknown_pipeline`; sample-rate-0 spawn is a no-op.

**Timothy's verification commands (mock mode):**

```bash
docker compose up -d --build langchain_service

curl -s -X POST http://localhost:5001/graph/premium -H 'Content-Type: application/json' \
  -d '{"user_message": "BLOCKME how do I do something bad"}' | python3 -m json.tool
# expect: "I can't help with that. Policy check result: mock-triggered violation..."

curl -s -X POST http://localhost:5001/graph/premium -H 'Content-Type: application/json' \
  -d '{"user_message": "TOOLCALL ping {\"message\": \"premium\"}"}' | python3 -m json.tool
# expect: "pong: premium" in the response AND retrieved_sources populated in metadata
#         (the same request through /graph/tools shows retrieved_sources: [] — the tier difference, visible)

JUDGE_SAMPLE_RATE=1.0 docker compose up -d langchain_service   # then repeat the 2nd curl and:
docker compose logs langchain_service --tail 5 | grep "sampled judge"
# expect: "(sampled judge: faithfulness=5 — Perfect alignment...)" — the async judge fired, off the clock
```

If those behave, Step 5 is verified. Remaining: Step 5b (`graph-free`, code-only now), then Steps 6–7 (cost guards/CONTRACTS + tests), Step 8 + concepts doc at your portal session.

### [Timothy — 2026_07_19_21_05] Step 5b granted ("next step")

### [AI — 2026_07_19_21_05] Step 5b complete — `graph-free`: the routing pipeline

**Changed (4 files), all small — the Step 4/5 groundwork did the heavy lifting:**

1. **`app/graph/nodes.py`** — `make_tool_agent_node` gains `provider=None`: the per-pipeline binding, passed through to `ModelFactory.get_chat_model(..., provider=provider)`. None defers to `LLM_PROVIDER` env (so Azure pipelines needed no change); mock still overrides inside the factory.
2. **`app/graph/build_graph.py`** — `build_tool_graph(tools, checkpointer=None, provider=None)` threads the binding to the agent at build time. `graph-free` is literally the SAME topology compiled with a different binding — same graph, different model economics, which is the routing-table point.
3. **`app/orchestration/pipelines.py`** — `_GRAPH_FREE = build_tool_graph(_TOOLBOX_TOOLS, provider="openai_compat")`; registered inside the toolbox conditional with a description stating the tier contract. Plus an honest-metadata fix: `_graph_response`/`_run_tool_graph` accept a `model_label` override so graph-free reports `OPENAI_COMPAT_MODEL` (the model that actually answered), not `LLM_MODEL`.
4. **`app/api/FlaskServer.py`** — `/graph/free` route.

No compose/.env changes needed — the `OPENAI_COMPAT_*` slots were pre-wired in Step 4.

**Note on fail-loud timing (on the record):** per-pipeline keys are checked at REQUEST time, not startup — nodes construct models per request, and a startup check for every provider would break the mock-first default. A live `/graph/free` call without Groq keys returns `_require_env`'s message naming `OPENAI_COMPAT_BASE_URL`. Consistent with the Azure pipelines; documented in-code.

**Verified by AI (sandbox):**
- Provider-binding proof: instrumented the factory and ran both graphs — free graph passes `openai_compat` on **every** loop iteration (both the tool-call emission and the post-tool answer), lean graph passes `None` (env-deferred). Tool loop produces `pong: free-e2e`.
- Full unit suite **40/40**; unregistered `/graph/free` → contract-shaped `404 unknown_pipeline`.

**Timothy's verification (mock mode — 30 seconds):**

```bash
docker compose up -d --build langchain_service
curl -s http://localhost:5001/v1/models | python3 -m json.tool | grep "llm-monitor.graph"
# expect FOUR graph pipelines now: graph-basic, graph-rag, graph-tools, graph-premium, graph-free (5 with basic)

curl -s -X POST http://localhost:5001/graph/free -H 'Content-Type: application/json' \
  -d '{"user_message": "TOOLCALL ping {\"message\": \"routed\"}"}' | python3 -m json.tool
# expect: "pong: routed", model_used: "mock-stub-provider" (mock mode) — the routing tier runs at $0
```

**The routing table, as it now stands** (this is the interview slide):

| Pipeline | Provider binding | Flow | Cost posture |
|---|---|---|---|
| `graph-tools` | env default (Azure) | agent ⇄ tools | lean: caps, no aux LLM calls |
| `graph-premium` | env default (Azure) | policy → RAG → agent ⇄ tools → sampled judge | full: 1 gate call + sampled async judge |
| `graph-free` | `openai_compat` (Groq) | agent ⇄ tools | $0: free tier, same caps |

Remaining: Step 6 (CONTRACTS tier rule + Grafana cost panel), Step 7 (formal test suite for all of the above), Step 8 + concepts document at the portal session. Your deferred portal batch is unchanged: Azure (the big session) + Groq (5 minutes).

### [Timothy — 2026_07_19_21_30] Step 6 granted ("next step")

### [AI — 2026_07_19_21_30] Step 6 complete — cost guards codified, cost made observable

**Changed (3 files):**

1. **`CONTRACTS.md`** — §4 registry table extended (Tools + Tier columns, the three conditional pipelines); new **§4a Cost-Tier Rules**: lean/free = no LLM calls beyond the capped loop; premium = one gate call + sampled off-clock judge, blocked responses never judged; evals never spend live tokens in CI (already structurally true — CI is `LLM_MODE=mock` throughout — now stated as contract); per-pipeline provider binding with truthful `model_used`. Changing a tier = contract change requiring a plan entry. §6 route table gains the three new routes with their conditional-404 semantics.
2. **`observability/grafana/dashboards/llm_monitor.json`** — new "Cost" row with two panels driven by **dashboard variables** `price_in_per_1m` / `price_out_per_1m` (defaults 0.15/0.60 = GPT-4o-mini-class; labeled CONFIRM — your 2-minute pricing-page check from the Stage 3 checklist plugs in here, no JSON editing needed): "Est. spend rate by pipeline ($/hour)" (priced token rates) and "Est. spend over dashboard time range ($)" (priced `increase()` — the after-a-demo number, with a panel note to reconcile it against Azure's own Cost analysis view: they should agree, and if they don't, the metrics are lying and THAT is the finding). Documented caveat: one price pair for all pipelines, so graph-free's line reads as "what this traffic WOULD cost on Azure".
3. **New `tests/test_cost_guards.py`** — CONTRACTS §4a as executable rules, 13 tests: caps default+override, paid constructors carry `max_tokens` (both azure and openai_compat), recursion limit default + actually raising `GraphRecursionError`; **model-call anatomy** via a counting mock — lean no-tool request = exactly 1 call, free tier same, premium conformant = exactly 2 (gate + agent), premium blocked = exactly 1 with retrieval never running, tool loop = 1 call per iteration; judge spawns off-thread at rate 1, never at rate 0, never for blocked responses, and parses via the shared eval parser.

**Verified by AI:** suite now **53/53** (40 existing + 13 new) with `TOOLBOX_URL` unset — the new tests build graphs directly, so they run in bare unit CI. Dashboard JSON re-parsed clean (13 panels).

**Timothy's verification:**

```bash
docker compose exec langchain_service python -m pytest tests/test_cost_guards.py -v   # 13 passed
# Grafana (obs profile running): http://localhost:3001 -> LLM Monitor -> Cost row
# - two price variables at the top; set them from YOUR Azure pricing page
# - mock traffic shows $0 (honest zeros); the panels come alive at the Step 8 live session
```

Remaining: Step 7 (integration tests: toolbox discovery + agent-calls-ping through the registry, factory matrix, acceptance_check line), then Step 8 + concepts doc at the portal session.

### [Timothy — 2026_07_19_21_55] Step 7 granted ("next step")

### [AI — 2026_07_19_21_55] Step 7 complete — the formal test suite

**Changed (3 files):**

1. **New `tests/test_toolbox_integration.py`** (6 tests, integration tier) — self-gating via `skipif(not TOOLBOX_URL)`: inside compose they run for real, in bare CI they SKIP visibly (skips show in output, so the tier's existence is never invisible). Contents: the walkthrough doc's two assertions verbatim (`{ping, server_info, current_time} ⊆ discovered`, agent-calls-ping → `pong: e2e` through the actual registry handler), plus premium full-path + gate (retrieval present on clean requests, absent on blocked), free-tier run with honest `model_used` label, `/v1/models` listing all three tool pipelines. What this tier proves vs the unit suite: the actual wire — MCP over streamable HTTP against the real .NET server.
2. **New `tests/test_provider_matrix.py`** (14 tests, unit tier, all offline) — every factory branch CALLED (the test_factory lesson: uncalled branches hide NameErrors behind green CI): mock overrides all four provider values; azure chat/embeddings construct with fake keys (deployment threaded, dimensions=768); **parametrized fail-loud test naming each missing Azure variable**; the empty-string-counts-as-missing compose subtlety; compat constructs/refuses-embeddings; unknown provider ValueErrors; and `provider` arg beating env — the routing mechanism itself, asserted.
3. **`scripts/acceptance_check.sh`** — (a) FIXED a stale assertion Step 7's review caught: `/v1/models` asserted *exactly the 4* original pipelines, which compose deployments now fail — updated to the 7; (b) new plan-003 section: toolbox 200 from inside the network (stdlib-python probe, same idiom as the healthcheck — no curl in python:slim), toolbox NOT reachable from host (lockdown posture as a PASS/FAIL check), and the four tier assertions (tools=pong+no retrieval, premium=pong+retrieval, premium BLOCKME=blocked+no retrieval, free=pong).

**Note (scripts touched):** the standing "don't change scripts" rule was overridden here by the plan itself — Stage 3 Step 7 explicitly includes the acceptance_check line, approved through the Stage 3 sign-off. `build.sh` remains untouched.

**Verified by AI:** unit run = **68 passed, 6 skipped** (the 6 = integration tier gating itself, exactly as designed); `bash -n` clean on the script; the new assert_json expressions validated as python.

**Timothy's verification:**

```bash
# integration tier for real, inside compose:
docker compose exec langchain_service python -m pytest tests/test_toolbox_integration.py -v   # 6 passed
# full acceptance pass:
bash scripts/acceptance_check.sh mock    # includes the 7 new plan-003 PASS lines
```

**That closes everything codeable without keys.**

### [AI — 2026_07_19_18_49, post-Step-7] Close-out concepts document delivered

Per the 20_02 arrangement, the concepts document was produced BEFORE the portal session so Timothy can walk through account creation with it open: `Documentation/concepts_documentation/021-Plan_003_Tools_Providers_Cost_Engineering_And_Azure_Onboarding_Lecture.md`. Part I lectures the plan-003 concepts (MCP/tool anatomy, async bridges, provider abstraction, cost engineering, honest agent testing); Part II is the ordered walkthrough of Timothy's remaining work (Azure phases A1–A6 with budget-first ordering, Groq, live boot + re-ingestion, and the Step 8 checklist whose evidence lands back here in Stage 4). Remaining in 003, all gated on your portal batch: Step 8 (live verification: Azure chat through OpenWebUI, `current_time` demo, judge score in Langfuse, Grafana cost row alive, spend reconciliation) and the close-out concepts document (`concepts_documentation/021`: Azure onboarding walkthrough + plan-003 concepts). When you're ready to do the Azure + Groq signups, say so and I'll produce the concepts document FIRST so you can walk through the portal with it open.

# Stage 5 (Final Results, Testing, Verification)

*(Populated at completion.)*
