"""Eval dataset schema tests (plan 002 Step 6c).

These run in CI: a malformed golden/calibration row fails the build the same
way a broken wire contract would. When Timothy adds rows, these tests are the
first reviewer.
"""

from eval.dataset import load_golden, load_calibration
from app.rag.seed_documents import SEED_DOCUMENTS
from app.rag.vector_store import VectorStoreManager


def test_golden_dataset_loads_and_validates():
    rows = load_golden()
    assert len(rows) >= 3  # the worked examples, minimum


def test_golden_expected_ids_reference_real_seed_documents():
    """Every expected_doc_id must be the deterministic id of an actual seed doc.
    Guards against drift: if seed content changes, its sha256 changes, and this
    test names exactly which golden rows now point at a ghost."""
    seed_ids = {VectorStoreManager.deterministic_id(d) for d in SEED_DOCUMENTS}
    for row in load_golden():
        for doc_id in row["expected_doc_ids"]:
            assert doc_id in seed_ids, (
                f"golden row '{row['id']}' references id {doc_id[:12]}… "
                f"which matches no document in seed_documents.py"
            )


def test_calibration_set_loads_and_validates():
    rows = load_calibration()
    assert len(rows) >= 1
