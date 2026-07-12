12 July, 2026

# Stage 1 (Design Documentation)

**Direction For This Implementation**

This document is an outline of Documentation/concepts_documentation/018-Observability_And_AI_Evaluation_Concepts_For_Plan_002.md which was made to overview the concepts and ideas which will be needed to be understood during implementation. Read that document to get a better understanding of this implementation plan.

## General Feel

After this implementation the system should be fully wired up in a sustainable and well architectured way to capture, log, and display all telemetry data coming from the system. The telemetry data will be both the standard traditional data (such as latency, error rate, request rate) and traditional data specific to AI systems (token per request, etc). In addition to the traditional metrics and telemetry, our system will also need to produce, collect, report, display, process AI information (LLM as judge, vector database retreival judging, etc).

All of this information will need to be collected and be able to be viewable to the users.

For LangFuse operations, we should make sure to take advantage of the registry pattern we developed in the previous 001 implementation. We should attach instrumentation at the registry boundary.

Another thing that I am now thinking about is that we have not yet added tools or memory into this system. This is going to be something that we will also want to have observability for. Therefore in this implementation plan we will need to do it in such a way that allows for easy addition and integration of tools and memory. Maybe this means adding fake stubs, or it means holding off entirely on this implementation plan and working on the tools and memory plan first, then returning to this plan.

## Retrieval 

This can be done within the CI testing regularly because it will be cheap. We will be able to deterministically test the quality of retrieval of the documents from the vector database.

With the retrieval, another thing that will need to be taken into consideration with the architecutre is that I am planning on having different tables for my vector databases. One will be for documents which contain 'acceptable ai usage', this will be used to block potentially harmful user requests, another table will be a group of documents which might be useful to suplement the user's message to give a more helpful answer.

### LLM as Judge

This will be to judge the output of the responses which the user gets back for their input. 

Because the LLM is itself a model, I (Timothy) will need to provide human examples as to what kind of responses will be expected and hoped for as responses. When creating this system, give a stub document and indicate where you want me to fill in human information. I think that we will also need a rubric (or maybe what I just described is the rubric itself). I also know that there is a standard of REGAS which we want to follow and implement in this evaluation system.

When implementing this, it will need to be considered carefully from an architectural point of view because as of now our system has a placeholder 'friendly assistant' prompt, but in the future, we will be changing this so that we can have more nuanced and better responses. We might also have different type of message prompts based on parameters. So we will need to have our system be able to plan for this.

Another interesting idea which I had was for user feedback, it is mentioned in the 018-Observability_And_AI_Evaluation_Concepts_For_Plan_002.md that we can use if the user gives us a thumbs up or thumbs down to determine if the llm's answer was good or not. An idea which I had was we could also use the user's reponse message back to the llm to determine the quality of the previous message. An example of this would be if the user got Response A and then they followed up by saying "But I still don't quite understand....." This indicates that Response A was not optimal, so the follow up can indicate information about the previous message. If we use an LLM judge to look at user's follow up messages, we can have it judge the previous llm response based on degree of positive or negative. If the user says "That's not what I mean at all!" This is a much stronger negative indicator than just saying "But I still don't quite understand....." so the llm judge would rate the stronger negative response with a larger negative number. Likewise, if the user says "Thank you, I got it now." this would be a positive indicator of the previous message.

### Errors to Fix Before Starting Implementation

- When I log onto OpenWebUI, I should only and always connect to my dotnet server. I should only be able to reach my langchain test endpoints with a curl command. (Now I am thinking that I need to look into the architecture on this because is it that we are automatically reporting all endpoint pipelines which we registered to OpenWebUI, because if that is the case then this will be more difficult to change.)

But it should be the case that we are automatically connected with the dotnet endpoints.

- When I first open up my OpenWebUI on my browser, I get spammed with messages telling me that I am connected.

## In Scope

I like the ouline which was given for this plan of:

1. OTel tracing: gateway root span → traceparent propagation → Flask/registry spans → Collector → local trace backend. (C#→Python distributed trace working = the headline.)
Metrics: RED + token/latency counters per pipeline_id, Prometheus + one Grafana dashboard.

2. LLM-layer capture: prompt/chunks/tokens per invocation at the registry boundary (Langfuse, or OTel attributes to start — a genuine Stage 2 discussion: Langfuse now vs OTel-only first).

3. Golden dataset v1 (15–30 items) + retrieval metrics (hit@k, MRR) running in CI mock mode.

4. First LLM-as-judge eval (faithfulness on the golden set), nightly/manual, using your existing judge prompt.

## Out of Scope

alerting/paging, SSE streaming, security gates beyond design notes, checkpointer/memory, RAGAS-the-library (although I am confused as to why REGAS would be out if it is part of the retreival metrics)


# Stage 2 (Discussion)

---

### [AI — 2026_07_12_15_45] Opening entry: review of your Stage 1

You captured the core architecture correctly — the two-layer model, instrumentation at the registry boundary, retrieval metrics as the cheap deterministic tier, and the judge needing human calibration. Four things need correcting or sharpening, your three ideas deserve real responses, and there are five decisions to settle before Stage 3.

#### A. Corrections and clarifications

**A1 — It's RAGAS (Retrieval Augmented Generation Assessment), and your confusion is legitimate because the distinction is subtle: RAGAS is not a standard, it's a *library*.** The *metrics* it popularized (faithfulness, answer relevance, context precision/recall) are in scope — we implement them ourselves with our own judge prompt. The *library* is out of scope because computing hit@k is ~10 lines of math and faithfulness is a judge prompt you already stubbed months ago; implementing them by hand is where the understanding lives (your persona.md hyperfixation note actually works FOR you here — this is a case where going one level down is the right call). Adopting the library later is a one-day swap if we ever want its extra metrics. So nothing you need is excluded — only the dependency is.

**A2 — An honest sharpening of what 018 said about retrieval metrics in CI.** I wrote that retrieval metrics "can run in CI on every commit using the mock-mode trick." True, but there's a nuance you shouldn't miss: `DeterministicFakeEmbeddings` produces vectors with **no semantic meaning** — "scripting policy" and "banana bread" land at arbitrary distances. So in mock mode, hit@k measures the *plumbing* (dataset format parses, ranking math correct, ids line up, metric code has no bugs — deterministic, so any change in output = a real code regression), NOT retrieval *quality*. Real semantic hit@k/MRR requires live embeddings. The design consequence: **two eval tiers** — CI tier (mock, plumbing + code regression) and quality tier (live embeddings, nightly/manual, real scores). Your Stage 1 said "test the quality of retrieval within CI" — amend that to "test the retrieval *machinery* in CI; measure retrieval *quality* in the live tier."

**A3 — Your OpenWebUI worry dissolves once you separate two independent things.** You asked: "are we automatically reporting all registered pipelines to OpenWebUI... then this will be more difficult to change." Separate them: (1) *which host OpenWebUI dials* is pure config — the fix from found-issue 3 (point the saved connection at `dotnet_server:8080/v1`); after that, every OpenWebUI request transits the gateway, which is exactly the architecture you want. (2) *which models it sees* is the registry-generated `/v1/models` — but that endpoint is *served by langchain and reached through the gateway*, so "auto-reporting all pipelines" and "only connect through dotnet" are perfectly compatible. Nothing is difficult to change; nothing needs changing. The `:5001` direct path remains curl-only by convention now, enforceable later by deleting the port mapping. The toast spam is a symptom of the broken connection URL (frontend re-toasts per socket reconnect while model fetches fail) — expect it to vanish with the fix; if it doesn't, we treat it separately. **Neither error belongs in plan 002's scope; both close with the found-issue-3 fix, pending your re-test.**

**A4 — Rubric vs calibration set — you blended two related things; here's the split.** The **rubric** is the scoring criteria handed TO the judge inside its prompt ("score 1–5 where 5 = every claim supported by context..."). The **human examples** serve two distinct roles: a few go *into* the judge prompt as few-shot anchors; a separate held-out set of human-scored items stays *outside* it, to measure judge–human agreement (calibration). If the judge disagrees with your held-out scores wildly, the judge isn't trustworthy yet. Yes — I'll deliver stub files with clearly marked `<!-- TIMOTHY -->` slots: golden dataset, rubric, and calibration examples.

#### B. Responses to your three ideas

**B1 — Tools & memory: do NOT block on them, and don't stub them either.** The reasoning: observability instruments *seams*, not features — and plan 001's seams (registry dispatch, graph nodes, ModelFactory) are exactly where tools and memory will later attach (a tool is a new node/edge; memory is the checkpointer already threaded through `build_graph`). Instrument the seams now and future features inherit instrumentation automatically — a new node gets a span the same way `retrieve` does; a new registry entry gets wrapped the same way all four are. Fake stubs would actually be *worse*: you'd be designing telemetry for imagined shapes. And the strongest argument for this ordering: building tools/memory WITH observability already running means you develop them with eyes open — traces will show you what your tool loop actually does the first time you run it. Recommendation: observability first, no stubs, tools/memory as plan 003+.

**B2 — Two vector collections (policy docs vs assist docs): good instinct, right pattern.** Terminology note: in pgvector-via-langchain these are *collections* (logical namespaces inside the same tables), same mechanism as our `company_policies_mock/live` split — so the machinery already exists. Design consequences for 002: the golden dataset schema gets a `collection` field, and eval metrics are computed *per collection* — plan 002 evaluates the assist collection only, but the harness is collection-parameterized so the policy collection (which resurrects your retired policy_check node in a future plan) plugs in without rework. Note the pleasant symmetry: the policy collection's eval is *more* tractable — "should this request be blocked" is closer to binary classification, so it gets precision/recall directly.

**B3 — Mining follow-up messages as implicit feedback: this is genuinely good, and it's a real production technique** (implicit satisfaction estimation — exactly the graded-polarity idea you describe: "that's not what I meant at all" ≫ "I still don't quite understand" as negative signal). Two honest caveats: (1) it requires *linked multi-turn conversations*, which requires memory/thread_id — not available until the memory plan; (2) follow-ups are *weak labels* (confounded by user mood, topic drift, terseness), so they're used in aggregate as a trend signal, never as per-item ground truth. Verdict: out of scope for 002, but it imposes ONE requirement on 002's design that costs nothing now: every trace/generation record must carry a `thread_id`-shaped field (already reserved in CONTRACTS.md §1) so consecutive turns are linkable later. We design the schema for your idea today, implement the idea after memory exists. Keep it in your interview stories — "I designed my telemetry schema so implicit-feedback mining could bolt on later" is a strong sentence.

#### C. Decisions needed before Stage 3 (the operating-weight question runs through all of them)

Full observability is potentially SIX new containers (otel-collector, Jaeger, Prometheus, Grafana, Langfuse, Langfuse's DB). On one laptop next to Ollama, that's real weight — so each decision below is partly "how much do you want to run?"

**D1 — LLM-layer capture: Langfuse now, or OTel-attributes first?** (the flagged discussion from 018).
   - *Langfuse now*: purpose-built UI (renders prompts/generations beautifully, stores eval scores next to traces — the flywheel in one tool), on your roadmap already; cost: +2 containers (can likely reuse our existing Postgres instead of a second one — worth investigating in Stage 3), +1 SDK in the service.
   - *OTel-only first*: prompts/tokens as span attributes in Jaeger — one mental model, minimal weight; cost: browsing prompts in a generic trace UI is clunky, eval scores have no natural home, and we'd add Langfuse in 003 anyway.
   - My recommendation: **Langfuse now** (reusing existing Postgres if feasible), because the eval half of 002 wants a place to PUT scores, and that's precisely what Langfuse is. But if your laptop is already wheezing in live mode, OTel-first is a respectable answer.

**D2 — Trace backend: Jaeger all-in-one** (single container, zero config, standard UI). Alternative is Grafana Tempo (integrates into Grafana but more config). Recommend Jaeger; low-stakes, easily swapped later thanks to the Collector indirection.

**D3 — Golden dataset: JSONL** (`{"id", "collection", "question", "expected_doc_ids", "reference_answer", "notes"}`), lives in `langchain_service/eval/golden/`, expected ids are the sha256 content-hash ids from plan 001 (nice payoff: our deterministic ids make eval expectations stable). You author ~15–30 items against the seed/policy docs; I deliver the stub with 3 worked examples.

**D4 — Judge execution: live-tier only for real scores; CI tests judge *plumbing* with `MOCK_LLM_JUDGE`** — the mock response pool you wrote months ago turns out to be exactly the right fixture for this. (Same two-tier logic as A2, applied to the judge.)

**D5 — Span granularity inside pipelines: registry-level + a retrieval span at minimum.** Per-graph-node spans come nearly free via callback handlers *if* we choose Langfuse in D1 (its LangChain/LangGraph integration does this); hand-rolling per-node OTel spans is real work I'd defer. So D5 mostly follows D1.

Answer inline as usual. A1/A2/A4 need no decision (clarifications you can accept or push back on); B1/B2/B3 need your agree/disagree; D1 is the big one — it shapes containers, SDKs, and D5.

---

Timothy Response:

D1: Lets do the full Langfuse now. But lets make observability as a passed in parameter to our build script. This way we do not need to have those heavy items if we just want to simply run our system.

D2: I don't really know the implications of this decision. But if you say that Jaeger is easily swapped out later and is the lower stakes, then I guess it does not really matter either way. Do the one which will be easier for me to see what is going on and understand the concepts. After this 002 is fully implemented, I will be going through all of the changes which you made and learning all of the concepts, so pick the one which will be most clear from a conceptual point of view.

D3: Sounds good to me.

D4: Sounds good to me.

D5: We selected langfuse, so we should be good.

---

### [AI — 2026_07_12_16_05] Stage 2 closing summary

Decisions locked: **D1** full Langfuse now, with ALL observability containers behind an opt-in flag (`./build.sh --obs`, implemented as a compose profile exactly like `live`) so the default system stays light — good call, and it becomes acceptance criterion (g) below. **D2** Jaeger — chosen for conceptual clarity per your instruction: its UI is nothing but the trace/span-tree concept, ideal for learning. **D3** JSONL golden set keyed by sha256 ids. **D4** two-tier judge (mock plumbing in CI, live scores nightly/manual). **D5** per-node spans via Langfuse callbacks. B1–B3 stand as agreed (no stubs for tools/memory; collection-parameterized eval harness; `thread_id`-shaped field in every generation record for your future implicit-feedback idea). Stage 2 converged.


# Stage 3 (Implementation Planning)

### [AI — 2026_07_12_16_05] Implementation Plan v1

**Ordering principle (same as plan 001):** every step leaves the repo runnable and independently verifiable; `./build.sh --mode mock` with NO `--obs` flag must behave identically to today after every single step.

**The target topology:**

```
                                          ┌─────────── obs profile (only with --obs) ───────────┐
gateway ──OTLP traces──────────────────►  │  otel-collector ──► Jaeger (trace UI :16686)         │
   │  └─ /metrics (pull) ◄────────────────│── Prometheus (:9090) ──► Grafana (:3001, dashboard)  │
langchain ──OTLP traces────────────────►  │       ▲                                              │
   │  └─ /metrics (pull) ◄────────────────│───────┘                                              │
   └──Langfuse SDK (push)──────────────►  │  Langfuse (:3002) ── langfuse db                     │
                                          └──────────────────────────────────────────────────────┘
```

Two transport models on display (deliberately, for the concepts): traces/generations are PUSHED by services; metrics are PULLED by Prometheus scraping `/metrics`. The collector is the indirection point for traces so backends are swappable.

---

#### Step 1 — Observability infrastructure skeleton (`obs` profile)

1a. `docker-compose.yaml`: new services under `profiles: ["obs"]` — `otel-collector` (config: OTLP in, Jaeger out), `jaeger` (all-in-one), `prometheus` (scrape config for both app services), `grafana` (provisioned Prometheus datasource + auto-loaded dashboard JSON; port 3001 to avoid OpenWebUI's 3000).
1b. Config files in a new `observability/` folder at repo root: `otel-collector-config.yaml`, `prometheus.yml`, `grafana/provisioning/*`.
1c. `build.sh`: `--obs` flag → adds `--profile obs` to the compose invocations (mirrors the existing `live` mechanics).

Verification: `./build.sh --mode mock --obs` → 4 new containers healthy; Jaeger/Prometheus/Grafana UIs load. Without `--obs`: identical container set to today.

#### Step 2 — Gateway (C#) instrumentation

2a. Packages: `OpenTelemetry.Extensions.Hosting`, `OpenTelemetry.Instrumentation.AspNetCore`, `OpenTelemetry.Instrumentation.Http`, OTLP exporter, Prometheus AspNetCore exporter.
2b. `Program.cs`: tracing (root span per request, automatic `traceparent` injection on the proxied hop — YARP forwards via HttpClient, which the Http instrumentation covers) + `/metrics` endpoint. All gated on `OBSERVABILITY_ENABLED` env (default false → zero overhead, no exporter errors when collectors absent).
2c. `TelemetryMiddleware` stays as the log pillar; its line gains the current `trace_id` so logs ↔ traces are joinable (the three pillars linked — a concept made concrete).

Verification: with `--obs`, one curl through the gateway → gateway-only trace visible in Jaeger; `curl :5000/metrics` shows request counters.

#### Step 3 — langchain_service (Python) tracing

3a. Dependencies: `opentelemetry-sdk`, `-instrumentation-flask`, `-exporter-otlp`. `observability.py` module: `init_observability()` called from `wsgi.py`/`main.py`, no-op unless `OBSERVABILITY_ENABLED`.
3b. Flask auto-instrumentation continues the gateway's `traceparent` (extract → same trace id).
3c. Manual spans at the seams: `pipeline.dispatch` span wrapping the registry handler call (attributes: `llm.pipeline_id`, `llm.model`, `llm.request.user_id`, `session.thread_id` when present) and `rag.retrieve` span inside `find_similar` (attributes: k, result count, top score).

Verification (the headline): one curl to `:5000/api/llm/chat/rag` → ONE trace in Jaeger containing gateway spans AND Flask/pipeline/retrieval spans under the same trace id. Acceptance criterion (a).

#### Step 4 — Metrics + Grafana dashboard

4a. `prometheus_client` in Python: request counter, error counter, duration histogram, token counters — all labeled by `pipeline_id` (bounded cardinality: 4 values; user_id explicitly NOT a label, per 018). `/metrics` on the Flask app.
4b. Token source: `usage_metadata` from the model response when live (ChatOllama provides it); zeros in mock (honest, documented) — plumbing identical in both modes.
4c. Grafana dashboard (provisioned JSON, versioned in `observability/`): RED row (rate, errors, p50/p95 duration by pipeline) + AI row (tokens/request, retrieval hit counts).

Verification: 20-request loop script → dashboard panels populate; per-pipeline latency differences visible. Acceptance criterion (b).

#### Step 5 — Langfuse (LLM-layer capture)

5a. Compose (obs profile): Langfuse + its datastore. **Known risk, decided with your input during implementation:** current Langfuse v3 self-host wants ClickHouse+Redis+MinIO (heavy); fallback is pinning the v2 image (single container + Postgres — can share `pgvector-service` with a second database). I'll try v3-minimal first, present the container count, you choose.
5b. Python SDK behind the same `OBSERVABILITY_ENABLED` gate: Langfuse LangChain callback handler passed into chain/graph invocations at the registry boundary (D5: per-node spans free), generation records carrying rendered prompt, retrieved chunk ids/sources, token counts, `trace_id` (link to Jaeger), and `thread_id` field (B3 future-proofing).
5c. Prompt versioning seed (your §LLM-as-Judge worry): `PromptFactory` prompts get a `name@version` label recorded on every generation — when prompts evolve, scores stay attributable.

Verification: OpenWebUI chat → generation in Langfuse UI showing full prompt + chunks, linked trace id matches Jaeger. Acceptance criterion (c).

#### Step 6 — Golden dataset + human-input stubs

6a. `langchain_service/eval/golden/golden_v1.jsonl` — schema `{id, collection, question, expected_doc_ids, reference_answer, notes}`; 3 worked examples by me; `<!-- TIMOTHY: ... -->`-marked slots for your 15–30.
6b. `eval/rubric.md` (faithfulness 1–5 rubric, judge-facing) and `eval/calibration.jsonl` (held-out human-scored items — YOUR scores, slots marked).
6c. Schema validator as a pytest (CI: malformed golden rows fail the build).

Verification: pytest green; you can author rows by copying a worked example.

#### Step 7 — Retrieval eval (`eval/eval_retrieval.py`)

7a. Computes hit@k (k=1,3) and MRR per collection from golden set vs live `find_similar` results; outputs JSON report + console summary. ~60 lines, hand-rolled (A1: the understanding lives here).
7b. Two tiers: `--tier plumbing` (mock embeddings — asserts determinism & code correctness, runs in CI via a new job step) and `--tier quality` (live embeddings, manual/nightly — real scores, baseline saved to `eval/baselines/`).
7c. Regression gate: `--gate` flag compares against baseline with thresholds file; exits nonzero on drop.

Verification: CI plumbing green; live run produces scores; **induced regression** (point golden set at wrong ids, or k=0) makes the gate FAIL — criterion (f), the fire-alarm test.

#### Step 8 — Judge eval (`eval/eval_judge.py`)

8a. Faithfulness scoring: golden-set questions → live RAG pipeline answers → judge prompt (your existing `get_llm_judge_prompt`, upgraded to the Step 6 rubric with structured output: score + cited evidence) → per-item scores + summary; scores pushed to Langfuse.
8b. CI plumbing tier via `MOCK_LLM_JUDGE` pool (parses mock verdicts end-to-end without Ollama).
8c. Judge calibration report: judge scores vs your `calibration.jsonl` scores, agreement summary printed (the A4 trust check).

Verification: plumbing test green in CI; live run shows scores in Langfuse; calibration report runs against your filled-in examples.

#### Step 9 — CI wiring, verification script, Stage 5 scaffold

9a. `ci.yml`: eval-plumbing steps added to the python job (golden schema test, retrieval plumbing tier, judge plumbing tier) — all mock, no containers.
9b. `scripts/observability_check.sh` (acceptance-pass style, like plan 001's): automates criteria (a)–(d) where scriptable, prints manual steps for (c)/(e).
9c. Stage 5 scaffold with the criteria matrix.

---

#### Acceptance criteria (formalizing, since Stage 1 left them implicit)

(a) One curl through the gateway → one trace in Jaeger with spans from BOTH services under the same trace id.
(b) Grafana dashboard shows per-pipeline RED + token metrics after a 20-request load.
(c) Every `/chat/rag` invocation records prompt + chunks + tokens in Langfuse, linked to its Jaeger trace id.
(d) Retrieval eval outputs hit@1/hit@3/MRR: plumbing tier green in CI, quality tier produces a live baseline.
(e) Judge eval produces per-item faithfulness scores + calibration agreement report.
(f) An induced regression fails the eval gate (prove the alarm rings by starting a fire).
(g) `./build.sh --mode mock` WITHOUT `--obs` is byte-for-byte today's container set, all 23 tests green, no observability overhead.

#### Risks

1. **Langfuse v3 self-host weight** (Step 5a) — decision point mid-implementation, v2-pin fallback ready.
2. **Version pinning** — same policy as plan 001: no guessed pins; freeze from the working environment (and the plan-001 `requirements.lock` follow-up is still open — this plan adds deps, so we should close both together in Step 9).
3. **C# OTel packages on net11.0** — verified only at your `dotnet build` (my sandbox has no SDK).
4. **Token counts in mock mode are zeros** — documented, not hidden; live mode is the real measure.
5. **Grafana dashboard JSON is fiddly** — budgeted as iterate-with-screenshots during Stage 4 rather than right-first-time.

### Stage 3 Discussion Subsection

Awaiting Timothy's review of Implementation Plan v1.

# Stage 4 (Implementation)

### [AI — 2026_07_12_16_28] Step 1 complete — observability infrastructure skeleton

**What changed:**

- **1a** Four services added to `docker-compose.yaml` under `profiles: ["obs"]` — `otel-collector` (OTLP in on 4317/4318, exports to Jaeger; ports exposed to host so non-docker dev processes can export too), `jaeger` all-in-one (UI :16686), `prometheus` (UI :9090, persistent volume), `grafana` (UI :3001 — 3000 is OpenWebUI; anonymous-admin enabled for local learning, with a "never outside localhost" comment). New volumes `prometheus_data`, `grafana_data`.
- **1b** New `observability/` folder at repo root: `otel-collector-config.yaml` (receivers→batch→Jaeger; a comment marks the deliberate ABSENCE of a metrics pipeline — metrics are pull-model), `prometheus.yml` (scrapes both app services every 5s; targets will show DOWN until Steps 2/4 create the endpoints — expected and noted in the file), Grafana provisioning (datasource + dashboard provider as *versioned files* — the plan-001 found-issue-3 lesson applied proactively: no click-config trapped in volumes) and a placeholder dashboard with one `up` panel so provisioning is verifiable end-to-end before Step 4 builds the real one.
- **1c** `build.sh`: `--obs` flag → adds `--profile obs` to both build and up (mirrors `live` mechanics), exports `OBSERVABILITY_ENABLED=true/false`, and prints the three UI URLs on startup. Compose passes `OBSERVABILITY_ENABLED` to both app services now (consumed starting Steps 2/3) so later steps don't touch compose again.

**Verification (mine):** bash syntax clean; compose parses; profile isolation asserted programmatically — obs profile contains exactly the 4 new services, and the no-profile (default) set is exactly the plan-001 four. All YAML/JSON configs parse.

**Verification (yours):**

```
./build.sh --mode mock            # control: identical container set to yesterday (criterion g)
./build.sh --mode mock --obs      # 4 new containers join
docker compose -p llm_monitor ps  # otel_collector, jaeger, prometheus, grafana present
# Jaeger    http://localhost:16686  → loads, no traces yet (Step 2 provides the first)
# Prometheus http://localhost:9090/targets → both targets DOWN (expected until Steps 2/4)
# Grafana   http://localhost:3001  → "LLM Monitor" dashboard exists, placeholder panel
```

Awaiting your check and permission for Step 2 (gateway instrumentation — first real trace).

### [AI — 2026_07_12_16_45] Step 2 complete — gateway instrumented (traces pushed, metrics pulled)

**What changed:**

- **2a** `server.csproj`: five OTel packages added with **floating versions** (`*`, and `*-*` for the historically-prerelease Prometheus exporter) — deliberate, same no-guessed-pins policy as Python; the resolved versions get locked in Step 9. My sandbox has no dotnet SDK or NuGet access, so `dotnet restore` on your machine is the moment of truth for resolution (plan risk 3).
- **2b** `Program.cs`: everything gated on `OBSERVABILITY_ENABLED` (from build.sh `--obs`); when false, nothing registers. When true: resource name `gateway` (that's the Jaeger service-dropdown label), tracing = AspNetCore instrumentation (root span per inbound request) + HttpClient instrumentation + OTLP push to the collector (standard `OTEL_EXPORTER_OTLP_ENDPOINT` env wins over the `http://otel-collector:4317` default). The comment on `AddHttpClientInstrumentation()` marks the conceptual keystone: YARP forwards through HttpClient, so that instrumentation is ALSO what injects `traceparent` on the proxied hop — the single header that makes Step 3's cross-service trace possible. Metrics = AspNetCore + HttpClient instruments exposed via Prometheus exporter at `GET /metrics` (pull model, mapped only when enabled).
- **2c** `TelemetryMiddleware` now logs `trace_id` sourced from `Activity.Current` — the log↔trace join: grep a slow request in logs, paste its trace_id into Jaeger, land on the span tree. (Bonus concept in the comment: `Activity` is .NET's built-in span type; ASP.NET creates one per request even without OTel — OTel is "just" the exporter of it.)

**Verification (mine):** static checks — usings present, gate applied to all three registration points, correct ordering (services before `Build()`, endpoint mapping after), csproj package count. Compile + runtime are yours (no dotnet here).

**Verification (yours):**

```
cd server && dotnet build                       # resolution + compile (risk 3 check)
./build.sh --mode mock --obs
curl -s localhost:5000/api/llm/chat/basic -X POST -H "Content-Type: application/json" -d '{"user_message":"hi"}'
# Jaeger http://localhost:16686 → service "gateway" → Find Traces → one trace,
#   spans: inbound POST + outbound HttpClient call to langchain (still a gateway-only
#   trace — langchain joins it in Step 3)
curl -s localhost:5000/metrics | head -30       # prometheus text format, http_server_* metrics
# Prometheus http://localhost:9090/targets → "gateway" target now UP (langchain still DOWN until Step 4)
docker logs dotnet_server | grep trace_id       # telemetry lines now carry trace_id=...
./build.sh --mode mock                          # control: no /metrics, no exporter errors in logs (criterion g)
```

If `dotnet restore` fails on any floating package (net11.0 compat), paste the error — fallback is pinning that one package to its latest net-compatible major.

### [AI — 2026_07_12_17_02] Step 3 complete — langchain_service traces; the distributed trace is wired

**The concept this step is built on (worth understanding before reviewing the code): OTel's API/SDK split.** The API (`opentelemetry.trace`) is always importable and always safe — with no SDK provider configured, every span is a NO-OP costing nanoseconds. The SDK (provider + OTLP exporter) is configured only inside `init_observability()`, only when `OBSERVABILITY_ENABLED=true`. Consequence: application code creates spans *unconditionally* — there is not a single `if enabled:` check in `app/orchestration/` or `app/rag/` (verified by grep; the only gate in the codebase is inside `observability.py`). The provider does the gating. Bonus: unit tests exercise the instrumented code paths for free, as no-ops.

**What changed:**

- **3a** New `app/observability.py`: `init_observability(app)` — provider with `service.name=langchain_service` (its label in Jaeger next to `gateway`), BatchSpanProcessor → OTLP → collector (same env-first endpoint logic as the C# side). SDK imports live inside the function so the disabled path never loads them. Called per-process from `wsgi.py` (each gunicorn worker — same reasoning as the per-worker connection pool) and `main.py`.
- **3b** `FlaskInstrumentor().instrument_app(app)` — server span per request AND the headline mechanism: extracts the gateway's `traceparent` header so our spans *continue* the gateway's trace rather than starting a new one.
- **3c** Manual spans at the seams:
  - `pipeline.dispatch` — implemented **inside `registry.register()` itself**: registration wraps every handler (via `dataclasses.replace`, respecting the frozen dataclass). This is the Stage-1/Stage-2 decision "instrument at the registry boundary" made literal — every current AND future pipeline is traced without its author ever thinking about spans. Attributes: `llm.pipeline_id`, `llm.request.user_id`, and post-invoke `llm.model_used`, `llm.latency_ms`, `rag.sources_count`.
  - `rag.retrieve` in `find_similar` — attributes `rag.k`, `rag.collection`, `rag.results`, `rag.top_score` (the best hit's distance; watching that value across queries is exactly the data your disabled `score_threshold` has been waiting for).
- `requirements.txt`: + `opentelemetry-sdk`, `-instrumentation-flask`, `-exporter-otlp` (floating, per policy).

**Verification (mine):** py_compile clean on all five touched files; gate-scatter grep confirms the single-gate design; registry wrapper preserves the handler signature so the 23 existing tests exercise the wrapped path in CI.

**Verification (yours — THE acceptance moment, criterion a):**

```
./build.sh --mode mock --obs
curl -s localhost:5000/api/llm/chat/rag -X POST -H "Content-Type: application/json" -d '{"user_message":"can I use scripting tools?"}'
# Jaeger http://localhost:16686 → service "gateway" → Find Traces → newest trace should show
# ONE tree, TWO services:
#   gateway: POST /api/llm/chat/rag
#     └─ gateway: HTTP POST (YARP hop, traceparent injected)
#         └─ langchain_service: POST /chat/rag        ← Flask continued the trace
#             └─ langchain_service: pipeline.dispatch  (llm.pipeline_id=chat-rag)
#                 └─ langchain_service: rag.retrieve   (rag.k=2, rag.top_score=…)
docker logs dotnet_server | grep trace_id     # paste one id into Jaeger search → same trace
cd langchain_service && python -m pytest -v   # 23 green, spans no-op'd
./build.sh --mode mock                        # control (criterion g)
```

If the two services appear as SEPARATE traces instead of one tree, the traceparent hop broke — report what Jaeger shows and we debug the propagation (that failure mode is itself a great lesson, but let's hope for the tree).

# Stage 5 (Final Results, Testing, Verficiation)

Not Gotten To Yet