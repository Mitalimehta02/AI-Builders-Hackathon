"""
Stored sample results for the intake page's "load a sample claim" and the dashboard.

These are the Stage 11 evaluation results: the pre-registered held-out sample, run through the final
configuration (temperature 0.2, no rebuttal round). They are read from the committed results file and
served without any model call, each labelled with the run that produced it.

Served only once the run has finished: while the batch is running, or while any pre-registered claim
is still unfinished, nothing is served, so no individual held-out result is visible before the run is
complete. A claim that failed in the run has no result to show and is left out.

The earlier development-set samples (produced under temperature 1.0, some with the since-removed
rebuttal round) are no longer shown, because they are not comparable with the final run
(docs/METHODOLOGY.md).
"""

import json
from pathlib import Path

from app import batch_status
from app.agents.sanitize import sanitize_claim

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CLAIMS_PATH = DATA_DIR / "synthetic_claims.json"
SAMPLE_PATH = DATA_DIR / "stage11_sample.json"
RESULTS_PATH = DATA_DIR / "results_claimlens.json"

SOURCE = ("Stage 11 evaluation run, 2026-09-14/15: final configuration (temperature 0.2, no rebuttal round), "
          "pre-registered held-out sample")
NOTE = "Stored result from the pre-registered Stage 11 evaluation run. No model call was made to show it."
FINISHED = ("complete", "failed")

_cache = {"key": None, "samples": {}}


def load_samples():
    """{claim_id: case detail in the same shape as GET /claims/{id}}; empty until the run has finished."""
    if batch_status.batch_is_running() or not RESULTS_PATH.exists():
        return {}
    stat = RESULTS_PATH.stat()
    key = (stat.st_mtime_ns, stat.st_size)   # rebuild only when the results file changes
    if _cache["key"] != key:
        _cache.update(key=key, samples=_build_samples())
    return _cache["samples"]


def _build_samples():
    sample_ids = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))["claim_ids"]
    results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))["claims"]
    if any(results.get(claim_id, {}).get("status") not in FINISHED for claim_id in sample_ids):
        return {}   # the run is not finished: show nothing rather than a partial set
    with open(CLAIMS_PATH, encoding="utf-8") as f:
        claims = {c["claim_id"]: c for c in json.load(f)}
    return {
        claim_id: _case_detail(claim_id, sanitize_claim(claims[claim_id]), results[claim_id]["evidence"],
                               results[claim_id]["result"])
        for claim_id in sample_ids   # the pre-registered processing order
        if results[claim_id]["status"] == "complete"
    }


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


def _case_detail(claim_id, claim, evidence, result):
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
        "stored_sample": {"source": SOURCE, "note": NOTE},
    }
