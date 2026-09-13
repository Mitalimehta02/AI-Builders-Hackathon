"""
Tests for the calibration layer, rebuttal accounting cap and auto-resolution gate. Offline: a
fake model returns canned replies, so no quota is used.

What they protect:
- the confidence tier rule, the mechanical cap and the auto-resolution gate, exactly as specified
- the swapped Judge sees the same system prompt and text, with only the opening arguments swapped
- a split verdict is LOW and goes to a human; a HIGH-confidence DENY still goes to a human
- resuming never repeats finished calls; nothing label-related reaches any call
- the Judge and rebuttal rules name no specific fraud pattern (PROJECT_PLAN.md Part 5b)
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
from tests.test_debate import ANSWERED_ALL, CANNED_REPLIES, USAGE, sample_inputs
from tests.test_sanitize import LABEL_WORDS, fake_weather_lookup, load_claims

PATTERN_WORDS = ["theft", "stolen", "weather", "freez", "frozen", "cold", "coverage", "comprehensive",
                 "deductible", "policy", "receipt", "police", "photo", "location", "address", "prior claim",
                 "timing", "days before", "value", "amount", "document"]


def judge(decision, confidence, assessments=ANSWERED_ALL):
    return {"decision": decision, "reasoning": "r", "verbalized_confidence": confidence,
            "confidence_justification": "j", "point_assessments": assessments}


class FakeModel:
    """Canned replies per step; the two Judge calls can be given different rulings."""

    def __init__(self, prosecutor_first=None, defender_first=None):
        self.replies = {
            "prosecutor": CANNED_REPLIES["prosecutor"],
            "defender": CANNED_REPLIES["defender"],
            "prosecutor_rebuttal": CANNED_REPLIES["prosecutor_rebuttal"],
            "judge": prosecutor_first or CANNED_REPLIES["judge"],
            "judge_defender_first": defender_first or CANNED_REPLIES["judge"],
        }
        self.calls = []

    def __call__(self, messages, label):
        step = label.split(":")[0].removeprefix("debate_")
        self.calls.append((step, messages))
        return {"data": self.replies[step], "usage": USAGE, "attempts": 1, "rate_limit": {}}


def run(prosecutor_first, defender_first):
    claim, evidence = sample_inputs()
    return calibration.run_claimlens(claim, evidence, llm=FakeModel(prosecutor_first, defender_first))


# ----- tier rule and gate -----

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


# ----- rebuttal accounting cap (mechanical, in code) -----

def test_significant_point_answered_only_by_assertion_caps_high_to_medium():
    assertion_only = [{"point_id": "P1", "significant": True, "status": "answered_by_assertion_only"}]
    result = run(judge("APPROVE", "HIGH", assertion_only), judge("APPROVE", "HIGH"))
    assert result["tier_before_cap"] == "HIGH" and result["confidence_tier"] == "MEDIUM" and result["cap_applied"]
    assert result["unresolved_points"]["prosecutor_first"] == [{"point_id": "P1", "status": "answered_by_assertion_only"}]
    assert result["gate"] == "human_review"


def test_unanswered_point_in_the_swapped_ruling_also_caps():
    unanswered = [{"point_id": "P1", "significant": True, "status": "unanswered"}]
    assert run(judge("APPROVE", "HIGH"), judge("APPROVE", "HIGH", unanswered))["confidence_tier"] == "MEDIUM"


def test_point_the_judge_did_not_assess_counts_as_unresolved():
    result = run(judge("APPROVE", "HIGH", []), judge("APPROVE", "HIGH"))
    assert result["confidence_tier"] == "MEDIUM"
    assert result["unresolved_points"]["prosecutor_first"] == [{"point_id": "P1", "status": "not_assessed"}]


def test_insignificant_or_fact_answered_points_do_not_cap():
    minor = [{"point_id": "P1", "significant": False, "status": "answered_by_assertion_only"}]
    result = run(judge("APPROVE", "HIGH", minor), judge("APPROVE", "HIGH"))
    assert result["confidence_tier"] == "HIGH" and not result["cap_applied"] and result["gate"] == "auto_resolved"


def test_deny_rulings_are_checked_against_the_defenders_points():
    # For a DENY the opposing points are the Defender's (D1); an unresolved Prosecutor point doesn't count.
    defender_point_open = [{"point_id": "P1", "significant": True, "status": "unanswered"},
                           {"point_id": "D1", "significant": True, "status": "answered_by_assertion_only"}]
    prosecutor_point_open = [{"point_id": "P1", "significant": True, "status": "unanswered"},
                             {"point_id": "D1", "significant": True, "status": "answered_with_case_file_fact"}]
    assert run(judge("DENY", "HIGH", defender_point_open), judge("DENY", "HIGH"))["confidence_tier"] == "MEDIUM"
    assert run(judge("DENY", "HIGH", prosecutor_point_open), judge("DENY", "HIGH"))["confidence_tier"] == "HIGH"


def test_cap_never_raises_a_tier():
    unresolved = [{"point_id": "P1", "status": "unanswered"}]
    assert calibration.apply_rebuttal_cap("MEDIUM", unresolved) == "MEDIUM"
    assert calibration.apply_rebuttal_cap("LOW", unresolved) == "LOW"
    assert calibration.apply_rebuttal_cap("LOW", []) == "LOW"


# ----- pipeline structure -----

def test_pipeline_makes_five_calls_and_the_swapped_judge_sees_the_same_text_reordered():
    claim, evidence = sample_inputs()
    model = FakeModel()
    result = calibration.run_claimlens(claim, evidence, llm=model)

    assert [step for step, _ in model.calls] == ["prosecutor", "defender", "prosecutor_rebuttal", "judge", "judge_defender_first"]
    first_messages, swapped_messages = model.calls[3][1], model.calls[4][1]
    assert first_messages[0] == swapped_messages[0]  # identical Judge system prompt

    first_text, swapped_text = first_messages[1]["content"], swapped_messages[1]["content"]
    assert first_text.index("PROSECUTOR'S ARGUMENT") < first_text.index("DEFENDER'S ARGUMENT") < first_text.index("PROSECUTOR'S REBUTTAL")
    assert swapped_text.index("DEFENDER'S ARGUMENT") < swapped_text.index("PROSECUTOR'S ARGUMENT") < swapped_text.index("PROSECUTOR'S REBUTTAL")
    for shared in (build_case_file(claim, evidence),
                   compact_json(result["transcript"]["prosecutor"]),
                   compact_json(result["transcript"]["defender"]),
                   compact_json(result["transcript"]["prosecutor_rebuttal"])):
        assert shared in first_text and shared in swapped_text
    assert len(first_text) == len(swapped_text)

    assert result["usage"]["total"]["total_tokens"] == 5 * USAGE["total_tokens"]
    assert result["attempts"]["total"] == 5


def test_split_verdict_is_low_and_goes_to_a_human():
    result = run(judge("APPROVE", "HIGH"), judge("DENY", "HIGH"))
    assert result["orderings_agree"] is False
    assert result["confidence_tier"] == "LOW"
    assert result["decision"] == "APPROVE"  # pre-registered: the Prosecutor-first ruling is the recommendation
    assert result["gate"] == "human_review"


def test_high_confidence_deny_still_goes_to_a_human():
    result = run(judge("DENY", "HIGH"), judge("DENY", "HIGH"))
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
        assert len(model.calls) == 5
        for step, messages in model.calls:
            everything_sent = json.dumps(messages).lower()
            for word in LABEL_WORDS:
                assert not re.search(rf"\b{re.escape(word)}\b", everything_sent), f"{raw['claim_id']} {step}: '{word}'"


# ----- Part 5b guards -----

def test_judge_rubric_names_no_specific_fraud_pattern():
    # The Judge-specific rules (not the shared field guide) must stay general principles of
    # argument evaluation. None of these case-pattern words may appear in them.
    rubric = debate_agent.JUDGE_SYSTEM_PROMPT.split("How to judge:")[1].split("Respond with only")[0].lower()
    for term in PATTERN_WORDS:
        assert term not in rubric, f"Judge rubric mentions '{term}'"


def test_rebuttal_rules_name_no_specific_fraud_pattern():
    rules = debate_agent.PROSECUTOR_REBUTTAL_SYSTEM_PROMPT.split("Rules for your rebuttal:")[1].split("Respond with only")[0].lower()
    for term in PATTERN_WORDS:
        assert term not in rules, f"rebuttal rules mention '{term}'"


def test_guide_explains_an_empty_documents_mentioned_but_absent_list():
    assert "it does not mean that documents are missing" in CASE_FILE_GUIDE


def test_development_scripts_refuse_held_out_claims():
    require_dev_set(DEV_SET_IDS)  # fine
    assert len(DEV_SET_IDS) == 13
    with pytest.raises(ValueError):
        require_dev_set(["CLM-0002"])
