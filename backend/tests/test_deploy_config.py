"""
Stage 13 deployment configuration tests: the live-submission switch and CORS. Offline.
"""

import copy

import pytest
from fastapi.testclient import TestClient

from app import batch_status, db
from app.main import CORS_ORIGINS, app
from tests.test_sanitize import load_claims


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(batch_status, "STATUS_PATH", tmp_path / "batch_status.json")
    monkeypatch.delenv(batch_status.LIVE_OVERRIDE_ENV, raising=False)
    with TestClient(app) as test_client:
        yield test_client


def test_deployment_can_switch_live_submission_off(client, monkeypatch):
    monkeypatch.setenv(batch_status.LIVE_SUBMISSION_ENV, "off")
    config = client.get("/config").json()
    assert config["live_submission_enabled"] is False and config["batch_running"] is False
    assert "switched off on this deployment" in config["reason"]

    claim = copy.deepcopy(next(c for c in load_claims() if c["claim_id"] == "CLM-0027"))
    assert client.post("/claims", json=claim).status_code == 423
    assert client.get("/claims").json() == []
    assert client.get("/samples").status_code == 200  # stored results still work


def test_switch_off_also_beats_the_batch_override(client, monkeypatch):
    monkeypatch.setenv(batch_status.LIVE_SUBMISSION_ENV, "off")
    monkeypatch.setenv(batch_status.LIVE_OVERRIDE_ENV, "1")
    assert client.get("/config").json()["live_submission_enabled"] is False


def test_live_submission_is_on_by_default(client, monkeypatch):
    monkeypatch.delenv(batch_status.LIVE_SUBMISSION_ENV, raising=False)
    assert client.get("/config").json()["live_submission_enabled"] is True


def test_cors_allows_only_the_configured_origins(client):
    assert CORS_ORIGINS == ["http://localhost:3000"]  # default when CLAIMLENS_CORS_ORIGINS is not set
    allowed = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:3000"
    other = client.get("/health", headers={"Origin": "https://example.com"})
    assert "access-control-allow-origin" not in other.headers
