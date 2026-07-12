"""Retrieval evaluation: hit@k and MRR over the golden dataset (plan 002 Step 7).

Hand-rolled on purpose (Stage 2 A1): hit@k is ~5 lines and MRR is ~7 — owning
them beats importing them.

Two tiers (Stage 2 A2 — the mock-embeddings nuance):

  --tier plumbing   No containers. Embeds seed docs + questions IN MEMORY with
                    DeterministicFakeEmbedding and ranks by cosine similarity.
                    Scores are semantically MEANINGLESS — what this tier proves
                    is that the machinery is correct and deterministic: dataset
                    parses, ranking math right, ids line up. Any change in its
                    output = a code regression. Runs in CI.

  --tier quality    Real vector store (pgvector + whatever embeddings the mode
                    provides). Run inside the container:
                      docker exec langchain_service python -m eval.eval_retrieval --tier quality
                    Live mode = the REAL retrieval quality numbers.

Gate (Step 7c): --save-baseline writes eval/baselines/retrieval_<tier>.json;
--gate compares current metrics against that baseline using eval/thresholds.json
and exits 1 on regression (CI-friendly). Exit 2 = no baseline yet.

Usage:
  python -m eval.eval_retrieval --tier plumbing --save-baseline
  python -m eval.eval_retrieval --tier plumbing --gate
  docker exec langchain_service python -m eval.eval_retrieval --tier quality --save-baseline
"""

import argparse
import json
import math
import sys
import time
from pathlib import Path

from eval.dataset import load_golden, EVAL_DIR

BASELINES_DIR = EVAL_DIR / "baselines"
REPORTS_DIR = EVAL_DIR / "reports"
THRESHOLDS_PATH = EVAL_DIR / "thresholds.json"
K_VALUES = (1, 3)


# ---------- the metrics (pure functions — unit-tested in tests/test_eval_retrieval.py) ----------

def hit_at_k(expected_ids: list[str], retrieved_ids: list[str], k: int) -> bool:
    """Did ANY expected document appear in the top k results?"""
    return any(doc_id in expected_ids for doc_id in retrieved_ids[:k])


def reciprocal_rank(expected_ids: list[str], retrieved_ids: list[str]) -> float:
    """1/rank of the FIRST expected document (1st place = 1.0, 3rd = 0.333, absent = 0).
    Rewards putting the right chunk first — context order matters to generation."""
    for position, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in expected_ids:
            return 1.0 / position
    return 0.0


def compute_metrics(rows: list[dict], retrieved: dict[str, list[str]]) -> dict:
    """Aggregate hit@k and MRR over golden rows given each row's retrieved ids."""
    metrics = {f"hit@{k}": 0.0 for k in K_VALUES}
    metrics["mrr"] = 0.0
    for row in rows:
        ids = retrieved[row["id"]]
        for k in K_VALUES:
            metrics[f"hit@{k}"] += hit_at_k(row["expected_doc_ids"], ids, k)
        metrics["mrr"] += reciprocal_rank(row["expected_doc_ids"], ids)
    n = len(rows)
    return {name: round(total / n, 4) for name, total in metrics.items()} | {"n": n}


# ---------- retrievers for each tier ----------

def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def plumbing_retrieve(rows: list[dict], k: int) -> dict[str, list[str]]:
    """In-memory fake retrieval: same embedding model as mock mode, no database."""
    from langchain_core.embeddings import DeterministicFakeEmbedding
    from app.rag.seed_documents import SEED_DOCUMENTS
    from app.rag.vector_store import VectorStoreManager

    embedder = DeterministicFakeEmbedding(size=768)
    seed_vectors = [
        (VectorStoreManager.deterministic_id(doc), embedder.embed_query(doc.page_content))
        for doc in SEED_DOCUMENTS
    ]

    retrieved = {}
    for row in rows:
        question_vector = embedder.embed_query(row["question"])
        ranked = sorted(seed_vectors, key=lambda pair: _cosine(question_vector, pair[1]), reverse=True)
        retrieved[row["id"]] = [doc_id for doc_id, _vector in ranked[:k]]
    return retrieved


def quality_retrieve(rows: list[dict], k: int) -> dict[str, list[str]]:
    """Real vector store retrieval (run inside the container; pgvector required)."""
    from app.rag.vector_store import vector_store, VectorStoreManager

    vector_store.initialize()
    retrieved = {}
    for row in rows:
        documents = vector_store.find_similar(row["question"], k=k)
        retrieved[row["id"]] = [VectorStoreManager.deterministic_id(doc) for doc in documents]
    return retrieved


# ---------- gate ----------

def gate_check(current: dict, baseline: dict, tolerance: float) -> list[str]:
    """Returns a list of regression messages (empty = pass)."""
    failures = []
    for name, baseline_value in baseline.items():
        if name == "n":
            continue
        current_value = current.get(name, 0.0)
        if current_value < baseline_value - tolerance:
            failures.append(
                f"REGRESSION {name}: {current_value} < baseline {baseline_value} (tolerance {tolerance})"
            )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", choices=["plumbing", "quality"], required=True)
    parser.add_argument("--save-baseline", action="store_true")
    parser.add_argument("--gate", action="store_true")
    args = parser.parse_args()

    rows = load_golden()
    retrieve = plumbing_retrieve if args.tier == "plumbing" else quality_retrieve

    retrieved = retrieve(rows, k=max(K_VALUES))
    if args.tier == "plumbing":
        # Determinism self-check: the entire point of this tier.
        assert retrieve(rows, k=max(K_VALUES)) == retrieved, "plumbing tier is non-deterministic!"

    metrics = compute_metrics(rows, retrieved)

    print(f"\n=== Retrieval eval — tier={args.tier}, {metrics['n']} golden rows ===")
    for name in [f"hit@{k}" for k in K_VALUES] + ["mrr"]:
        print(f"  {name:>7}: {metrics[name]}")
    if args.tier == "plumbing":
        print("  (plumbing scores are semantically meaningless by design — stability is the signal)")

    REPORTS_DIR.mkdir(exist_ok=True)
    report_path = REPORTS_DIR / f"retrieval_{args.tier}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps({"tier": args.tier, "metrics": metrics,
                                       "per_row": retrieved}, indent=2))
    print(f"  report: {report_path.relative_to(EVAL_DIR.parent)}")

    baseline_path = BASELINES_DIR / f"retrieval_{args.tier}.json"
    if args.save_baseline:
        BASELINES_DIR.mkdir(exist_ok=True)
        baseline_path.write_text(json.dumps(metrics, indent=2))
        print(f"  baseline saved: {baseline_path.relative_to(EVAL_DIR.parent)} (commit this file)")

    if args.gate:
        if not baseline_path.exists():
            print("  GATE: no baseline found — run with --save-baseline first")
            return 2
        tolerance = json.loads(THRESHOLDS_PATH.read_text())["retrieval"][args.tier]["tolerance"]
        failures = gate_check(metrics, json.loads(baseline_path.read_text()), tolerance)
        if failures:
            print("\n".join("  " + f for f in failures))
            return 1
        print(f"  GATE: pass (tolerance {tolerance})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
