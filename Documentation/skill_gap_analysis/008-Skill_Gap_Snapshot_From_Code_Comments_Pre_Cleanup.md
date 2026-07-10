2026_07_09_21_55-Skill_Gap_Snapshot_From_Code_Comments_Pre_Cleanup

# Skill Gap Snapshot — Extracted From Code Comments Before Cleanup

Archive record. Source: every self-identified struggle in the in-code comments (verbatim quotes preserved in `Developer_Journal/001`), cross-checked against the bugs actually hit during the July 5–9 live-mode bring-up. Each gap lists evidence, severity for a Microsoft SWE loop, and mitigation. Compare against snapshots 001–007 to track closure over time.

## Gap table

| # | Gap | Evidence (comment/bug) | Severity | Status/Mitigation |
|---|-----|------------------------|----------|-------------------|
| 1 | Serialization contracts across languages (naming policies, DTO discipline, pydantic) | "It seems this is so fragile"; lowercase C# DTO props; untyped `data.get()` in Flask | **High** — API design is core interview material | Lecture 015 §3; adopt pydantic + `JsonNamingPolicy`; then re-review |
| 2 | Chat prompt roles & structured output | "I don't know the proper way to use assistant"; policy checker parses raw strings; crossed-prompt bug | **High** — AI-engineering differentiator | 015 §4; implement `with_structured_output` for policy checker |
| 3 | Agentic tool loop | "No idea how to do this" (tool invocation) | **High** — next milestone blocks on it | 015 §5; implement `/test/tool_use`, then LangGraph tools node |
| 4 | Text encoding & HttpContent model | "is UTF8 changing the string or adding metadata?"; `"/application/json"` media-type bug shipped | Medium | 015 §3; fix the bug; re-explain aloud (Feynman check) |
| 5 | Extension methods / middleware pipeline / DI lifetimes | "Lack of understanding" in Program.cs; lifecycle questions in three Python files | Medium — but ASP.NET DI is prime Microsoft interview ground | 015 §1, §7; wire real logic into TelemetryMiddleware as practice |
| 6 | `*args/**kwargs`, decorators | "still shaky... scared me when I was first learning C" | Medium | 015 §6; decorator exercise |
| 7 | Python idioms for C constructs (Enum vs typedef) | "In C I would do a typedef struct. but what should I do in python?" | Low | 015 §6; refactor ChatType to Enum during cleanup |
| 8 | HTTP response anatomy in libraries | "it seems it is only the body?"; `Deserialize(response.Body)` near-miss | Medium | 015 §3; already partially closed by doc 014 — needs spaced review |
| 9 | RAG quality controls (score thresholds, idempotent IDs, metadata filters) | "block erronious retrevials"; duplicate ingestion on every restart; dead `documentToSearchAgainst` param | **High** — separates demo-RAG from production-RAG | 015 §8; implement all three |
| 10 | Auth: schemes, claims, identity | "what does 'schema' mean"; "where does userId come from?" | Medium now, High later (security phase) | 015 §2; dedicated lecture when security phase starts |
| 11 | Prod serving for Python (WSGI/ASGI, gunicorn, debug=True RCE risk) | dockerfile TODO conflating uvicorn/Flask; Werkzeug debugger exposed on :5001 | **High** (it's a live security hole in the current build) | 015 §9; switch CMD to gunicorn, `debug=False` |
| 12 | Compose layering & shell quoting | "$GPU is called a dynamic string injector" (invented term); referenced gpu.yml doesn't exist | Low | 015 §10; create the actual override file |
| 13 | API-contract verification habit | `"streaming"` vs `"stream"`; `PGVector` kwargs from deprecated API; `ElephantVectorStore` (hallucinated-name class) | **High** — process gap, not knowledge gap | Habit: read installed package source / `inspect.signature`; pin dependencies |
| 14 | Observability discipline | logs destroyed by teardown before reading; "terrible error message" self-note | Medium — improving fast (used `docker logs` correctly by 3rd session) | Telemetry middleware milestone; structured logging next |

## Closed since last snapshot (evidence of progress)

Abstract-method contracts (MockChatModel now implements `_generate` + `_llm_type` correctly); Compose profiles/healthchecks/env-var layering (working build.sh both modes); LangGraph node contract (correct partial-state-update comments in nodes.py); implicit-None return bug class (root-caused personally; adopted annotation habit); Docker init-script lifecycle (learned via volume-reset fix).

## Reviewer's note on trajectory

The dominant pattern is *instinct ahead of vocabulary*: structured output, similarity thresholds, model allowlists, naming-policy contracts, and singleton lifetimes were all independently re-derived in comments before Timothy knew the standard terms. That is the profile of someone who will convert fast with targeted study. The two gaps that most threaten interview performance are #1/#2 (contract fluency — because interviewers probe API design early) and #13 (verification habit — because "how do you know?" follow-ups expose it). Both are process-fixable within weeks. Recommend the next skill-gap update after the LangGraph milestone to measure #3.
