"""
Tests for the calibration layer, point-accounting cap and auto-resolution gate. Offline: a fake
model returns canned replies (or a stored transcript is read), so no quota is used.

What they protect:
- the confidence tier rule, the mechanical cap and the auto-resolution gate, exactly as specified
- a conceded opposing point always triggers the cap, including in the stored CLM-0035 transcript
- the swapped Judge sees the same system prompt and text, with only the two arguments swapped
- a split verdict is LOW and goes to a human; a HIGH-confidence DENY still goes to a human
- resuming never repeats finished calls; nothing label-related reaches any call
- the Judge rules name no specific fraud pattern (PROJECT_PLAN.md Part 5b)
- development scripts refuse held-out claims

Run from the backend/ folder:
    .\\.venv\\Scripts\\python.exe -m pytest tests -v
"""

import json
import re
from pathlib import Path

import pytest

from app.agents import calibration, debate_agent
from app.agents.case_file import CASE_FILE_GUIDE, build_case_file, compact_json
from app.agents.evidence_agent import gather_evidence
from app.agents.llm_client import GENERATION_SETTINGS
from app.agents.sanitize import sanitize_claim
from app.synthetic.eval_split import DEV_SET_IDS, require_dev_set
from tests.test_debate import ANSWERED_ALL, CANNED_REPLIES, USAGE, sample_inputs
from tests.test_sanitize import LABEL_WORDS, fake_weather_lookup, load_claims

STORED_CLM_0035 = Path(__file__).resolve().parents[1] / "data" / "stage7_e2e" / "claim_1_CLM-0035_detail.json"
PATTERN_WORDS = ["theft", "stolen", "weather", "freez", "frozen", "cold", "coverage", "comprehensive",
                 "deductible", "policy", "receipt", "police", "photo", "location", "address", "prior claim",
                 "timing", "days before", "value", "amount", "document"]


def judge(decision, confidence, assessments=ANSWERED_ALL):
    return {"decision": decision, "reasoning": "r", "verbalized_confidence": confidence,
            "confidence_justification": "j", "point_assessments": assessments}


class FakeModel:
    """Canned replies per step; the two Judge calls and the Defender can be customised."""

    def __init__(self, prosecutor_first=None, defender_first=None, defender=None):
        self.replies = {
            "prosecutor": CANNED_REPLIES["prosecutor"],
            "defender": defender or CANNED_REPLIES["defender"],
            "judge": prosecutor_first or CANNED_REPLIES["judge"],
            "judge_defender_first": defender_first or CANNED_REPLIES["judge"],
        }
        self.calls = []

    def __call__(self, messages, label):
        step = label.split(":")[0].removeprefix("debate_")
        self.calls.append((step, messages))
        return {"data": self.replies[step], "usage": USAGE, "attempts": 1, "rate_limit": {}}


def run(prosecutor_first, defender_first, defender=None):
    claim, evidence = sample_inputs()
    return calibration.run_claimlens(claim, evidence, llm=FakeModel(prosecutor_first, defender_first, defender))


# ----- settings -----

def test_step_list_has_no_rebuttal_round_and_temperature_is_low():
    assert calibration.STEPS == ("prosecutor", "defender", "judge", "judge_defender_first")
    assert GENERATION_SETTINGS["temperature"] == 0.2


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


# ----- point-accounting cap (mechanical, in code) -----

def test_significant_point_answered_only_by_assertion_caps_high_to_medium():
    assertion_only = [{"point_id": "P1", "significant": True, "status": "answered_by_assertion_only"}]
    result = run(judge("APPROVE", "HIGH", assertion_only), judge("APPROVE", "HIGH"))
    assert result["tier_before_cap"] == "HIGH" and result["confidence_tier"] == "MEDIUM" and result["cap_applied"]
    assert result["unresolved_points"]["prosecutor_first"] == [{"point_id": "P1", "status": "answered_by_assertion_only"}]
    assert result["gate"] == "human_review"


def test_point_the_judge_did_not_assess_counts_as_unresolved():
    result = run(judge("APPROVE", "HIGH", []), judge("APPROVE", "HIGH"))
    assert result["confidence_tier"] == "MEDIUM"
    assert result["unresolved_points"]["prosecutor_first"] == [{"point_id": "P1", "status": "not_assessed"}]


def test_insignificant_or_fact_answered_points_do_not_cap():
    minor = [{"point_id": "P1", "significant": False, "status": "answered_by_assertion_only"}]
    result = run(judge("APPROVE", "HIGH", minor), judge("APPROVE", "HIGH"))
    assert result["confidence_tier"] == "HIGH" and not result["cap_applied"] and result["gate"] == "auto_resolved"


def test_judge_labelled_concession_caps_even_when_marked_insignificant():
    conceded = [{"point_id": "P1", "significant": False, "status": "conceded"}]
    result = run(judge("APPROVE", "HIGH", conceded), judge("APPROVE", "HIGH"))
    assert result["confidence_tier"] == "MEDIUM"
    assert result["unresolved_points"]["prosecutor_first"] == [{"point_id": "P1", "status": "conceded"}]


def test_defenders_own_concession_caps_whatever_the_judge_labelled():
    defender_concedes = {**CANNED_REPLIES["defender"], "responses": [
        {"responds_to": "P1", "position": "concede", "response": "Agreed.", "evidence": "timeline"}]}
    # Both Judge rulings wrongly call the conceded point answered with a fact.
    result = run(judge("APPROVE", "HIGH"), judge("APPROVE", "HIGH"), defender=defender_concedes)
    assert result["tier_before_cap"] == "HIGH" and result["confidence_tier"] == "MEDIUM"
    assert {"point_id": "P1", "status": "conceded"} in result["unresolved_points"]["defender_first"]
    assert result["gate"] == "human_review"


def test_conceded_point_in_stored_clm_0035_transcript_triggers_the_cap():
    # Zero-token check against the real Stage 7 transcript for dev claim CLM-0035.
    transcript = json.loads(STORED_CLM_0035.read_text(encoding="utf-8"))["transcript"]
    prosecutor, defender, ruling = transcript["prosecutor"], transcript["defender"], transcript["judge_prosecutor_first"]

    # What happened: the Defender conceded P1, but the Judge labelled it answered with a fact and not significant.
    assert any(r["responds_to"] == "P1" and r["position"] == "concede" for r in defender["responses"])
    p1 = next(a for a in ruling["point_assessments"] if a["point_id"] == "P1")
    assert p1["status"] == "answered_with_case_file_fact" and p1["significant"] is False

    unresolved = calibration.unresolved_points_against_decision(ruling, prosecutor, defender)
    assert ruling["decision"] == "APPROVE"
    assert {"point_id": "P1", "status": "conceded"} in unresolved
    assert calibration.apply_accounting_cap("HIGH", unresolved) == "MEDIUM"


def test_deny_rulings_are_checked_against_the_defenders_points():
    defender_point_open = [{"point_id": "P1", "significant": True, "status": "unanswered"},
                           {"point_id": "D1", "significant": True, "status": "answered_by_assertion_only"}]
    prosecutor_point_open = [{"point_id": "P1", "significant": True, "status": "unanswered"},
                             {"point_id": "D1", "significant": True, "status": "answered_with_case_file_fact"}]
    assert run(judge("DENY", "HIGH", defender_point_open), judge("DENY", "HIGH"))["confidence_tier"] == "MEDIUM"
    assert run(judge("DENY", "HIGH", prosecutor_point_open), judge("DENY", "HIGH"))["confidence_tier"] == "HIGH"


def test_cap_never_raises_a_tier():
    unresolved = [{"point_id": "P1", "status": "unanswered"}]
    assert calibration.apply_accounting_cap("MEDIUM", unresolved) == "MEDIUM"
    assert calibration.apply_accounting_cap("LOW", unresolved) == "LOW"
    assert calibration.apply_accounting_cap("LOW", []) == "LOW"


# ----- pipeline structure -----

def test_pipeline_makes_four_calls_and_the_swapped_judge_sees_the_same_text_reordered():
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

    assert set(result["transcript"]) == {"prosecutor", "defender", "judge_prosecutor_first", "judge_defender_first"}
    assert result["usage"]["total"]["total_tokens"] == 4 * USAGE["total_tokens"]
    assert result["attempts"]["total"] == 4


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
        assert len(model.calls) == 4
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


def test_guide_explains_an_empty_documents_mentioned_but_absent_list():
    assert "it does not mean that documents are missing" in CASE_FILE_GUIDE


def test_development_scripts_refuse_held_out_claims():
    require_dev_set(DEV_SET_IDS)  # fine
    assert len(DEV_SET_IDS) == 13
    with pytest.raises(ValueError):
        require_dev_set(["CLM-0002"])
