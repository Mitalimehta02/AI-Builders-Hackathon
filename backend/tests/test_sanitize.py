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

from app.agents.case_file import build_case_file
from app.agents.evidence_agent import gather_evidence
from app.agents.naive_baseline_agent import BASELINE_HIGH_CONFIDENCE_THRESHOLD, parse_decision, run_naive_baseline
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


# ---------------------------------------------------------------------------
# Stage 4: the case file and the naive baseline go through the same sanitization path
# ---------------------------------------------------------------------------

# Label and signal words that must never appear anywhere in what is sent to a model,
# including the system prompt. (The system prompt may legitimately say "fraudulent".)
LABEL_WORDS = ["ground_truth", "is_fraud", "difficulty", "easy", "ambiguous", "hard"] + list(SIGNAL_FUNCTIONS)


def stub_llm_reply(messages, label):
    return {
        "data": {"decision": "APPROVE", "confidence": 85, "reasoning": "stub"},
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0},
        "attempts": 1,
        "rate_limit": {},
    }


def test_case_file_contains_no_labels_or_personal_identifiers():
    for raw in load_claims():
        claim = sanitize_claim(raw)
        case_file = build_case_file(claim, gather_evidence(claim, weather_lookup=fake_weather_lookup)).lower()
        for word in FORBIDDEN_WORDS:
            assert not re.search(rf"\b{re.escape(word)}\b", case_file), f"{raw['claim_id']}: case file contains '{word}'"
        assert raw["policyholder"]["name"].lower() not in case_file, raw["claim_id"]
        assert raw["policyholder"]["email"].lower() not in case_file, raw["claim_id"]


def test_naive_baseline_sends_only_sanitized_content():
    sent = []

    def capturing_llm(messages, label):
        sent.append(messages)
        return stub_llm_reply(messages, label)

    for raw in load_claims():
        claim = sanitize_claim(raw)
        run_naive_baseline(claim, gather_evidence(claim, weather_lookup=fake_weather_lookup), llm=capturing_llm)

    assert len(sent) == 40
    for messages in sent:
        everything_sent = json.dumps(messages).lower()
        for word in LABEL_WORDS:
            assert not re.search(rf"\b{re.escape(word)}\b", everything_sent), f"prompt contains '{word}'"
        user_message = messages[-1]["content"].lower()
        for word in FORBIDDEN_WORDS:
            assert not re.search(rf"\b{re.escape(word)}\b", user_message), f"case file contains '{word}'"


def test_naive_baseline_rejects_unsanitized_claims_without_calling_the_model():
    raw = load_claims()[0]
    evidence = gather_evidence(sanitize_claim(raw), weather_lookup=fake_weather_lookup)

    def must_not_be_called(messages, label):
        raise AssertionError("the model was called with an unsanitized claim")

    with pytest.raises(ValueError):
        run_naive_baseline(raw, evidence, llm=must_not_be_called)


def test_baseline_high_confidence_threshold_is_the_preregistered_value():
    # Fixed at Stage 4 before any results were observed. If this test fails, someone moved it.
    assert BASELINE_HIGH_CONFIDENCE_THRESHOLD == 80


def test_baseline_rejects_malformed_model_output():
    for bad in [{"decision": "MAYBE", "confidence": 70, "reasoning": "x"},
                {"decision": "DENY", "confidence": 170, "reasoning": "x"},
                {"decision": "DENY", "confidence": 70.5, "reasoning": "x"},
                {"decision": "APPROVE", "confidence": 70, "reasoning": ""}]:
        with pytest.raises(ValueError):
            parse_decision(bad)
    assert parse_decision({"decision": "deny", "confidence": "75", "reasoning": "ok"})["confidence"] == 75
