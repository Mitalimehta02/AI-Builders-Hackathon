"""
Calibration layer and auto-resolution gate (Stage 6).

1. Order-swap consistency check. LLM judges are known to be swayed by the order in which
   arguments are presented. So the Judge rules twice on the SAME Prosecutor and Defender
   arguments: once with the Prosecutor's argument first (the Stage 5 debate), once with the
   Defender's first. A verdict that flips when only the order flips is not one to act on.

2. Confidence tier, combining agreement across orderings with both verbalized confidences:
     HIGH    both orderings reach the same decision AND both say HIGH
     MEDIUM  both orderings reach the same decision, but at least one says MEDIUM or LOW
     LOW     the orderings reach different decisions

3. Auto-resolution gate: a claim is auto-resolved ONLY if the tier is HIGH and the decision is
   APPROVE. Every DENY, and every non-HIGH case, goes to a human adjuster with the full case
   file. ClaimLens never denies a claim on its own.

Pre-registered before any Stage 6 results (docs/METHODOLOGY.md): the recommendation is the
Prosecutor-first Judge's decision. The swap only feeds the confidence tier; when the two
orderings disagree the recommendation is still shown, but the tier is LOW so a human decides.

Not built: the optional FULL_DOUBLE_DEBATE mode in PROJECT_PLAN.md (re-running the whole debate
instead of only the Judge). It can be added for the final run if the measured budget allows.

Usage:
    claim = sanitize_claim(raw_claim)
    result = run_claimlens(claim, gather_evidence(claim))
    result["decision"], result["confidence_tier"], result["gate"]
"""

from app.agents.case_file import build_case_file
from app.agents.debate_agent import ROLES, build_judge_messages, parse_judge, run_debate, run_step, sum_usage
from app.agents.llm_client import call_llm

SWAPPED_JUDGE_STEP = "judge_defender_first"
STEPS = ROLES + (SWAPPED_JUDGE_STEP,)  # prosecutor, defender, judge (prosecutor first), judge (defender first)


def combine_confidence(prosecutor_first_judge, defender_first_judge):
    """Final confidence tier from the two Judge rulings (see the rule at the top of this file)."""
    if prosecutor_first_judge["decision"] != defender_first_judge["decision"]:
        return "LOW"
    if prosecutor_first_judge["verbalized_confidence"] == "HIGH" and defender_first_judge["verbalized_confidence"] == "HIGH":
        return "HIGH"
    return "MEDIUM"


def auto_resolution_gate(decision, confidence_tier):
    """Only a HIGH-tier APPROVE resolves without a human. Everything else is escalated."""
    if decision == "APPROVE" and confidence_tier == "HIGH":
        return "auto_resolved"
    return "human_review"


def run_claimlens(claim, evidence, llm=call_llm, completed_steps=None, on_step=None):
    """Full ClaimLens pipeline for one sanitized claim: debate, swapped Judge, tier, gate.

    completed_steps / on_step work as in run_debate: finished steps are never re-run, and
    on_step is called after every new model call so progress can be saved.
    """
    steps = dict(completed_steps or {})

    def record(debate_steps):
        steps.update(debate_steps)
        if on_step:
            on_step(steps)

    # Calls 1-3: Prosecutor, Defender, Judge with the Prosecutor's argument first.
    run_debate(claim, evidence, llm=llm, completed_steps=steps, on_step=record)

    # Call 4: the same Judge, same arguments, Defender's argument first.
    if SWAPPED_JUDGE_STEP not in steps:
        messages = build_judge_messages(
            build_case_file(claim, evidence),
            steps["prosecutor"]["output"],
            steps["defender"]["output"],
            order="defender_first",
        )
        run_step(steps, SWAPPED_JUDGE_STEP, messages, parse_judge, llm, claim["claim_id"], on_step)

    prosecutor_first = steps["judge"]["output"]
    defender_first = steps[SWAPPED_JUDGE_STEP]["output"]
    decision = prosecutor_first["decision"]  # pre-registered: see the note at the top of this file
    tier = combine_confidence(prosecutor_first, defender_first)

    return {
        "claim_id": claim["claim_id"],
        "decision": decision,
        "confidence_tier": tier,
        "orderings_agree": prosecutor_first["decision"] == defender_first["decision"],
        "gate": auto_resolution_gate(decision, tier),
        "transcript": {
            "prosecutor": steps["prosecutor"]["output"],
            "defender": steps["defender"]["output"],
            "judge_prosecutor_first": prosecutor_first,
            "judge_defender_first": defender_first,
        },
        "usage": {**{name: steps[name]["usage"] for name in STEPS}, "total": sum_usage(steps[name]["usage"] for name in STEPS)},
        "attempts": {**{name: steps[name]["attempts"] for name in STEPS}, "total": sum(steps[name]["attempts"] for name in STEPS)},
    }
