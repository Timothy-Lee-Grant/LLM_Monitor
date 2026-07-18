# Observability: Startup & Guided Tour

How to start the full observability stack and watch one request flow through
every pillar — logs, metrics, traces, and LLM-layer capture. Written as a tour:
do it once end-to-end and you'll know where everything lives.

Concepts behind everything here: `Documentation/concepts_documentation/019-...`
(and 018 for the theory). Decision log: `Documentation/AI_Implementation_Plans/002-...`.

---

## 1. Start it

```bash
./build.sh --mode mock --obs        # lightweight models + full observability
# or
./build.sh --mode live --obs        # real Ollama models + full observability
```

`--obs` adds the observability compose profile (10 extra containers) and sets
`OBSERVABILITY_ENABLED=true` for the app services. Without it, none of this
exists and the system runs exactly as before — that's the design.

**First boot is slow, on purpose to be patient with:** image pulls, Langfuse
database migrations (~1–3 min), and the startup chain (pgvector healthy →
langchain ingests + healthy → gateway starts → OpenWebUI). Check readiness:

```bash
docker compose -p llm_monitor ps          # langchain_service should show (healthy)
bash scripts/observability_check.sh       # automated PASS/FAIL; waits for readiness itself
```

## 2. Where everything is

| UI | URL | Login |
|---|---|---|
| OpenWebUI (chat) | http://localhost:3000 | — |
| Gateway | http://localhost:5000 | — |
| langchain (dev/test path) | http://localhost:5001 | — |
| Grafana (dashboards) | http://localhost:3001 | anonymous admin (local only) |
| Langfuse (LLM traces) | http://localhost:3002 | `timothy@localhost.dev` / `local-dev-password-1` |
| Prometheus (metrics) | http://localhost:9090 | — |
| Jaeger (traces) | http://localhost:16686 | — |

## 3. The tour: one request through all four pillars

Send exactly one request through the gateway:

```bash
curl -s -X POST localhost:5000/api/llm/graph/rag \
  -H "Content-Type: application/json" \
  -d '{"user_message":"Am I allowed to use scripting tools for automation?"}'
```

Now find it, four times:

**(1) Logs — the diarist.**
```bash
docker logs dotnet_server | grep telemetry | tail -1
```
One structured line: method, path, status, elapsed_ms, and `trace_id=...`.
**Copy that trace_id** — it's your ticket to the next pillar.

**(2) Traces — the private investigator.**
Open Jaeger (http://localhost:16686), paste the trace_id into the search box
(or: Service → `gateway` → Find Traces → newest). You should see ONE tree,
TWO services:

```
gateway: POST /api/llm/graph/rag
└─ gateway: POST (the YARP hop — this span injected the traceparent header)
   └─ langchain_service: POST /graph/rag        ← Flask continued the same trace
      └─ langchain_service: pipeline.dispatch    (llm.pipeline_id, tokens, latency)
         └─ langchain_service: rag.retrieve      (rag.k, rag.results, rag.top_score)
```

Click spans and read their attributes — `rag.top_score` on retrieve is the
number that will eventually tune `score_threshold`.

**(3) Metrics — the accountant.**
Prometheus (http://localhost:9090): query `llm_requests_total` — your request
is one increment on the `pipeline_id="graph-rag", status="success"` series.
Then Grafana (http://localhost:3001) → "LLM Monitor" dashboard. One request
barely moves a rate graph, so give it a heartbeat:

```bash
for i in $(seq 1 20); do for p in chat/basic chat/rag graph/basic graph/rag; do
  curl -s -o /dev/null -X POST localhost:5000/api/llm/$p \
    -H "Content-Type: application/json" -d '{"user_message":"dashboard traffic"}'; done; done
```

Within ~15s: RED row alive per pipeline (rate, errors, p50/p95). Token panels
stay at zero in mock mode (mock reports honest zeros); run live to see them move.

**(4) LLM layer — Langfuse.**
http://localhost:3002 → log in → Traces → newest. Open it: the fully RENDERED
prompt (system text with retrieved context injected), the completion, nested
observations for the graph nodes (retrieve → agent → respond), tags
(`graph-rag`), and metadata carrying `prompt_version` and `thread_id`.
This is the pillar that answers "why did it SAY that."

**Full circle:** chat in OpenWebUI (http://localhost:3000, pick an
`llm-monitor.*` model) and watch the same message surface in all four places.

## 4. Eval data flowing

```bash
# machinery check (mock, anywhere):
docker exec langchain_service python -m eval.eval_retrieval --tier plumbing
docker exec langchain_service python -m eval.eval_judge --tier plumbing

# real numbers (live mode):
docker exec langchain_service python -m eval.eval_retrieval --tier quality --save-baseline
docker exec langchain_service python -m eval.eval_judge --tier quality --calibration
```

Quality-tier judge scores also appear in Langfuse (Scores) when the push
succeeds; the JSON report in `eval/reports/` is always the source of truth.
Commit `eval/baselines/*` — committed baselines arm the CI regression gate.

## 5. Shutting down / running light

```bash
docker compose -p llm_monitor --profile "*" down    # everything off
./build.sh --mode mock                              # run WITHOUT observability (default-light)
```

## 6. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Gateway unreachable right after startup | Startup chain still assembling (gateway starts only after langchain is healthy). `docker compose -p llm_monitor ps`, wait, retry. The check script waits for you. |
| Langfuse health fails on first boot | Migrations take 1–3 min. `docker logs langfuse_web --tail 20`. Crash-looping instead? Env-var name drift — diff against the reference compose linked in docker-compose.yaml. |
| Two separate traces instead of one tree | traceparent propagation broke on the YARP hop — check `OBSERVABILITY_ENABLED=true` on BOTH app services (`docker exec <svc> env | grep OBS`). |
| Empty gateway panel in Grafana | OTel semconv metric-name drift: check the real name at `localhost:5000/metrics`, fix the expr in `observability/grafana/dashboards/llm_monitor.json` (provisioned read-only — edit the file, not the UI). |
| Counters bounce between scrapes | Prometheus multiprocess dir problem — see `app/metrics.py` docstring; verify `PROMETHEUS_MULTIPROC_DIR` is set in the container. |
| Token panels flat | Mock mode reports zeros by design. Run `--mode live`. |
