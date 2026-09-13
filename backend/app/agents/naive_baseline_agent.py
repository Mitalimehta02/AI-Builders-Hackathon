"""
Naive baseline agent (Stage 4): ONE model call that decides APPROVE or DENY directly.

This is the honest comparison point for ClaimLens. It is deliberately single-pass (no
debate, no cross-checking), but it is NOT a strawman:
- same inputs as the full pipeline: the sanitized claim + the Stage 3 evidence object,
  rendered by the shared build_case_file(), explained by the shared CASE_FILE_GUIDE
- same review instructions as the debate Judge (shared REVIEW_GUIDANCE)
- same model and generation settings: every call goes through llm_client.call_llm()
- a prompt written as carefully as if this single call were the whole product, including
  an explicit request for calibrated confidence

At Stage 11 the only difference between this and ClaimLens is the architecture.

Usage:
    evidence = gather_evidence(sanitize_claim(raw_claim))
    result = run_naive_baseline(sanitize_claim(raw_claim), evidence)
"""

from app.agents.case_file import CASE_FILE_GUIDE, DECISION_DEFINITIONS, REVIEW_GUIDANCE, build_case_file
from app.agents.llm_client import call_llm

# PRE-REGISTERED THRESHOLD. Fixed at Stage 4, BEFORE any baseline or ClaimLens results were
# observed. In the Stage 11 confidently-wrong comparison, a baseline decision is in the
# HIGH-confidence band when confidence >= this value. Changing it after seeing results would
# be tuning the metric to flatter the design - don't. (The debate Judge's HIGH level is
# defined from this same number, so both systems' "high confidence" means the same thing.)
BASELINE_HIGH_CONFIDENCE_THRESHOLD = 80

SYSTEM_PROMPT = f"""You are a senior claims investigator at a US property and casualty insurer. You review one insurance claim at a time and decide whether it should be paid.

{CASE_FILE_GUIDE}

Decisions:
{DECISION_DEFINITIONS}

{REVIEW_GUIDANCE}
- Choose the decision that is more likely to be correct given the case file.

Confidence:
- Give an integer from 0 to 100: your probability that your decision is correct. Because you choose the more probable decision, this should normally be 50 or higher.
- Be calibrated. If you would be right about 70 out of 100 times on claims like this one, answer 70. Reserve 90 and above for claims where the facts leave very little room for doubt.

Respond with only a JSON object in exactly this form:
{{"decision": "APPROVE or DENY", "confidence": <integer 0-100>, "reasoning": "<one paragraph citing the specific facts from the case file that drove the decision>"}}"""


def build_messages(claim, evidence):
    """The exact messages sent to the model (build_case_file enforces sanitized input)."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_case_file(claim, evidence)},
    ]


def run_naive_baseline(claim, evidence, llm=call_llm):
    """Decide one sanitized claim with a single model call.

    llm can be replaced in tests with a function taking (messages, label).
    Returns {"claim_id", "decision", "confidence", "high_confidence", "reasoning",
             "usage", "attempts", "rate_limit"}.
    """
    messages = build_messages(claim, evidence)
    result = llm(messages, label=f"naive_baseline:{claim['claim_id']}")
    decision = parse_decision(result["data"])
    return {
        "claim_id": claim["claim_id"],
        **decision,
        "high_confidence": decision["confidence"] >= BASELINE_HIGH_CONFIDENCE_THRESHOLD,
        "usage": result["usage"],
        "attempts": result["attempts"],
        "rate_limit": result.get("rate_limit", {}),
    }


def parse_decision(data):
    """Validate the model's JSON. Raises ValueError rather than guessing at a bad reply."""
    decision = str(data.get("decision", "")).strip().upper()
    if decision not in ("APPROVE", "DENY"):
        raise ValueError(f"decision must be APPROVE or DENY, got {data.get('decision')!r}")

    raw_confidence = data.get("confidence")
    try:
        confidence = float(str(raw_confidence).strip().rstrip("%"))
    except ValueError:
        raise ValueError(f"confidence must be a number, got {raw_confidence!r}") from None
    if not confidence.is_integer() or not 0 <= confidence <= 100:
        raise ValueError(f"confidence must be an integer from 0 to 100, got {raw_confidence!r}")

    reasoning = str(data.get("reasoning", "")).strip()
    if not reasoning:
        raise ValueError("reasoning is empty")

    return {"decision": decision, "confidence": int(confidence), "reasoning": reasoning}
