"""
Stage 9 queue tests: GET /claims filters by status, confidence tier and gate outcome, and every
row says whether the confidence cap fired. Offline: fake model, temporary database and status file.
"""

import copy

import pytest
from fastapi.testclient import TestClient

from app import batch_status, db, pipeline
from app.main import app
from tests.test_calibration import FakeModel, judge
from tests.test_sanitize import fake_weather_lookup, load_claims

ASSERTION_ONLY = [{"point_id": "P1", "significant": True, "status": "answered_by_assertion_only"}]


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(batch_status, "STATUS_PATH", tmp_path / "batch_status.json")
    monkeypatch.setattr(pipeline, "get_historical_weather", fake_weather_lookup)
    with TestClient(app) as test_client:
        yield test_client


def submit(client, monkeypatch, model):
    monkeypatch.setattr(pipeline, "call_llm", model)
    claim = copy.deepcopy(next(c for c in load_claims() if c["claim_id"] == "CLM-0027"))
    return client.post("/claims", json=claim).json()["id"]


def test_queue_filters_by_tier_and_gate_and_shows_the_cap(client, monkeypatch):
    medium = submit(client, monkeypatch, FakeModel())  # canned MEDIUM ruling -> human review
    auto = submit(client, monkeypatch, FakeModel(judge("APPROVE", "HIGH"), judge("APPROVE", "HIGH")))
    capped = submit(client, monkeypatch, FakeModel(judge("APPROVE", "HIGH", ASSERTION_ONLY), judge("APPROVE", "HIGH")))

    rows = {row["id"]: row for row in client.get("/claims").json()}
    assert rows[auto]["confidence_tier"] == "HIGH" and rows[auto]["gate"] == "auto_resolved" and rows[auto]["cap_applied"] is False
    assert rows[capped]["confidence_tier"] == "MEDIUM" and rows[capped]["cap_applied"] is True
    assert rows[medium]["cap_applied"] is False

    assert [r["id"] for r in client.get("/claims?confidence_tier=HIGH").json()] == [auto]
    assert sorted(r["id"] for r in client.get("/claims?gate=human_review").json()) == sorted([medium, capped])
    assert [r["id"] for r in client.get("/claims?status=resolved&confidence_tier=MEDIUM&gate=human_review").json()] == [capped, medium]

    detail = client.get(f"/claims/{capped}").json()
    assert detail["tier_before_cap"] == "HIGH" and detail["unresolved_points"]["prosecutor_first"][0]["point_id"] == "P1"


def test_queue_rejects_unknown_filter_values(client):
    assert client.get("/claims?confidence_tier=VERY_HIGH").status_code == 422
    assert client.get("/claims?gate=maybe").status_code == 422


def test_sample_rows_carry_status_and_cap(client):
    rows = client.get("/samples").json()
    assert all(row["status"] == "resolved" and "cap_applied" in row for row in rows)
