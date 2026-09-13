"""
Debate engine: Prosecutor -> Defender -> Prosecutor rebuttal -> Judge, through the shared client.

Why a debate: two agents argue opposite sides and a judge decides. It is easier to check a
winning argument against the facts than to verify a hard claim directly (Irving, Christiano &
Amodei, "AI Safety via Debate", 2018). Here each side must cite case-file facts, and the Judge
is told to check every citation against the case file.

  1. Prosecutor: the strongest honest case that the claim should be DENIED.
  2. Defender:   answers each Prosecutor point by id (rebut or concede), then adds its own.
  3. Prosecutor rebuttal: one short reply to the Defender (no new points), so the Defender's
     answers can be challenged before the Judge rules. Alternating rounds is standard in
     debate formats: otherwise whoever speaks last is never challenged.
  4. Judge: reads the case file and all arguments; returns decision, reasoning,
     verbalized_confidence (HIGH / MEDIUM / LOW) with a justification, and an assessment of
     whether every numbered point was answered with a case-file fact.

Fairness with the naive baseline: every role receives the same case file (build_case_file),
the same CASE_FILE_GUIDE, DECISION_DEFINITIONS and REVIEW_GUIDANCE, and goes through the same
llm_client with the same settings. The Judge's HIGH level is defined with the baseline's
pre-registered threshold, so "high confidence" means the same thing for both systems.

The Judge's input can present the two opening arguments in either order (build_judge_messages);
the calibration layer uses that for its order-swap consistency check.

Usage:
    claim = sanitize_claim(raw_claim)
    result = run_debate(claim, gather_evidence(claim))
    result["transcript"]  # {"prosecutor", "defender", "prosecutor_rebuttal", "judge"}
"""

from app.agents.case_file import CASE_FILE_GUIDE, DECISION_DEFINITIONS, REVIEW_GUIDANCE, build_case_file, compact_json
from app.agents.llm_client import call_llm
from app.agents.naive_baseline_agent import BASELINE_HIGH_CONFIDENCE_THRESHOLD

ROLES = ("prosecutor", "defender", "prosecutor_rebuttal", "judge")
CONFIDENCE_LEVELS = ("HIGH", "MEDIUM", "LOW")
JUDGE_ORDERS = ("prosecutor_first", "defender_first")
POINT_STATUSES = ("answered_with_case_file_fact", "answered_by_assertion_only", "unanswered")
MEDIUM_CONFIDENCE_FLOOR = 65  # below this many correct out of 100 is LOW

MAX_PROSECUTOR_POINTS = 5
MAX_DEFENDER_EXTRA_POINTS = 3
MAX_REBUTTALS = 3

_SHARED_CONTEXT = f"""{CASE_FILE_GUIDE}

Decisions:
{DECISION_DEFINITIONS}

{REVIEW_GUIDANCE}"""

PROSECUTOR_SYSTEM_PROMPT = f"""You are the prosecutor in a structured claims review at a US property and casualty insurer. Your job is to make the strongest honest case that this claim should be DENIED because it is fraudulent or materially misrepresented. A defender will answer your points, and a judge will decide.

{_SHARED_CONTEXT}

Rules for your argument:
- Cite the exact case-file facts behind each point (field names, values, document titles). The defender and the judge will check every citation against the case file, and an invented or misstated fact will count against you.
- Give at most {MAX_PROSECUTOR_POINTS} points, most important first, each in one or two sentences. If the facts only support a weak case, make the best case they honestly allow rather than overstating it.

Respond with only a JSON object in exactly this form:
{{"points": [{{"id": "P1", "point": "<the argument>", "evidence": "<the specific case-file facts it rests on>"}}], "summary": "<one or two sentences: your overall case for denial>"}}"""

DEFENDER_SYSTEM_PROMPT = f"""You are the defender in a structured claims review at a US property and casualty insurer. Your job is to make the strongest honest case that this claim should be APPROVED as a genuine loss. The prosecutor's argument follows the case file. A judge will decide.

{_SHARED_CONTEXT}

Rules for your argument:
- Answer every prosecutor point by its id. Rebut it with case-file facts, or concede it if the facts support it. A conceded point costs you less than a rebuttal the judge can see is false.
- Then add at most {MAX_DEFENDER_EXTRA_POINTS} further points for approval, each in one or two sentences.
- Cite the exact case-file facts behind every response and point. The judge will check every citation against the case file.

Respond with only a JSON object in exactly this form:
{{"responses": [{{"responds_to": "P1", "position": "rebut or concede", "response": "<your answer>", "evidence": "<the specific case-file facts>"}}], "points": [{{"id": "D1", "point": "<the argument>", "evidence": "<the specific case-file facts>"}}], "summary": "<one or two sentences: your overall case for approval>"}}"""

PROSECUTOR_REBUTTAL_SYSTEM_PROMPT = f"""You are the prosecutor in a structured claims review at a US property and casualty insurer. You have argued that this claim should be DENIED, and the defender has answered. Their argument follows yours after the case file. You now give one short rebuttal; after it, a judge decides.

{_SHARED_CONTEXT}

Rules for your rebuttal:
- Reply only to what the defender said. Do not raise new points.
- Dispute a defender response or point only if it fails to engage the specific case-file facts it is answering, or misstates a fact. Say exactly which fact it leaves unanswered or gets wrong. Do not dispute a response that does answer your point with case-file facts.
- Give at most {MAX_REBUTTALS} rebuttals, each in one or two sentences. An empty list is acceptable if nothing should be disputed.
- Cite the exact case-file facts. The judge will check every citation against the case file.

Respond with only a JSON object in exactly this form:
{{"rebuttals": [{{"responds_to": "<the P# response or D# point you dispute>", "rebuttal": "<what it fails to answer or misstates>", "evidence": "<the specific case-file facts>"}}], "summary": "<one sentence>"}}"""

JUDGE_SYSTEM_PROMPT = f"""You are the judge in a structured claims review at a US property and casualty insurer. A prosecutor has argued that the claim should be denied, a defender has argued that it should be paid, and the prosecutor has given a short rebuttal. Their arguments follow the case file. You decide.

{_SHARED_CONTEXT}

How to judge:
- The arguments are advocacy, not evidence. Check every fact either side cites against the case file, and give no weight to anything the case file does not support.
- A response answers a point only if it engages the specific facts that point relies on. Saying that something is permitted, common or normal does not answer a point about whether it fits the particular facts of this claim; treat a point answered only in that way as unanswered.
- A point conceded by the side it hurts can be treated as settled. A point one side raised and the other did not actually answer deserves close attention, but only if the case file supports it.
- Choose the decision that is more likely to be correct given the case file.
- For every numbered point from either side (P1, P2, ... and D1, D2, ...), record whether the other side answered it: "answered_with_case_file_fact" if the other side engaged the point with specific facts from the case file that actually answer it; "answered_by_assertion_only" if the other side only asserted, gave an opinion, or said something is permitted, common or normal; "unanswered" if the other side did not respond to it. Mark a point as significant if, left standing, it could change the decision.

Confidence (verbalized_confidence), with a justification for that specific level:
- HIGH: you would expect this decision to be correct at least {BASELINE_HIGH_CONFIDENCE_THRESHOLD} times out of 100 on claims like this one. The facts clearly support it, and the other side's strongest point is actually answered by facts in the case file, not merely by an assertion.
- MEDIUM: roughly {MEDIUM_CONFIDENCE_FLOOR} to {BASELINE_HIGH_CONFIDENCE_THRESHOLD - 1} times out of 100. The decision is better supported, but a significant point for the other side is not fully answered.
- LOW: fewer than {MEDIUM_CONFIDENCE_FLOOR} times out of 100. The case file supports both decisions about equally, or the outcome turns on facts the case file does not contain.

Respond with only a JSON object in exactly this form:
{{"decision": "APPROVE or DENY", "reasoning": "<one paragraph citing the specific case-file facts, and the prosecutor (P#) and defender points, that decided it>", "verbalized_confidence": "HIGH, MEDIUM or LOW", "confidence_justification": "<why this level and not the level above or below it>", "point_assessments": [{{"point_id": "P1", "significant": true, "status": "answered_with_case_file_fact, answered_by_assertion_only or unanswered"}}]}}"""


# ---------------------------------------------------------------------------
# Messages for each role
# ---------------------------------------------------------------------------

def build_prosecutor_messages(case_file):
    return [
        {"role": "system", "content": PROSECUTOR_SYSTEM_PROMPT},
        {"role": "user", "content": case_file},
    ]


def build_defender_messages(case_file, prosecutor_argument):
    return [
        {"role": "system", "content": DEFENDER_SYSTEM_PROMPT},
        {"role": "user", "content": f"{case_file}\n\nPROSECUTOR'S ARGUMENT:\n{compact_json(prosecutor_argument)}"},
    ]


def build_rebuttal_messages(case_file, prosecutor_argument, defender_argument):
    return [
        {"role": "system", "content": PROSECUTOR_REBUTTAL_SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"{case_file}\n\nPROSECUTOR'S ARGUMENT:\n{compact_json(prosecutor_argument)}"
            f"\n\nDEFENDER'S ARGUMENT:\n{compact_json(defender_argument)}"
        )},
    ]


def build_judge_messages(case_file, prosecutor_argument, defender_argument, prosecutor_rebuttal, order="prosecutor_first"):
    """The Judge's input. Between orders only the two opening arguments swap places; the
    rebuttal (a reply to the Defender) comes last in both, and all text is identical."""
    prosecutor_section = f"PROSECUTOR'S ARGUMENT:\n{compact_json(prosecutor_argument)}"
    defender_section = f"DEFENDER'S ARGUMENT:\n{compact_json(defender_argument)}"
    rebuttal_section = f"PROSECUTOR'S REBUTTAL:\n{compact_json(prosecutor_rebuttal)}"
    if order == "prosecutor_first":
        first, second = prosecutor_section, defender_section
    elif order == "defender_first":
        first, second = defender_section, prosecutor_section
    else:
        raise ValueError(f"order must be one of {JUDGE_ORDERS}, got {order!r}")
    return [
        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
        {"role": "user", "content": f"{case_file}\n\n{first}\n\n{second}\n\n{rebuttal_section}"},
    ]


# ---------------------------------------------------------------------------
# Running the debate
# ---------------------------------------------------------------------------

def run_debate(claim, evidence, llm=call_llm, completed_steps=None, on_step=None):
    """Run Prosecutor, Defender, Prosecutor rebuttal and Judge (Prosecutor's argument first).

    completed_steps: steps saved from an interrupted run ({role: step}); those roles are
                     skipped, so a failure late in the debate never re-spends earlier calls.
    on_step:         called with all steps so far after each new call (use it to checkpoint).
    llm:             replaceable in tests with a function taking (messages, label).
    """
    case_file = build_case_file(claim, evidence)  # refuses unsanitized input
    claim_id = claim["claim_id"]
    steps = dict(completed_steps or {})

    if "prosecutor" not in steps:
        messages = build_prosecutor_messages(case_file)
        run_step(steps, "prosecutor", messages, parse_prosecutor, llm, claim_id, on_step)

    if "defender" not in steps:
        messages = build_defender_messages(case_file, steps["prosecutor"]["output"])
        run_step(steps, "defender", messages, parse_defender, llm, claim_id, on_step)

    if "prosecutor_rebuttal" not in steps:
        messages = build_rebuttal_messages(case_file, steps["prosecutor"]["output"], steps["defender"]["output"])
        run_step(steps, "prosecutor_rebuttal", messages, parse_rebuttal, llm, claim_id, on_step)

    if "judge" not in steps:
        messages = build_judge_messages(case_file, steps["prosecutor"]["output"], steps["defender"]["output"],
                                        steps["prosecutor_rebuttal"]["output"])
        run_step(steps, "judge", messages, parse_judge, llm, claim_id, on_step)

    judge = steps["judge"]["output"]
    return {
        "claim_id": claim_id,
        "decision": judge["decision"],
        "verbalized_confidence": judge["verbalized_confidence"],
        "transcript": {role: steps[role]["output"] for role in ROLES},
        "usage": {**{role: steps[role]["usage"] for role in ROLES}, "total": sum_usage(steps[role]["usage"] for role in ROLES)},
        "attempts": {**{role: steps[role]["attempts"] for role in ROLES}, "total": sum(steps[role]["attempts"] for role in ROLES)},
    }


def run_step(steps, name, messages, parse, llm, claim_id, on_step):
    """Make one model call, validate its reply, store it under steps[name], then checkpoint."""
    result = llm(messages, label=f"debate_{name}:{claim_id}")
    steps[name] = {"output": parse(result["data"]), "usage": result["usage"], "attempts": result["attempts"]}
    if on_step:
        on_step(steps)


def sum_usage(usages):
    total = {"prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0}
    for usage in usages:
        for key in total:
            total[key] += usage.get(key, 0)
    return total


# ---------------------------------------------------------------------------
# Validating each role's JSON (raise ValueError rather than guess at a bad reply)
# ---------------------------------------------------------------------------

def parse_prosecutor(data):
    points = _parse_points(data.get("points"), prefix="P")
    if not points:
        raise ValueError("prosecutor returned no points")
    return {"points": points, "summary": _required_text(data, "summary", "prosecutor")}


def parse_defender(data):
    raw_responses = data.get("responses")
    if not isinstance(raw_responses, list) or not raw_responses:
        raise ValueError("defender returned no responses to the prosecutor's points")
    responses = [
        {
            "responds_to": str(item.get("responds_to", "")).strip(),
            "position": str(item.get("position", "")).strip().lower(),
            "response": str(item.get("response", "")).strip(),
            "evidence": str(item.get("evidence", "")).strip(),
        }
        for item in raw_responses if isinstance(item, dict)
    ]
    if not all(r["response"] for r in responses):
        raise ValueError("defender returned an empty response")
    return {
        "responses": responses,
        "points": _parse_points(data.get("points") or [], prefix="D"),
        "summary": _required_text(data, "summary", "defender"),
    }


def parse_rebuttal(data):
    raw_rebuttals = data.get("rebuttals")
    if not isinstance(raw_rebuttals, list):
        raise ValueError("prosecutor rebuttal must contain a rebuttals list (it may be empty)")
    rebuttals = [
        {
            "responds_to": str(item.get("responds_to", "")).strip(),
            "rebuttal": str(item.get("rebuttal", "")).strip(),
            "evidence": str(item.get("evidence", "")).strip(),
        }
        for item in raw_rebuttals if isinstance(item, dict)
    ]
    if not all(r["rebuttal"] for r in rebuttals):
        raise ValueError("prosecutor rebuttal contains an empty rebuttal")
    return {"rebuttals": rebuttals, "summary": _required_text(data, "summary", "prosecutor rebuttal")}


def parse_judge(data):
    decision = str(data.get("decision", "")).strip().upper()
    if decision not in ("APPROVE", "DENY"):
        raise ValueError(f"judge decision must be APPROVE or DENY, got {data.get('decision')!r}")
    confidence = str(data.get("verbalized_confidence", "")).strip().upper()
    if confidence not in CONFIDENCE_LEVELS:
        raise ValueError(f"verbalized_confidence must be HIGH, MEDIUM or LOW, got {data.get('verbalized_confidence')!r}")
    return {
        "decision": decision,
        "reasoning": _required_text(data, "reasoning", "judge"),
        "verbalized_confidence": confidence,
        "confidence_justification": _required_text(data, "confidence_justification", "judge"),
        "point_assessments": _parse_point_assessments(data.get("point_assessments")),
    }


def _parse_point_assessments(raw_assessments):
    if not isinstance(raw_assessments, list):
        raise ValueError("judge returned no point_assessments list")
    assessments = []
    for item in raw_assessments:
        if not isinstance(item, dict):
            raise ValueError("each point assessment must be an object")
        status = str(item.get("status", "")).strip().lower()
        if status not in POINT_STATUSES:
            raise ValueError(f"point assessment status must be one of {POINT_STATUSES}, got {item.get('status')!r}")
        significant = item.get("significant")
        if isinstance(significant, str) and significant.strip().lower() in ("true", "false"):
            significant = significant.strip().lower() == "true"
        if not isinstance(significant, bool):
            raise ValueError(f"point assessment 'significant' must be true or false, got {item.get('significant')!r}")
        assessments.append({"point_id": str(item.get("point_id", "")).strip(), "significant": significant, "status": status})
    return assessments


def _parse_points(raw_points, prefix):
    if not isinstance(raw_points, list):
        raise ValueError("points must be a list")
    points = []
    for number, item in enumerate(raw_points, start=1):
        if not isinstance(item, dict) or not str(item.get("point", "")).strip():
            raise ValueError(f"point {number} is missing its text")
        points.append({
            "id": str(item.get("id") or f"{prefix}{number}").strip(),
            "point": str(item["point"]).strip(),
            "evidence": str(item.get("evidence", "")).strip(),
        })
    return points


def _required_text(data, key, role):
    text = str(data.get(key, "")).strip()
    if not text:
        raise ValueError(f"{role} returned an empty {key}")
    return text
