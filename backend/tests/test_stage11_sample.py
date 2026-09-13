"""
Guards for the pre-registered Stage 11 sample (backend/data/stage11_sample.json). No model calls.

- the committed selection is reproduced exactly by the documented method and seed
- the ID list and the frozen claim data still match their recorded hashes
- every selected claim is held-out, and the label ratio and tier spread follow the method
"""

import json

from app.synthetic.eval_split import is_dev_claim
from app.synthetic.stage11_sample import SAMPLE_PATH, data_hash, ids_hash, largest_remainder, select_sample
from tests.test_sanitize import load_claims


def load_sample():
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


def test_committed_sample_is_reproduced_by_the_documented_method():
    assert select_sample(load_claims()) == load_sample()


def test_sample_hashes_still_match():
    sample = load_sample()
    assert ids_hash(sample["claim_ids"]) == sample["claim_ids_sha256"]
    assert data_hash(load_claims()) == sample["claims_data_sha256"], "the frozen claim data has changed since pre-registration"


def test_sample_contains_only_held_out_claims_in_the_registered_proportions():
    sample = load_sample()
    assert len(sample["claim_ids"]) == len(set(sample["claim_ids"])) == 15
    assert not any(is_dev_claim(claim_id) for claim_id in sample["claim_ids"])
    counts = sample["label_counts"]
    assert sum(c["selected"] for c in counts.values()) == 15
    assert sum(c["held_out"] for c in counts.values()) == 27


def test_largest_remainder_allocation():
    assert largest_remainder(15, {"a": 10, "b": 17}) == {"a": 6, "b": 9}
    assert sum(largest_remainder(6, {"easy": 3, "ambiguous": 4, "hard": 3}).values()) == 6
