"""
Stage 8 backend tests: stored samples, the live-submission switch, and the batch guard.
Offline: fake model, temporary database and status file, so no quota is used.

What they protect:
- "load a sample claim" serves the stored Stage 11 results only once the run has finished, with no model
  call and no labels
- live submission is refused (HTTP 423) while the Stage 11 batch is running, unless explicitly overridden
- a stale batch status (a crashed batch) no longer blocks live submission
"""

import copy
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import batch_status, db, pipeline, samples
from app.main import app
from app.synthetic.eval_split import is_dev_claim
from tests.test_calibration import FakeModel
from tests.test_sanitize import fake_weather_lookup, load_claims


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(batch_status, "STATUS_PATH", tmp_path / "batch_status.json")
    monkeypatch.delenv(batch_status.LIVE_OVERRIDE_ENV, raising=False)
    model = FakeModel()
    monkeypatch.setattr(pipeline, "call_llm", model)
    monkeypatch.setattr(pipeline, "get_historical_weather", fake_weather_lookup)
    with TestClient(app) as test_client:
        test_client.model = model
        yield test_client


def write_batch_status(running, minutes_ago=0):
    updated = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    batch_status.STATUS_PATH.write_text(json.dumps({
        "running": running, "claims_finished": 3, "claims_total": 15,
        "current_claim": "CLM-0010", "waiting_until": None, "updated_at": updated.isoformat(timespec="seconds"),
    }), encoding="utf-8")


def dev_claim():
    return copy.deepcopy(next(c for c in load_claims() if c["claim_id"] == "CLM-0027"))


# ----- stored samples -----

def test_samples_are_stage11_results_served_without_model_calls(client):
    listed = client.get("/samples").json()
    ids = [s["claim_id"] for s in listed]
    registered = json.loads(samples.SAMPLE_PATH.read_text(encoding="utf-8"))["claim_ids"]
    assert ids == registered  # every pre-registered claim completed; shown in the pre-registered order
    assert not any(is_dev_claim(claim_id) for claim_id in ids)
    assert all("Stage 11 evaluation run" in s["source"] and s["decision"] in ("APPROVE", "DENY") for s in listed)

    detail = client.get("/samples/CLM-0040").json()
    assert detail["status"] == "resolved" and detail["claim"]["claim_id"] == "CLM-0040"
    assert {"judge_prosecutor_first", "judge_defender_first"} <= set(detail["transcript"])
    assert "prosecutor_rebuttal" not in detail["transcript"]  # the final configuration has no rebuttal round
    assert "temperature 0.2" in detail["stored_sample"]["source"]
    assert "ground_truth" not in json.dumps(detail) and "is_fraud" not in json.dumps(detail)
    assert client.model.calls == []


def test_samples_hidden_while_a_batch_runs_and_unknown_ids_not_found(client):
    assert client.get("/samples/CLM-0002").status_code == 404  # held-out, but not in the evaluation sample
    assert client.get("/samples/CLM-0035").status_code == 404  # development-set claim: no longer a sample
    write_batch_status(running=True)
    assert client.get("/samples").json() == []  # no individual result is shown while a batch runs
    assert client.get("/samples/CLM-0040").status_code == 404


# ----- live-submission switch -----

def test_live_submission_enabled_when_no_batch_is_running(client):
    config = client.get("/config").json()
    assert config["live_submission_enabled"] is True and config["batch_running"] is False and config["reason"] is None
    assert config["estimated_tokens_per_live_claim"] > 0


def test_running_batch_disables_live_submission_and_the_api_refuses_it(client):
    write_batch_status(running=True)
    config = client.get("/config").json()
    assert config["live_submission_enabled"] is False and config["batch_running"] is True
    assert "evaluation batch is running" in config["reason"]
    assert config["batch"]["claims_finished"] == 3 and config["batch"]["claims_total"] == 15

    response = client.post("/claims", json=dev_claim())
    assert response.status_code == 423
    assert "evaluation batch is running" in response.json()["detail"]
    assert client.get("/claims").json() == [] and client.model.calls == []


def test_stale_batch_status_does_not_block(client):
    write_batch_status(running=True, minutes_ago=batch_status.STALE_AFTER_SECONDS / 60 + 5)
    assert client.get("/config").json()["live_submission_enabled"] is True
    assert client.post("/claims", json=dev_claim()).status_code == 202


def test_finished_batch_does_not_block(client):
    write_batch_status(running=False)
    assert client.get("/config").json()["live_submission_enabled"] is True


def test_explicit_override_allows_live_submission_during_the_batch(client, monkeypatch):
    write_batch_status(running=True)
    monkeypatch.setenv(batch_status.LIVE_OVERRIDE_ENV, "1")
    config = client.get("/config").json()
    assert config["live_submission_enabled"] is True and config["override_active"] is True
    assert client.post("/claims", json=dev_claim()).status_code == 202
