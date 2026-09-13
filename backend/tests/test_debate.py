"""
Tests for the debate engine. Offline: a fake model returns canned replies, so no quota is used.

What they protect:
- every role sees exactly the shared, sanitized case file, and nothing label-related
- the roles run in order (Prosecutor, Defender, Prosecutor rebuttal, Judge) and each builds on
  the previous arguments
- an interrupted debate resumes without repeating finished calls
- every role's reply is validated, and the Judge's HIGH level is the baseline's pre-registered band
- baseline and debate prompts share the same case-file guide and review guidance

Run from the backend/ folder:
    .\\.venv\\Scripts\\python.exe -m pytest tests -v
"""

import json
import re

import pytest

from app.agents import debate_agent
from app.agents.case_file import CASE_FILE_GUIDE, REVIEW_GUIDANCE, build_case_file, compact_json
from app.agents.evidence_agent import gather_evidence
from app.agents.naive_baseline_agent import BASELINE_HIGH_CONFIDENCE_THRESHOLD, SYSTEM_PROMPT as BASELINE_PROMPT
from app.agents.sanitize import sanitize_claim
from tests.test_sanitize import LABEL_WORDS, fake_weather_lookup, load_claims

ANSWERED_ALL = [
    {"point_id": "P1", "significant": True, "status": "answered_with_case_file_fact"},
    {"point_id": "D1", "significant": True, "status": "answered_with_case_file_fact"},
]

CANNED_REPLIES = {
    "prosecutor": {"points": [{"id": "P1", "point": "The policy is new.", "evidence": "days_policy_start_to_incident"}],
                   "summary": "Deny."},
    "defender": {"responses": [{"responds_to": "P1", "position": "rebut", "response": "A bill of sale explains it.",
                                "evidence": "dated_documents"}],
                 "points": [{"id": "D1", "point": "Police report listed.", "evidence": "supporting_documents"}],
                 "summary": "Pay."},
    "prosecutor_rebuttal": {"rebuttals": [{"responds_to": "D1", "rebuttal": "No report number is given.",
                                           "evidence": "supporting_documents"}],
                            "summary": "The response to P1 stands."},
    "judge": {"decision": "approve", "reasoning": "D1 answers P1.", "verbalized_confidence": "medium",
              "confidence_justification": "One point is not fully answered.", "point_assessments": ANSWERED_ALL},
}
USAGE = {"prompt_tokens": 10, "completion_tokens": 5, "reasoning_tokens": 2, "total_tokens": 15}


class FakeModel:
    def __init__(self):
        self.calls = []

    def __call__(self, messages, label):
        role = label.split(":")[0].removeprefix("debate_")
        self.calls.append((role, messages))
        return {"data": CANNED_REPLIES[role], "usage": USAGE, "attempts": 1, "rate_limit": {}}


def sample_inputs(index=0):
    claim = sanitize_claim(load_claims()[index])
    return claim, gather_evidence(claim, weather_lookup=fake_weather_lookup)


def test_roles_run_in_order_and_build_on_earlier_arguments():
    claim, evidence = sample_inputs()
    model = FakeModel()
    result = debate_agent.run_debate(claim, evidence, llm=model)

    assert [role for role, _ in model.calls] == ["prosecutor", "defender", "prosecutor_rebuttal", "judge"]
    case_file = build_case_file(claim, evidence)
    user_messages = {role: messages[-1]["content"] for role, messages in model.calls}
    assert all(case_file in text for text in user_messages.values())

    prosecutor_json = compact_json(result["transcript"]["prosecutor"])
    defender_json = compact_json(result["transcript"]["defender"])
    rebuttal_json = compact_json(result["transcript"]["prosecutor_rebuttal"])
    assert prosecutor_json not in user_messages["prosecutor"]
    assert prosecutor_json in user_messages["defender"] and defender_json not in user_messages["defender"]
    assert prosecutor_json in user_messages["prosecutor_rebuttal"] and defender_json in user_messages["prosecutor_rebuttal"]
    for argument in (prosecutor_json, defender_json, rebuttal_json):
        assert argument in user_messages["judge"]
    assert user_messages["judge"].index("PROSECUTOR'S REBUTTAL") > user_messages["judge"].index("DEFENDER'S ARGUMENT")

    assert result["decision"] == "APPROVE" and result["verbalized_confidence"] == "MEDIUM"
    assert result["usage"]["total"]["total_tokens"] == 4 * USAGE["total_tokens"] and result["attempts"]["total"] == 4


def test_debate_sends_only_sanitized_content_for_every_claim():
    for raw in load_claims():
        claim = sanitize_claim(raw)
        model = FakeModel()
        debate_agent.run_debate(claim, gather_evidence(claim, weather_lookup=fake_weather_lookup), llm=model)
        for role, messages in model.calls:
            everything_sent = json.dumps(messages).lower()
            for word in LABEL_WORDS:
                assert not re.search(rf"\b{re.escape(word)}\b", everything_sent), f"{raw['claim_id']} {role}: '{word}'"


def test_debate_rejects_unsanitized_claims_without_calling_the_model():
    raw = load_claims()[0]
    _, evidence = sample_inputs()
    model = FakeModel()
    with pytest.raises(ValueError):
        debate_agent.run_debate(raw, evidence, llm=model)
    assert model.calls == []


def test_resume_skips_finished_steps():
    claim, evidence = sample_inputs()
    saved = {}
    debate_agent.run_debate(claim, evidence, llm=FakeModel(), on_step=lambda steps: saved.update(steps))

    # Pretend the run died after the prosecutor: only that step was saved.
    resumed_model = FakeModel()
    debate_agent.run_debate(claim, evidence, llm=resumed_model, completed_steps={"prosecutor": saved["prosecutor"]})
    assert [role for role, _ in resumed_model.calls] == ["defender", "prosecutor_rebuttal", "judge"]


def test_judge_reply_is_validated():
    good = {"decision": "DENY", "reasoning": "r", "verbalized_confidence": "HIGH", "confidence_justification": "j",
            "point_assessments": ANSWERED_ALL}
    for key, bad_value in [("decision", "MAYBE"), ("verbalized_confidence", "VERY HIGH"), ("reasoning", ""),
                           ("confidence_justification", " "), ("point_assessments", None),
                           ("point_assessments", [{"point_id": "P1", "significant": True, "status": "partly"}]),
                           ("point_assessments", [{"point_id": "P1", "significant": "maybe", "status": "unanswered"}])]:
        with pytest.raises(ValueError):
            debate_agent.parse_judge({**good, key: bad_value})
    parsed = debate_agent.parse_judge({**good, "point_assessments": [{"point_id": "P1", "significant": "true", "status": "Unanswered"}]})
    assert parsed["point_assessments"] == [{"point_id": "P1", "significant": True, "status": "unanswered"}]
    with pytest.raises(ValueError):
        debate_agent.parse_prosecutor({"points": [], "summary": "x"})


def test_rebuttal_reply_is_validated():
    assert debate_agent.parse_rebuttal({"rebuttals": [], "summary": "Nothing to dispute."})["rebuttals"] == []
    with pytest.raises(ValueError):
        debate_agent.parse_rebuttal({"rebuttals": "none", "summary": "x"})
    with pytest.raises(ValueError):
        debate_agent.parse_rebuttal({"rebuttals": [{"responds_to": "D1", "rebuttal": ""}], "summary": "x"})


def test_judge_high_confidence_uses_the_preregistered_baseline_band():
    assert f"at least {BASELINE_HIGH_CONFIDENCE_THRESHOLD} times out of 100" in debate_agent.JUDGE_SYSTEM_PROMPT


def test_decision_is_defined_as_genuineness_not_payout():
    from app.agents.case_file import DECISION_DEFINITIONS
    assert "only about whether the claim is genuine" in DECISION_DEFINITIONS
    assert "paid as submitted" not in DECISION_DEFINITIONS
    for prompt in (BASELINE_PROMPT, debate_agent.JUDGE_SYSTEM_PROMPT):
        assert DECISION_DEFINITIONS in prompt


def test_baseline_and_every_debate_role_share_the_same_guide_and_review_guidance():
    for prompt in (BASELINE_PROMPT, debate_agent.PROSECUTOR_SYSTEM_PROMPT, debate_agent.DEFENDER_SYSTEM_PROMPT,
                   debate_agent.PROSECUTOR_REBUTTAL_SYSTEM_PROMPT, debate_agent.JUDGE_SYSTEM_PROMPT):
        assert CASE_FILE_GUIDE in prompt and REVIEW_GUIDANCE in prompt


def test_case_file_guide_states_the_amount_conventions():
    assert "BEFORE the deductible" in CASE_FILE_GUIDE
    assert "actual cash value" in CASE_FILE_GUIDE
    assert "industry-wide claims database" in CASE_FILE_GUIDE
    assert "sales tax" in CASE_FILE_GUIDE
