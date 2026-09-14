"""
Calibration layer and auto-resolution gate.

1. Order-swap consistency check. LLM judges are known to be swayed by the order in which
   arguments are presented. So the Judge rules twice on the SAME Prosecutor and Defender
   arguments: once with the Prosecutor's argument first (the debate's own Judge call), once with
   the Defender's first. A verdict that flips when only the order flips is not one to act on.

2. Confidence tier, combining agreement across orderings with both verbalized confidences:
     HIGH    both orderings reach the same decision AND both say HIGH
     MEDIUM  both orderings reach the same decision, but at least one says MEDIUM or LOW
     LOW     the orderings reach different decisions

3. Point-accounting cap, applied IN CODE after step 2: a HIGH tier becomes MEDIUM if either Judge
   ruling leaves a point against its own decision unresolved (the Prosecutor's points for an
   APPROVE, the Defender's for a DENY). A point is unresolved if:
     - it was conceded - the Judge labelled it "conceded", or, independently of the Judge, the
       Defender's own response marked it conceded - whatever significance the Judge gave it;
     - or the Judge marked it significant and not answered with a case-file fact;
     - or the Judge did not assess it at all.
   The cap only lowers HIGH to MEDIUM, and the Judge is not told it exists: asking the model to be
   stricter with itself did not work.

4. Auto-resolution gate: a claim is auto-resolved ONLY if the final tier is HIGH and the decision
   is APPROVE. Every DENY, and every non-HIGH case, goes to a human adjuster with the full case
   file. ClaimLens never denies a claim on its own.

Pre-registered (docs/METHODOLOGY.md): the recommendation is the Prosecutor-first Judge's decision.
The swap and the cap only affect the confidence tier; when the two orderings disagree the
recommendation is still shown, but the tier is LOW so a human decides.

Usage:
    claim = sanitize_claim(raw_claim)
    result = run_claimlens(claim, gather_evidence(claim))
    result["decision"], result["confidence_tier"], result["gate"]
"""

from app.agents.case_file import build_case_file
from app.agents.debate_agent import ROLES, build_judge_messages, parse_judge, run_debate, run_step, sum_usage
from app.agents.llm_client import call_llm

SWAPPED_JUDGE_STEP = "judge_defender_first"
STEPS = ROLES + (SWAPPED_JUDGE_STEP,)  # prosecutor, defender, judge (Prosecutor first), judge (Defender first)
ANSWERED_WITH_FACT = "answered_with_case_file_fact"
CONCEDED = "conceded"


def combine_confidence(prosecutor_first_judge, defender_first_judge):
    """Tier from the two Judge rulings, before the point-accounting cap."""
    if prosecutor_first_judge["decision"] != defender_first_judge["decision"]:
        return "LOW"
    if prosecutor_first_judge["verbalized_confidence"] == "HIGH" and defender_first_judge["verbalized_confidence"] == "HIGH":
        return "HIGH"
    return "MEDIUM"


def points_conceded_by_defender(defender_argument):
    """Prosecutor point ids the Defender's own responses concede."""
    return {r["responds_to"] for r in defender_argument["responses"] if r["position"].startswith("conced")}


def unresolved_points_against_decision(judge, prosecutor_argument, defender_argument):
    """Points against this Judge ruling's own decision that remain unresolved (see rule 3 above)."""
    if judge["decision"] == "APPROVE":
        opposing_points = prosecutor_argument["points"]
        conceded_by_other_side = points_conceded_by_defender(defender_argument)
    else:
        opposing_points = defender_argument["points"]
        conceded_by_other_side = set()  # the Prosecutor does not reply to the Defender's points

    assessments = {a["point_id"]: a for a in judge["point_assessments"]}
    unresolved = []
    for point in opposing_points:
        assessment = assessments.get(point["id"])
        if point["id"] in conceded_by_other_side or (assessment and assessment["status"] == CONCEDED):
            unresolved.append({"point_id": point["id"], "status": CONCEDED})
        elif assessment is None:
            unresolved.append({"point_id": point["id"], "status": "not_assessed"})
        elif assessment["significant"] and assessment["status"] != ANSWERED_WITH_FACT:
            unresolved.append({"point_id": point["id"], "status": assessment["status"]})
    return unresolved


def apply_accounting_cap(tier, unresolved_points):
    """Lower HIGH to MEDIUM when any opposing point is unresolved. Never raises a tier."""
    return "MEDIUM" if tier == "HIGH" and unresolved_points else tier


def auto_resolution_gate(decision, confidence_tier):
    """Only a HIGH-tier APPROVE resolves without a human. Everything else is escalated."""
    if decision == "APPROVE" and confidence_tier == "HIGH":
        return "auto_resolved"
    return "human_review"


def run_claimlens(claim, evidence, llm=call_llm, completed_steps=None, on_step=None):
    """Full ClaimLens pipeline for one sanitized claim: debate, swapped Judge, tier, cap, gate.

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
    prosecutor, defender = steps["prosecutor"]["output"], steps["defender"]["output"]

    # Call 4: the same Judge on the same arguments, Defender's argument first.
    if SWAPPED_JUDGE_STEP not in steps:
        messages = build_judge_messages(build_case_file(claim, evidence), prosecutor, defender, order="defender_first")
        run_step(steps, SWAPPED_JUDGE_STEP, messages, parse_judge, llm, claim["claim_id"], on_step)

    prosecutor_first = steps["judge"]["output"]
    defender_first = steps[SWAPPED_JUDGE_STEP]["output"]
    decision = prosecutor_first["decision"]  # pre-registered: see the note at the top of this file

    tier_before_cap = combine_confidence(prosecutor_first, defender_first)
    unresolved = {
        "prosecutor_first": unresolved_points_against_decision(prosecutor_first, prosecutor, defender),
        "defender_first": unresolved_points_against_decision(defender_first, prosecutor, defender),
    }
    tier = apply_accounting_cap(tier_before_cap, unresolved["prosecutor_first"] + unresolved["defender_first"])

    return {
        "claim_id": claim["claim_id"],
        "decision": decision,
        "confidence_tier": tier,
        "tier_before_cap": tier_before_cap,
        "cap_applied": tier != tier_before_cap,
        "unresolved_points": unresolved,
        "orderings_agree": prosecutor_first["decision"] == defender_first["decision"],
        "gate": auto_resolution_gate(decision, tier),
        "transcript": {
            "prosecutor": prosecutor,
            "defender": defender,
            "judge_prosecutor_first": prosecutor_first,
            "judge_defender_first": defender_first,
        },
        "usage": {**{name: steps[name]["usage"] for name in STEPS}, "total": sum_usage(steps[name]["usage"] for name in STEPS)},
        "attempts": {**{name: steps[name]["attempts"] for name in STEPS}, "total": sum(steps[name]["attempts"] for name in STEPS)},
    }
