"""
Evaluation split (PROJECT_PLAN.md Part 5b).

DEVELOPMENT SET (13): all prompt iteration, debugging and design changes happen on these only.
- CLM-0001, 0006, 0019, 0027, 0030, 0034, 0035 were inspected and run during Stages 2-5.
- CLM-0014, 0024, 0025, 0032, 0033, 0036 drove data or evidence-rule fixes before the split
  existed, so they were moved here after Stage 6 (docs/METHODOLOGY.md).

HELD-OUT SET (27): every other benchmark claim. Not inspected, run or tuned against until the
final Stage 11 batch, which uses the pre-registered sample in backend/data/stage11_sample.json.

Development scripts call require_dev_set() before running anything, and the API refuses
held-out claims (is_held_out_claim), so a held-out claim can't be run by accident.
"""

import json
from functools import lru_cache
from pathlib import Path

CLAIMS_PATH = Path(__file__).resolve().parents[2] / "data" / "synthetic_claims.json"

DEV_SET_IDS = (
    "CLM-0001", "CLM-0006", "CLM-0014", "CLM-0019", "CLM-0024", "CLM-0025", "CLM-0027",
    "CLM-0030", "CLM-0032", "CLM-0033", "CLM-0034", "CLM-0035", "CLM-0036",
)


def is_dev_claim(claim_id):
    return claim_id in DEV_SET_IDS


@lru_cache(maxsize=1)
def benchmark_claim_ids():
    """IDs of every synthetic benchmark claim (only the IDs are read)."""
    with open(CLAIMS_PATH, encoding="utf-8") as f:
        return frozenset(claim["claim_id"] for claim in json.load(f))


def is_held_out_claim(claim_id):
    """True for a benchmark claim outside the development set."""
    return claim_id in benchmark_claim_ids() and not is_dev_claim(claim_id)


def require_dev_set(claim_ids):
    """Raise before anything runs if a held-out claim was requested outside Stage 11."""
    held_out = [claim_id for claim_id in claim_ids if not is_dev_claim(claim_id)]
    if held_out:
        raise ValueError(f"held-out claims must not be run before Stage 11: {held_out}")
