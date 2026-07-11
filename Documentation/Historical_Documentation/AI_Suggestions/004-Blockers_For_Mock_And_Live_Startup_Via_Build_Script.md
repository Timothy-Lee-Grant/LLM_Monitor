2026_07_05_21_10-Blockers_For_Mock_And_Live_Startup_Via_Build_Script

# Blockers For Mock And Live Startup Via build.sh

Goal for today: `./build.sh --mode mock` and `./build.sh --mode live` both come up cleanly, pgvector has its table, and `/test/langchain/chatnosecurity` + `/test/langgraph/chatnosecurity` return successful responses (mocked data in mock mode, real Ollama in live mode).

I traced every file in the startup path and verified syntax with `py_compile`. Below are the blockers **in the order you will hit them**. Fix them top to bottom — each one hides the next.

---

## Blocker 1 — pgvector container crashes on first boot (both modes)

`scripts/init.sql` line 12:

```sql
id UUID PRIMARY KEY DEFAULT gen_rendom_uuid(),
```

`gen_rendom_uuid` is a typo for `gen_random_uuid`. Postgres's entrypoint runs init scripts with `ON_ERROR_STOP`, so the container **exits** on this error. Since `langchain_service` has `depends_on: pgvector-service: condition: service_healthy`, nothing downstream ever starts.

**Gotcha:** init scripts only run when the `pgdata` volume is **empty**. If you've already booted pgvector once, the script won't re-run after you fix it. To force a re-init:

```bash
docker compose -p llm_monitor down --volumes   # deletes pgdata (and ollama_data!)
```

Or drop only the pg volume: `docker volume rm llm_monitor_pgdata`.

**Steps:**
1. Fix the typo in `init.sql`.
2. Remove the stale `pgdata` volume so the script re-runs.
3. Verify: `docker exec -it pgvector_service psql -U admin -d vectordb -c '\dt'` (after Blocker 2 makes those credentials real).

**Note on VECTOR(1536):** `nomic-embed-text` produces **768**-dimensional vectors, not 1536 (that's OpenAI's `text-embedding-ada-002` size). Also be aware that `langchain_postgres.PGVector` does NOT use your `corporate_policies` table — it creates its own `langchain_pg_collection` / `langchain_pg_embedding` tables. So today your hand-made table is decorative. Decide later whether you want LangChain-managed tables or raw SQL against your own table; for today, just fix the typo so the container boots.

---

## Blocker 2 — docker-compose.yaml: three `${...}` interpolations missing the `$`

`docker-compose.yaml` lines 53, 54, 59:

```yaml
- POSTGRES_PASSWORD={POSTGRES_PASSWORD:-secret_pass}   # missing $
- POSTGRES_DB={POSTGRES_DB:-secret_pass}               # missing $, and wrong default
test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-admin} -d {POSTGRES_DB:-vectordb}"]  # missing $
```

Without `$`, Compose treats these as **literal strings**. Your password becomes the literal text `{POSTGRES_PASSWORD:-secret_pass}` and your database is literally named `{POSTGRES_DB:-secret_pass}`. Meanwhile `Ingestion.py` defaults to `db_name = "secret_pass"` — note your compose default for DB is also `secret_pass`, which looks like a copy-paste slip; you probably meant `vectordb` (that's what the healthcheck default says).

**Steps:**
1. Add the `$` to all three.
2. Pick one canonical default DB name (`vectordb`) and use it in compose, the healthcheck, **and** `Ingestion.py`'s `os.getenv("POSTGRES_DB", ...)` default.
3. Compose never passes `POSTGRES_USER/PASSWORD/DB` into `langchain_service`'s `environment:` block, so the Python side always falls back to its hardcoded defaults. Add them to the `langchain_service` environment so both containers share one source of truth.
4. Verify: `docker compose -p llm_monitor config` renders the resolved file — read the pgvector section and confirm the values look right.

---

## Blocker 3 — langchain_service crash-loops at import time (both modes)

`main.py` imports `app.rag.Ingestion`, which fails on **its very first import line**, so Flask never even starts. There is a chain of import-time errors; Python stops at the first, so you'll discover them one at a time unless you fix them all now:

1. **`Ingestion.py` line 12:** `from langchain_postgres import ElephantVectorStore` — this class does not exist. The real class is `PGVector` (and its constructor signature differs: `connection=` not `connection_string=`, and the embeddings kwarg is `embeddings=` in newer versions — check the version pip resolves). "Elephant" appears to be a hallucinated name; always verify class names against the package's actual `__init__`.
2. **`Ingestion.py` line 13:** `from langchain_core import Document` — wrong path. It's `from langchain_core.documents import Document`.
3. **`factory.py` line 7:** `from app.models.Instructions import TryGetOllamaModel` — that function doesn't exist. `Instructions.py` defines `TryGetOllamaChatModel` and `TryGetOllamaEmbeddingModel`. Pick the chat one and match names.
4. **`MyPromptTemplates.py` line 69:** `MockChatTypePointers = [MockFriendlyAssistant, ...]` references lists that are only defined **below** it (lines 77+). Module-level code runs top to bottom → `NameError` at import. Move the three mock lists above the dictionary (and delete `MockChatTypePointers` — the dictionary supersedes it).
5. **`nodes.py` line 3:** `def retrieve_node(state: ChatState)` — `ChatState` is never imported. Annotations are evaluated at function-definition time, so this is a `NameError` **at import**, not at call. Add `from app.graph.state import ChatState`.

Not blocking startup but worth knowing: `OrchestrationLogic.py` and `orchestration/langchain_service.py` both have hard **syntax errors** (`....` on line 25; the dangling `ModelFactory.` on the last line). They only get away with it because nothing imports them. The moment anything does, the service dies. Don't import them until they're finished.

**Verify step 3 locally without Docker:** from `langchain_service/`, run `python3 -c "import main"` (with a venv that has the requirements installed). It should get all the way to Flask initialization without a traceback.

---

## Blocker 4 — Mock mode still tries to call Ollama (mock-specific)

`main.py` calls `RunIdempotentRagIngestion()` unconditionally, and `Ingestion.py` builds `OllamaEmbeddings` + the vector store at **module import**. In mock mode there is no ollama container (it's behind the `live` profile), so `add_documents` → embedding call → connection refused → container exits.

**Steps:**
1. In `main.py` (or inside `RunIdempotentRagIngestion`), gate ingestion: if `os.getenv("LLM_MODE") == "mock"`, skip it (or use a fake embedding class — `langchain_core.embeddings.fake.FakeEmbeddings(size=768)` exists for exactly this).
2. Consider moving the `vector_store = ...` construction out of module scope into a `GetVectorStore()` function. Module-level side effects (network connections at import) are what made this fragile — this is the same lesson as Blocker 3.4.

---

## Blocker 5 — MockChatModel cannot work as written (mock-specific)

`factory.py`, current mock path has five independent bugs:

1. `return MockChatModel` returns the **class**, not an instance. LangChain's `|` pipe will then fail. Needs `MockChatModel(...)`.
2. `_generate(self, modelType)` has the wrong signature. LangChain calls `_generate(self, messages, stop=None, run_manager=None, **kwargs)` — your `_old` version at the bottom of the file has the **correct** signature. The model type can't arrive through `_generate`; make it a field on the class (pydantic-style: `modelType: str = "friendly_assistent"`) set at construction time.
3. `BaseChatModel` has an abstract `_llm_type` property — without it, instantiation raises `TypeError`. Again, your `_old` class already does this right.
4. `random.random(0, n)` → `random.random()` takes no args. You want `random.randint(0, len(mockResponsesList) - 1)` — and note the bound must be the **length of the chosen response list**, not `number_of_chat_types` (that's the number of personas, 3, and would index out of range on the 2-item friendly list).
5. Your `_old` version has its own two typos: `ChatGeneration(messages=...)` should be `message=`, and `ChatResult(generation=[...])` should be `generations=[...]`. Don't copy those forward.

Also: `get_chat_model` checks LLM_MODE but `get_embedding_model` does not — every caller gets a real `OllamaEmbeddings` even in mock (this is half of Blocker 4).

---

## Blocker 6 — The four target endpoints are empty stubs (both modes)

`FlaskServer.py` lines 93–99: `/test/langchain/chatnosecurity` and `/test/langgraph/chatnosecurity` (and the two `/chat` variants) are just `pass`. A Flask view returning `None` raises a 500 before you even get to your own logic. This is the main construction work of the day, and it's yours to write. Shape:

- **langchain endpoint:** parse `userId`/`chatMessage` → `ModelFactory.get_chat_model(...)` → `prompt | model | StrOutputParser()` → `.invoke({"user_msg": chatMessage})` → jsonify. "No security" = skip the policy-checker chain, just the friendly assistant.
- **langgraph endpoint:** same parse → `build_graph()` → `.invoke({"user_id": ..., "user_msg": ...})` → return `result["answer"]`.

But note the langgraph path has its own prerequisites (Blocker 7), and `FlaskServer.py` has **no imports** for any of the functions its other endpoints call (`invoke_langchain`, `TestRagSystem`, `TestToolUseSystem`, `TestingMethod` are all undefined names — those routes 500 at request time). The new endpoints must import what they use.

Also `MyPromptTemplates.py`: `ChatPromptTemplate(("system", ...), ("system", ...))` is not a valid constructor call — use `ChatPromptTemplate.from_messages([("system", ...), ...])`. This bites the moment an endpoint builds a prompt.

---

## Blocker 7 — build_graph references three nodes that don't exist

`build_graph.py` uses `ChatState`, `policy_check_node`, `retrieve_node`, `agent_node`, `respond_node` — with **zero imports**, and only `retrieve_node` exists anywhere in the repo. For the "nosecurity" version today you could build a minimal graph: START → agent → respond → END (skip policy_check; retrieve is optional if mock). You need to write `agent_node` and `respond_node` in `nodes.py`, and import everything into `build_graph.py`. Fix the `chekcpointer` typo while you're in there (it works, it's just misspelled in both places consistently).

---

## Blocker 8 — Live mode: nothing ever pulls the embedding model

The `ollama-pull-model` container is commented out in compose. For the **chat** model, `TryGetOllamaChatModel` pulls on demand — fine. But `get_embedding_model` constructs `OllamaEmbeddings` directly and **never calls** `TryGetOllamaEmbeddingModel`, so `nomic-embed-text` is never pulled and the first embedding call 404s. Either call your existing TryGet function inside `get_embedding_model`, or pull manually once (`docker exec ollama_service ollama pull nomic-embed-text` — it persists in the `ollama_data` volume).

Two latent bugs in `Instructions.py` to fix when you wire it up: (a) line 86 compares `desired_model` against a list of **dicts** (`downloaded_models` is `models` raw, not names — your Chat variant does this correctly with a list comprehension); (b) `/api/pull` with `stream:false` returns `{"status":"success"}` — your check is right — but the chat variant at line 38 checks `response.json().get("status")` on a response that may be a multi-line stream if anything changes; keep `stream: False`.

Also: `ChatOllama` in `get_chat_model` (line 67) doesn't pass `base_url`, so it defaults to `localhost:11434` — inside the container that's **itself**, not the ollama container. Add `base_url=base_url` (your `_old` factory did this correctly).

---

## Blocker 9 — Smaller things that will bite after the above

1. **dotnet port mapping:** compose maps `5000:80`, but .NET 8+ listens on **8080** (your own dockerfile comment says so, and it EXPOSEs 8080). The dotnet server will start but be unreachable from the host. Change to `5000:8080`. (Doesn't block today's Flask-direct testing on `:5001`, but you said "start up all containers" — start them *usefully*.)
2. **`--gpu` flag:** `build.sh` references `docker-compose.gpu.yml`, which doesn't exist in the repo. Fine as long as you don't pass `--gpu`.
3. **Base image:** `python:3.9.13-slim-buster` — Debian Buster's apt repos are archived and Python 3.9 is EOL (Oct 2025); newer langchain/langgraph releases require Python ≥3.10, so pip may resolve old versions or fail outright. Recommend `python:3.11-slim`. Unpinned requirements + old Python is the classic "works today, breaks next build" setup.
4. **`_a = []` mutable class attribute** in `MockChatModel` — unused, delete it; on a pydantic `BaseChatModel` subclass, stray underscore attributes can also trip pydantic validation depending on version.
5. **`docker compose down` at the top of `build.sh`** runs without `--profile live`, so on some Compose versions the ollama container from a previous live run isn't torn down (`--remove-orphans` usually catches it, but check `docker ps` after a mode switch).

---

## Suggested order of attack today

1. Fix `init.sql` typo + the three `$` bugs in compose + unify DB name → `./build.sh --mode mock` → confirm `pgvector_service` is **healthy** (`docker ps`), and `psql` into it.
2. Fix the five import-chain errors (Blocker 3) → confirm `python3 -c "import main"` passes locally, then rebuild → confirm Flask answers `GET /` on `:5001`.
3. Gate ingestion for mock (Blocker 4) + repair MockChatModel (Blocker 5).
4. Implement `/test/langchain/chatnosecurity` (Blocker 6) → test with curl in mock.
5. Write the missing nodes + imports (Blocker 7) → implement `/test/langgraph/chatnosecurity` → test in mock.
6. Switch to live: fix `base_url` + embedding pull (Blocker 8) → `./build.sh --mode live` → curl both endpoints.

A curl to keep handy:

```bash
curl -s -X POST http://localhost:5001/test/langchain/chatnosecurity \
  -H 'Content-Type: application/json' \
  -d '{"userId":"space","chatMessage":"hello there"}'
```

Everything above was verified by reading the code and running `py_compile` on every module; nothing in your code was modified.
