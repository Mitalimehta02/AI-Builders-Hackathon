"""
Claims API (Stage 7; queue filters added in Stage 9).

    POST /claims              submit a claim; processing starts in the background, the id comes back at once
    GET  /claims              the queue, newest first; filter with ?status=, ?confidence_tier=, ?gate=
    GET  /claims/{id}/status  lightweight progress check, meant for polling every 1-2 seconds
    GET  /claims/{id}         everything: claim, evidence, debate transcript, decision, confidence, gate

Processing a claim costs roughly 17,000 model tokens from a limited daily allowance, so each
submission is processed once and its stored result is served from then on. While the Stage 11
evaluation batch runs, new submissions are refused (HTTP 423) so they can't use up its allowance.

Held-out benchmark claims are refused until Stage 11 (PROJECT_PLAN.md Part 5b), and a synthetic
claim's answer sheet is never stored.
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app import batch_status, db
from app.agents.sanitize import sanitize_claim
from app.models import PENDING, STATUSES, ClaimSubmission
from app.pipeline import process_claim
from app.synthetic.eval_split import is_held_out_claim

router = APIRouter(prefix="/claims", tags=["claims"])

TIERS = ("HIGH", "MEDIUM", "LOW")
GATES = ("auto_resolved", "human_review")


@router.post("", status_code=202)
def submit_claim(submission: ClaimSubmission, background_tasks: BackgroundTasks):
    """Store the claim and start processing it in the background."""
    live = batch_status.live_submission_state()
    if not live["live_submission_enabled"]:  # the evaluation batch needs the daily model allowance
        raise HTTPException(status_code=423, detail=live["reason"])

    claim = sanitize_claim(submission.to_claim_dict())  # belt and braces: unknown fields are already dropped
    if "claim_id" in claim and is_held_out_claim(claim["claim_id"]):
        raise HTTPException(status_code=403, detail=f"{claim['claim_id']} is a held-out benchmark claim and cannot be processed before Stage 11")
    claim.setdefault("claim_id", f"CLM-M-{uuid.uuid4().hex[:8].upper()}")  # manual claims get a generated id

    record_id = db.create_claim(claim)
    background_tasks.add_task(process_claim, record_id)
    return {"id": record_id, "claim_id": claim["claim_id"], "status": PENDING, "status_url": f"/claims/{record_id}/status"}


@router.get("")
def list_claims(status: str | None = None, confidence_tier: str | None = None, gate: str | None = None):
    """The claim queue, newest first.

    Filters: ?status=pending|gathering_evidence|debating|calibrating|resolved|failed,
    ?confidence_tier=HIGH|MEDIUM|LOW, ?gate=auto_resolved|human_review.
    """
    for name, value, allowed in (("status", status, STATUSES), ("confidence_tier", confidence_tier, TIERS), ("gate", gate, GATES)):
        if value is not None and value not in allowed:
            raise HTTPException(status_code=422, detail=f"{name} must be one of {list(allowed)}")
    summaries = [_summary(record) for record in db.list_claims(status)]
    return [
        summary for summary in summaries
        if (confidence_tier is None or summary["confidence_tier"] == confidence_tier)
        and (gate is None or summary["gate"] == gate)
    ]


@router.get("/{record_id}/status")
def claim_status(record_id: int):
    record = _get_or_404(record_id)
    return {
        "id": record["id"],
        "claim_id": record["claim_id"],
        "status": record["status"],
        "steps_completed": list(record["steps"] or {}),
        "error": record["error"],
        "updated_at": record["updated_at"],
    }


@router.get("/{record_id}")
def claim_detail(record_id: int):
    record = _get_or_404(record_id)
    result = record["result"] or {}
    return {
        "id": record["id"],
        "claim_id": record["claim_id"],
        "status": record["status"],
        "error": record["error"],
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
        "claim": record["claim"],
        "evidence": record["evidence"],
        "decision": result.get("decision"),
        "confidence_tier": result.get("confidence_tier"),
        "gate": result.get("gate"),
        "auto_resolved": (result["gate"] == "auto_resolved") if result else None,
        "tier_before_cap": result.get("tier_before_cap"),
        "cap_applied": result.get("cap_applied"),
        "orderings_agree": result.get("orderings_agree"),
        "unresolved_points": result.get("unresolved_points"),
        "transcript": result.get("transcript"),
        "usage": result.get("usage"),
    }


def _get_or_404(record_id):
    record = db.get_claim(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"no claim with id {record_id}")
    return record


def _summary(record):
    result = record["result"] or {}
    return {
        "id": record["id"],
        "claim_id": record["claim_id"],
        "claim_type": record["claim"]["claim_type"],
        "claim_amount": record["claim"]["claim_amount"],
        "status": record["status"],
        "decision": result.get("decision"),
        "confidence_tier": result.get("confidence_tier"),
        "gate": result.get("gate"),
        "cap_applied": result.get("cap_applied"),
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
    }
