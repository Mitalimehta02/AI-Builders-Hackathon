"""
Debate engine (Stage 5): Prosecutor -> Defender -> Judge, three calls through the shared client.

Why a debate: two agents argue opposite sides and a judge decides. It is easier to check a
winning argument against the facts than to verify a hard claim directly (Irving, Christiano &
Amodei, "AI Safety via Debate", 2018). Here each side must cite case-file facts, and the Judge
is told to check every citation against the case file.

  1. Prosecutor: the strongest honest case that the claim should be DENIED.
  2. Defender:   answers each Prosecutor point by id (rebut or concede), then adds its own.
  3. Judge:      reads the case file and both arguments, returns decision, reasoning,
                 verbalized_confidence (HIGH / MEDIUM / LOW) and a justification for that level.

Fairness with the naive baseline: every role receives the same case file (build_case_file),
the same CASE_FILE_GUIDE, DECISION_DEFINITIONS and REVIEW_GUIDANCE, and goes through the same
llm_client with the same settings. The Judge's HIGH level is defined with the baseline's
pre-registered threshold, so "high confidence" means the same thing for both systems.

The Judge's input can present the two arguments in either order (build_judge_messages); the
Stage 6 calibration layer uses that for its order-swap consistency check.

Usage:
    claim = sanitize_claim(raw_claim)
    result = run_debate(claim, gather_evidence(claim))
    result["transcript"]  # {"prosecutor": ..., "defender": ..., "judge": ...}
"""

from app.agents.case_file import CASE_FILE_GUIDE, DECISION_DEFINITIONS, REVIEW_GUIDANCE, build_case_file, compact_json
from app.agents.llm_client import call_llm
from app.agents.naive_baseline_agent import BASELINE_HIGH_CONFIDENCE_THRESHOLD

ROLES = ("prosecutor", "defender", "judge")
CONFIDENCE_LEVELS = ("HIGH", "MEDIUM", "LOW")
JUDGE_ORDERS = ("prosecutor_first", "defender_first")
MEDIUM_CONFIDENCE_FLOOR = 65  # below this many correct out of 100 is LOW

MAX_PROSECUTOR_POINTS = 5
MAX_DEFENDER_EXTRA_POINTS = 3

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

JUDGE_SYSTEM_PROMPT = f"""You are the judge in a structured claims review at a US property and casualty insurer. A prosecutor has argued that the claim should be denied and a defender has argued that it should be paid. Both arguments follow the case file. You decide.

{_SHARED_CONTEXT}

How to judge:
- The arguments are advocacy, not evidence. Check every fact either side cites against the case file, and give no weight to anything the case file does not support.
- A response answers a point only if it engages the specific facts that point relies on. Saying that something is permitted, common or normal does not answer a point about whether it fits the particular facts of this claim; treat a point answered only in that way as unanswered.
- A point conceded by the side it hurts can be treated as settled. A point one side raised and the other did not actually answer deserves close attention, but only if the case file supports it.
- Choose the decision that is more likely to be correct given the case file.

Confidence (verbalized_confidence), with a justification for that specific level:
- HIGH: you would expect this decision to be correct at least {BASELINE_HIGH_CONFIDENCE_THRESHOLD} times out of 100 on claims like this one. The facts clearly support it, and the other side's strongest point is actually answered by facts in the case file, not merely by an assertion.
- MEDIUM: roughly {MEDIUM_CONFIDENCE_FLOOR} to {BASELINE_HIGH_CONFIDENCE_THRESHOLD - 1} times out of 100. The decision is better supported, but a significant point for the other side is not fully answered.
- LOW: fewer than {MEDIUM_CONFIDENCE_FLOOR} times out of 100. The case file supports both decisions about equally, or the outcome turns on facts the case file does not contain.

Respond with only a JSON object in exactly this form:
{{"decision": "APPROVE or DENY", "reasoning": "<one paragraph citing the specific case-file facts, and the prosecutor (P#) and defender points, that decided it>", "verbalized_confidence": "HIGH, MEDIUM or LOW", "confidence_justification": "<why this level and not the level above or below it>"}}"""


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


def build_judge_messages(case_file, prosecutor_argument, defender_argument, order="prosecutor_first"):
    """The Judge's input. Only the order of the two arguments changes between orders;
    the system prompt, case file and argument text are identical."""
    prosecutor_section = f"PROSECUTOR'S ARGUMENT:\n{compact_json(prosecutor_argument)}"
    defender_section = f"DEFENDER'S ARGUMENT:\n{compact_json(defender_argument)}"
    if order == "prosecutor_first":
        first, second = prosecutor_section, defender_section
    elif order == "defender_first":
        first, second = defender_section, prosecutor_section
    else:
        raise ValueError(f"order must be one of {JUDGE_ORDERS}, got {order!r}")
    return [
        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
        {"role": "user", "content": f"{case_file}\n\n{first}\n\n{second}"},
    ]


# ---------------------------------------------------------------------------
# Running the debate
# ---------------------------------------------------------------------------

def run_debate(claim, evidence, llm=call_llm, completed_steps=None, on_step=None):
    """Run Prosecutor, Defender and Judge (Prosecutor's argument presented first) for one sanitized claim.

    completed_steps: steps saved from an interrupted run ({role: step}); those roles are
                     skipped, so a failure at the Judge never re-spends the first two calls.
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

    if "judge" not in steps:
        messages = build_judge_messages(case_file, steps["prosecutor"]["output"], steps["defender"]["output"])
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
    }


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
