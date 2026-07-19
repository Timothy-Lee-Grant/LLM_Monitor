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

# Stage 3 (Implementation Planning)

### [AI — 2026_07_19_15_46] Implementation Plan v2 (supersedes v1 per Stage 2 discussion; v1 assumed Groq — v2 targets Azure OpenAI and adds the premium tier)

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
- `ModelFactory.get_chat_model`: add `LLM_PROVIDER` branch — `azure` → `AzureChatOpenAI(azure_deployment=..., temperature=0, max_tokens=LLM_MAX_TOKENS)`; `ollama` branch kept. Add pinned `langchain-openai` to requirements.
- `get_embedding_model`: `azure` → `AzureOpenAIEmbeddings(azure_deployment=..., dimensions=768)` — pgvector schema unchanged; re-ingestion required (document why: mock and real vectors don't share a space).
- Compose: ollama moves to `local-live` profile; `live` requires the Azure env vars; `.env.example` documents names; startup fails loudly if `LLM_MODE=live` with missing key.
- Proof: `LLM_MODE=live LLM_PROVIDER=azure` chat through OpenWebUI returns a real Azure OpenAI answer through the full gateway path.

#### Step 5 — `graph-premium` pipeline (full tier; separately permissioned — may be deferred without touching other steps)

- New builder variant: policy-gate node (single cheap-model classification: allowed/blocked, reviving the retired plan-001 policy prompt) → retrieve → agent/tool loop → respond → **async sampled judge** (configurable sample rate; judge call happens after the response is committed; score written to Langfuse via the existing SDK wiring from plan 002).
- Register `graph-premium`; document the tier contract next to the registry: lean = no auxiliary LLM calls; premium = policy gate + sampled judge, each with a stated reason.
- Proof: premium request shows policy-gate span + (when sampled) a judge score attached to the trace in Langfuse; lean request shows neither.

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
7. Resume delta is real: the project now truthfully supports "Azure OpenAI (chat + embeddings), LLM tool calling via MCP, cost-tiered pipeline design with eval scoring on production traffic."

#### Risks

- **Azure onboarding friction**: resource creation, model deployment quotas, and API versioning are their own learning curve (that's partly the point); budget a session for it before Step 4 coding.
- **Tool-calling quality**: mini-class models occasionally emit malformed tool calls; the loop cap bounds the damage; escalate the deployed model only if demos actually suffer.
- **Async/sync integration** (Stage 2 A2): the known unknown; explicitly spiked in Step 3 before deep wiring.
- **Judge/policy cost creep** (premium tier): bounded by sample rate + cheap judge model; the Step 6 cost panel makes any creep visible immediately.
- **Sibling-checkout build**: `build: ../Tool_Box` requires both repos side by side on the right branch; documented in README as a prerequisite.
- **Price/quota drift**: Azure prices and free-credit terms change; verify at implementation time; the provider abstraction keeps exit costs low.

### Stage 3 Discussion Subsection

*(v1 → v2 changes are recorded in the Stage 2 entries of 2026_07_19_15_46. Discussion of Plan v2 goes here; the plan above will be revised in place as this conversation proceeds.)*

# Stage 4 (Implementation)

*(Begins after Stage 3 agreement; step-by-step permission from Timothy.)*

# Stage 5 (Final Results, Testing, Verification)

*(Populated at completion.)*
