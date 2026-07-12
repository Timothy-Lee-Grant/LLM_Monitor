2026_06_30_07_41-LangChain_AI_Components_Review

# Code Review — RAG / Tools / LangGraph Implementation Attempt

| | |
|---|---|
| **Date** | 30-06-2026 (07:41) |
| **Reviewer** | Senior Engineer (review pass) |
| **Scope** | `langchain_service/`: `lang_practice.py`, `lang_graph_practice.py`, `lang_tools.py`, `main.py`, `requirements.txt`, plus the new `pgvector-service` in `docker-compose.yaml` |
| **Verdict** | 🔴 **Request changes** — the service currently **cannot import or start** (multiple syntax/name errors + a missing dependency). This is expected for a first pass at five hard concepts at once; the issues are enumerable and mostly mechanical. |

---

## 1. Summary

This iteration is an ambitious reach: in one pass you attempted RAG (PGVector + embeddings), native tool use, and a LangGraph orchestration skeleton, and you added a `pgvector` container to compose. That's a lot of new surface, and the result is a set of files that don't yet run — which is *the normal outcome* of a first attempt at this much, and your comments make it very reviewable.

The single most important structural fact: **the service won't import.** `main.py` imports from `lang_practice.py`, which has syntax errors and undefined names, and imports `langchain_postgres`, which isn't installed. In Python, a broken imported module breaks everything downstream, so right now nothing in the Flask app can start. The good news is the failures are concrete and ordered; fix them top-to-bottom and you'll get back to a running service quickly.

I've split findings into **blocking (won't run)**, **correctness (will run but misbehave)**, **infrastructure**, and **what's genuinely good**. Your own comments already caught a remarkable share of these — where you did, I note it, because self-catching bugs is the skill that matters.

**Severity:** 🔴 Blocking · 🟠 Major · 🟡 Minor · 🟢 Nit · ✅ Positive

---

## 2. Blocking — the service cannot import/start

### 🔴 B1 — Missing dependency: `langchain_postgres` (and a Postgres driver)
`lang_practice.py` does `from langchain_postgres import PGVector`, but `requirements.txt` lists only flask, langchain-core, langchain-community, langchain-ollama, langgraph. The import fails at startup.
**Fix direction:** add `langchain-postgres` and a driver (`psycopg[binary]`) to `requirements.txt`, rebuild the image.

### 🔴 B2 — `@tool` applied to a list, and `tool` not imported
```python
@tool
tool_list = [FindWeather, TellTime]
```
`@tool` is a decorator for a **function**, not a variable assignment, and `tool` is never imported. This is a hard `SyntaxError`/`NameError` at import. (Concept: M4 in the companion lecture — decorate each tool *function*, with a docstring.)

### 🔴 B3 — Undefined names in `Init()` and `TestRagSystem`
`OLLAMA_BASE_URL`, `PG_CONN`, `splitter`, `loader`, and `ChatOllama` (not imported at top) are all undefined where used. Each is a `NameError` the moment the function runs (and `ChatOllama` in `Init` fails at call time).
**Fix direction:** read config from `os.getenv(...)`, define a `connection` string for PGVector, import `ChatOllama`, and construct a real `TextSplitter` + `DocumentLoader` (see B7).

### 🔴 B4 — `search_kwargs{"k":4}` missing `=`
```python
retriever = store.as_retriever(search_kwargs{"k":4})   # SyntaxError
```
Should be `search_kwargs={"k": 4}`.

### 🔴 B5 — `ChatPromptTemplate(...)` constructed wrong + missing commas
In both `TestRagSystem` and `TestToolUseSystem` you call `ChatPromptTemplate(("system", ...), ("user", ...))` with **missing commas between tuples** (e.g., the `{chunks}` line has no trailing comma) and using the **constructor instead of `.from_messages([...])`**. Both are syntax/usage errors. (Concept: M3.)

### 🔴 B6 — `global` declared at module scope; `Init()` writes locals
```python
global lModel        # no effect at module level
def Init():
    lModel = ...      # local; discarded on return → module lModel stays unset
```
Even after the syntax errors are fixed, `lModel`/`store` will be `NameError`/`None` in the functions that use them. (Concept: M2 — declare `global lModel, store` *inside* `Init`.)

> **Net effect of B1–B6:** `import lang_practice` throws, so `main.py` throws, so Flask never starts. These are the "get one file to import" blockers.

---

## 3. Correctness — would misbehave once it imports

### 🟠 C1 — `chunks` is a list of `Document` objects, not text
`retriever.invoke(userMessage)` returns `List[Document]`. Dropping it into a `{chunks}` prompt slot won't render usefully. Join `doc.page_content` into a string first. (Concept: M3.)

### 🟠 C2 — Prompt placeholder vs. invoke key mismatch
`TestRagSystem` template uses `{chunks}` but `chain.invoke({"message": userMessage})` supplies `message` and not `chunks` → missing-variable error. Supply a key for **every** placeholder. (Concept: M3.)

### 🟠 C3 — Manual tool-call parsing is the wrong approach
`TestToolUseSystem` asks the model to print a tool name as a string, then inspects `res[0] != '{'`, extracts a name it doesn't know how to parse (`tool_name = _`), and indexes `tool_list[foundIndex]` (`foundIndex` undefined). You flagged this yourself. Replace with `lModel.bind_tools(tool_list)` → structured `tool_calls`, and a dispatch dict `{name: fn}` to execute. (Concept: M4.)

### 🟠 C4 — `createdPrompt.append(...)` — templates aren't lists
You can't append messages to a `ChatPromptTemplate`. In the native loop you accumulate a **message list** and re-invoke the model on it. (Concept: M4.)

### 🟠 C5 — Tools lack docstrings/decorator → unusable as tools
In `lang_tools.py`, `FindWeather`/`TellTime` have no `@tool` and no docstrings, so a model can't be told what they do or call them. `TellTime()` also takes no args (fine), but both need typed signatures + docstrings. (Concept: M4.)

### 🟠 C6 — LangGraph graph is incomplete and runs at import time
`lang_graph_practice.py`:
- `MyState` is undefined — `StateGraph(MyState)` needs a `TypedDict` schema (Concept: M5).
- `policy_check_fn` returns a bare `True`, but the conditional edge reads `s["violated"]`; nodes must return **state-update dicts** (you noticed this mismatch). `retrieve_fn`/`agent_fn` are empty `pass` stubs.
- No entry point (`add_edge(START, ...)`) and no edges connecting `retrieve`/`agent` → the graph isn't wired.
- `app.invoke({...})` runs at **module top level** with `msg`/`uid` undefined → crashes on import. Guard with `if __name__ == "__main__":`.

### 🟡 C7 — `lang.py invoke_langchain` still returns `model.response`
The mock path returns a nonexistent attribute (should be `response.content`). `/api/chat` calls it, so that endpoint is broken even apart from the above. Carried from earlier reviews.

### 🟡 C8 — `OpenAiInvokation` defects (unused but real)
`os.environ["OPENAI_API_KEY"] = 7` (int → `TypeError`; also a secret shouldn't be a literal), `from_message` (should be `from_messages`), `gpt-40-mini` (typo for `gpt-4o-mini`). Carried from the last review.

---

## 4. Infrastructure — the new `pgvector-service`

### 🟠 I1 — pgvector added, but nothing connects to it
Good that you added `pgvector/pgvector:pg16`. But:
- It has **no port, no healthcheck, and no `depends_on` wiring** from `langchain_service`.
- `langchain_service` gets `OLLAMA_BASE_URL` but **no `PG_CONN`/database URL env**, so the Python (B3) has nothing to read.
- `environment: [POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB]` is the *pass-through* form — it forwards those vars from your shell/`.env`, but your project `.env` defines `APP_Name/APP_ENV/APP_PORT`, not those — so they'll be empty and Postgres won't init correctly.
**Fix direction:** set explicit `POSTGRES_*` values (from a gitignored env), add a `pg_isready` healthcheck, give `langchain_service` a `PG_CONN`/connection-string env and `depends_on: { pgvector-service: { condition: service_healthy } }`.

### 🟠 I2 — No embedding model is pulled
RAG needs `nomic-embed-text` in Ollama, but your model-puller only pulls the chat model. First embedding call will stall/download.
**Fix direction:** pull the embedding model in the puller job too.

### 🟡 I3 — No `CREATE EXTENSION vector` / ingestion ownership
You correctly worried (in comments) "I don't see how I'm creating a schema or putting data in." PGVector can create its tables, but the `vector` extension must be enabled once per DB, and ingestion (load→split→embed→store) is an app step that needs a real `DocumentLoader` + `TextSplitter`. None exist yet. (Concept: prior full-system lecture §3.)

### 🟡 I4 — Carried infra items
dotnet port still `5000:80` vs `8080`; Flask `debug=True` in container; `slim-buster` EOL base; unpinned Python deps; no `.dockerconfig`/`.dockerignore`. All from prior reviews, still open.

---

## 5. What's good (✅)

- ✅ **You reached for the right components.** `OllamaEmbeddings`, `PGVector`, `as_retriever`, `bind`-style tools, `StateGraph`/conditional edges — these are the correct building blocks. The *selection* is right; the wiring is what's off.
- ✅ **pgvector container added** with a named volume (`pgdata`) — correct persistence instinct.
- ✅ **You separated concerns into files** (`lang_practice`, `lang_graph_practice`, `lang_tools`) — good structure for experimentation.
- ✅ **Test endpoints per capability** (`/test`, `/test/rag`, `/test/tool_use`) — continuing the incremental-verification habit. Smart.
- ✅ **Exceptionally honest comments.** You self-caught the global/lifetime issue, the policy-return-vs-state mismatch, the string-parsing smell, and even linked it to your DSA gap. Self-diagnosis at this rate is the strongest signal in this review.
- ✅ **`TestingMethod` still works** — it's the one proven, correct path (real LCEL chain → Ollama). Use it as your known-good anchor.

---

## 6. Required actions (in order)

**Get it importing/running again:**
- [ ] B1 add `langchain-postgres` + `psycopg[binary]` to requirements
- [ ] B2 decorate tool *functions* with `@tool` (+ import) instead of `@tool` on a list
- [ ] B3 define/import `OLLAMA_BASE_URL`, `PG_CONN`, `ChatOllama`, splitter, loader
- [ ] B4 `search_kwargs={"k":4}`
- [ ] B5 `ChatPromptTemplate.from_messages([...])` with commas
- [ ] B6 `global lModel, store` *inside* `Init()`

**Make it behave:**
- [ ] C1–C2 format `Document.page_content`; match invoke keys to placeholders
- [ ] C3–C5 switch to `bind_tools` + dispatch dict; docstring the tools
- [ ] C6 define `MyState`, make nodes return dicts, add `START` edge, guard `__main__`
- [ ] C7 `return response.content` in the mock path

**Infra:**
- [ ] I1 wire pgvector (creds, healthcheck, `PG_CONN`, depends_on); I2 pull `nomic-embed-text`; I3 extension + ingestion.

---

## 7. Reviewer's note

Don't read "the service won't start" as a step back — read it as five hard concepts attempted simultaneously, which is genuinely a lot. The right move now is to **shrink the blast radius**: comment out the RAG/tool/graph imports in `main.py`, confirm the service boots with just `TestingMethod` (your known-good path), then re-introduce *one* capability at a time — RAG first (get pgvector wired and one document retrieved), then tools (via `bind_tools`), then LangGraph (one node, then the chain). Prove each with its `/test/...` endpoint before adding the next, and commit each green state. The companion concepts lecture explains the *why* behind every fix above; work them together. Ambitious iteration — now make it boot.

*No source files were modified as part of this review.*
