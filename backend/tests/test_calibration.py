"""
Stage 6 tests for the calibration layer and auto-resolution gate. Offline: a fake model
returns canned replies, so no quota is used.

What they protect:
- the confidence tier rule and the auto-resolution gate, exactly as specified
- the swapped Judge sees the same system prompt, case file and arguments, in the other order
- a split verdict is LOW and goes to a human; a HIGH-confidence DENY still goes to a human
- resuming never repeats finished calls; nothing label-related reaches any call
- the Judge's rubric names no specific fraud pattern (PROJECT_PLAN.md Part 5b tuning line)
- development scripts refuse held-out claims

Run from the backend/ folder:
    .\\.venv\\Scripts\\python.exe -m pytest tests -v
"""

import json
import re

import pytest

from app.agents import calibration, debate_agent
from app.agents.case_file import CASE_FILE_GUIDE, build_case_file, compact_json
from app.agents.evidence_agent import gather_evidence
from app.agents.sanitize import sanitize_claim
from app.synthetic.eval_split import DEV_SET_IDS, require_dev_set
from tests.test_debate import CANNED_REPLIES, USAGE, sample_inputs
from tests.test_sanitize import LABEL_WORDS, fake_weather_lookup, load_claims


def judge(decision, confidence):
    return {"decision": decision, "reasoning": "r", "verbalized_confidence": confidence, "confidence_justification": "j"}


class FakeModel:
    """Canned replies per step; the two Judge calls can be given different rulings."""

    def __init__(self, prosecutor_first=None, defender_first=None):
        self.replies = {
            "prosecutor": CANNED_REPLIES["prosecutor"],
            "defender": CANNED_REPLIES["defender"],
            "judge": prosecutor_first or CANNED_REPLIES["judge"],
            "judge_defender_first": defender_first or CANNED_REPLIES["judge"],
        }
        self.calls = []

    def __call__(self, messages, label):
        step = label.split(":")[0].removeprefix("debate_")
        self.calls.append((step, messages))
        return {"data": self.replies[step], "usage": USAGE, "attempts": 1, "rate_limit": {}}


@pytest.mark.parametrize("first, second, expected_tier", [
    (("APPROVE", "HIGH"), ("APPROVE", "HIGH"), "HIGH"),
    (("DENY", "HIGH"), ("DENY", "HIGH"), "HIGH"),
    (("APPROVE", "HIGH"), ("APPROVE", "MEDIUM"), "MEDIUM"),
    (("DENY", "LOW"), ("DENY", "MEDIUM"), "MEDIUM"),
    (("APPROVE", "LOW"), ("APPROVE", "LOW"), "MEDIUM"),
    (("APPROVE", "HIGH"), ("DENY", "HIGH"), "LOW"),
    (("DENY", "MEDIUM"), ("APPROVE", "LOW"), "LOW"),
])
def test_confidence_tier_rule(first, second, expected_tier):
    assert calibration.combine_confidence(judge(*first), judge(*second)) == expected_tier


def test_gate_auto_resolves_only_high_tier_approvals():
    assert calibration.auto_resolution_gate("APPROVE", "HIGH") == "auto_resolved"
    for decision, tier in [("APPROVE", "MEDIUM"), ("APPROVE", "LOW"), ("DENY", "HIGH"), ("DENY", "MEDIUM"), ("DENY", "LOW")]:
        assert calibration.auto_resolution_gate(decision, tier) == "human_review", (decision, tier)


def test_pipeline_makes_four_calls_and_the_swapped_judge_sees_the_same_content_reordered():
    claim, evidence = sample_inputs()
    model = FakeModel()
    result = calibration.run_claimlens(claim, evidence, llm=model)

    assert [step for step, _ in model.calls] == ["prosecutor", "defender", "judge", "judge_defender_first"]
    first_messages, swapped_messages = model.calls[2][1], model.calls[3][1]
    assert first_messages[0] == swapped_messages[0]  # identical Judge system prompt

    first_text, swapped_text = first_messages[1]["content"], swapped_messages[1]["content"]
    assert first_text.index("PROSECUTOR'S ARGUMENT") < first_text.index("DEFENDER'S ARGUMENT")
    assert swapped_text.index("DEFENDER'S ARGUMENT") < swapped_text.index("PROSECUTOR'S ARGUMENT")
    for shared in (build_case_file(claim, evidence),
                   compact_json(result["transcript"]["prosecutor"]),
                   compact_json(result["transcript"]["defender"])):
        assert shared in first_text and shared in swapped_text
    assert len(first_text) == len(swapped_text)

    assert result["usage"]["total"]["total_tokens"] == 4 * USAGE["total_tokens"]
    assert result["attempts"]["total"] == 4


def test_split_verdict_is_low_and_goes_to_a_human():
    claim, evidence = sample_inputs()
    model = FakeModel(prosecutor_first=judge("APPROVE", "HIGH"), defender_first=judge("DENY", "HIGH"))
    result = calibration.run_claimlens(claim, evidence, llm=model)
    assert result["orderings_agree"] is False
    assert result["confidence_tier"] == "LOW"
    assert result["decision"] == "APPROVE"  # pre-registered: the Prosecutor-first ruling is the recommendation
    assert result["gate"] == "human_review"


def test_high_confidence_deny_still_goes_to_a_human():
    claim, evidence = sample_inputs()
    model = FakeModel(prosecutor_first=judge("DENY", "HIGH"), defender_first=judge("DENY", "HIGH"))
    result = calibration.run_claimlens(claim, evidence, llm=model)
    assert result["confidence_tier"] == "HIGH" and result["gate"] == "human_review"


def test_resume_after_the_debate_only_runs_the_swapped_judge():
    claim, evidence = sample_inputs()
    saved = {}
    calibration.run_claimlens(claim, evidence, llm=FakeModel(), on_step=lambda steps: saved.update(steps))

    resumed = FakeModel()
    calibration.run_claimlens(claim, evidence, llm=resumed, completed_steps={role: saved[role] for role in debate_agent.ROLES})
    assert [step for step, _ in resumed.calls] == ["judge_defender_first"]


def test_pipeline_sends_only_sanitized_content_for_every_claim():
    for raw in load_claims():
        claim = sanitize_claim(raw)
        model = FakeModel()
        calibration.run_claimlens(claim, gather_evidence(claim, weather_lookup=fake_weather_lookup), llm=model)
        assert len(model.calls) == 4
        for step, messages in model.calls:
            everything_sent = json.dumps(messages).lower()
            for word in LABEL_WORDS:
                assert not re.search(rf"\b{re.escape(word)}\b", everything_sent), f"{raw['claim_id']} {step}: '{word}'"


def test_judge_rubric_names_no_specific_fraud_pattern():
    # The Judge-specific rules (not the shared field guide) must stay general principles of
    # argument evaluation. None of these case-pattern words may appear in them.
    rubric = debate_agent.JUDGE_SYSTEM_PROMPT.split("How to judge:")[1].split("Respond with only")[0].lower()
    for term in ["theft", "stolen", "weather", "freez", "frozen", "cold", "coverage", "comprehensive",
                 "deductible", "policy", "receipt", "police", "photo", "location", "address", "prior claim",
                 "timing", "days before", "value", "amount", "document"]:
        assert term not in rubric, f"Judge rubric mentions '{term}'"


def test_guide_explains_an_empty_documents_mentioned_but_absent_list():
    assert "it does not mean that documents are missing" in CASE_FILE_GUIDE


def test_development_scripts_refuse_held_out_claims():
    require_dev_set(DEV_SET_IDS)  # fine
    assert len(DEV_SET_IDS) == 7
    with pytest.raises(ValueError):
        require_dev_set(["CLM-0002"])
