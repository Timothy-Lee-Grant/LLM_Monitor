2026_08_23_15_38-Reading_Logs_And_Traces_A_Worked_Incident

# Reading Logs and Traces: A Worked Incident

You asked, mid-session, staring at a wall of Docker log output and a Jaeger screenshot full of red icons: *"what does this tell me, and how should I parse it?"* That question — turning raw telemetry into a story — is a real, specific skill, and this lecture teaches it using an incident that happened live in your own system on 2026-08-23, rather than a toy example. Two genuinely different bugs were hiding in that one screenshot. Finding both, and telling them apart, is the whole lesson.

---

## Part I — The four kinds of log line, and why lumping them together makes logs feel useless

The raw dump you pasted mixed four fundamentally different *kinds* of output. Before you can read logs fast, you need to sort each line into one of these buckets on sight — it's a classification skill, not a reading-comprehension skill.

| # | Bucket | Who wrote it | Example from your paste | How much to trust/read it |
|---|---|---|---|---|
| 1 | **Framework internals** | The framework itself (ASP.NET Core, Flask's dev server, etc.) | `info: Microsoft.AspNetCore.Routing.EndpointMiddleware[0]` / `Executing endpoint 'HTTP: GET /health'` | Almost never worth reading. It's the framework narrating its own internal steps at `Information` level — "I matched a route," "I set a status code," "I serialized JSON." Pure scaffolding noise unless you suspect the *framework* itself is misbehaving. |
| 2 | **Your own application signal** | Code you wrote, deliberately | `LLM_MONITOR.server.TelemetryMiddleware[0]  telemetry method=GET path=/metrics status=200 elapsed_ms=2 trace_id=8ca263b8802d023a13c625faf8b59773` | This is gold. One structured line per request, every field greppable, a `trace_id` that lets you join it to every other service's view of the same request. This is `TelemetryMiddleware.cs` — the thing you built specifically so this line would exist. |
| 3 | **Web server access log** | The WSGI/ASGI server (gunicorn, uvicorn) — not your code | `172.18.0.2 - - [23/Aug/2026:21:57:10 +0000] "GET /metrics HTTP/1.1" 200 1689 "-" "Prometheus/3.14.0"` | Standard **NCSA Common Log Format** / "combined log format": `client_ip - user [timestamp] "METHOD path HTTP/version" status_code response_bytes "referrer" "user-agent"`. Useful for a quick eyeball of traffic patterns, but has no `trace_id` and can't be joined to anything — it's a different, older, orthogonal logging tradition. |
| 4 | **SDK / library diagnostics** | A third-party library, complaining about *its own* plumbing | `Failed to export span batch due to timeout, max retries or shutdown.` | Sounds alarming, is completely orthogonal to whether the actual user-facing request succeeded — this is the OpenTelemetry SDK's `BatchSpanProcessor` failing to *ship telemetry about a request*, not the request itself failing. Ironically, in this incident, this category turned out to matter a lot (see Part III) — the lesson isn't "always ignore this bucket," it's "know which bucket you're in before deciding how much weight to give it." |

**The habit that actually matters:** grep for `error|exception|traceback` first, skim everything else. And whenever you have a `trace_id`, `grep` it across *every* service's logs at once — that's the join key that turns "three unrelated walls of text" into "one request, three vantage points." That's literally the technique used in Part II below.

---

## Part II — Bug #1: reading a real stack trace to its root cause

### The symptom, as it appeared in Jaeger

Your screenshot showed a trace: `gateway POST /v1/{**catch-all} → gateway POST → langchain_service POST /v1/chat/completions → pipeline.dispatch → LangGraph → agent → ChatOpenAI`, every single span marked with a red `!` icon, total duration 14.45s.

### Rule #1 for reading any trace: read bottom-up

A parent span doesn't turn red because it personally failed — it turns red because **OpenTelemetry's error-propagation convention marks every ancestor of a failed span as errored too**, all the way to the root. That's *by design*: it answers "did anything go wrong inside this operation, at any depth?" at a glance, without you having to expand every child. The consequence: **the deepest red span is where the failure actually happened; everything above it is just "yes, and this broke me too."** In your trace, that's `ChatOpenAI` — a leaf span, nothing red-and-nested underneath it.

### Getting the actual error text

Jaeger *can* show the exception inline if the SDK attached it as a span event/tag (worth clicking the span and checking its "Logs" tab and `error`/`exception.message` tags next time), but the fastest path — and the one with the full traceback, not just a summary — is going straight to the source container's logs and using the `trace_id` from the Jaeger URL as your grep key:

```bash
docker compose -p llm_monitor logs 2>&1 | grep "da016c59f5cb989daabcdac6513b49da"
# ->  dotnet_server | telemetry method=POST path=/v1/chat/completions status=500 elapsed_ms=14452 trace_id=da016c59f5cb989daabcdac6513b49da
```

One line, but it's the whole confirmation: the gateway's *own* telemetry (bucket 2 from Part I — your deliberate structured log) independently confirms the exact same fact Jaeger showed graphically — `status=500`, `elapsed_ms=14452` matching the trace's `14.45s` duration to three significant figures. Two completely different observability pillars (traces vs. structured logs), same event, same numbers. That agreement *is* the four-pillar observability stack doing its job — this is the concrete version of what `Documentation/observability/README.md`'s "one request, four pillars" tour describes.

To get the traceback itself, drop the trace_id constraint and search the failing service's logs for the exception type instead:

```bash
docker compose -p llm_monitor logs langchain_service 2>&1 | grep -A3 "ERROR in FlaskServer"
```

```
[2026-08-23 21:56:46,161] ERROR in FlaskServer: Unhandled error
Traceback (most recent call last):
    raise exceptions[0]
    raise self._make_status_error_from_response(err.response) from None
openai.BadRequestError: Error code: 400 - {'error': {'message': "Tool call validation
  failed: tool call validation failed: attempted to call tool 'json' which was not in
  request.tools", 'type': 'invalid_request_error', 'code': 'tool_use_failed', ...}}
```

### The actual root cause

The model you're routing to live (`openai/gpt-oss-120b` on Groq) tried to emit a tool call to a tool literally named `"json"` — almost certainly its own internal mechanism for "I want to force structured JSON output" — but `"json"` was never one of the tools your pipeline actually registered and sent in the request's `tools` array. Groq's own server-side validation rejected the completion with a 400 before it ever got back to your code as a normal response. Your Python code didn't handle that specific `BadRequestError`, so it propagated up as an unhandled exception, which Flask's default error handler turned into a 500, which OpenTelemetry then (correctly) marked every ancestor span in the trace as errored.

This is a **live-mode, model-specific behavior bug**, not an infrastructure problem — a different model, or a version of the prompt that more strictly constrains tool use, might not trigger it. Worth knowing for the interview-story file: this is a good example of "the failure mode you have to design for with agentic/tool-calling systems" — the model's own tool-selection behavior is not fully deterministic, so production code around it needs to catch and handle exactly this class of provider-side validation error, not just the happy path.

---

## Part III — Bug #2: when the "boring" SDK-diagnostic bucket turns out to matter

Buried in the same log dump, appearing on *every single request*, not just the failing ones:

```
Transient error HTTPConnectionPool(host='langfuse-web', port=3000): Max retries
exceeded with url: /api/public/otel/v1/traces (Caused by NameResolutionError(
"Failed to resolve 'langfuse-web' ([Errno -2] Name or service not known)"))
encountered while exporting span batch, retrying in 0.99s.
```

This is bucket 4 from Part I — an OpenTelemetry SDK diagnostic, not an application error. The instinct is to ignore it. Here, ignoring it would be a mistake, because of context you already had from earlier in this same session: `langfuse_web` had been **OOM-killed** (Docker capped the VM at 3072 MiB on an 8GB-RAM machine, and Langfuse's containers alone are the heaviest slice of the `--obs` profile) and — because it has no `restart:` policy in `docker-compose.yaml` — it never came back.

**Why this produces a `NameResolutionError` specifically, not a connection-refused:** Docker Compose's embedded DNS only resolves service names for containers that are actually running. A stopped container isn't "reachable but refusing connections" (which would be a `ConnectionRefusedError`) — its hostname stops existing in DNS entirely, which is a distinct, more specific failure signature. If you ever see `NameResolutionError` for a service you know is *defined* in your compose file, your first move should be "is that container actually up?", not "check my network config" — the DNS-name-not-found error is Docker telling you the container isn't there, full stop.

**Why this matters even though nothing user-facing broke:** `langchain_service` is configured to export OpenTelemetry spans (for Langfuse's LLM-trace capture) synchronously-ish, with retries, on every request. Every one of those failed export attempts costs real wall-clock time (the `retrying in 0.99s` backoff) and fills your logs with noise that could mask a *real* error sitting right next to it — which is almost what happened here, since the tool-call bug and the DNS-failure noise were interleaved in the same log stream. This is also the same failure family documented in `Documentation/AI_Suggestions/001` (a prior Langfuse dependency issue) and its own note about distinguishing "cosmetic housekeeping-queue noise" from "an actual ingestion-path problem" — the lesson generalizes: **when a system has a background telemetry/export path, that path failing silently-but-loudly (logs but no crash) is a distinct failure mode from the request path failing, and you have to check which one you're looking at before deciding how urgent it is.**

---

## Part IV — The general algorithm, distilled

Next time you're staring at a wall of mixed logs or a red-lit trace, this is the repeatable sequence:

1. **Find the red/failed thing** (a 500 in a log, a red span in Jaeger, a non-zero exit code in `docker compose ps -a`).
2. **Get its `trace_id`** (from the Jaeger URL, or a structured log line like your `TelemetryMiddleware` output).
3. **Grep that trace_id across every service's logs at once** (`docker compose logs | grep <trace_id>`) — this is the step that turns "which of my 15 containers do I even look at" into "here's the one line from the gateway that already tells me the status and duration."
4. **In the trace view, read bottom-up** — the deepest red span is the origin; everything above it is propagated, not independent.
5. **Sort every log line you encounter into one of the four buckets from Part I** before deciding how much attention it deserves — framework noise, your own signal, access log, or SDK diagnostic — and remember bucket 4 (SDK diagnostics) is "usually safe to skim, but check whether it's masking something" rather than "always safe to ignore."
6. **Get the actual exception text from the source service's raw logs**, not just the trace UI — the UI is for navigation and shape, the container log is where the full Python/C# traceback actually lives.

---

## Common mistakes this incident illustrates

- **Treating every red icon in a trace as an independent failure.** Seven red spans in this trace were one bug, not seven — error propagation up the span tree is the mechanism, not seven separate problems to chase.
- **Ignoring "SDK diagnostic" log lines by category, instead of by content.** `Failed to export span batch` sounds like boilerplate and usually is — until you have independent reason (like a known OOM-killed dependency) to suspect it's load-bearing.
- **Reading logs top-to-bottom in arrival order instead of joining by `trace_id`.** Interleaved multi-service logs read in wall-clock order are close to unreadable during an incident; the join key is what makes them legible.

## Interview relevance

"Walk me through how you'd debug a failing request in a distributed system" is a near-universal systems-interview question, and this incident *is* the answer, concretely: trace_id-based correlation across services, reading a span tree bottom-up instead of treating every red mark as equally significant, and distinguishing a request-path failure from a telemetry-path failure that happens to be logging at the same time. Being able to say "here's a real trace_id, here's the exact grep, here's the two distinct bugs I told apart in the same five minutes of logs" is a stronger answer than describing the theory in the abstract.

## References

- `server/TelemetryMiddleware.cs` — the structured request-log line (bucket 2, Part I).
- `observability/README.md` — the four-pillar guided tour this incident is a live instance of.
- `Documentation/AI_Suggestions/001-Langfuse-CallbackHandler-Missing-Langchain-Dependency.md` — an earlier instance of "which Langfuse-adjacent error is cosmetic vs. real."
- `Documentation/AI_Suggestions/002-Post_Break_Catchup_And_MCP_Dependency_Drift.md` — the same-day `langfuse_web` OOM-kill finding that this lecture's Part III builds on directly.
