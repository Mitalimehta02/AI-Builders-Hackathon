"""
Ground-truth leak tests: the highest-priority correctness check in the project.

If a fraud label, difficulty tag or baked-in signal name reaches an agent, every number in
the Stage 11 comparison is meaningless. These tests run over ALL synthetic claims.

Run from the backend/ folder:
    .\\.venv\\Scripts\\python.exe -m pytest tests -v
"""

import json
import re
from pathlib import Path

import pytest

from app.agents.evidence_agent import gather_evidence
from app.agents.sanitize import LABEL_KEYS, find_label_keys, sanitize_claim
from app.synthetic.generate_claims import SIGNAL_FUNCTIONS

CLAIMS_PATH = Path(__file__).resolve().parents[1] / "data" / "synthetic_claims.json"


def load_claims():
    with open(CLAIMS_PATH, encoding="utf-8") as f:
        return json.load(f)


def fake_weather_lookup(latitude, longitude, start_date, end_date):
    """Offline stand-in for the Open-Meteo tool so tests never touch the network."""
    return {
        "status": "ok",
        "response": {"daily": {
            "temperature_2m_min": [5.0, 4.0, 6.0],
            "temperature_2m_max": [15.0, 14.0, 16.0],
            "precipitation_sum": [0.0, 1.2, 0.0],
            "snowfall_sum": [0.0, 0.0, 0.0],
        }},
    }


# Words that must never appear anywhere in an evidence object: label names and values,
# the generator's signal names, and judgement words (evidence states facts, not verdicts).
FORBIDDEN_WORDS = (
    ["ground_truth", "is_fraud", "difficulty", "fraud", "fraudulent", "legitimate",
     "easy", "ambiguous", "hard", "suspicious", "suspect", "likely", "red flag"]
    + list(SIGNAL_FUNCTIONS)  # e.g. "early_claim", "weather_mismatch"
)


def test_sanitized_claims_have_no_ground_truth():
    claims = load_claims()
    assert len(claims) == 40
    for raw in claims:
        assert "ground_truth" in raw, "fixture check: raw synthetic claims should carry labels"
        clean = sanitize_claim(raw)
        assert "ground_truth" not in clean, raw["claim_id"]
        assert find_label_keys(clean) == [], raw["claim_id"]
        for key in LABEL_KEYS:
            assert f'"{key}"' not in json.dumps(clean), f"{raw['claim_id']}: '{key}' still in sanitized claim"


def test_sanitize_does_not_modify_the_original():
    raw = load_claims()[0]
    sanitize_claim(raw)
    assert "ground_truth" in raw


def test_sanitize_removes_nested_label_keys():
    claim = {"claim_id": "X", "incident": {"is_fraud": True, "notes": [{"difficulty": "hard"}]}, "signals": ["a"]}
    clean = sanitize_claim(claim)
    assert find_label_keys(clean) == []
    assert clean == {"claim_id": "X", "incident": {"notes": [{}]}}


def test_evidence_agent_rejects_unsanitized_claims():
    raw = load_claims()[0]
    with pytest.raises(ValueError):
        gather_evidence(raw, weather_lookup=fake_weather_lookup)


def test_no_evidence_object_contains_labels_or_verdicts():
    for raw in load_claims():
        evidence = gather_evidence(sanitize_claim(raw), weather_lookup=fake_weather_lookup)
        assert find_label_keys(evidence, path="evidence") == [], raw["claim_id"]

        text = json.dumps(evidence).lower()
        for word in FORBIDDEN_WORDS:
            assert not re.search(rf"\b{re.escape(word)}\b", text), f"{raw['claim_id']}: evidence contains '{word}'"


def test_weather_failure_is_recorded_not_raised():
    raw = load_claims()[0]

    def failing_lookup(latitude, longitude, start_date, end_date):
        return {"status": "unavailable", "reason": "simulated network failure"}

    evidence = gather_evidence(sanitize_claim(raw), weather_lookup=failing_lookup)
    assert evidence["weather"]["status"] == "unavailable"
    assert evidence["weather"]["reason"] == "simulated network failure"
