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

**D2 — Which provider to start with (money).** Current landscape (verify limits at implementation time — free tiers move):

- **Groq free tier**: no credit card, ~30 req/min / ~1,000 req/day on `llama-3.3-70b-versatile`-class models, very fast, tool calling supported. $0.
- **Google Gemini free tier**: no credit card, generous daily quota on Flash models, 1M context, tool calling supported; Google cut free quotas in late 2025 so verify. $0.
- **OpenRouter**: one key routing to many providers including $0 community models; good as an abstraction layer but free models rotate and tool-calling quality varies per model.
- **Cheapest paid fallbacks** if a free tier's limits bite: DeepSeek or Gemini Flash-Lite class models at roughly $0.30/M input tokens or less — a full day of heavy dev chat is cents.

My recommendation: **Groq free tier first** (a real $0 budget, no card on file means a runaway loop cannot cost anything — the strongest possible cost control), Gemini free tier as the second key for A/B and rate-limit relief. Because of D1, this choice is two env vars, not a commitment. **Timothy to decide.**

**D3 — Embeddings.** Ollama also provided `nomic-embed-text`. Options:

1. **CPU embedding in-container** (e.g. `fastembed` or `sentence-transformers` with a small model): embeddings are tiny compared to LLM inference — they run fine on any laptop CPU. $0, no rate limits, but "no local AI calls" needs interpreting: if the constraint is *no GPU-class hardware*, this works; if it's *the machine can't even run small models*, it doesn't.
2. **Hosted embeddings**: Gemini's embedding endpoint has a free tier; OpenAI's `text-embedding-3-small` is ~$0.02/M tokens (effectively free at our volume). Adds a network dependency to ingestion and every RAG query.
3. Keep `DeterministicFakeEmbedding` even in live mode — rejected: live RAG answers would be retrieving on noise; worse than not having RAG.

My recommendation: option 2 (hosted, free tier) for consistency with the "this machine does no inference" posture, with option 1 as the fallback if the free embedding quota is annoying. **Timothy to decide, and to clarify how hard the "no local" constraint is.**

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

# Stage 3 (Implementation Planning)

### [AI — 2026_07_19_15_35] Implementation Plan v1 (DRAFT — pending Stage 2 decisions above; defaults assumed: Groq, hosted free-tier embeddings, ollama kept under `local-live`, eager discovery)

Ordering rationale: compose plumbing first (everything else needs a reachable toolbox), then discovery, then the graph, then the model migration (independent of tools, but verified *through* the tool demo at the end), then cost guards, then tests/verification.

#### Step 1 — Compose: toolbox service + wiring

- Add `toolbox` service per the walkthrough doc: `build: ../Tool_Box`, `AllowedHosts: "localhost;127.0.0.1;toolbox"`, curl healthcheck, **no ports**, not profile-gated.
- `langchain_service`: add `depends_on: toolbox: condition: service_healthy` and `TOOLBOX_URL=http://toolbox:8080/mcp`.
- Proof: `docker compose up` shows toolbox healthy before langchain_service starts; `docker compose exec langchain_service python -c "import urllib.request; urllib.request.urlopen('http://toolbox:8080/health')"` succeeds.

#### Step 2 — Tool discovery client

- Pin `langchain-mcp-adapters==<resolved>` in requirements.
- New module `app/tools/toolbox_client.py`: `build_toolbox_client()` reading `TOOLBOX_URL` (KeyError if unset — no silent default), `discover_tools()` wrapping the async `get_tools()` for startup use.
- Proof: inside compose, a one-liner discovery script lists `ping`, `server_info`, `current_time`.

#### Step 3 — `graph-tools` pipeline

- `build_graph` gains a tool-loop variant (`with_tools=True` or a sibling builder): `agent → (conditional: tool_calls?) → tool_node → agent`, `agent → respond` otherwise. `ToolNode(tools)` from `langgraph.prebuilt`; model bound with `.bind_tools(tools)`.
- Resolve the async question (Stage 2 A2): spike both `graph.ainvoke` under `asyncio.run` and sync invoke with adapter tools; adopt whichever is cleaner, document why.
- Set `recursion_limit` on invocation (cost guard, D4).
- Register `graph-tools` in `pipelines.py` — additive; appears in `/v1/models` automatically; instrumented for free by the registry wrapper.
- Mock-mode behavior: mock model must be able to emit a scripted tool call (extend `MockChatModel` with an optional scripted-tool-call response, or test the tool node directly — decide during implementation, per the walkthrough doc's note).

#### Step 4 — Hosted model provider (the Ollama exit)

- `ModelFactory.get_chat_model`: add `LLM_PROVIDER` branch; `openai_compat` uses `ChatOpenAI(base_url=OPENAI_COMPAT_BASE_URL, api_key=env, model=LLM_MODEL, temperature=0, max_tokens=LLM_MAX_TOKENS)`. Add `langchain-openai` (pinned) to requirements.
- `get_embedding_model`: per D3 decision (default draft: hosted embedding endpoint behind the same provider switch; embedding dimension config must match the pgvector column — document the migration note if dimension changes from 768).
- Compose: `live` profile no longer requires ollama; ollama moves to `local-live` profile; new env vars threaded through with no secrets committed (`.env.example` documents the names).
- Proof: `LLM_MODE=live LLM_PROVIDER=openai_compat` chat through OpenWebUI returns a real Groq-generated answer through the full gateway path.

#### Step 5 — Cost guards, stated and enforced

- `max_tokens` + `recursion_limit` wired (Steps 3–4) and asserted in a unit test.
- Write the cost-posture rule into CONTRACTS.md (or a short ADR): no LLM calls on the live request path beyond the agent loop; evals never run against paid/live APIs in CI.
- Grafana/token metrics already count tokens per pipeline (plan 002) — add a note (or panel) interpreting token counts as cost, so spend is *observable*, not guessed.

#### Step 6 — Tests

- Integration pytest (compose, mock mode, marked so unit CI skips): `test_toolbox_tools_discovered` (`{ping, server_info, current_time} ⊆ names`), `test_agent_can_call_ping` (`pong: e2e` reaches the final answer).
- Unit tests: factory returns the right model class per `LLM_MODE`/`LLM_PROVIDER` matrix; loud failure when live without an API key.
- `scripts/acceptance_check.sh`: add toolbox health curl.

#### Step 7 — Live verification (the demo moment)

- Through OpenWebUI on `graph-tools`, live mode: "what time is it on the server?" → agent calls `current_time` and answers with the real server time — an answer the model cannot know without the tool.
- Record actual token spend for the session from the metrics/Langfuse to confirm the cost posture (expected: $0 on Groq free tier).

#### Acceptance criteria

1. `docker compose up` (default/mock): toolbox healthy before langchain_service; existing pipelines unaffected; `graph-tools` listed in `/v1/models`.
2. Mock-mode pytest green, including both toolbox integration tests.
3. Live mode runs with zero local inference: chat works with only the hosted API reachable, ollama container not running.
4. The `current_time` demo succeeds end-to-end through the gateway.
5. No secret in git; live mode without a key fails loudly at startup, not silently mid-request.
6. Adding a toolset to Tool_Box requires zero LLM_Monitor code changes to appear in the agent (verify by rebuilding toolbox with an extra tool if convenient, or by inspection of the discovery path).

#### Risks

- **Free-tier drift**: quotas/models change without notice; mitigated by D1's provider abstraction (base URL + key swap) and by mock-default development.
- **Tool-calling quality on free models**: small/free models sometimes emit malformed tool calls; mitigate by choosing a tool-calling-capable model (llama-3.3-70b class on Groq) and capping the loop.
- **Async/sync integration** (Stage 2 A2): the known unknown; explicitly spiked in Step 3 before deep wiring.
- **Embedding dimension migration**: if the hosted embedding model isn't 768-dim, pgvector schema and re-ingestion are affected; surfaced in Step 4 as a checkpoint, not discovered in production.
- **Sibling-checkout build**: `build: ../Tool_Box` requires both repos checked out side by side on the right branch; documented in README as a prerequisite.

### Stage 3 Discussion Subsection

*(Discussion of Implementation Plan v1 goes here. The plan above will be revised in place as this conversation proceeds.)*

# Stage 4 (Implementation)

*(Begins after Stage 3 agreement; step-by-step permission from Timothy.)*

# Stage 5 (Final Results, Testing, Verification)

*(Populated at completion.)*
