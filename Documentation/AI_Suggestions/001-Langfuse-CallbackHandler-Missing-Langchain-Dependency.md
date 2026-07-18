2026_07_18_16_23-Langfuse-CallbackHandler-Missing-Langchain-Dependency

# Problem

`langchain_service` never sends generations to Langfuse (pillar 4 of the
observability tour in `observability/README.md`), even though logs (pillar 1),
traces (pillar 2, Jaeger), and metrics (pillar 3, Prometheus) all work
correctly. `scripts/observability_check.sh` fails exactly one criterion:

```
--- Criterion (c): Langfuse captured generations ---
  FAIL: Langfuse API returns at least one trace (verify prompt/chunks visually in UI)
```

# Root cause

`app/observability.py` (`get_langchain_callbacks()`, ~line 54) does:

```python
from langfuse.langchain import CallbackHandler
_langfuse_handler = CallbackHandler()
```

This import is lazy — it only runs when `OBSERVABILITY_ENABLED=true` and
`LANGFUSE_PUBLIC_KEY` is set, i.e. only under `./build.sh --obs`. When it
does run, it throws:

```
ModuleNotFoundError: No module named 'langchain'
```

`langfuse` (installed version 4.14.0) ships `langfuse/langchain/CallbackHandler.py`,
which contains a hard `import langchain` at module load time — it uses
`langchain.__version__` to branch its internal behavior between LangChain v0
and v1 message/agent types. This is a real dependency of Langfuse's
LangChain/LangGraph integration, not incidental.

Your `langchain_service/requirements.txt` intentionally avoids the full
`langchain` metapackage — the whole pipeline is built on `langgraph` +
`langchain-core` only (checked: `app/graph/build_graph.py`,
`app/graph/nodes.py`, `app/models/factory.py`, `app/rag/vector_store.py`,
etc. all import from `langchain_core.*`, never `langchain`). That's a fine
architectural choice on its own — `langchain-core` is the lighter,
framework-agnostic package. The gap is just that Langfuse's callback
integration doesn't honor that boundary; it needs the metapackage present
even if your code never imports it directly.

Because the exception happens inside `get_langchain_callbacks()` with no
try/except around the import, it currently raises an unhandled error
(`ERROR in FlaskServer: Unhandled error` in the container logs) whenever a
request under `--obs` tries to attach the callback — meaning any pipeline run
that calls this function is silently losing its Langfuse instrumentation for
that request.

# Fix

**Step 1 — add the dependency.**
In `langchain_service/requirements.txt`, add a line for `langchain` near the
other `langchain-*` entries:

```
langchain-core
langchain
langchain-community
#langchain-openai
langchain-ollama
langgraph
langchain-postgres
langfuse
```

Leave it unpinned like its neighbors (the file doesn't pin any of the
`langchain-*` family), so pip resolves a version compatible with the
`langchain-core==1.4.9` / `langgraph==1.2.9` already installed — that should
land on the `langchain` v1.x line, which is the branch
`CallbackHandler.py` checks for (`langchain.__version__.startswith("1")`).

**Step 2 — rebuild the langchain_service image** so the new dependency is
actually installed (a running container won't pick up a requirements.txt
change on its own):

```bash
./build.sh --mode live --obs
```

**Step 3 — verify.** Send a request through the gateway and check the
container no longer logs the `ModuleNotFoundError`:

```bash
curl -s -X POST localhost:5000/api/llm/graph/rag \
  -H "Content-Type: application/json" \
  -d '{"user_message":"test langfuse callback"}'

docker logs langchain_service --tail 30 | grep -i langfuse
```

Then re-run the acceptance check — criterion (c) should flip to PASS:

```bash
bash scripts/observability_check.sh
```

Or check visually: http://localhost:3002 (`timothy@localhost.dev` /
`local-dev-password-1`) → Traces → newest trace should show the rendered
prompt and nested graph-node observations.

# Secondary observation (not blocking, worth knowing)

`langfuse_worker`'s logs show repeated Redis socket timeouts on background
housekeeping queues (`data-retention-queue`, `blobstorage-integration-queue`,
`posthog-integration-queue`, etc.) — roughly 30s-timeout errors, cycling
continuously:

```
error  Queue job data-retention-queue errored: Error: Socket timeout.
Expecting data, but didn't receive any in 30000ms.
```

These are Langfuse's own internal maintenance/integration queues (retention
cleanup, third-party integrations like PostHog/Mixpanel/Slack you haven't
configured, blob storage export) — not the ingestion path that actually
receives your traces. They don't appear to block criterion (a)/(b)/(d) above
and are a known chatty pattern in Langfuse v3's self-hosted worker when
optional integrations are unconfigured. Worth keeping an eye on after the
Step 1 fix lands: if trace ingestion itself (the queue actually named
something like `ingestion-queue` or `trace-upsert-queue`) shows the same
timeout, that would point to a real `langfuse-redis` connectivity problem
worth its own investigation (check `REDIS_AUTH` / `REDIS_PORT` env
consistency between `langfuse-web`, `langfuse-worker`, and the
`langfuse-redis` container's `--requirepass` flag in `docker-compose.yaml`).
If it's only the housekeeping queues, it's safe to ignore for a local
learning setup.
