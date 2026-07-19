"""LLM-as-judge faithfulness eval + calibration report (plan 002 Step 8).

Two tiers, same philosophy as eval_retrieval.py:

  --tier plumbing   No containers, no Ollama, no DB. Answers = the golden
                    reference answers; contexts = the expected seed docs;
                    judge = MockChatModel with the MOCK_LLM_JUDGE pool.
                    Scores are meaningless; what's proven is the LOOP:
                    rubric loads -> prompt renders -> judge invoked ->
                    verdict parsed -> aggregation + calibration math correct.

  --tier quality    Real answers from the chat-rag pipeline, judged against
                    the actually-retrieved context by a real model. Run
                    inside the container in live mode:
                      docker exec langchain_service python -m eval.eval_judge --tier quality --calibration

Calibration (--calibration): the judge also scores eval/calibration.jsonl
rows and the report compares judge vs YOUR scores (exact-match rate + mean
absolute difference). A judge you haven't calibrated is just a confident
stranger (concepts doc 018 §5.3).

Langfuse push: best-effort — scores land in the JSON report ALWAYS; pushing
to Langfuse happens only when observability is enabled and the SDK call
succeeds (API drift tolerated gracefully; report is the source of truth).
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

from eval.dataset import load_golden, load_calibration, EVAL_DIR

REPORTS_DIR = EVAL_DIR / "reports"
RUBRIC_PATH = EVAL_DIR / "rubric.md"


# ---------- verdict parsing (pure; unit-tested) ----------

def parse_verdict(text: str) -> tuple[int | None, str]:
    """'<score>: <rationale>' -> (score, rationale). None score = unparseable.

    partition(":") splits on the FIRST colon only, so rationales containing
    colons survive (same idiom as the policy node from plan 001).
    """
    head, _, tail = text.strip().partition(":")
    try:
        score = int(head.strip())
    except ValueError:
        return None, text.strip()
    if not 1 <= score <= 5:
        return None, text.strip()
    return score, tail.strip()


def agreement_report(pairs: list[tuple[int, int]]) -> dict:
    """(judge, human) score pairs -> agreement stats. Pure."""
    if not pairs:
        return {"n": 0}
    exact = sum(1 for judge, human in pairs if judge == human)
    return {
        "n": len(pairs),
        "exact_match_rate": round(exact / len(pairs), 4),
        "mean_abs_difference": round(
            statistics.mean(abs(judge - human) for judge, human in pairs), 4
        ),
    }


# ---------- judge invocation ----------

def _judge_chain(tier: str):
    from app.prompts.MyPromptTemplates import PromptFactory
    if tier == "plumbing":
        from app.models.factory import MockChatModel
        from app.prompts.mock_prompts import MOCK_RESPONSES
        model = MockChatModel(response_pool=MOCK_RESPONSES["llm_judge"])
    else:
        import os
        from app.models.factory import ModelFactory
        # A (usually stronger) judge model can differ from the serving model.
        model = ModelFactory.get_chat_model(os.getenv("JUDGE_MODEL", os.getenv("LLM_MODEL", "mock")))
    return PromptFactory.get_llm_judge_prompt() | model


def judge_one(chain, rubric: str, context: str, answer: str) -> tuple[int | None, str]:
    message = chain.invoke({"rubric": rubric, "context": context, "model_response": answer})
    return parse_verdict(message.content)


# ---------- per-tier material: (question, context, answer) triples ----------

def plumbing_material(rows: list[dict]) -> list[dict]:
    """Reference answers judged against their expected docs — no pipeline, no DB."""
    from app.rag.seed_documents import SEED_DOCUMENTS
    from app.rag.vector_store import VectorStoreManager

    seed_text_by_id = {VectorStoreManager.deterministic_id(d): d.page_content for d in SEED_DOCUMENTS}
    return [
        {
            "id": row["id"],
            "context": "\n\n".join(seed_text_by_id[i] for i in row["expected_doc_ids"]),
            "answer": row["reference_answer"],
        }
        for row in rows
    ]


def quality_material(rows: list[dict]) -> list[dict]:
    """Real pipeline answers judged against the retrieved context (RAGAS-style
    faithfulness: grounding vs what was RETRIEVED, not vs what SHOULD have been)."""
    import app.orchestration.pipelines  # noqa: F401 — registers pipelines
    from app.orchestration.registry import get_pipeline
    from app.orchestration.contracts import ChatRequest
    from app.rag.vector_store import vector_store

    material = []
    for row in rows:
        response = get_pipeline("chat-rag").handler(ChatRequest(user_message=row["question"], user_id="eval"))
        # Re-run retrieval to get chunk TEXT (metadata only carries source names).
        # Deterministic embeddings make this an identical query to the pipeline's own.
        documents = vector_store.find_similar(row["question"], k=2)
        material.append({
            "id": row["id"],
            "context": "\n\n".join(doc.page_content for doc in documents),
            "answer": response.response,
        })
    return material


def push_scores_to_langfuse(results: list[dict]) -> bool:
    from app.observability import observability_enabled
    import os
    if not observability_enabled() or not os.getenv("LANGFUSE_PUBLIC_KEY"):
        return False
    try:
        from langfuse import Langfuse
        client = Langfuse()
        for result in results:
            if result["score"] is None:
                continue
            trace = client.trace(name=f"eval-faithfulness-{result['id']}",
                                 input=result["context"][:500], output=result["answer"][:500])
            trace.score(name="faithfulness", value=result["score"], comment=result["rationale"][:500])
        client.flush()
        return True
    except Exception as exc:  # SDK API drift tolerated — report stays source of truth
        print(f"  (Langfuse push skipped: {type(exc).__name__}: {exc})")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", choices=["plumbing", "quality"], required=True)
    parser.add_argument("--calibration", action="store_true",
                        help="also judge calibration.jsonl and report judge-vs-human agreement")
    args = parser.parse_args()

    rubric = RUBRIC_PATH.read_text()
    chain = _judge_chain(args.tier)
    rows = load_golden()
    material = (plumbing_material if args.tier == "plumbing" else quality_material)(rows)

    results = []
    for item in material:
        score, rationale = judge_one(chain, rubric, item["context"], item["answer"])
        results.append({**item, "score": score, "rationale": rationale})

    scored = [r["score"] for r in results if r["score"] is not None]
    parse_failures = len(results) - len(scored)

    print(f"\n=== Judge eval — tier={args.tier}, {len(results)} items ===")
    for result in results:
        print(f"  {result['id']}: {result['score']} — {result['rationale'][:90]}")
    print(f"  mean faithfulness: {round(statistics.mean(scored), 2) if scored else 'n/a'}"
          f"   parse failures: {parse_failures}")
    if args.tier == "plumbing":
        print("  (plumbing scores are meaningless by design — the parsed LOOP is the signal)")

    calibration = None
    if args.calibration:
        pairs = []
        calibration_rows = load_calibration()
        for row in calibration_rows:
            judge_score, _ = judge_one(chain, rubric, row["context"], row["model_answer"])
            if judge_score is not None:
                pairs.append((judge_score, row["human_faithfulness_score"]))
        calibration = agreement_report(pairs)
        print(f"  calibration vs human ({calibration.get('n', 0)} rows): {calibration}")

    REPORTS_DIR.mkdir(exist_ok=True)
    report_path = REPORTS_DIR / f"judge_{args.tier}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps({
        "tier": args.tier, "results": results, "parse_failures": parse_failures,
        "calibration": calibration,
    }, indent=2))
    print(f"  report: {report_path.relative_to(EVAL_DIR.parent)}")

    if push_scores_to_langfuse(results):
        print("  scores pushed to Langfuse")

    # Plumbing gate-lite: the loop itself must work end to end.
    if args.tier == "plumbing" and parse_failures:
        print("  PLUMBING FAILURE: judge verdicts failed to parse")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
