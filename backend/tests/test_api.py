"""
Stage 7 API tests. Offline: the model client and weather lookup are replaced with fakes and the
database is a temporary file, so no quota is used.

What they protect:
- a submitted claim goes pending -> gathering_evidence -> debating -> calibrating -> resolved,
  and the full result has evidence, transcript, decision, confidence tier and gate
- a synthetic claim's answer sheet is never stored or returned, and never reaches a model
- held-out benchmark claims are refused; malformed claims get a 422
- failures are recorded on the claim, keeping the debate steps already completed
- the queue filters by status; unknown ids return 404; a restart marks unfinished claims failed

Run from the backend/ folder:
    .\\.venv\\Scripts\\python.exe -m pytest tests -v
"""

import copy
import json
import re

import pytest
from fastapi.testclient import TestClient

from app import db, pipeline
from app.agents.llm_client import LLMError
from app.main import app
from tests.test_calibration import FakeModel
from tests.test_sanitize import LABEL_WORDS, fake_weather_lookup, load_claims

DEV_CLAIM_ID = "CLM-0027"
HELD_OUT_CLAIM_ID = "CLM-0002"  # any benchmark id outside the development set


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    model = FakeModel()
    monkeypatch.setattr(pipeline, "call_llm", model)
    monkeypatch.setattr(pipeline, "get_historical_weather", fake_weather_lookup)
    with TestClient(app) as test_client:  # starts the app, which creates the table
        test_client.model = model
        yield test_client


def dev_claim():
    """A development-set claim exactly as stored in the benchmark file, answer sheet included."""
    return copy.deepcopy(next(c for c in load_claims() if c["claim_id"] == DEV_CLAIM_ID))


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_claim_is_processed_end_to_end_and_the_answer_sheet_is_never_stored(client):
    submitted = dev_claim()
    assert "ground_truth" in submitted

    response = client.post("/claims", json=submitted)
    assert response.status_code == 202
    body = response.json()
    assert body["claim_id"] == DEV_CLAIM_ID and body["status"] == "pending"
    record_id = body["id"]

    # TestClient runs the background task before returning, so processing is already finished.
    status = client.get(f"/claims/{record_id}/status").json()
    assert status["status"] == "resolved" and status["error"] is None
    assert status["steps_completed"] == ["prosecutor", "defender", "prosecutor_rebuttal", "judge", "judge_defender_first"]

    detail = client.get(f"/claims/{record_id}").json()
    assert detail["evidence"]["claim_id"] == DEV_CLAIM_ID
    assert set(detail["transcript"]) == {"prosecutor", "defender", "prosecutor_rebuttal", "judge_prosecutor_first", "judge_defender_first"}
    assert detail["decision"] in ("APPROVE", "DENY")
    assert detail["confidence_tier"] in ("HIGH", "MEDIUM", "LOW")
    assert detail["gate"] in ("auto_resolved", "human_review") and isinstance(detail["auto_resolved"], bool)

    assert "ground_truth" not in db.get_claim(record_id)["claim"]
    assert "ground_truth" not in json.dumps(detail) and "is_fraud" not in json.dumps(detail)
    assert len(client.model.calls) == 5
    for _, messages in client.model.calls:
        for word in LABEL_WORDS:
            assert not re.search(rf"\b{re.escape(word)}\b", json.dumps(messages).lower()), word


def test_status_moves_through_every_stage_in_order(client, monkeypatch):
    seen = []

    def recording_weather(*args):
        seen.append(("weather", db.list_claims()[0]["status"]))
        return fake_weather_lookup(*args)

    def recording_model(messages, label):
        seen.append((label.split(":")[0].removeprefix("debate_"), db.list_claims()[0]["status"]))
        return client.model(messages, label)

    monkeypatch.setattr(pipeline, "get_historical_weather", recording_weather)
    monkeypatch.setattr(pipeline, "call_llm", recording_model)
    record_id = client.post("/claims", json=dev_claim()).json()["id"]

    assert seen == [
        ("weather", "gathering_evidence"),
        ("prosecutor", "debating"),
        ("defender", "debating"),
        ("prosecutor_rebuttal", "debating"),
        ("judge", "debating"),
        ("judge_defender_first", "calibrating"),
    ]
    assert client.get(f"/claims/{record_id}/status").json()["status"] == "resolved"


def test_held_out_benchmark_claims_are_refused(client):
    claim = dev_claim()
    claim["claim_id"] = HELD_OUT_CLAIM_ID
    response = client.post("/claims", json=claim)
    assert response.status_code == 403
    assert client.get("/claims").json() == [] and client.model.calls == []


def test_malformed_claims_are_rejected(client):
    missing_incident = dev_claim()
    del missing_incident["incident"]
    assert client.post("/claims", json=missing_incident).status_code == 422

    auto_without_vehicle = dev_claim()
    del auto_without_vehicle["policy"]["insured_vehicle"]
    assert client.post("/claims", json=auto_without_vehicle).status_code == 422

    filed_before_incident = dev_claim()
    filed_before_incident["filed_date"] = "2000-01-01"
    assert client.post("/claims", json=filed_before_incident).status_code == 422
    assert client.get("/claims").json() == []


def test_claim_without_an_id_gets_one(client):
    claim = dev_claim()
    del claim["claim_id"]
    body = client.post("/claims", json=claim).json()
    assert body["claim_id"].startswith("CLM-M-")
    assert client.get(f"/claims/{body['id']}/status").json()["status"] == "resolved"


def test_failure_is_recorded_and_completed_steps_are_kept(client, monkeypatch):
    def model_that_fails_at_the_judge(messages, label):
        if label.startswith("debate_judge:"):
            raise LLMError("simulated daily token limit")
        return client.model(messages, label)

    monkeypatch.setattr(pipeline, "call_llm", model_that_fails_at_the_judge)
    record_id = client.post("/claims", json=dev_claim()).json()["id"]

    status = client.get(f"/claims/{record_id}/status").json()
    assert status["status"] == "failed"
    assert "LLMError" in status["error"] and "simulated daily token limit" in status["error"]
    assert status["steps_completed"] == ["prosecutor", "defender", "prosecutor_rebuttal"]
    assert client.get(f"/claims/{record_id}").json()["decision"] is None


def test_queue_filters_by_status(client, monkeypatch):
    client.post("/claims", json=dev_claim())
    monkeypatch.setattr(pipeline, "call_llm", lambda messages, label: (_ for _ in ()).throw(LLMError("down")))
    client.post("/claims", json=dev_claim())

    everything = client.get("/claims").json()
    assert [c["status"] for c in everything] == ["failed", "resolved"]  # newest first
    assert [c["status"] for c in client.get("/claims?status=resolved").json()] == ["resolved"]
    assert client.get("/claims?status=nonsense").status_code == 422


def test_unknown_claim_returns_404(client):
    assert client.get("/claims/999").status_code == 404
    assert client.get("/claims/999/status").status_code == 404


def test_restart_marks_unfinished_claims_failed(client):
    claim = {k: v for k, v in dev_claim().items() if k != "ground_truth"}
    record_id = db.create_claim(claim)  # stored, never processed
    db.init_db()  # what happens when the server starts again
    record = db.get_claim(record_id)
    assert record["status"] == "failed" and "interrupted" in record["error"]
