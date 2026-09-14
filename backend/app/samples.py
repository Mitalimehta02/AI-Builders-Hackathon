"""
Stored sample results for the intake page's "load a sample claim" (Stage 8).

These are real ClaimLens results for DEVELOPMENT-SET claims, saved from earlier runs and served
without any model call. They predate the final Stage 11 configuration, so each one is labelled with
the protocol and temperature it was produced under (see docs/METHODOLOGY.md).

Left out on purpose:
- CLM-0030: its data was repaired after its stored run, so that result no longer matches the claim.
- claims whose only stored result is incomplete.
Held-out claims are never included.
"""

from functools import lru_cache
import json
from pathlib import Path

from app.agents.sanitize import sanitize_claim
from app.synthetic.eval_split import is_dev_claim

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CLAIMS_PATH = DATA_DIR / "synthetic_claims.json"

STAGE6_V1 = "Stage 6 dev run, 2026-09-13: order swap, no point accounting, temperature 1.0"
STAGE6_V2 = "Stage 6 dev re-run, 2026-09-13: with the since-removed rebuttal round, temperature 1.0"
STAGE7_API = "Stage 7 live API run, 2026-09-14: with the since-removed rebuttal round, temperature 1.0"

# (claim id, stored file, file format, label)
SAMPLE_SOURCES = [
    ("CLM-0001", "stage6_dev_results_v2.json", "dev_results", STAGE6_V2),
    ("CLM-0006", "stage6_dev_results.json", "dev_results", STAGE6_V1),
    ("CLM-0019", "stage6_dev_results.json", "dev_results", STAGE6_V1),
    ("CLM-0027", "stage7_e2e/claim_2_CLM-0027_detail.json", "api_detail", STAGE7_API),
    ("CLM-0034", "stage6_dev_results.json", "dev_results", STAGE6_V1),
    ("CLM-0035", "stage7_e2e/claim_1_CLM-0035_detail.json", "api_detail", STAGE7_API),
]

NOTE = ("Stored result for a development-set claim, produced before the final evaluation settings. "
        "No model call was made to show it.")


@lru_cache(maxsize=1)
def load_samples():
    """{claim_id: case detail in the same shape as GET /claims/{id}}."""
    with open(CLAIMS_PATH, encoding="utf-8") as f:
        claims = {c["claim_id"]: c for c in json.load(f)}

    samples = {}
    for claim_id, file_name, file_format, label in SAMPLE_SOURCES:
        if not is_dev_claim(claim_id):
            raise ValueError(f"{claim_id} is not a development-set claim and must not be shown as a sample")
        stored = json.loads((DATA_DIR / file_name).read_text(encoding="utf-8"))
        if file_format == "dev_results":
            evidence, result = stored[claim_id]["evidence"], stored[claim_id]["claimlens"]
        else:
            evidence, result = stored["evidence"], stored
        samples[claim_id] = _case_detail(claim_id, sanitize_claim(claims[claim_id]), evidence, result, label)
    return samples


def list_samples():
    return [
        {
            "claim_id": detail["claim_id"],
            "claim_type": detail["claim"]["claim_type"],
            "claim_amount": detail["claim"]["claim_amount"],
            "description": detail["claim"]["incident"]["description"],
            "status": detail["status"],
            "decision": detail["decision"],
            "confidence_tier": detail["confidence_tier"],
            "gate": detail["gate"],
            "cap_applied": detail["cap_applied"],
            "source": detail["stored_sample"]["source"],
        }
        for detail in load_samples().values()
    ]


def get_sample(claim_id):
    return load_samples().get(claim_id)


def _case_detail(claim_id, claim, evidence, result, label):
    return {
        "id": None,
        "claim_id": claim_id,
        "status": "resolved",
        "error": None,
        "claim": claim,
        "evidence": evidence,
        "decision": result.get("decision"),
        "confidence_tier": result.get("confidence_tier"),
        "gate": result.get("gate"),
        "auto_resolved": result.get("gate") == "auto_resolved",
        "tier_before_cap": result.get("tier_before_cap"),
        "cap_applied": result.get("cap_applied"),
        "orderings_agree": result.get("orderings_agree"),
        "unresolved_points": result.get("unresolved_points"),
        "transcript": result.get("transcript"),
        "usage": result.get("usage"),
        "stored_sample": {"source": label, "note": NOTE},
    }
