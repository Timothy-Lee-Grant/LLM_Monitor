2026_07_05_21_35-Diagnosing_The_Live_Mode_Langchain_Exit_1

# Diagnosing the Live-Mode `langchain_service` Exit(1)

Symptom: `./build.sh --mode live` → all containers start → `langchain_service` is `Exited (1)` seconds later.

First, the meta-lesson: **the answer was in the logs, and the logs were lost.** `docker compose down` deletes containers *and their logs*. Next time, before tearing down:

```bash
docker logs langchain_service          # or:
docker compose -p llm_monitor logs langchain_service
```

That one command would have printed the exact traceback below. Get in the habit: container exits → read its logs → then act.

---

## The startup path in live mode

`main.py` runs: `IntializeFlaskEndpoints()` → `RunIdempotentRagIngestion()` → `app.run(...)`. The crash is inside ingestion, before Flask ever binds the port. The call chain:

```
RunIdempotentRagIngestion → InitVectorStore
  → ModelFactory.get_embedding_model("nomic-embed-text")
      → TryGetOllamaEmbeddingModel(...)        ← 💥 Crash #1
  → PGVector(embedding=..., connection_string=...)   ← 💥 Crash #2 (waiting behind #1)
```

## Crash #1 — `"streaming"` is not Ollama's parameter name (it's `"stream"`)

`Instructions.py`, `TryGetOllamaEmbeddingModel`:

```python
payload = {
    "model": desired_model,
    "streaming": False        # Ollama ignores this unknown key
}
response = requests.post(f"{base_ollama_url}/api/pull", json=payload)
if response.json().get("status", "bad") != "success":   # 💥
```

On a fresh `ollama_data` volume, `nomic-embed-text` isn't present, so this pull path runs. Because the key should be `"stream"` (your Chat variant on line ~33 uses the correct key!), Ollama defaults to streaming and returns **NDJSON** — many JSON objects separated by newlines:

```
{"status":"pulling manifest"}
{"status":"pulling 970aa74c0a90...","total":274290656,...}
...
{"status":"success"}
```

`response.json()` tries to parse that whole body as ONE JSON document → `json.decoder.JSONDecodeError: Extra data` → nothing catches it (your `try/except` only wraps the earlier GET) → exception propagates through `get_embedding_model` → `InitVectorStore` → `main.py` → **exit 1**.

**Fixes (three separate bugs in this function):**
1. `"streaming"` → `"stream"`.
2. Two lines later: `knownPulledOllamaEmbeddingModels.add(desired_model)` — that variable is a **dict** (`{}`), and dicts have no `.add`. Either make it a `set()` at the top of the file, or use dict assignment. (You'd have hit this AttributeError immediately after fixing the JSON one.)
3. The pull POST has no `timeout=None` and no try/except, unlike your chat variant. Make the two functions consistent — better yet, notice they're now ~90% identical and could be one function.

**Fun side effect to check:** even though your client crashed parsing the response, Ollama finished the pull server-side — your client read the entire stream (that's what it choked on, including the final `"status":"success"` line). The model is probably sitting in the volume right now. Verify:

```bash
docker exec ollama_service ollama list
```

If it's there, your *next* run skips the pull branch entirely and lands directly on…

## Crash #2 — `PGVector` keyword arguments are from the old API

`Ingestion.py`:

```python
vector_store = PGVector(
    embedding=embeddings,              # 💥 wrong kwarg
    connection_string=connection_string,  # 💥 wrong kwarg
    collection_name=collection_name
)
```

`langchain_postgres.PGVector`'s signature is:

```python
PGVector(embeddings=..., connection=..., collection_name=...)
```

(`embedding`/`connection_string` were the old `langchain_community.vectorstores.pgvector` names — most tutorials online still show those.) Wrong kwargs → `TypeError: __init__() got an unexpected keyword argument` → same exit(1). When in doubt, check the installed package itself, not tutorials: `docker run --rm llm_monitor-langchain_service python3 -c "import inspect, langchain_postgres; print(inspect.signature(langchain_postgres.PGVector.__init__))"`.

Also fix the default in the same file while you're there: `db_name = os.getenv("POSTGRES_DB","secret_pass")` — the fallback should be `vectordb` to match compose.

## Crash #3 — waiting at request time: the prompt constructor

Once the service boots, your first curl to `/test/langchain/chatnosecurity` will 500, because `GetHappyEncouragingAssistentPrompt` does:

```python
ChatPromptTemplate(("system", "..."), ("user", "{user_message}"))
```

`ChatPromptTemplate` doesn't take message tuples as positional args. Use:

```python
ChatPromptTemplate.from_messages([
    ("system", "You are happy and cheerful encouraging assistent."),
    ("user", "{user_message}"),
])
```

(Same fix needed in the other two prompt functions.)

## Crash #4 — also at request time, live only: ChatOllama has no base_url

`factory.py`:

```python
chatConnection = ChatOllama(model=userDesiredModel, temperature=0)
```

No `base_url` → defaults to `localhost:11434`, which inside the langchain container is the langchain container. Connection refused. Add `base_url=base_url` (you already computed it 10 lines up).

## Not a code bug, but why your curl showed nothing

```bash
curl -X POST http://localhost:5000/test/langchain/chatnosecurity ...
```

Port **5000 is the dotnet server**; Flask is published on **5001**. The dotnet server has no such route, so it returned an empty 404 (add `-i` to curl to see status codes). And of course the Flask container was already dead. Test the Flask service directly:

```bash
curl -i -X POST http://localhost:5001/test/langchain/chatnosecurity \
  -H "Content-Type: application/json" \
  -d '{"user_requested_model":"llama3.1:8b","user_id":42,"user_message":"Tell me a crispy bacon joke."}'
```

Note your request body keys are right for the new endpoint (`user_message` etc.) — good — but `"user_requested_model": "llama3"` will trigger a real Ollama pull of llama3 on first use. Use the model you actually intend (`llama3.1:8b` matches your compose default).

## One more thing you'll notice after these fixes

`/test/langgraph/chatnosecurity` currently lives **inside the big `"""..."""` comment block** in `FlaskServer.py`, so the route doesn't exist anymore. Mock-mode goal includes that endpoint — it needs to come back out (and get a real body) at some point.

## Suggested order

1. Fix `"streaming"` → `"stream"`, the dict `.add`, and the PGVector kwargs + db default.
2. Rebuild live. **Before doing anything else:** `docker logs langchain_service`. Confirm Flask prints its "Running on 0.0.0.0:5000" banner.
3. Fix `from_messages` + `base_url`, rebuild, curl port **5001**.
4. Teardown tip: your `docker compose down` (without `--profile live`) left `ollama_service` running and the network "in use". Use `docker compose -p llm_monitor --profile live down`.
