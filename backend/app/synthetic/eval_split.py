"""
Evaluation split (PROJECT_PLAN.md Part 5b).

DEVELOPMENT SET (13): all prompt iteration, debugging and design changes happen on these only.
- CLM-0001, 0006, 0019, 0027, 0030, 0034, 0035 were inspected and run during Stages 2-5.
- CLM-0014, 0024, 0025, 0032, 0033, 0036 drove data or evidence-rule fixes before the split
  existed, so they were moved here after Stage 6 (docs/METHODOLOGY.md).

HELD-OUT SET (27): every other claim. Not inspected, run or tuned against until the final
Stage 11 batch. Headline accuracy and confidently-wrong figures come from them.

Development scripts call require_dev_set() before running anything, so a held-out claim
can't be run by accident.
"""

DEV_SET_IDS = (
    "CLM-0001", "CLM-0006", "CLM-0014", "CLM-0019", "CLM-0024", "CLM-0025", "CLM-0027",
    "CLM-0030", "CLM-0032", "CLM-0033", "CLM-0034", "CLM-0035", "CLM-0036",
)


def is_dev_claim(claim_id):
    return claim_id in DEV_SET_IDS


def require_dev_set(claim_ids):
    """Raise before anything runs if a held-out claim was requested outside Stage 11."""
    held_out = [claim_id for claim_id in claim_ids if not is_dev_claim(claim_id)]
    if held_out:
        raise ValueError(f"held-out claims must not be run before Stage 11: {held_out}")
