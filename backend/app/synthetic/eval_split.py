"""
Evaluation split (PROJECT_PLAN.md Part 5b).

DEVELOPMENT SET: the 7 claims inspected and run during Stages 2-5. All prompt iteration,
debugging and design changes happen on these, and only these.

HELD-OUT SET: the other 33 claims. They are not inspected, run or tuned against until the
final Stage 11 batch. Headline accuracy and confidently-wrong figures come from them.

Development scripts call require_dev_set() before running anything, so a held-out claim
can't be run by accident.
"""

DEV_SET_IDS = ("CLM-0001", "CLM-0006", "CLM-0019", "CLM-0027", "CLM-0030", "CLM-0034", "CLM-0035")


def is_dev_claim(claim_id):
    return claim_id in DEV_SET_IDS


def require_dev_set(claim_ids):
    """Raise before anything runs if a held-out claim was requested outside Stage 11."""
    held_out = [claim_id for claim_id in claim_ids if not is_dev_claim(claim_id)]
    if held_out:
        raise ValueError(f"held-out claims must not be run before Stage 11: {held_out}")
