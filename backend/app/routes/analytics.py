"""
Portfolio analytics (Stage 10): the PROJECT_PLAN.md Part 5 must-have metrics, computed from the
stored Stage 11 batch results on the pre-registered held-out sample. No model calls.

    GET /analytics

Built to make the Part 5b reporting rules easy to follow:
- raw counts, never percentages (the sample is only 15 claims);
- the "always approve" reference line next to every accuracy figure;
- the sample size, the pre-registration, and how many of the 15 claims are complete, always included;
- a difference of one or two claims is flagged as directionally suggestive at most.

The batch may still be running. Metrics cover claims where BOTH the baseline and ClaimLens have
finished, taken in the pre-registered processing order up to the first claim that has not finished
yet (the stopping rule in docs/METHODOLOGY.md). A claim that failed keeps its place and is counted as
failed. Only aggregate counts are returned - never individual held-out claims or transcripts.
"""

import json
from collections import Counter
from pathlib import Path

from fastapi import APIRouter

from app import batch_status

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
SAMPLE_PATH = DATA_DIR / "stage11_sample.json"
CLAIMS_PATH = DATA_DIR / "synthetic_claims.json"
NAIVE_PATH = DATA_DIR / "results_naive.json"
CLAIMLENS_PATH = DATA_DIR / "results_claimlens.json"

MANUAL_REVIEW_MINUTES = 22   # assumption stated in PROJECT_PLAN.md Part 5; shown on the page
SUGGESTIVE_ONLY_WITHIN = 2   # Part 5b: a gap of one or two claims is directionally suggestive at most
TIERS = ("HIGH", "MEDIUM", "LOW")

router = APIRouter(tags=["analytics"])


@router.get("/analytics")
def analytics():
    return compute_analytics()


def _load(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def claim_states(sample, naive, claimlens):
    """[(claim_id, state)] in the pre-registered order: complete, failed, in_progress or not_started."""
    states = []
    for claim_id in sample["claim_ids"]:
        naive_entry = (naive or {}).get("claims", {}).get(claim_id, {})
        lens_entry = (claimlens or {}).get("claims", {}).get(claim_id, {})
        if naive_entry.get("status") == "complete" and lens_entry.get("status") == "complete":
            state = "complete"
        elif "failed" in (naive_entry.get("status"), lens_entry.get("status")):
            state = "failed"
        elif naive_entry or lens_entry:
            state = "in_progress"
        else:
            state = "not_started"
        states.append((claim_id, state))
    return states


def system_metrics(claim_ids, claims, decision_of, is_high_confidence):
    """Counts for one system over the reported, completed claims."""
    metrics = {"correct": 0, "high_confidence": 0, "high_confidence_wrong": 0, "false_positives": 0,
               "false_negatives": 0, "fraud_amount_caught": 0.0, "fraud_amount_total": 0.0}
    for claim_id in claim_ids:
        is_fraud = claims[claim_id]["ground_truth"]["is_fraud"]
        amount = claims[claim_id]["claim_amount"]
        decision = decision_of(claim_id)
        correct = (decision == "DENY") == is_fraud
        metrics["correct"] += correct
        if is_high_confidence(claim_id):
            metrics["high_confidence"] += 1
            metrics["high_confidence_wrong"] += not correct
        if not is_fraud and decision == "DENY":
            metrics["false_positives"] += 1
        if is_fraud and decision == "APPROVE":
            metrics["false_negatives"] += 1
        if is_fraud:
            metrics["fraud_amount_total"] += amount
            if decision == "DENY":
                metrics["fraud_amount_caught"] += amount
    metrics["fraud_amount_caught"] = round(metrics["fraud_amount_caught"], 2)
    metrics["fraud_amount_total"] = round(metrics["fraud_amount_total"], 2)
    return metrics


def compute_analytics():
    sample = _load(SAMPLE_PATH)
    naive, claimlens = _load(NAIVE_PATH), _load(CLAIMLENS_PATH)
    claims = {c["claim_id"]: c for c in _load(CLAIMS_PATH) if c["claim_id"] in sample["claim_ids"]}
    states = claim_states(sample, naive, claimlens)
    state_counts = Counter(state for _, state in states)
    total = len(states)

    # Reported set: the pre-registered order, up to the first claim that has not finished.
    reported = []
    for claim_id, state in states:
        if state not in ("complete", "failed"):
            break
        reported.append((claim_id, state))
    complete = [claim_id for claim_id, state in reported if state == "complete"]
    failed = [claim_id for claim_id, state in reported if state == "failed"]
    fraud = [c for c in complete if claims[c]["ground_truth"]["is_fraud"]]
    legitimate = [c for c in complete if not claims[c]["ground_truth"]["is_fraud"]]

    baseline = system_metrics(
        complete, claims,
        decision_of=lambda c: naive["claims"][c]["result"]["decision"],
        is_high_confidence=lambda c: naive["claims"][c]["result"]["high_confidence"],
    )
    baseline["high_confidence_rule"] = "confidence of 80 or more (pre-registered at Stage 4)"

    results = {c: claimlens["claims"][c]["result"] for c in complete}
    lens = system_metrics(
        complete, claims,
        decision_of=lambda c: results[c]["decision"],
        is_high_confidence=lambda c: results[c]["confidence_tier"] == "HIGH",
    )
    auto_resolved = [c for c in complete if results[c]["gate"] == "auto_resolved"]
    wrong = {c for c in complete if (results[c]["decision"] == "DENY") != claims[c]["ground_truth"]["is_fraud"]}
    high_before_cap = [c for c in complete if results[c].get("tier_before_cap") == "HIGH"]
    lens.update(
        high_confidence_rule="final confidence tier HIGH",
        auto_resolved=len(auto_resolved),
        auto_resolved_fraud=sum(claims[c]["ground_truth"]["is_fraud"] for c in auto_resolved),
        human_review=len(complete) - len(auto_resolved),
        tier_counts={tier: sum(results[c]["confidence_tier"] == tier for c in complete) for tier in TIERS},
        tier_before_cap_high=len(high_before_cap),
        tier_before_cap_high_wrong=sum(c in wrong for c in high_before_cap),
        cap_applied=sum(bool(results[c].get("cap_applied")) for c in complete),
        cap_applied_on_wrong_decisions=sum(bool(results[c].get("cap_applied")) and c in wrong for c in complete),
        orderings_disagreed=sum(not results[c]["orderings_agree"] for c in complete),
        manual_review_minutes_assumed=MANUAL_REVIEW_MINUTES,
        adjuster_hours_saved=round(len(auto_resolved) * MANUAL_REVIEW_MINUTES / 60, 1),
    )

    status = batch_status.read_status()
    is_final = len(reported) == total
    notes = []
    if not is_final:
        notes.append(f"Interim figures: {len(complete)} of {total} pre-registered claims are complete. "
                     "These counts will change as the batch continues; they are not final results.")
    if failed:
        notes.append(f"{len(failed)} claim(s) failed and are counted as failed in their pre-registered position.")
    if complete:
        if len(fraud) * 2 != len(legitimate):
            notes.append(f"The completed claims are {len(fraud)} fraud and {len(legitimate)} legitimate, "
                         "not the 1 : 2 mix of the full sample.")
        accuracy_gap = lens["correct"] - baseline["correct"]
        if abs(accuracy_gap) <= SUGGESTIVE_ONLY_WITHIN:
            notes.append(f"Accuracy differs by {abs(accuracy_gap)} claim(s) between the systems: within two claims, "
                         "so at most directionally suggestive.")
        confident_gap = lens["high_confidence_wrong"] - baseline["high_confidence_wrong"]
        if abs(confident_gap) <= SUGGESTIVE_ONLY_WITHIN:
            notes.append(f"Confidently wrong answers differ by {abs(confident_gap)} claim(s): within two claims, "
                         "so at most directionally suggestive.")

    meta = (claimlens or naive or {}).get("meta", {})
    return {
        "evaluation": {
            "sample_size": total,
            "held_out_size": sample["held_out_size"],
            "registered_on": sample["registered_on"],
            "seed": sample["seed"],
            "claim_ids_sha256": sample["claim_ids_sha256"],
            "processing_order": "ascending claim ID, as pre-registered",
            "model": meta.get("model"),
            "settings": meta.get("settings"),
        },
        "progress": {
            "total": total,
            "complete": len(complete),
            "failed": len(failed),
            "in_progress": state_counts["in_progress"],
            "not_started": state_counts["not_started"],
            "reported": len(reported),
            "is_final": is_final,
            "batch_running": batch_status.batch_is_running(status),
            "waiting_until": status.get("waiting_until") if status else None,
        },
        "composition": {"fraud": len(fraud), "legitimate": len(legitimate)},
        "reference": {
            "always_approve_correct": len(legitimate),
            "out_of": len(complete),
            "full_sample_always_approve_correct": sum(not c["ground_truth"]["is_fraud"] for c in claims.values()),
            "full_sample_size": total,
        },
        "baseline": baseline,
        "claimlens": lens,
        "notes": notes,
    }
