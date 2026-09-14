"""
Stage 10 analytics tests. Offline: results files are built in a temporary folder from the
pre-registered sample IDs, so no quota is used and the real batch files are never read.

What they protect:
- only claims finished by BOTH systems count, in pre-registered order up to the first unfinished claim
- a failed claim keeps its place and is counted as failed
- every Part 5 metric is a raw count, computed correctly, with the always-approve reference line
- the response never contains percentages or individual held-out claims
- small differences are flagged as directionally suggestive
"""

import json

import pytest
from fastapi.testclient import TestClient

from app import batch_status
from app.main import app
from app.routes import analytics
from tests.test_sanitize import load_claims

SAMPLE = json.loads(analytics.SAMPLE_PATH.read_text(encoding="utf-8"))
ORDER = SAMPLE["claim_ids"]
TRUTH = {c["claim_id"]: c for c in load_claims() if c["claim_id"] in ORDER}


def is_fraud(claim_id):
    return TRUTH[claim_id]["ground_truth"]["is_fraud"]


@pytest.fixture
def results_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(analytics, "NAIVE_PATH", tmp_path / "results_naive.json")
    monkeypatch.setattr(analytics, "CLAIMLENS_PATH", tmp_path / "results_claimlens.json")
    monkeypatch.setattr(batch_status, "STATUS_PATH", tmp_path / "batch_status.json")
    return tmp_path


def write_results(results_dir, entries):
    """entries: {claim_id: dict(baseline=(decision, confidence), lens=(decision, tier, gate, cap, agree)) or 'failed' or 'in_progress'}."""
    meta = {"model": "test-model", "settings": {"temperature": 0.2}, "sample_claim_ids_sha256": SAMPLE["claim_ids_sha256"]}
    naive, lens = {"meta": meta, "claims": {}}, {"meta": meta, "claims": {}}
    for claim_id, entry in entries.items():
        if entry in ("failed", "in_progress"):
            naive["claims"][claim_id] = {"status": "complete" if entry == "failed" else "in_progress"}
            lens["claims"][claim_id] = {"status": entry, "steps": {}}
            continue
        decision, confidence = entry["baseline"]
        naive["claims"][claim_id] = {"status": "complete", "result": {"decision": decision, "confidence": confidence,
                                                                     "high_confidence": confidence >= 80}}
        lens_decision, tier, gate, cap, agree = entry["lens"]
        lens["claims"][claim_id] = {"status": "complete", "result": {
            "decision": lens_decision, "confidence_tier": tier, "gate": gate, "cap_applied": cap,
            "tier_before_cap": "HIGH" if cap else tier, "orderings_agree": agree}}
    (results_dir / "results_naive.json").write_text(json.dumps(naive), encoding="utf-8")
    (results_dir / "results_claimlens.json").write_text(json.dumps(lens), encoding="utf-8")


def perfect_claimlens_naive_baseline(claim_id):
    """Baseline always approves with confidence 90; ClaimLens is always right, HIGH + auto-resolved on legitimate claims."""
    if is_fraud(claim_id):
        return {"baseline": ("APPROVE", 90), "lens": ("DENY", "MEDIUM", "human_review", False, True)}
    return {"baseline": ("APPROVE", 90), "lens": ("APPROVE", "HIGH", "auto_resolved", False, True)}


def test_no_results_yet(results_dir):
    report = analytics.compute_analytics()
    assert report["progress"] == {**report["progress"], "total": 15, "complete": 0, "reported": 0, "not_started": 15, "is_final": False}
    assert report["reference"]["out_of"] == 0
    assert report["reference"]["full_sample_always_approve_correct"] == 10 and report["reference"]["full_sample_size"] == 15
    assert report["evaluation"]["sample_size"] == 15 and report["evaluation"]["seed"] == 20260914
    assert "0 of 15" in report["notes"][0]


def test_partial_batch_counts_only_the_finished_prefix(results_dir):
    entries = {claim_id: perfect_claimlens_naive_baseline(claim_id) for claim_id in ORDER[:3]}
    entries[ORDER[3]] = "in_progress"
    entries[ORDER[5]] = perfect_claimlens_naive_baseline(ORDER[5])  # finished out of order: not reported yet
    write_results(results_dir, entries)

    report = analytics.compute_analytics()
    first_three = ORDER[:3]
    legit = sum(not is_fraud(c) for c in first_three)
    fraud = 3 - legit
    assert report["progress"]["complete"] == 3 and report["progress"]["reported"] == 3
    assert report["progress"]["in_progress"] == 1 and report["progress"]["is_final"] is False
    assert report["reference"] == {**report["reference"], "always_approve_correct": legit, "out_of": 3}

    baseline, lens = report["baseline"], report["claimlens"]
    assert baseline["correct"] == legit and baseline["high_confidence"] == 3 and baseline["high_confidence_wrong"] == fraud
    assert baseline["false_negatives"] == fraud and baseline["false_positives"] == 0 and baseline["fraud_amount_caught"] == 0
    assert lens["correct"] == 3 and lens["high_confidence"] == legit and lens["high_confidence_wrong"] == 0
    assert lens["auto_resolved"] == legit and lens["auto_resolved_fraud"] == 0 and lens["human_review"] == fraud
    assert lens["fraud_amount_caught"] == pytest.approx(sum(TRUTH[c]["claim_amount"] for c in first_three if is_fraud(c)))
    assert lens["adjuster_hours_saved"] == round(legit * 22 / 60, 1) and lens["manual_review_minutes_assumed"] == 22
    assert lens["tier_counts"] == {"HIGH": legit, "MEDIUM": fraud, "LOW": 0}


def test_failed_claim_keeps_its_place(results_dir):
    write_results(results_dir, {ORDER[0]: "failed", ORDER[1]: perfect_claimlens_naive_baseline(ORDER[1])})
    report = analytics.compute_analytics()
    assert report["progress"]["failed"] == 1 and report["progress"]["complete"] == 1 and report["progress"]["reported"] == 2
    assert any("failed" in note for note in report["notes"])


def test_complete_batch_is_final_with_no_interim_note(results_dir):
    write_results(results_dir, {claim_id: perfect_claimlens_naive_baseline(claim_id) for claim_id in ORDER})
    report = analytics.compute_analytics()
    assert report["progress"]["is_final"] is True and report["progress"]["complete"] == 15
    assert report["reference"]["always_approve_correct"] == 10 and report["composition"] == {"fraud": 5, "legitimate": 10}
    assert not any(note.startswith("Interim") for note in report["notes"])


def test_cap_counts_and_suggestive_note(results_dir):
    entries = {}
    for claim_id in ORDER[:4]:
        # both systems wrong everywhere, ClaimLens capped from HIGH each time
        wrong = "APPROVE" if is_fraud(claim_id) else "DENY"
        entries[claim_id] = {"baseline": (wrong, 85), "lens": (wrong, "MEDIUM", "human_review", True, True)}
    write_results(results_dir, entries)
    lens = analytics.compute_analytics()["claimlens"]
    assert lens["cap_applied"] == 4 and lens["cap_applied_on_wrong_decisions"] == 4
    assert lens["tier_before_cap_high"] == 4 and lens["tier_before_cap_high_wrong"] == 4 and lens["high_confidence_wrong"] == 0
    notes = analytics.compute_analytics()["notes"]
    assert any("Accuracy differs by 0 claim(s)" in note for note in notes)


def test_endpoint_returns_counts_only(results_dir):
    write_results(results_dir, {claim_id: perfect_claimlens_naive_baseline(claim_id) for claim_id in ORDER[:5]})
    with TestClient(app) as client:
        response = client.get("/analytics")
    assert response.status_code == 200
    text = json.dumps(response.json())
    assert "%" not in text                       # Part 5b: raw counts, no percentages
    assert not any(claim_id in text for claim_id in ORDER)  # no individual held-out claims
    assert "ground_truth" not in text and "is_fraud" not in text
