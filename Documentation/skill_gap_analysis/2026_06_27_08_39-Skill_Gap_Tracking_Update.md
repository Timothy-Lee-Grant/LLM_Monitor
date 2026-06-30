# Skill Gap Tracking Update

| | |
|---|---|
| **Date** | 27-06-2026 (08:39) |
| **Candidate** | Timothy Grant |
| **Target** | Software Engineer (cloud/backend + AI integration), Microsoft |
| **Document type** | Progress-tracking snapshot (archive) |
| **Baseline** | `25-06-2026_microsoft-readiness-skill-gap-analysis.md` (the 12-gap baseline) |
| **New evidence since baseline** | The `test_langchain_implementation` stub in `langchain_service/lang.py`; the AI-engineering research + concepts lecture added to `Documentation/` |
| **Purpose** | Re-score the baseline gaps, log movement, and register newly-surfaced gaps with mitigation plans, so progress is trackable over time |

---

## 1. How to read this update

This is an **archive/tracking document**, not a fresh analysis. It does three things:
1. **Re-scores** each of the 12 baseline gaps with a status (`Improved` / `No change` / `New evidence`), citing what changed.
2. **Registers new gaps** that only became visible once you started designing the AI orchestrator — your stub revealed both growth *and* new, more advanced gaps.
3. Logs a **mitigation status** per item so the next snapshot can measure movement.

**Status legend:** 🟢 Improving / on track · 🟡 Identified, not yet actioned · 🔴 Still a hard gate, no movement · ✨ New gap surfaced this period.

**The headline since the baseline:** the evidence base shifted from "fixing broken scaffolding" to "designing a sophisticated AI pipeline." That itself is signal — your `test_langchain_implementation` stub independently sketched policy guardrails, prompt-injection defense, RAG, an agent loop, and conversation memory. That is a *meaningful jump in architectural maturity* in two days. The flip side: designing at that level exposes a new tier of gaps (evaluation, structured-output reliability, production RAG) that weren't even visible when the code was simpler.

---

## 2. Re-score of the 12 baseline gaps

| # | Baseline gap | Prior priority | Status now | Evidence of movement |
|---|--------------|----------------|------------|----------------------|
| 1 | Testing / verification rigor | 🔴 P0 | 🔴 **No change** | No tests or eval harness exist yet; the stub is unrun. Still the #1 habit to fix. Now *doubly* important because AI correctness is statistical (needs evals). |
| 2 | Async / concurrency | 🔴 P0 | 🟡 No change | The .NET→Flask awaited call still isn't written; stub is synchronous. Knowledge still theoretical. |
| 3 | Distributed-systems reasoning | 🔴 P0 | 🟢 **Improved (conceptual)** | Your `# NOTE` on statefulness ("assumes one user, history in RAM") is genuine distributed-systems insight — you *identified* the stateless/external-state problem yourself. Not yet implemented, but the intuition is forming. |
| 4 | Backend framework fundamentals | 🟠 P1 | 🟡 No change | Server still has the DI/`MapControllers` issue from the code review. |
| 5 | DSA / coding fluency | 🔴 P0 | 🔴 **No change** | Untouched. Longest-runway gate; still needs a daily cadence started. |
| 6 | System design | 🟠 P1 | 🟢 **Improved** | The orchestrator design (multi-stage pipeline, trust boundaries, retrieval) is a real system-design artifact. You're practicing decomposition. |
| 7 | Observability | 🟡 P2 | 🟡 No change | Middleware still a stub; LLM-specific observability now understood conceptually (concepts doc M10) but not built. |
| 8 | Data layer | 🟠 P1 | 🟢 **Improved (conceptual)** | You correctly scoped pgvector for RAG and a relational store for history; Postgres still not stood up. |
| 9 | Security / hygiene | 🟡 P2 | 🟢 **Improved (conceptual)** | Big jump: you independently planned prompt-injection defense — a security-first instinct most juniors lack. Implementation pending. |
| 10 | Large codebases | 🟡 P2 | 🟡 No change | No OSS contribution yet. |
| 11 | Networking / gRPC | 🟡 P2 | 🟡 No change | Untouched. |
| 12 | Behavioral / culture | 🟠 P1 | 🟡 No change | STAR stories not yet prepared. |

**Pattern in the movement:** every "Improved" is marked *(conceptual)* or design-level. You are converting unknowns into *understood-but-unbuilt*. That's real progress, but the next snapshot needs to show **Improved → Implemented**. The recurring word across this whole archive is the same as the code review's: *built but not run / understood but not demonstrated*. Closing that conversion is the throughline of your development.

---

## 3. New gaps surfaced this period (✨)

These were invisible at baseline because the code wasn't ambitious enough to reveal them. They come directly from the AI-engineering research and your stub.

### ✨ NG-1 — Evaluation of probabilistic systems 🔴 P0 (new top priority)
**Evidence.** The stub has five processing steps and **zero** way to measure if any of them are correct. Research flagged evaluation as *the single most underrated, most-requested AI-engineer skill* and a named Microsoft requirement ("rubrics, golden datasets, judge agents").
**Why it's P0.** AI correctness is statistical, not binary — without evals you cannot know if a change helped. This also *is* the AI-specific form of baseline GAP 1.
**Mitigation plan.**
- Build a ~40-case **golden dataset** (block / allow / inject / tool-needed) for the orchestrator.
- Score deterministic outcomes programmatically; use **calibrated LLM-as-judge** (validate against ~100 human labels) for quality.
- Run it in **CI on every PR**; fail on regression.
**Status:** 🟡 Identified, highest-value next build. *Closing this closes GAP 1 simultaneously.*

### ✨ NG-2 — Structured outputs & probabilistic-to-deterministic boundary 🟠 P1
**Evidence.** Stub does `if policyResult == "Policy Violated"` and `if there is a prompt injection` against free-text LLM output — brittle string-matching of a probabilistic generator.
**Why it matters.** Reliability of any LLM app depends on constraining output shape (JSON schema / function-calling / constrained decoding). It's the bridge between the model and your control flow.
**Mitigation plan.** Replace every string comparison with a validated schema (`{violation: bool, policy_id, confidence, reason}`) via Pydantic; retry on parse failure.
**Status:** 🟡 Identified.

### ✨ NG-3 — Production-grade RAG (beyond naive retrieval) 🟠 P1
**Evidence.** Stub calls `SearchVectorDatabaseBySemanticSearch` with no similarity threshold, no chunking strategy, no citations, no "do we even need retrieval?" decision.
**Why it matters.** Microsoft asks about *hierarchical/agentic RAG, re-ranking, grounding* — the gap between "works in a demo" and "production."
**Mitigation plan.** Add a retrieval threshold (semantic search always returns *something*); cite retrieved chunks; decide retrieval agentically; leave a `# TODO: re-ranking` to show awareness of the ceiling.
**Status:** 🟡 Identified.

### ✨ NG-4 — Agent-loop safety & cost bounding 🟠 P1
**Evidence.** Stub plans "keep invoking until the llm determines it is finished" with no `max_steps`, no token budget, no tool-argument validation, no human-in-the-loop for side-effecting tools.
**Why it matters.** Unbounded agent loops are a cost bomb and an availability/security risk (OWASP "excessive agency"). Your embedded watchdog instinct applies directly.
**Mitigation plan.** Cap iterations + token budget; adopt the action-selector pattern (model picks from pre-approved tools); validate tool args before execution; gate side-effecting tools behind approval.
**Status:** 🟡 Identified.

### ✨ NG-5 — AI cost engineering 🟡 P2
**Evidence.** No model routing (flagship vs cheap classifier), no semantic caching, no context-window management in the stub.
**Why it matters.** "Multi-model cost management" is a named 2026 competency; token cost is a real production constraint.
**Mitigation plan.** Use a cheap model for Steps 1–2; add semantic caching; window/summarize history.
**Status:** 🟡 Identified.

---

## 4. Updated priority stack (what to work next)

Ordered by leverage toward the Microsoft bar, blending baseline + new gaps:

1. 🔴 **DSA daily cadence (GAP 5)** — longest runway, hard gate, *still not started*. Begin today; it's the one item that only moves with calendar time.
2. 🔴 **Evaluation harness (NG-1) + testing rigor (GAP 1)** — one build closes both; highest differentiation in a junior portfolio.
3. 🟠 **Make one thing real end-to-end** — fix the baseline blocking bugs, get one request to flow, run it. Converts "understood" → "demonstrated" (the throughline of this archive).
4. 🟠 **Structured outputs (NG-2)** — cheapest reliability win in the stub.
5. 🟠 **Externalize conversation state (GAP 3 + 8)** — implement the insight your own `# NOTE` already had.
6. 🟡 **Behavioral/STAR prep (GAP 12)** — low effort, graded round, easy to neglect.

---

## 5. Trend log (for future snapshots)

| Snapshot date | P0 gates open | Gaps improving | New gaps | One-line state |
|---------------|---------------|----------------|----------|----------------|
| 25-06-2026 (baseline) | 4 (testing, async, distributed, DSA) | — | — | Strong instincts, broken scaffolding |
| 27-06-2026 (this) | 5 (+ evaluation) | 4 conceptual (distributed, design, data, security) | 5 (eval, structured out, prod-RAG, agent safety, cost) | Design maturity jumped; everything still unbuilt/unrun |
| *(next)* | *target: ≤4* | *target: ≥2 → Implemented* | | *goal: first green eval run in CI* |

**Suggested cadence:** add a new snapshot to this folder every ~2 weeks, or after any major build, so the trend log shows the conversion from *understood* → *implemented* → *demonstrated*.

---

## 6. One-paragraph summary for future-you

Between the baseline and now, the project's ambition outran its execution — in a *good* way. You designed an AI orchestrator that, on paper, demonstrates security-first thinking, RAG, agentic tool use, and a real grasp of statefulness, lifting the conceptual scores on distributed systems, system design, data, and security. But nothing new was built or run, the four original P0 gates remain open, and the leap in design ambition surfaced a fresh tier of P0/P1 gaps led by **evaluation** — the most-valued, least-practiced AI skill. The single most important move remains unchanged from the baseline and is now even more urgent: **start the DSA cadence, and build one thing — an eval harness over one working request — completely, then run it.** Convert understanding into demonstrated, verified reps.

*No source files were modified. Only this tracking document was added to `Documentation/skill_gap_analysis/`.*
