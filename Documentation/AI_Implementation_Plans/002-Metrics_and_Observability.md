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