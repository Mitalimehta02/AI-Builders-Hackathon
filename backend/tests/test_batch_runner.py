"""
Stage 11 batch runner ordering test. Offline: claim processing is replaced with a fake, results are
written to a temporary folder, and sleeping is skipped.

Protects the pre-registered stopping rule: claims are processed strictly in order, so a claim that
fails is retried (up to MAX_FAILURES_PER_CLAIM) before any later claim is started.
"""

import pytest

from app.agents.llm_client import LLMError
from app.synthetic import run_full_batch


@pytest.fixture
def batch(monkeypatch, tmp_path):
    monkeypatch.setattr(run_full_batch, "NAIVE_PATH", tmp_path / "results_naive.json")
    monkeypatch.setattr(run_full_batch, "CLAIMLENS_PATH", tmp_path / "results_claimlens.json")
    monkeypatch.setattr(run_full_batch.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(run_full_batch.batch_status, "STATUS_PATH", tmp_path / "status.json")
    sample = {"claim_ids": ["CLM-A", "CLM-B", "CLM-C"], "claim_ids_sha256": "test"}
    results = lambda: {"meta": {}, "claims": {}}
    return run_full_batch.Batch(sample, {}, results(), results())


def install_fake_run_claim(batch, failures):
    """failures: {claim_id: [exception to raise on attempt 1, attempt 2, ...]}; otherwise the claim completes."""
    calls = []

    def fake_run_claim(number, claim_id):
        calls.append(claim_id)
        planned = failures.get(claim_id, [])
        attempt = calls.count(claim_id)
        if attempt <= len(planned):
            raise planned[attempt - 1]
        batch.naive["claims"][claim_id] = {"status": "complete"}
        batch.claimlens["claims"][claim_id] = {"status": "complete"}

    batch.run_claim = fake_run_claim
    return calls


def test_a_failed_claim_is_retried_before_the_next_claim(batch):
    calls = install_fake_run_claim(batch, {"CLM-B": [ValueError("empty summary")]})
    batch.run()
    assert calls == ["CLM-A", "CLM-B", "CLM-B", "CLM-C"]


def test_a_claim_that_keeps_failing_is_marked_failed_in_place_then_the_batch_moves_on(batch):
    calls = install_fake_run_claim(batch, {"CLM-A": [ValueError("bad")] * run_full_batch.MAX_FAILURES_PER_CLAIM})
    batch.run()
    assert calls == ["CLM-A"] * run_full_batch.MAX_FAILURES_PER_CLAIM + ["CLM-B", "CLM-C"]
    assert batch.claimlens["claims"]["CLM-A"]["status"] == "failed"


def test_rate_limit_waits_and_resumes_the_same_claim(batch, monkeypatch):
    waited = []
    monkeypatch.setattr(batch, "wait_for_refill", lambda error: waited.append(error.retry_after_seconds))
    calls = install_fake_run_claim(batch, {"CLM-B": [LLMError("429", rate_limited=True, retry_after_seconds=600)]})
    batch.run()
    assert calls == ["CLM-A", "CLM-B", "CLM-B", "CLM-C"] and waited == [600]
    assert "failures" not in batch.claimlens["claims"]["CLM-B"]  # rate limits are not failures
