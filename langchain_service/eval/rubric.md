# Faithfulness Rubric v1 (judge-facing)

This text is injected into the LLM-as-judge prompt (plan 002 Step 8). It defines
ONE metric: **faithfulness** — is every claim in the answer supported by the
retrieved context? (Not "is the answer good" — just "is it grounded".)

Version: `judge.rubric.faithfulness@1` — bump on ANY wording change, same rule
as prompt versions.

## Scale

| Score | Meaning |
|---|---|
| 5 | Every factual claim in the answer is directly supported by the provided context. Nothing invented. |
| 4 | All material claims supported; at most trivial unsupported embellishment (politeness, phrasing) that carries no factual content. |
| 3 | Core claim supported, but the answer adds secondary factual claims the context does not contain. |
| 2 | Mix of supported and unsupported claims; a reader could be materially misled about what the source says. |
| 1 | The answer's central claim is absent from or contradicted by the context (hallucination). |

## Judge instructions

- Judge ONLY against the provided context. Outside knowledge being "true" does not make a claim faithful.
- An answer that says "the provided policies do not cover this" when the context is irrelevant scores **5** (refusing to invent is perfectly faithful).
- Output format (machine-parsed — must be followed exactly): `<score 1-5>: <one-sentence rationale citing the decisive claim>`

## Few-shot anchors

Anchor 1 (score 5):
Context: "Employees are permitted to use local scripting tools for local automation, provided no proprietary source code leaves company assets."
Answer: "Yes, you can use scripting tools locally as long as proprietary source code stays on company assets."
Verdict: `5: Both claims (permission, source-code condition) restate the context directly.`

Anchor 2 (score 1):
Context: "Employees are permitted to use local scripting tools for local automation, provided no proprietary source code leaves company assets."
Answer: "Yes, and the IT department will issue you a license for PyCharm within 3 business days."
Verdict: `1: The license/timeline claim is entirely invented; the context says nothing about IT issuing anything.`

<!-- TIMOTHY: add 1-3 anchors of your own, ideally from REAL system outputs once live —
     anchors from your actual traffic calibrate the judge far better than synthetic ones.
     Also add any domain-specific rules here (e.g., how to score answers that quote
     the policy verbatim vs paraphrase it). Bump the version when you do. -->
