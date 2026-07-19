"""Eval dataset loading + validation (plan 002 Step 6).

Shared by the schema tests (CI) and the eval runners (Steps 7/8) — one
definition of "a valid row" everywhere. The datasets are CONTRACTS for eval
data: a malformed row fails CI, exactly like a malformed wire shape would.

Format note: files are JSONL with one pragmatic extension — lines starting
with '#' are ignored, so guidance for Timothy can live next to the data.
(Strict JSONL forbids comments; the loader documents and owns this deviation.)
"""

import json
from pathlib import Path

EVAL_DIR = Path(__file__).parent
GOLDEN_PATH = EVAL_DIR / "golden" / "golden_v1.jsonl"
CALIBRATION_PATH = EVAL_DIR / "calibration.jsonl"

# Logical collection names; the eval runner maps these to the physical
# per-mode collections (e.g. company_policies -> company_policies_live).
KNOWN_COLLECTIONS = {"company_policies"}

GOLDEN_FIELDS = {
    "id": str,
    "collection": str,
    "question": str,
    "expected_doc_ids": list,
    "reference_answer": str,
    "notes": str,
}

CALIBRATION_FIELDS = {
    "id": str,
    "question": str,
    "context": str,
    "model_answer": str,
    "human_faithfulness_score": int,
    "human_rationale": str,
}


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            rows.append(json.loads(stripped))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name}:{line_number}: not valid JSON — {exc}") from None
    return rows


def _validate(rows: list[dict], fields: dict, source: str) -> None:
    seen_ids = set()
    for row in rows:
        row_id = row.get("id", "<missing id>")
        for field, expected_type in fields.items():
            if field not in row:
                raise ValueError(f"{source} row '{row_id}': missing field '{field}'")
            if not isinstance(row[field], expected_type):
                raise ValueError(
                    f"{source} row '{row_id}': field '{field}' must be {expected_type.__name__}"
                )
        if row["id"] in seen_ids:
            raise ValueError(f"{source}: duplicate id '{row['id']}'")
        seen_ids.add(row["id"])


def load_golden(path: Path = GOLDEN_PATH) -> list[dict]:
    rows = _read_jsonl(path)
    _validate(rows, GOLDEN_FIELDS, path.name)
    for row in rows:
        if row["collection"] not in KNOWN_COLLECTIONS:
            raise ValueError(f"{path.name} row '{row['id']}': unknown collection '{row['collection']}'")
        if not row["expected_doc_ids"]:
            raise ValueError(f"{path.name} row '{row['id']}': expected_doc_ids is empty")
        for doc_id in row["expected_doc_ids"]:
            if not (isinstance(doc_id, str) and len(doc_id) == 64):
                raise ValueError(
                    f"{path.name} row '{row['id']}': '{doc_id}' is not a sha256 hex id "
                    f"(see the command in the file header for generating ids)"
                )
    return rows


def load_calibration(path: Path = CALIBRATION_PATH) -> list[dict]:
    rows = _read_jsonl(path)
    _validate(rows, CALIBRATION_FIELDS, path.name)
    for row in rows:
        if not 1 <= row["human_faithfulness_score"] <= 5:
            raise ValueError(
                f"{path.name} row '{row['id']}': human_faithfulness_score must be 1-5"
            )
    return rows
