"""Retrieval eval tests (plan 002 Step 7). Three layers:
1. The metrics as pure functions against hand-computed truths.
2. The plumbing tier end-to-end (no containers) + its determinism guarantee.
3. The gate logic against a synthetic baseline.
"""

from eval.eval_retrieval import (
    hit_at_k,
    reciprocal_rank,
    compute_metrics,
    plumbing_retrieve,
    gate_check,
)
from eval.dataset import load_golden

EXPECTED = ["doc_a"]


def test_hit_at_k_hand_computed_cases():
    assert hit_at_k(EXPECTED, ["doc_a", "x", "y"], 1) is True
    assert hit_at_k(EXPECTED, ["x", "doc_a", "y"], 1) is False   # right doc, rank 2, k=1
    assert hit_at_k(EXPECTED, ["x", "doc_a", "y"], 3) is True
    assert hit_at_k(EXPECTED, ["x", "y", "z"], 3) is False


def test_reciprocal_rank_hand_computed_cases():
    assert reciprocal_rank(EXPECTED, ["doc_a", "x"]) == 1.0
    assert reciprocal_rank(EXPECTED, ["x", "doc_a"]) == 0.5
    assert reciprocal_rank(EXPECTED, ["x", "y", "doc_a"]) == 1.0 / 3
    assert reciprocal_rank(EXPECTED, ["x", "y"]) == 0.0


def test_compute_metrics_aggregates_correctly():
    rows = [
        {"id": "r1", "expected_doc_ids": ["doc_a"]},
        {"id": "r2", "expected_doc_ids": ["doc_b"]},
    ]
    retrieved = {"r1": ["doc_a", "x", "y"], "r2": ["x", "doc_b", "y"]}
    metrics = compute_metrics(rows, retrieved)
    assert metrics["hit@1"] == 0.5      # r1 yes, r2 no
    assert metrics["hit@3"] == 1.0
    assert metrics["mrr"] == round((1.0 + 0.5) / 2, 4)
    assert metrics["n"] == 2


def test_plumbing_tier_runs_and_is_deterministic():
    rows = load_golden()
    first = plumbing_retrieve(rows, k=3)
    second = plumbing_retrieve(rows, k=3)
    assert first == second                      # the tier's entire promise
    assert set(first) == {row["id"] for row in rows}
    metrics = compute_metrics(rows, first)
    assert 0.0 <= metrics["mrr"] <= 1.0          # scores meaningless, bounds are not


def test_gate_detects_regression_and_passes_equal():
    baseline = {"hit@1": 0.8, "hit@3": 1.0, "mrr": 0.9, "n": 3}
    assert gate_check({"hit@1": 0.8, "hit@3": 1.0, "mrr": 0.9}, baseline, 0.0) == []
    failures = gate_check({"hit@1": 0.5, "hit@3": 1.0, "mrr": 0.9}, baseline, 0.0)
    assert len(failures) == 1 and "hit@1" in failures[0]
    # tolerance absorbs small wobble
    assert gate_check({"hit@1": 0.76, "hit@3": 1.0, "mrr": 0.9}, baseline, 0.05) == []
