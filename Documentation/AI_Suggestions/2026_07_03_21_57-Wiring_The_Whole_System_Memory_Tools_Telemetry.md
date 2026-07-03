# AI Suggestions: Getting the System Working Holistically — with Memory, Tools & Telemetry Integrated

> **How to use this (per `CLAUDE.md`):** I give you the design, the folder responsibilities, and step-by-step instructions with illustrative code — but **I do not change your code.** You implement each step. Snippets are patterns to adapt.

You asked how to make the whole system work *holistically*, and specifically how to organize and integrate **memory, tools, and telemetry**. This doc gives you (1) the one architectural decision that makes everything else fall into place, (2) a folder-responsibility map, (3) integration designs for memory/tools/telemetry, and (4) an ordered build plan that keeps the system runnable in mock mode the whole way.

---

## 1. The decision that unblocks everything: make orchestration a LangGraph state machine

Your `ProcessNormalChatMessageRequest` is a hand-written linear function that got stuck exactly where hand-writing gets hard (the tool loop, history threading). The fix is to express the flow as a **graph**: nodes do the steps, edges decide order, and a shared **State** object carries data between them. This isn't extra complexity — it's *less*, because it replaces threaded local variables and placeholder blocks with small, independently testable pieces. It also gives you memory and telemetry seams for free.

### The target State (the shared object)
```python
# app/graph/state.py
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class ChatState(TypedDict):
    user_id: str
    user_msg: str
    desired_model: str
    violated: bool
    chunks: str                       # retrieved policy/knowledge text (already joined)
    messages: Annotated[list, add_messages]   # conversation history (auto-appends)
    answer: str
    telemetry: dict                   # per-request metrics accumulate here
```

### The graph (this replaces your function body)
```python
# app/graph/build_graph.py
from langgraph.graph import StateGraph, START, END

def build_graph(checkpointer=None):
    g = StateGraph(ChatState)
    g.add_node("policy_check", policy_check_node)
    g.add_node("retrieve", retrieve_node)
    g.add_node("agent", agent_node)          # bounded tool loop
    g.add_node("respond", respond_node)

    g.add_edge(START, "policy_check")
    g.add_conditional_edges("policy_check",
        lambda s: "blocked" if s["violated"] else "ok",
        {"blocked": END, "ok": "retrieve"})
    g.add_edge("retrieve", "agent")
    g.add_edge("agent", "respond")
    g.add_edge("respond", END)
    return g.compile(checkpointer=checkpointer)   # checkpointer = MEMORY (§3)
```
Each node is a small function `(state) -> dict` that reads and updates state — every placeholder in your current function becomes one of these. This lives in a new `app/graph/` package (you already scaffolded the folder).

**Why this first:** once the graph exists with *mock* nodes, a request flows end-to-end deterministically on your laptop. Then you make each node real one at a time. That's the holistic wiring you're after.

---

## 2. Folder responsibilities — who owns what (so you stop wondering where code goes)

You keep (correctly) asking "does this belong here?" Here's the map. Give each folder one job:

| Folder | Owns | Example |
|--------|------|---------|
| `app/api/` | HTTP layer (Flask): parse request, call the graph, shape response | `FlaskServer.py` |
| `app/graph/` | the LangGraph: `state.py`, `build_graph.py`, and the **nodes** | orchestration lives here now |
| `app/orchestration/` | a thin entry point the API calls (builds/invokes the graph) | `ProcessNormalChatMessageRequest` → just invokes the graph |
| `app/models/` | model **factory** (mock/live), the mock model | `factory.py` |
| `app/prompts/` | pure prompt templates only (no data injection) | `MyPromptTemplates.py` |
| `app/rag/` | ingestion + retrieval against pgvector | `Ingestion.py` |
| `app/tools/` | tool functions + the tool registry | §4 |
| `app/memory/` | load/save conversation history; checkpointer setup | §3 |
| `app/telemetry/` | metrics capture, correlation ids, logging | §5 |
| `app/eval/` | golden datasets, mock response fixtures, judges | move mock data here |
| `app/config/` | settings from env (one place) | connection strings, LLM_MODE |

Two immediate moves from your current code: (a) the **mock response lists** should leave `prompts/` and go to `eval/` or `models/mock_responses.py` (you noticed this); (b) `orchestration/langchain_service.py` should be deleted/absorbed — the orchestration is the graph now.

---

## 3. Integrating MEMORY

Your comments here were spot-on questions: "where do I get history? what format? would this be the memory file? do I only store user+llm messages?" Here's the professional design.

### 3a. Two kinds of memory (know the distinction)
- **Short-term (thread) memory** — the current conversation's messages. Scoped to one `thread_id` (use your `user_id` or a conversation id). This is what you inject so the model "remembers" the last turns.
- **Long-term (cross-thread) memory** — facts/preferences that persist across conversations (e.g., "this user prefers concise answers"). Optional for now.

### 3b. The clean way: let LangGraph's checkpointer do it
LangGraph has built-in persistence. A **checkpointer** saves the graph's State (including `messages`) after each step, keyed by `thread_id`, and reloads it on the next call. For production use the **Postgres checkpointer** (you already have Postgres):
```python
# app/memory/checkpointer.py
from langgraph.checkpoint.postgres import PostgresSaver
def get_checkpointer():
    return PostgresSaver.from_conn_string(CONN_STRING)   # creates its own tables

# invoking with a thread = automatic memory
graph = build_graph(checkpointer=get_checkpointer())
result = graph.invoke(
    {"user_msg": msg, "user_id": uid},
    config={"configurable": {"thread_id": uid}},   # <-- this is the memory key
)
```
With this, you do **not** manually load/append/save — the checkpointer persists `state["messages"]` per `thread_id` and restores it next time. This directly resolves your `prev_messages = _` / `.append(...)` / "store it back" struggle: **the framework threads the history for you.**

### 3c. If you'd rather do it by hand (to learn the mechanics)
Your instinct — store only `{user, llm}` turns and reload them — is correct. The manual shape:
```python
# app/memory/history.py  (backed by a Postgres table you own)
# table: conversation(id, user_id, role, content, created_at)
def load_history(user_id) -> list:      # returns [HumanMessage(...), AIMessage(...), ...]
    rows = db.query("SELECT role, content FROM conversation WHERE user_id=%s ORDER BY created_at", (user_id,))
    return [to_message(r) for r in rows]
def save_turn(user_id, user_msg, ai_answer):
    db.execute("INSERT INTO conversation(user_id, role, content) VALUES (%s,'user',%s),(%s,'assistant',%s)",
               (user_id, user_msg, user_id, ai_answer))
```
Then a node loads history into `state["messages"]` at the start and saves at the end. **Format matters:** history should be a **list of message objects** (`HumanMessage`/`AIMessage`), injected via a `MessagesPlaceholder("history")` in the respond prompt — that's "what format" the model wants.

### 3d. Don't forget the context window
Don't replay 500 messages — **window** (last N turns) or **summarize** older ones. This is both a quality and a cost lever. Start with "last 10 turns."

### 3e. Where it plugs into the graph
- Load history → part of graph state on entry (or automatic via checkpointer).
- Inject into the `respond` node's prompt via `MessagesPlaceholder`.
- Save the new turn → the checkpointer does it, or a final step calls `save_turn`.

---

## 4. Integrating TOOLS

The `....` in your function is the tool step. Here's the whole design.

### 4a. Define tools (with docstrings — the model reads them)
```python
# app/tools/registry.py
from langchain_core.tools import tool

@tool
def find_weather(city: str) -> str:
    """Get the current weather for a given city."""    # the LLM reads this to decide to call it
    return "12°C, cloudy"

@tool
def tell_time() -> str:
    """Return the current server time."""
    return "14:22"

TOOL_REGISTRY = [find_weather, tell_time]
TOOL_BY_NAME = {t.name: t for t in TOOL_REGISTRY}      # dispatch dict: string -> tool
```

### 4b. The agent node (bounded loop, native tool-calling)
Don't parse strings. Bind tools; the model returns structured `tool_calls`:
```python
# app/graph/nodes/agent.py
def agent_node(state):
    model = ModelFactory.get_chat_model(state["desired_model"]).bind_tools(TOOL_REGISTRY)
    messages = build_messages(state)             # system + history + user + chunks
    for _ in range(MAX_STEPS):                   # <-- BOUND the loop (cost/safety)
        ai = model.invoke(messages)
        messages.append(ai)
        if not ai.tool_calls:                    # model is done
            return {"answer": ai.content}
        for call in ai.tool_calls:
            result = TOOL_BY_NAME[call["name"]].invoke(call["args"])   # dispatch dict
            messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
    return {"answer": "stopped: max tool steps reached"}
```
(Or use LangGraph's prebuilt `create_react_agent(model, TOOL_REGISTRY)` and skip hand-writing the loop.)

### 4c. Safety (you'll want this for the injection-defense goal)
- **Bound** iterations + token budget (done above).
- **Least privilege / human-in-the-loop** for any tool with side effects (writes, sends). Read-only tools (weather, time) run freely.
- **Validate arguments** before executing (structured `tool_calls` already validate against the schema).

`app/tools/` owns the registry; the `agent` node in `app/graph/` owns the loop.

---

## 5. Integrating TELEMETRY (your project's namesake)

This is what makes LLM_Monitor *monitor*. Design it as a **cross-cutting concern** captured at each node, then persisted.

### 5a. What to capture (per request + per node)
- **Correlation id** — generated at the .NET edge, passed in the request body/header, threaded through everything so one conversation is traceable end-to-end.
- **Per node:** name, latency (ms), tokens in/out (when live), model used, and the decision (policy `violated`, retrieval hit count, tools called).
- **Per request:** total latency, final status, user id, timestamp.

### 5b. How to wire it cleanly (a node wrapper)
Rather than sprinkling timing code in every node, wrap nodes with a decorator that records into `state["telemetry"]`:
```python
# app/telemetry/instrument.py
import time, logging
logger = logging.getLogger("telemetry")

def instrument(node_name):
    def wrap(fn):
        def inner(state):
            t0 = time.perf_counter()
            update = fn(state)
            elapsed = (time.perf_counter() - t0) * 1000
            tel = state.get("telemetry", {})
            tel[node_name] = {"latency_ms": round(elapsed, 1)}
            logger.info("node=%s latency_ms=%.1f corr_id=%s", node_name, elapsed, state.get("corr_id"))
            update["telemetry"] = tel
            return update
        return inner
    return wrap

# usage: g.add_node("policy_check", instrument("policy_check")(policy_check_node))
```
Note: use Python's **`logging`** module (the real analog of C#'s `_logger`), not `print`. Levels + structured output route to `docker logs` now and to an OpenTelemetry collector later.

### 5c. Persist it (the queryable record)
At the end of a request, write one telemetry row to Postgres (the relational side of the DB you already run):
```
telemetry(request_id, user_id, corr_id, total_latency_ms, tokens_in, tokens_out,
          model, policy_violated, retrieval_hits, tools_used, created_at)
```
This table is what your dashboards and evals will read. `app/telemetry/` owns capture + persistence.

### 5d. The upgrade path (don't build it all now)
1. Now: structured `logging` + one Postgres telemetry row per request.
2. Next: **LangSmith** (LangChain-native tracing UI — near-zero effort, set env vars).
3. Later: **OpenTelemetry** spans → Grafana/Azure App Insights, correlated with the .NET edge.

---

## 6. The end-to-end picture (how it all connects)

```
 .NET edge ──{userId, chatMessage, corr_id}──▶ Flask /api/chat
                                                   │  builds initial ChatState
                                                   ▼
        ┌──────────────── LangGraph (checkpointer = MEMORY) ────────────────┐
        │ START ▶ policy_check ─(violated)▶ END(refuse)                      │
        │            │ ok                                                    │
        │            ▼                                                       │
        │        retrieve (RAG: pgvector) ▶ agent (TOOLS loop) ▶ respond     │
        │                                                                    │
        │  every node wrapped with TELEMETRY (latency/tokens/decisions)      │
        └──────────────────────────────┬────────────────────────────────────┘
                                        ▼
                     Postgres:  conversation (memory)  +  telemetry (metrics)
                                        │
                     Flask returns {answer, corr_id} ──▶ .NET edge ──▶ user
```
Memory = the checkpointer + conversation table. Tools = the registry + agent node. Telemetry = the node wrapper + telemetry table. All three hang off the *same* graph — which is why building the graph first is the unlock.

---

## 7. Ordered build plan (stay runnable in mock mode throughout)

**Phase A — a running skeleton (mock, no compute):**
1. Fix the import-chain blockers (mock-list order, `TryGetOllamaChatModel` name, `PGVector`/`Document`, move module-level DB setup into a function). *Verify:* service boots in `LLM_MODE=mock`.
2. Create `app/graph/state.py` + `build_graph.py` with **4 mock nodes** (each returns canned state). *Verify:* `graph.invoke({...})` returns an answer with Ollama/DB down.
3. Wire `/api/chat` → a thin `ProcessNormalChatMessageRequest` that builds + invokes the graph. *Verify:* one curl returns mock text end-to-end.

**Phase B — make nodes real, one at a time (mock model, real logic):**
4. `policy_check` node: structured output (`PolicyResult`) via a mock that returns violated/conformant by scenario. *Verify:* harmful msg routes to END.
5. `retrieve` node: real pgvector retrieval (join `.page_content`, add threshold). *Verify:* chunks appear in state.
6. `respond` node: `prompt | model | parser` with history + chunks. *Verify:* answer uses context.

**Phase C — the three integrations:**
7. **Memory:** add the Postgres checkpointer + `thread_id`. *Verify:* two calls with the same id remember prior turns.
8. **Tools:** `app/tools/registry.py` + `agent` node (bounded). *Verify:* a tool-needing message calls the tool.
9. **Telemetry:** node wrapper + telemetry table + `logging`. *Verify:* one row per request; latencies logged.

**Phase D — go live occasionally:** flip `LLM_MODE=live` on better hardware and validate with real models.

Commit a green mock-mode state after every numbered step.

---

## 8. Definition of done

- Service boots in mock mode; `/api/chat` runs the **graph** end-to-end and returns an answer with no models loaded.
- Flipping to live changes no code.
- **Memory:** same-user second request remembers the first (checkpointer + `thread_id`).
- **Tools:** the agent node calls a registered tool in a bounded loop.
- **Telemetry:** every request writes one Postgres row and logs per-node latency with a correlation id.
- Each of memory/tools/telemetry lives in its own folder with one responsibility.

When that's true, you have a holistically working system — and, not coincidentally, the exact commercial architecture from the production lecture, in miniature.

---

## Sources / further reading

- [LangGraph Persistence (checkpointers, threads) — LangChain docs](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph State Management: Checkpoints, Thread State, Failure Recovery — BetterLink](https://eastondev.com/blog/en/posts/ai/20260424-langgraph-agent-architecture/)
- [Persistent Agent Memory in LangGraph: Cross-Thread State & Stores — Focused](https://focused.io/lab/persistent-agent-memory-in-langgraph)

*No source files were modified. This document only describes changes for you to implement.*
