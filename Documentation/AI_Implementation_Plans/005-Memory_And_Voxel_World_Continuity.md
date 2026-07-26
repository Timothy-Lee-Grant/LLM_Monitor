2026_07_26_14_10-Memory_And_Voxel_World_Continuity

# Stage 1 (Design Documentation)

**Direction For This Implementation** (Timothy, 26 July 2026)

Now it is time to start integrating memory into the system so the agent can remember past messages. Two goals, stated together because the second complicates the first:

1. **Give the agent memory of past messages.** Multi-turn conversations should actually be multi-turn — the agent should remember what was said earlier in a conversation instead of every request starting from a blank slate.
2. **Account for the voxel world tool.** The AI system places blocks/block groups one after another via the Tool_Box voxel toolset, and there's a suspicion (not yet confirmed) that this requires the agent to know about past events — i.e., what it has already built — in order to keep building coherently across multiple tool calls and multiple turns. Timothy is explicitly unsure how this should work and asked for it to be researched and explained, not assumed.

Deliverable requested: an in-depth concepts document (delivered — `Documentation/concepts_documentation/023-Agent_Memory_And_Stateful_Tool_Grounding_Lecture.md`) and an implementation plan for adding memory (this document).

# Stage 2 (Discussion)

### [AI — 2026_07_26_14_10] Opening entry: what's already in place, what's actually missing, and the decisions needed

#### A. What I verified before planning anything

I read the current pipeline/graph code end to end rather than assuming, and read the Voxel toolset's C# implementation and its own design docs in the sibling `Tool_Box` repo, because "does the agent need to remember the world" is exactly the kind of question that looks obvious and isn't (see concepts doc 023, Part V, for the full reasoning — summarized here for the decisions that follow).

1. **The graph side is already wired for this, unused.** Every builder in `build_graph.py` (`build_graph`, `build_tool_graph`, `build_premium_graph`) already accepts a `checkpointer=None` parameter and passes it straight to `.compile()`. `ChatState.messages` already uses the `add_messages` reducer. `pipelines.py`'s `_invoke_config` already builds a `metadata.thread_id` key, hardcoded to `None` with the comment "populated when memory (checkpointer) arrives." Nothing here needs re-architecting — it needs *plugging in*.
2. **Nothing currently reads a `thread_id` from anywhere.** `CONTRACTS.md` §1 reserves `thread_id` as a future additive field on `ChatRequest`, but `app/orchestration/contracts.py`'s `ChatRequest` dataclass doesn't have the field, and `app/api/FlaskServer.py`'s `_parse_chat_request` doesn't read it from the request body even where it exists in the JSON. This has to be added before a checkpointer can do anything useful — a checkpointer with no stable `thread_id` per conversation just makes every request its own permanent one-message thread.
3. **The OpenAI-compatible surface is currently even more stateless than the canonical one.** `/v1/chat/completions` (the route OpenWebUI actually talks to) receives a full `messages[]` array from the client every request — OpenWebUI resends its own client-side history, standard OpenAI-protocol behavior — and `chat_completions()` currently discards all of it except the single most recent `user` message before building a `ChatRequest`. There is no `thread_id`, `chat_id`, or session identifier read from that body either. This matters for Decision C below: OpenWebUI may already be *sending* something usable as a conversation key, and I have not verified what (flagged as an implementation-time check, not a code-reading exercise I can finish from this repo alone).
4. **`VoxelWorld` is a single global singleton in the Tool_Box process — not scoped to a thread, a user, or anything else.** Confirmed directly in `ToolBox.Voxel/VoxelWorld.cs` (`AddSingleton<VoxelWorld>()`) and in Tool_Box's own design docs, which document this as an intentional, still-open v1 limitation (ADR-009: "one world, shared by every connected client... deferred rather than solved now: session-scoped state"). Consequence: a LangGraph checkpointer keyed by `thread_id` **cannot** track "what the world currently looks like" — it can only track "what this conversation believes it did." Those are different facts and can drift (another thread edits the same world; the toolbox container restarts and its in-memory `Dictionary` is wiped, unrelated to whatever durability we add here). Full reasoning in concepts doc 023 Part V — I'm not re-deriving it here, just stating the conclusion it drives: **this plan's job is conversation memory. Keeping the agent honest about world state is a separate, cheaper fix (a system-prompt / re-grounding change), not a memory-infrastructure problem.** I've scoped that fix in as Step 6 below rather than folding it into the memory work itself, because conflating the two is exactly the mistake the concepts doc warns against.
5. **Checkpointed message history, once it spans multiple requests instead of resetting every time, grows without bound unless something bounds it.** `TOOL_RECURSION_LIMIT` already bounds *one request's* tool loop (8 steps); nothing bounds a *thread's lifetime* message count. This becomes a real cost/context-window risk the moment Step 2 below ships, not a someday concern.
6. **Dependencies are already staged.** `requirements.txt` already has `langgraph`, `langchain-postgres`, and `psycopg[binary,pool]` — present but currently unused by any import in `app/`. Worth confirming at implementation time whether these were pulled in deliberately ahead of this plan or rode in as transitive dependents of something else; either way, no new package family needs adding, only version pinning per the codebase's existing "honest dependencies" convention (see plan 003's `langchain-mcp-adapters==0.3.0` precedent).

#### B. Decisions needed before Stage 3

**D1 — Where do checkpoints live?** `langchain-postgres` ships `PostgresSaver`/`AsyncPostgresSaver`. Two placement options:
   - **(a) Reuse `pgvector-service`** (a new schema/set of tables inside the existing Postgres container, created via the checkpointer's own `.setup()` call — the same "call `.setup()`, don't hand-write DDL" pattern LangGraph owns for itself). Cheapest, one fewer moving container, and matches this project's own stated discipline of not adding infrastructure until the shared version actually causes a problem (the same reasoning Tool_Box used to justify a plain `Dictionary` over a `ConcurrentDictionary` — "abstract from evidence, not imagination").
   - **(b) A dedicated new Postgres service**, mirroring the existing `langfuse_postgres` / `pgvector-service` isolation (this codebase already separates Langfuse's schema from the RAG schema specifically so one product's migrations can never touch the other's data). The counter-argument for (b): LangGraph's checkpoint tables are *this project's own* schema (unlike Langfuse, which is a whole separate vendored product), so the isolation reasoning that justified splitting Langfuse out doesn't obviously transfer.
   - **My recommendation: (a).** The risk (a) is guarding against — some future LangGraph upgrade running destructive migrations against tables it doesn't own — is real but small and caught by normal review; the container/cost/compose-complexity savings are certain and immediate.

**D2 — Rollout scope: which pipelines get a checkpointer first?** Only the `StateGraph`-based pipelines can have one at all (`graph-basic`, `graph-rag`, `graph-tools`, `graph-premium`, `graph-free`) — the two chain pipelines (`chat-basic`, `chat-rag`) are LCEL chains with no graph/state to checkpoint, and would need a different, chain-shaped memory mechanism (e.g., `RunnableWithMessageHistory`) if that's ever wanted; **out of scope for this plan** unless Timothy wants it pulled in.
   - **(a) All five graph pipelines at once.** Uniform, no "why does only one pipeline remember me" surprise for users.
   - **(b) `graph-tools` and `graph-free` first** (the two pipelines that actually drive the Voxel toolset and the ones this request was motivated by), extending to `graph-rag`/`graph-basic`/`graph-premium` as a follow-up step — additive, same growth pattern every past plan has used ("new capability = new step/registry entry, existing pipelines untouched").
   - **My recommendation: (b).** It's the smaller, faster-to-verify slice that actually answers the question Timothy asked, and the extension to the remaining graphs is mechanical once the pattern is proven on two pipelines.

**D3 — Is long-term (cross-thread) memory in scope for this plan, or a later one?** Concepts doc 023 Part III covers the Store primitive (cross-thread key-value memory, e.g. "Timothy prefers stone+brick builds") as a distinct, later capability — nothing in Timothy's Stage 1 direction asked for cross-session recall of preferences, only for the agent to remember *within* an ongoing multi-turn task.
   - **My recommendation: defer.** Ship the checkpointer (short-term/thread-scoped) here; note a Store as a named future plan rather than scope-creeping this one. Flagging explicitly because "add memory" is exactly the kind of request that quietly grows to include both if nobody draws the line.

#### C. One thing that is NOT a decision, just a needed verification step

**thread_id sourcing.** For the checkpointer to be useful through the OpenWebUI path (not just via direct curl testing with a hand-supplied `thread_id`), something needs to hand a *stable, per-conversation* identifier to `ChatRequest.thread_id` on every turn of the same chat. Candidates, to be checked against OpenWebUI's actual outgoing request body at implementation time rather than guessed here: a `chat_id`/session field OpenWebUI may already send outside the strict OpenAI schema; falling back to a server-minted UUID the first time a given `user_id` is seen with no messages history (weaker — doesn't distinguish two concurrent chats from the same user); or, if OpenWebUI sends the full `messages[]` array (which it does), hashing that array's *first* message as a cheap, stateless thread key (fragile, but zero client changes). This needs a Step of its own with a concrete "look at what actually arrives" checkpoint before committing to one mechanism — called out as Step 3 below.

---

### [Timothy — 2026_07_26_14_20] Decisions D1–D3

All three taken as recommended: **D1 = (a)** reuse `pgvector-service` (new schema, no new container); **D2 = (b)** `graph-tools` + `graph-free` first, extend later; **D3 = defer** — short-term/thread-scoped memory only in this plan, a long-term Store is a named future plan, not folded in here.

### [AI — 2026_07_26_14_20] Stage 3 follows below, built on D1(a)/D2(b)/D3(defer)

---

# Stage 3 (Implementation Planning)

Ordering rationale: the wire contract has to exist before anything can read a `thread_id` (Step 1); the *actual* source of that id has to be confirmed against OpenWebUI's real traffic before the checkpointer plumbing is built around a guess (Step 2); the checkpointer/database work is the core deliverable (Step 3–4); message-growth bounding has to land in the same slice as persistence, not after, because persistence is what makes growth possible in the first place (Step 5); the Voxel re-grounding fix is a small, separate, cheap addition scoped in during Stage 2 discussion (Step 6); tests and acceptance verification close it out (Step 7–8).

#### Step 1 — Activate `thread_id` on the wire contract

- `CONTRACTS.md` §1: promote `thread_id` from "reserved future field" to a real, documented, optional field on the canonical chat request (`string | null`; additive, per the doc's own "never rename or remove within v1" rule).
- `app/orchestration/contracts.py`: add `thread_id: str | None = None` to `ChatRequest`.
- `app/api/FlaskServer.py`: `_parse_chat_request` reads `data.get("thread_id")`; `/v1/chat/completions` reads whatever Step 2 determines OpenWebUI actually sends (placeholder pass-through until Step 2 lands, so the two steps can be built in either order without blocking each other).
- **Proof:** a request body containing `"thread_id": "abc"` round-trips into `ChatRequest.thread_id == "abc"`; a request omitting it still parses (`None`), unchanged behavior for every existing test.

#### Step 2 — Confirm the real `thread_id` source from OpenWebUI

- Inspect an actual OpenWebUI request to `/v1/chat/completions` (browser devtools network tab, or a `docker compose logs` capture of a raw request body) for any stable per-conversation identifier sent outside the strict OpenAI schema (candidates named in Stage 2 discussion C: a `chat_id`/session-shaped field; failing that, the full `messages[]` array itself as a fallback keying signal).
- Decide and document the concrete mechanism based on what's actually observed — this step is a verification checkpoint, not a code checkpoint; the finding gets written back into this document before Step 4 wires it in.
- **Proof:** a captured example request body, annotated with which field (if any) is being used as `thread_id`, committed into this Stage 3 entry as a dated finding.

#### Step 3 — Postgres checkpointer: dependency pin + schema setup

- Pin `langchain-postgres` (currently unpinned in `requirements.txt`) to the version verified against `AsyncPostgresSaver`'s actual constructor/`.setup()` API — same "pin what we verified" discipline as `langchain-mcp-adapters==0.3.0`.
- New module, `app/memory/checkpointer.py` (the existing empty `app/memory/` package is clearly a stub left for exactly this): a `build_checkpointer()` factory reading the existing `POSTGRES_*` env vars (D1: same `pgvector-service` instance, new schema — no new compose service, no new secrets), constructing an `AsyncPostgresSaver` (async, matching Step 2-of-plan-003's finding that the tool graphs are already `ainvoke`-only).
- One-time `.setup()` call to create LangGraph's own checkpoint tables — run it the same way RAG ingestion runs once at container start (`entrypoint.sh`), not per-request.
- **Proof:** after `docker compose up`, the new checkpoint tables exist in `pgvector-service` (inspectable via `psql`); a throwaway script writes and reads back one checkpoint.

#### Step 4 — Wire the checkpointer into `graph-tools` and `graph-free` (D2 scope)

- `pipelines.py`: `_GRAPH_TOOLS` and `_GRAPH_FREE` compile with `checkpointer=build_checkpointer()` instead of the current no-arg calls. `_initial_state`/`_run_tool_graph` thread `request.thread_id` into `config["configurable"]["thread_id"]`, and set the existing (currently hardcoded-`None`) `metadata.thread_id` in `_invoke_config` to the same value — both dict paths, one value, per concepts doc 023 §2.2's warning about conflating them.
- Requests with no `thread_id` fall back to a fresh, uncheckpointed run (today's behavior, unchanged) — additive, not a breaking change for existing callers/tests.
- **Proof:** two sequential `curl` calls to `/graph/tools` with the same `thread_id` — the second response demonstrably has access to the first turn's context (e.g., "what did I just ask you to build?" answered correctly); a third call with a different `thread_id` does not.

#### Step 5 — Bound message growth across a thread's lifetime

- Recommendation from concepts doc 023 Part IV: a count/token-budget **trim**, not summarization, for v1 — cheapest option, no extra LLM call, matches the codebase's "don't build what isn't needed yet" discipline. `langchain_core.messages.trim_messages` applied at the top of `tool_agent_node` (or as a LangGraph `pre_model_hook`), keeping the system message plus the most recent N messages/tokens.
- Bound is env-tunable (`MEMORY_MESSAGE_LIMIT` or similar), same pattern as `TOOL_RECURSION_LIMIT` — a cap that exists in config, not hardcoded, and is documented as a v1 simplification (summarize-and-replace is the named upgrade path if trimming loses too much, per concepts doc 023 Part IV item 2).
- **Proof:** a scripted thread that exceeds the configured limit still runs without error and without unbounded token growth; a test asserts the message list never exceeds the bound after N turns.

#### Step 6 — Voxel re-grounding (the Stage 2 A4 fix, deliberately NOT part of the memory infrastructure)

- Extend `PromptFactory.get_tool_agent_system` (or add a small conditional first-step in the tool graph) with guidance to call `describe_world`/`world_info` when resuming a thread with prior voxel-building history, rather than trusting the persisted transcript as current — the concrete mitigation concepts doc 023 Part V.3 argues for.
- Scoped narrowly: a prompt/topology change, no new infrastructure, reviewed separately from Steps 1–5 since it addresses a different failure mode (staleness against a global external singleton, not conversation continuity).
- **Proof:** a manual voxel session across two threads — build in thread A, `clear` from thread B, then ask thread A to "keep building" — the agent re-checks and notices the world is empty instead of assuming its old build still stands.

#### Step 7 — Tests

- Unit tier (no containers): checkpointer round-trip against a lightweight in-memory equivalent (`MemorySaver`) proving the *wiring* (config plumbing, `thread_id` propagation) independent of Postgres; `thread_id` parsing in both `_parse_chat_request` and the OpenAI-compatible route; message-trim bound enforcement.
- Integration tier (compose, self-skipping like `test_toolbox_integration.py`): real `AsyncPostgresSaver` round-trip against `pgvector-service`; same-thread continuity and different-thread isolation, end to end through the registry handler.
- **Proof:** new tests pass; existing suite stays green with zero regressions (same "prove nothing broke" bar every prior plan has held itself to).

#### Step 8 — Acceptance + docs close-out

- `scripts/acceptance_check.sh`: one new section asserting same-`thread_id` continuity and different-`thread_id` isolation against a live compose stack (mock mode).
- `CONTRACTS.md`: confirm §1's `thread_id` entry reads as implemented, not reserved; note the checkpointer in the pipeline registry description for `graph-tools`/`graph-free` (mirroring how cost-tier facts are already stated in each pipeline's `description`).
- Concepts document already delivered ahead of implementation (023) — no separate close-out lecture needed unless Stage 4 surfaces something genuinely new to teach.

**Acceptance criteria for this plan:**
1. A conversation through `graph-tools` or `graph-free` with a stable `thread_id` remembers prior turns after the HTTP request that created them has completed.
2. A different `thread_id` never sees another conversation's history.
3. Restarting the `langchain_service` container does not lose in-progress conversation memory (Postgres-backed, not in-process).
4. Message history growth is bounded and the bound is configurable.
5. The agent re-checks live Voxel world state when resuming a thread rather than blindly trusting its own transcript.
6. Zero regressions in the existing test suite; `chat-basic`/`chat-rag`/`graph-basic`/`graph-rag`/`graph-premium` behavior is unchanged (D2 explicitly scoped this rollout to two pipelines).

**Risks / explicitly deferred:**
- Long-term/cross-session Store (D3) — deferred to a future plan, not started here.
- Concurrent-writer hazard on the global `VoxelWorld` singleton (two threads editing it at once) — Tool_Box's own open limitation (ADR-009), out of scope for an LLM_Monitor-side plan.
- `chat-basic`/`chat-rag` (chain pipelines, not graphs) have no checkpointer story in this plan; would need a different mechanism (`RunnableWithMessageHistory`) if ever wanted.
- Extending memory to `graph-basic`/`graph-rag`/`graph-premium` is the natural Step 9+ once Steps 1–8 are proven, not committed to yet.

# Stage 4 (Implementation)

*(Populated once Stage 3 is finalized and steps are permissioned one at a time.)*

# Stage 5 (Final Results, Testing, Verification)

*(Populated at completion.)*
