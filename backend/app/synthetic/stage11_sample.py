"""
Pre-registered Stage 11 evaluation sample (PROJECT_PLAN.md Part 5b, budget-constrained sample).

Selects 15 of the 27 held-out claims by stratified random sampling with a fixed seed and writes
the selection to backend/data/stage11_sample.json, BEFORE any held-out claim is run. It reads
only each claim's ID and label (is_fraud, difficulty) - never claim content - and calls no model.

Method:
1. Split the 27 held-out claims by label (fraud / legitimate). Allocate the 15 slots between the
   two in proportion to the held-out ratio, using largest-remainder rounding.
2. Within each label, allocate that label's slots across the difficulty tiers (easy, ambiguous,
   hard) in proportion to tier size, again by largest remainder (ties go to the earlier tier in
   that fixed order), then draw claims at random within each tier using the fixed seed.
3. Record SHA-256 hashes of the sorted ID list and of the frozen claim data, so any later change
   to either is detectable.

Run from the backend/ folder:
    .\\.venv\\Scripts\\python.exe -m app.synthetic.stage11_sample
Re-running reproduces the identical selection; it refuses to overwrite a different one.
"""

import hashlib
import json
import random
import sys
from pathlib import Path

from app.synthetic.eval_split import is_dev_claim

SEED = 20260914
SAMPLE_SIZE = 15
HELD_OUT_SIZE = 27
REGISTERED_ON = "2026-09-14"
LABELS = ("fraud", "legitimate")
DIFFICULTIES = ("easy", "ambiguous", "hard")

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CLAIMS_PATH = DATA_DIR / "synthetic_claims.json"
SAMPLE_PATH = DATA_DIR / "stage11_sample.json"


def largest_remainder(total, sizes):
    """Split `total` slots across groups in proportion to `sizes` ({group: size}), whole numbers only."""
    grand_total = sum(sizes.values())
    exact = {group: total * size / grand_total for group, size in sizes.items()}
    allocation = {group: int(share) for group, share in exact.items()}
    order = list(sizes)
    by_remainder = sorted(order, key=lambda group: (-(exact[group] - allocation[group]), order.index(group)))
    for group in by_remainder[: total - sum(allocation.values())]:
        allocation[group] += 1
    return allocation


def ids_hash(claim_ids):
    return hashlib.sha256("\n".join(sorted(claim_ids)).encode("utf-8")).hexdigest()


def data_hash(claims):
    """Hash of the parsed claim data (independent of file line endings)."""
    return hashlib.sha256(json.dumps(claims, sort_keys=True).encode("utf-8")).hexdigest()


def select_sample(claims):
    """Return the pre-registration record for the stratified sample."""
    held_out = [c for c in claims if not is_dev_claim(c["claim_id"])]
    if len(held_out) != HELD_OUT_SIZE:
        raise ValueError(f"expected {HELD_OUT_SIZE} held-out claims, found {len(held_out)}")

    strata = {(label, tier): [] for label in LABELS for tier in DIFFICULTIES}
    for claim in held_out:  # only the ID and the two label fields are read
        label = "fraud" if claim["ground_truth"]["is_fraud"] else "legitimate"
        strata[(label, claim["ground_truth"]["difficulty"])].append(claim["claim_id"])

    label_sizes = {label: sum(len(strata[(label, tier)]) for tier in DIFFICULTIES) for label in LABELS}
    label_slots = largest_remainder(SAMPLE_SIZE, label_sizes)

    rng = random.Random(SEED)
    selected, strata_counts = [], {}
    for label in LABELS:
        tier_sizes = {tier: len(strata[(label, tier)]) for tier in DIFFICULTIES}
        tier_slots = largest_remainder(label_slots[label], tier_sizes)
        for tier in DIFFICULTIES:
            chosen = rng.sample(sorted(strata[(label, tier)]), tier_slots[tier])
            selected += chosen
            strata_counts[f"{label}/{tier}"] = {"held_out": tier_sizes[tier], "selected": tier_slots[tier]}

    claim_ids = sorted(selected)
    return {
        "registered_on": REGISTERED_ON,
        "purpose": "Stage 11 headline evaluation sample (PROJECT_PLAN.md Part 5b); chosen before any held-out claim was run",
        "seed": SEED,
        "sample_size": SAMPLE_SIZE,
        "held_out_size": HELD_OUT_SIZE,
        "method": ("stratified random sample: slots split between fraud and legitimate in proportion to the held-out set "
                   "(largest remainder), then across easy/ambiguous/hard within each label (largest remainder, ties to the "
                   "earlier tier), then drawn at random within each tier with random.Random(seed)"),
        "label_counts": {label: {"held_out": label_sizes[label], "selected": label_slots[label]} for label in LABELS},
        "strata_counts": strata_counts,
        "claim_ids": claim_ids,
        "claim_ids_sha256": ids_hash(claim_ids),
        "claim_ids_hash_input": "the claim IDs sorted ascending, joined with newline characters, UTF-8 encoded",
        "claims_data_sha256": data_hash(claims),
        "claims_data_hash_input": "json.dumps(<parsed synthetic_claims.json>, sort_keys=True), UTF-8 encoded",
    }


def main():
    with open(CLAIMS_PATH, encoding="utf-8") as f:
        claims = json.load(f)
    record = select_sample(claims)

    if SAMPLE_PATH.exists():
        existing = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
        if existing["claim_ids_sha256"] != record["claim_ids_sha256"]:
            print("REFUSING: a different pre-registered sample already exists. It must not be replaced.")
            return 1
        print("Pre-registered sample already exists and is reproduced exactly.")
    else:
        SAMPLE_PATH.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {SAMPLE_PATH.name}")

    print(f"seed {record['seed']}; {record['sample_size']} of {record['held_out_size']} held-out claims")
    print("label counts:", record["label_counts"])
    print("strata counts:", record["strata_counts"])
    print("claim IDs:", ", ".join(record["claim_ids"]))
    print("claim_ids_sha256:", record["claim_ids_sha256"])
    print("claims_data_sha256:", record["claims_data_sha256"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
