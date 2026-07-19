"""Judge eval tests (plan 002 Step 8). Parser and agreement math as pure
functions; the plumbing loop end-to-end with the mock judge (no containers).
"""

from eval.eval_judge import parse_verdict, agreement_report, plumbing_material, _judge_chain, judge_one
from eval.dataset import load_golden
from eval.eval_judge import RUBRIC_PATH


def test_parse_verdict_valid_cases():
    assert parse_verdict("5: fully supported") == (5, "fully supported")
    # first-colon-only split: colons inside the rationale survive
    assert parse_verdict("2: bad: invents details") == (2, "bad: invents details")
    assert parse_verdict("  3:  spaced  ") == (3, "spaced")


def test_parse_verdict_rejects_garbage():
    assert parse_verdict("the answer looks fine to me")[0] is None
    assert parse_verdict("7: out of range")[0] is None
    assert parse_verdict("")[0] is None


def test_agreement_report_hand_computed():
    report = agreement_report([(5, 5), (3, 5), (2, 2)])
    assert report["n"] == 3
    assert report["exact_match_rate"] == round(2 / 3, 4)
    assert report["mean_abs_difference"] == round((0 + 2 + 0) / 3, 4)
    assert agreement_report([]) == {"n": 0}


def test_plumbing_loop_end_to_end():
    """Rubric loads, prompt renders, mock judge answers, parser parses — the
    whole loop, zero containers."""
    rows = load_golden()
    material = plumbing_material(rows)
    assert {m["id"] for m in material} == {row["id"] for row in rows}
    assert all(m["context"] and m["answer"] for m in material)

    chain = _judge_chain("plumbing")
    rubric = RUBRIC_PATH.read_text()
    for item in material:
        score, rationale = judge_one(chain, rubric, item["context"], item["answer"])
        assert score in (2, 5)          # the two mock-pool verdicts
        assert rationale
