# Blockworld — Engineering Concepts

*Tailored for Timothy Grant: embedded/firmware engineer → backend, distributed systems, and AI-native engineering.*
*Generated 2026-07-14 from a full read of the codebase (`server.js`, `viewer/index.html`, `config.js`, `palette.js`, `.claude/skills/*`).*

---

## 1. Executive Overview

Blockworld is small (~1,300 lines), but it is a **complete distributed agentic system in miniature**. One Node process (`server.js`) speaks two protocols at once:

```
                    ┌─────────────────────────────┐
   AI agent         │       server.js             │        browser(s)
  (Claude, Grok)    │                             │
 ┌────────────┐     │  ┌────────┐   ┌──────────┐  │     ┌─────────────┐
 │ tool calls ├──────▶│ MCP     │──▶│ world    │  │     │ viewer      │
 │ (requests) │◀──────│ (stdio) │   │ state    │  │     │ (Three.js)  │
 └────────────┘     │  └────────┘   │ Map<k,v> │  │     └──────▲──────┘
                    │               └────┬─────┘  │            │
                    │               ┌────▼─────┐  │   events   │
                    │               │ WebSocket├──────(broadcast)
                    │               │ :8080    │  │  fire-and-forget
                    │               └──────────┘  │
                    └─────────────────────────────┘
        COMMAND PLANE                                  EVENT PLANE
     request/response, 1:1                        pub/sub, 1:N, one-way
```

Why this project matters *to you specifically*: it contains, in readable form, a half-dozen patterns that appear in every system on your learning list — MCP tool design (your LLM_Monitor work), pub/sub and event-driven flow (your stated weakest area), snapshot + delta state replication (the core trick behind Kafka, Redis replication, and multiplayer games), schema-validated API contracts (zod here, your snake_case contract doc in LLM_Monitor), and graceful degradation. You can hold the entire system in your head — which makes it the ideal specimen for building intuition before you meet these patterns at production scale.

### The cast of characters

You said you like personified components. Here is the ecosystem:

| Character | Component | Personality & job |
|---|---|---|
| **The Architect** | The AI agent | Brilliant, remote, has never seen the site. Sends instructions down a private phone line. Knows *what* a castle looks like; owns no hands. |
| **The Foreman** | `server.js` MCP tools | The only one with hands and the only one holding the ledger (`blocks` Map). Takes orders, validates them, does the work, answers on the same phone line. |
| **The Town Crier** | WebSocket broadcast | Stands on the wall shouting every change to whoever is in the square. Doesn't care if anyone listens. Never waits for a reply. |
| **The Spectators** | viewer(s) | Wander into the square (connect), get handed a photo of the site so far (`snapshot`), then keep up via the crier's shouts (`place`/`batch`/`remove`). |
| **The Pattern Books** | `.claude/skills/*.md` | Sit on a shelf. Pure knowledge, zero mechanism. The Architect reads them before drawing plans. |
| **The One Dial** | `config.js` `BLOCK_SIZE` | The site's unit of measure. Everyone *asks* for it at runtime; nobody memorizes it. |

Keep these names — every module below refers to them.

---

## 2. Your Personal Mindset Shift

**How your embedded background would approach this problem:** one process, one loop. Poll for a command over UART/I2C, execute it, update a struct in RAM, maybe toggle a status LED. The "display" reads the same RAM directly. Everything is synchronous, single-owner, and tightly coupled — because on a microcontroller, that's correct.

**How this architecture actually solves it:** the same single-owner state (`blocks` Map — you'd feel at home) but with **two decoupled communication planes** around it:

1. The **command plane** (MCP over stdio) is synchronous request/response — the Architect asks, the Foreman answers. This is your familiar world.
2. The **event plane** (WebSocket broadcast) is asynchronous, one-way, and *optional*. The Foreman never waits for the Spectators. If nobody is watching, `broadcast()` returns immediately (`if (!wss) return;`). If a Spectator arrives late, they get a snapshot and catch up.

The shift: **in distributed systems, readers are decoupled from writers via events, and readers are allowed to be behind.** The viewer is *eventually consistent* with the server. Your firmware instinct says "the display must always show the real register value, now." Blockworld says "the display converges on the truth within milliseconds, and that's fine — and this tolerance is what lets us have N displays without slowing the writer down."

This single idea — *state changes become events; consumers subscribe rather than poll; the producer never blocks on consumers* — **is** Kafka, is Redis pub/sub, is event-driven microservices. You listed all three as weaknesses. Blockworld is the 400-line version of them.

One more shift, aimed at your hyperfixation observation: notice that the Architect uses `place_tube` **without knowing how rasterization works**. It describes intent (a path, two radii) and trusts the Foreman's implementation. The system is *designed* so that the caller doesn't need the callee's internals — that's what a good abstraction boundary is. Practice reading this codebase the way the Architect uses it: contract first (§3.1), internals only when the contract surprises you.

---

## 3. Deep-Dive Modules

### 3.1 MCP and the Tool Contract — how an LLM gets hands

**The why.** An LLM produces text. To act on the world it needs a vocabulary of *typed, described operations* it can invoke and get results from. The problem MCP solves is standardizing that vocabulary exchange: tool discovery, schemas, invocation, results — so any agent can drive any server.

**The theory.** MCP is JSON-RPC 2.0 over a transport (here: stdio). At startup the client asks the server to list its tools; each tool ships a **name, natural-language description, and JSON Schema** for its parameters. The description is not documentation for humans — *it is prompt engineering aimed at the model*. The schema is the contract; the description is the persuasion.

**The implementation.** Every tool in `server.js` follows one shape:

```js
server.tool(
  'world_info',
  'Report the physical scale of the world. CALL THIS FIRST, before any build…',
  {},                       // zod schema → published as JSON Schema
  async () => ok(`One block is ${gridLabel()}…`)
);
```

Three things worth internalizing:

- **Descriptions steer behavior.** `world_info` says "CALL THIS FIRST" because the #1 failure mode (documented in `skills/blockworld/SKILL.md`) is building at the wrong scale. The fix wasn't code — it was a sentence in a tool description. In AI engineering, tool descriptions are a first-class API surface. You'll use this directly in your LLM_Monitor tool loop.
- **Validation is layered.** Zod validates *shape* (`z.number().int().min(0)`), but materials are validated by hand in `checkMat()` — because a 100-value enum would bloat every tool's schema in the model's context window. Note what `checkMat` returns on failure: not an exception, but a **helpful message with near-miss suggestions** ("Did you mean: scale_green, scale_jade…?"). Error messages returned to an LLM are *self-correction fuel*. Design them for the model to recover, not for a human to read a stack trace.
- **Token/call economy is an architectural force.** See §3.3 — several design decisions here exist only because the caller pays per token and per call.

**Common mistake:** treating tool descriptions as an afterthought. **Interview relevance:** "How do you design tools for an agent?" is now a real interview question at AI-forward companies; the answer is contract design + error-as-guidance + context-window economics. **Production usage:** every MCP server you'll write for Claude/agents; function-calling APIs at OpenAI/Anthropic follow the same schema-and-description model.

### 3.2 The Sacred Channel — stdio as protocol transport

**The why.** MCP over stdio means **stdout is the wire**. The very first comment in `server.js`:

```js
 * NEVER console.log here — stdout is the MCP protocol channel.
 * Use console.error (stderr) for anything you want to see.
```

One stray `console.log("debug")` corrupts the JSON-RPC stream and kills the session — silently, from the agent's point of view.

**The theory.** This is **in-band vs out-of-band signaling**. When a channel carries framed protocol data, anything else injected into it is corruption. The fix is a second channel: stderr for diagnostics, stdout for protocol.

**Your embedded bridge.** You already know this problem intimately: it's a UART carrying a binary framing protocol. You would never `printf` debug text into the same UART mid-frame — you'd use a second UART or SWO. Same discipline, new context. Notice every log line in `server.js` is `console.error` with a `[blockworld]` prefix — that prefix is the poor man's structured logging, and the habit scales up to real log pipelines (your Langfuse/OTel roadmap).

**Common mistake:** a dependency you import calls `console.log` internally and breaks your MCP server — a real, notorious failure mode. **Interview relevance:** in-band signaling failures appear in networking questions (HTTP response splitting is the same disease). **Production usage:** every stdio-based MCP server; also why 12-factor apps log to stderr/stdout *by convention agreed with the platform*, never mixed with data output.

### 3.3 Server-Side Rasterization — declarative intent vs imperative coordinates

**The why.** A dragon is ~5,000 cubes. If the Architect had to compute and send each cube, that's 5,000 tool calls (minutes of latency, enormous token cost) and the agent would be doing geometry — a thing LLMs are bad at. The problem: **the caller's compute is scarce and expensive; the server's is abundant and free.**

**The theory.** Move work across the boundary to where it's cheap, and raise the abstraction level of the API. The client sends a *description of a form* — a path, radii, a taper — and the server rasterizes it into cubes. This is the same reasoning behind:

- SQL (send a query, not row-fetching loops),
- GraphQL (describe the shape of the data you want),
- stored procedures / server-side aggregation,
- GPU shaders (upload a program, not pixels).

**The implementation.** `place_tube` is the flagship. The agent sends ≤24 spine points plus `r_start`/`r_end`; the server sweeps a sphere along interpolated segments:

```js
const t  = (s + i / steps) / segs;          // 0..1 along the whole path
const rr = r_start + (r_end - r_start) * t; // linear taper
// … then rasterize: every grid cell within rr of the segment point
```

with a `seen` Set to deduplicate cells where segments overlap. One tool call ≈ thousands of blocks. The skill file then teaches the agent the *economics*: "A good build is **150–400 tool calls**. If you are looping `place_block` more than ~30 times, you have reached for the wrong primitive." That's an API telling its client what efficient usage looks like — the equivalent of "use the batch endpoint."

Also note `mirror`: symmetry is computed server-side (`c[axis] = 2 * plane - b[axis]`) because asking an LLM to hand-mirror coordinates *will* produce subtle errors. **Push determinism to code; leave judgment to the model.** That division of labor is a core AI-engineering principle.

**Common mistake:** chatty APIs — N+1 calls where one intent-level call would do. **Interview relevance:** "design an API for X" answers should always address call granularity and where computation lives. **Production usage:** batch endpoints, gRPC streaming, and every agent tool that accepts a *plan* instead of primitive steps.

### 3.4 The Event Plane — pub/sub, snapshot + delta, eventual consistency

*This module targets your #1 stated weakness. Read it twice.*

**The why.** The viewer must show blocks *as they land*, and there may be zero, one, or many viewers. Polling (`GET /blocks` every 100 ms) would hammer the server, waste bandwidth re-sending the whole world, and still lag. The problem: **fan-out of state changes to an unknown, dynamic set of consumers, without slowing the producer.**

**The theory.** Three composable ideas:

1. **Pub/sub:** producers emit events to a channel; subscribers receive them. Producer and consumers don't know each other. Adding a 10th viewer costs the Foreman nothing extra in design terms.
2. **Snapshot + delta replication:** a late joiner can't reconstruct state from future deltas alone. So on connect you send a **snapshot** (full current state), then the subscriber applies **deltas** (incremental events) from that point forward. This is precisely how Redis replication works (RDB snapshot, then command stream), how Kafka consumers with compacted topics bootstrap, and how every multiplayer game syncs a joining player.
3. **Eventual consistency:** between an event being emitted and applied, the viewer is stale. The system *converges* rather than being continuously exact. The producer never blocks waiting for consumers to catch up (`readyState === 1` check — if the socket isn't ready, that client simply misses out).

**The implementation.** The entire event vocabulary is five message types:

| Event | Meaning | Viewer handler |
|---|---|---|
| `snapshot` | full state, sent once on connect | `clearWorld()` then add all, **unanimated** |
| `place` | one block delta | `addBlock(…, animate=true)` |
| `batch` | many-block delta (one primitive call) | loop `addBlock` |
| `remove` | targeted deletion | `removeBlock` — surgical, no rebuild |
| `clear` | world reset | `clearWorld()` |

Producer side, `server.js`:

```js
server.on('connection', (sock) => {
  sock.send(JSON.stringify({ type: 'snapshot', blocks: [...blocks.values()] }));
});
function broadcast(msg) {
  if (!wss) return;                       // no listeners? no work.
  const payload = JSON.stringify(msg);    // serialize ONCE, send N times
  for (const c of wss.clients) if (c.readyState === 1) c.send(payload);
}
```

Two subtleties that generalize:

- **The snapshot is unanimated; deltas are animated.** The viewer passes `animate=false` for snapshot blocks. Why? Semantically, a snapshot is *history* — replaying it with drop animations would misrepresent 5,000 old blocks as new events. Distinguishing "catch-up state" from "live event" is a real concern in every event-sourced UI (think Slack loading history vs receiving a new message).
- **`remove` is targeted, not a rebuild.** The comment in the viewer says it outright: "Does NOT rebuild the world, so nothing already at rest gets re-animated." The naïve implementation (clear + re-add everything) would be *correct* but would visually re-drop the whole castle. Incremental application of deltas is both a performance and a semantics decision.

**Design question to chew on:** what happens if the network drops a `batch` message? Answer: the viewer silently diverges *until the next reconnect*, when the snapshot heals it. That is the consistency model here — deltas are best-effort, snapshots are the repair mechanism. Kafka would instead give you an offset and replayable log — durability the crier doesn't have. Knowing *which guarantees you're buying* is the distributed-systems skill.

**Common mistake:** having consumers acknowledge every event synchronously — you've reinvented blocking RPC and lost the decoupling. **Interview relevance:** "design a live dashboard / chat / multiplayer sync" — the answer is always snapshot + ordered deltas + reconnect healing. **Production usage:** Redis replication, Kafka compacted topics, Figma/Google Docs sync, game state replication, your future event-driven microservices.

### 3.5 One Source of Truth — the config dial and runtime discovery

**The why.** `BLOCK_SIZE` affects the server's reference dimensions, the viewer's mesh scale and grid, and the agent's sense of proportion. If each hardcoded its own copy, changing one would silently break the others — the classic **configuration drift** problem.

**The implementation.** Three mechanisms stack:

1. **Single definition:** `config.js` exports `BLOCK_SIZE = 0.5`, imported by both server and viewer. The comment sets the norm: *"If you find a literal '1m' anywhere, it's a bug."*
2. **Runtime discovery for the agent:** the agent can't `import` config — it lives outside the process. So it *asks*: `world_info` computes reference dimensions at runtime (`Math.round(9.0 / BLOCK_SIZE)` for a castle wall). This is service discovery in miniature: **don't bake environmental facts into the client; expose an endpoint that reports them.**
3. **Dimensionless knowledge:** the skills are written in *ratios* — "towers 3–4× wall height," "wingspan = 1.5× body length" — never metres. Ratios are scale-invariant, so halving `BLOCK_SIZE` requires zero skill edits. Engineers from physics call this **nondimensionalization**; you'd recognize it as writing firmware against `CLOCK_FREQ` instead of literal microsecond counts.

**An instructive real bug:** the README's example shows `BLOCK_SIZE = 1.0` while `config.js` says `0.5`. Docs drifted from config — proving the comment's own point that *anything duplicating the dial eventually lies*. A second one: the viewer hardcodes `ws://localhost:8080`, but the server may fall back to 8081–8083 (§3.6). The dial pattern was applied to scale but not to the port. Spotting where a codebase's own principle is inconsistently applied is exactly the "reasoning about unfamiliar systems" skill you're building.

**Interview relevance:** 12-factor config, feature flags, service discovery (Consul/etcd/K8s DNS). **Production usage:** your Docker Compose env-driven config in LLM_Monitor is the same pattern one level up.

### 3.6 Graceful Degradation — the port fallback chain

**The why.** A leftover process squatting on :8080 must not kill the MCP handshake — the Foreman's phone line matters more than the Town Crier's stage.

**The implementation.** `listenWs()` recursively tries `[8080, 8081, 8082, 8083]` on `EADDRINUSE`, and if all fail:

```js
console.error('[blockworld] no free websocket port — MCP still works, viewer disabled');
```

That line is the whole philosophy: **rank your subsystems by criticality and let the optional ones fail without taking down the essential ones.** MCP (core function) survives; the viewer (observability layer) degrades. Note also the event-driven error handling — `candidate.once('error', …)` / `candidate.once('listening', …)` — you can't try/catch an async bind failure; readiness *arrives as an event*. That's Node's event-loop model in one small function, and a gentle on-ramp to your async/await internals goal: the callback isn't run "in parallel," it's queued and run by the same single-threaded loop when the OS reports back.

On the other side, the viewer's `connect()` schedules `setTimeout(connect, 2500)` on close — an infinite retry loop with a fixed backoff, paired with the snapshot-heals-everything guarantee from §3.4. Reconnect + snapshot = crash recovery for free.

**Common mistake:** letting an optional dependency's failure crash the process (the #1 cause of cascading failures). **Interview relevance:** "what happens when X is down?" — always have a degradation story. **Production usage:** circuit breakers, health-checked optional sidecars, your Compose healthchecks.

### 3.7 Skills as Data — mechanism vs policy

**The why.** What makes a castle *fairytale* rather than *fortress*? That knowledge changes often, is subjective, and shouldn't require a server redeploy. The problem is an old one: **separating mechanism (what the system can do) from policy (what it should do)**.

**The theory.** `server.js` is mechanism: place, remove, mirror, rasterize. The `.claude/skills/*.md` files are policy: proportions, palettes, build order, failure modes. Policy lives in *data* (markdown the agent reads), so it's editable by a non-programmer, versionable in git, and hot-swappable. This is the Unix "mechanism, not policy" principle reborn as prompt engineering.

**The implementation — study how the skills teach.** They're written *defensively against known model failure modes*:

- `castle/SKILL.md`: "Left alone you will build a fortress… every element correct for a real castle and **wrong for this one**" — then five specific named errors with corrections.
- `dragon/SKILL.md`: "a crocodile with a kite attached" — then four errors ("a straight spine. Fatal.").
- Layering: `blockworld` (conventions) → `castle`/`dragon` (style) mirrors base-class → subclass, or platform docs → team runbooks.

Writing anticipated-failure-mode documentation is a transferable senior skill: it's what great runbooks, API migration guides, and code review checklists look like. And for your AI-engineering track: **a skill file is a unit-tested prompt** — the "budget" numbers (150–400 calls) and ratio tables are assertions the author derived from watching real builds fail.

**Interview relevance:** "how do you make agent behavior reliable?" — constrain with tools (mechanism), steer with retrieved knowledge (policy), and encode observed failure modes explicitly. **Production usage:** RAG knowledge bases, Claude skills, system-prompt libraries — the fastest-growing artifact type in AI engineering.

### 3.8 The Viewer's Inner Loop — reconciliation, O(1) indexes, and camera ownership

**The why.** The viewer must apply an unbounded event stream to a 3D scene at 60 fps without stutter, on the browser's single thread.

**The implementation — three patterns worth stealing:**

- **A keyed index for O(1) reconciliation.** `index: Map<"x,y,z" → mesh>` mirrors the server's `blocks` Map. Placement replaces any existing mesh at the key; removal is a single lookup. Without the index, every remove would be an $O(n)$ scan of scene children. Same idea as React's keyed reconciliation or a DB primary key: **identity enables cheap diffs.**
- **Animation as data, not control flow.** A falling block isn't a running coroutine — it's an entry in the `falling` Map (`{mesh, rest, start}`). Each frame, `tick()` computes progress from wall-clock time (`(now - f.start) / DROP_MS`, cubic ease-out) and writes the position. Hundreds of concurrent animations cost one loop; there are no timers or threads per block, and a block that gets removed mid-fall is just a Map delete. This is how game engines and UI frameworks all work internally, and it's a concrete answer to "how does concurrency exist on one thread?" — *state machines advanced by a single loop*, the same shape as async/await's state-machine transformation you want to understand.
- **Camera ownership — a tiny coordination protocol.** `userHasCamera` arbitrates between two would-be controllers of one resource (auto-framer vs human). User input claims it (`controls.addEventListener('start', …)`); `clearWorld()` and `reframe()` release it. Without the flag, the auto-framer "fights every zoom you make." Two writers, one resource, explicit ownership token — that's a mutex in street clothes, and the UX bug it prevents is a livelock.

**Common mistake:** spawning a timer/`setInterval` per animated object — death by a thousand callbacks. **Interview relevance:** event-loop questions, "how would you render a live-updating list efficiently." **Production usage:** every game loop, React reconciliation, and the mental model you need before Kubernetes controllers (which are also "reconcile observed state against desired state in a loop").

---

## 4. Mental Sandbox & Next Steps

These are ordered by proximity to your goals. Each is designed so you *design first, code second*.

### Challenge 1 — Two Architects, one site (distributed systems)

Point two agents at the server simultaneously, both building. Today: last-write-wins per coordinate (`blocks.set` just overwrites), and `mirror`/`clear` operate on *global* state — Agent A's `clear` vaporizes Agent B's half-built dragon.

Design questions: How would you scope operations per-agent (sessions? build regions? optimistic locking per bounding box?)? What ordering guarantees does the event plane need so viewers see a consistent interleaving? Sketch the solution three ways — pessimistic locking, region leases, CRDT-style merge — and write down what each costs. *This is a CAP-flavored exercise you can actually run on your laptop.*

### Challenge 2 — The Foreman's ledger survives a restart (event sourcing)

Kill the server mid-build and everything is gone (`blocks` is in-memory). Add persistence two ways and compare: (a) periodic snapshots to disk; (b) an **append-only event log** of every mutation, replayed on boot. Then combine them (snapshot + log tail = how Kafka, Postgres WAL, and Redis AOF+RDB all actually work). Bonus: once you have the log, implement `undo` — and notice that undo of `place_box` requires knowing what each cell held *before* (the log needs prior state or inverse events). That discovery is the heart of event-sourcing design.

### Challenge 3 — Fix the port-discovery bug (service discovery, and shipping a small PR)

The server falls back through ports 8081–8083, but the viewer only ever dials 8080 (§3.5). Fix it properly: have the viewer try the same port list, or better, add a tiny HTTP endpoint (or a file, or a query param) through which the server *publishes* its chosen port — a real service-discovery mechanism, 30 lines. This one is deliberately small: practice using the abstraction (ws, three.js) without spelunking its internals first. Timebox the internals-reading to zero. Ship it working; *then* allow yourself one hour of reading if curiosity demands it. That ordering — working integration first, depth second — is the exact skill you flagged wanting to build.

### Where this connects to LLM_Monitor

Blockworld's tool-description discipline (§3.1) and error-as-guidance (`checkMat`) apply directly to your LangGraph tool loop. The snapshot+delta plane (§3.4) is the pattern for streaming agent progress to OpenWebUI over SSE. And the skills-as-policy split (§3.7) is an argument for keeping your agent's domain knowledge in versioned retrievable documents rather than baked into prompts scattered through code.

---

*Suggested follow-on topics, in order: WebSocket protocol internals (framing, ping/pong) → Redis pub/sub (same pattern, networked) → Kafka (same pattern, durable + replayable) → event-sourced services. Each is the previous one plus exactly one new guarantee.*
