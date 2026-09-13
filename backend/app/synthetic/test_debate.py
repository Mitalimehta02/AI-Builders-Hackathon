"""
Stage 5 check: run the full debate (Prosecutor -> Defender -> Judge) on 3 fixed claims,
print every transcript, and measure real tokens per claim for the Stage 11 budget.

Sample (chosen by ID before running; notes are for humans, the agents see sanitized input only):
  CLM-0027  legitimate: the claim the Stage 4 baseline got wrong
  CLM-0035  fraud: a "frozen pipe" in Miami in July
  CLM-0019  fraud: theft cover added days before the theft; the Stage 4 baseline was right
            for the wrong reason

Quota safety: progress is saved to backend/data/stage5_debate_sample.json after EVERY call,
so an interrupted run resumes mid-debate without re-spending finished calls. Delete the file
to start over. Raw requests/responses are in backend/data/llm_logs/.

Run from the backend/ folder:
    .\\.venv\\Scripts\\python.exe -m app.synthetic.test_debate
"""

import json
import sys
import textwrap
from pathlib import Path

from app.agents.debate_agent import ROLES, run_debate
from app.agents.evidence_agent import gather_evidence
from app.agents.sanitize import sanitize_claim

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CLAIMS_PATH = DATA_DIR / "synthetic_claims.json"
RESULTS_PATH = DATA_DIR / "stage5_debate_sample.json"
BASELINE_SAMPLE_PATH = DATA_DIR / "stage4_baseline_sample.json"

SAMPLE = [
    ("CLM-0027", "legitimate; Stage 4 baseline got it wrong"),
    ("CLM-0035", "fraud; 'frozen pipe' in Miami in July"),
    ("CLM-0019", "fraud; Stage 4 baseline right for the wrong reason"),
]

STAGE11_CLAIMS = 40
TOKENS_PER_MINUTE_LIMIT = 8000  # confirmed from Groq's response headers at Stage 4


def wrap(text, indent="      "):
    return textwrap.fill(text, width=92, initial_indent=indent, subsequent_indent=indent)


def print_transcript(claim_id, note, raw_claim, result):
    transcript = result["transcript"]
    prosecutor, defender, judge = transcript["prosecutor"], transcript["defender"], transcript["judge"]
    truth = raw_claim["ground_truth"]

    print("=" * 96)
    print(f"{claim_id}  [{note}]   ${raw_claim['claim_amount']:,.2f} {raw_claim['claim_type']} claim")
    print("=" * 96)
    print("PROSECUTOR")
    for point in prosecutor["points"]:
        print(f"  {point['id']}: {point['point']}")
        print(wrap(f"evidence: {point['evidence']}"))
    print(wrap(f"summary: {prosecutor['summary']}", indent="  "))
    print("-" * 96)
    print("DEFENDER")
    for response in defender["responses"]:
        print(f"  re {response['responds_to']} [{response['position']}]: {response['response']}")
        print(wrap(f"evidence: {response['evidence']}"))
    for point in defender["points"]:
        print(f"  {point['id']}: {point['point']}")
        print(wrap(f"evidence: {point['evidence']}"))
    print(wrap(f"summary: {defender['summary']}", indent="  "))
    print("-" * 96)
    print("JUDGE")
    print(f"  decision:              {judge['decision']}")
    print(f"  verbalized_confidence: {judge['verbalized_confidence']}")
    print(wrap(f"reasoning: {judge['reasoning']}", indent="  "))
    print(wrap(f"confidence justification: {judge['confidence_justification']}", indent="  "))
    print("-" * 96)
    correct = (judge["decision"] == "DENY") == truth["is_fraud"]
    print(f"answer (reference only, never shown to the agents): is_fraud={truth['is_fraud']} -> judge was {'CORRECT' if correct else 'WRONG'}")
    usage = result["usage"]
    print("tokens: " + " | ".join(
        f"{role} {usage[role]['total_tokens']} (prompt {usage[role]['prompt_tokens']}, reasoning {usage[role]['reasoning_tokens']})"
        for role in ROLES) + f" | TOTAL {usage['total']['total_tokens']}")


def main():
    sys.stdout.reconfigure(errors="replace")  # Windows consoles can't print every character models use

    with open(CLAIMS_PATH, encoding="utf-8") as f:
        claims_by_id = {c["claim_id"]: c for c in json.load(f)}
    results = json.loads(RESULTS_PATH.read_text(encoding="utf-8")) if RESULTS_PATH.exists() else {}

    def save():
        RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")

    requests_this_run = 0
    for claim_id, note in SAMPLE:
        raw_claim = claims_by_id[claim_id]
        saved = results.get(claim_id, {})
        if saved.get("status") != "complete":
            claim = sanitize_claim(raw_claim)
            evidence = saved.get("evidence") or gather_evidence(claim)
            already_done = saved.get("steps", {})

            def checkpoint(steps, claim_id=claim_id, evidence=evidence):
                results[claim_id] = {"status": "in_progress", "claim_id": claim_id, "evidence": evidence, "steps": steps}
                save()

            result = run_debate(claim, evidence, completed_steps=already_done, on_step=checkpoint)
            requests_this_run += sum(result["attempts"][role] for role in ROLES if role not in already_done)
            # The full transcript is stored together with the claim's evidence.
            results[claim_id] = {"status": "complete", "evidence": evidence, **result}
            save()
        print_transcript(claim_id, note, raw_claim, results[claim_id])

    # ----- Measured budget -----
    done = [results[claim_id] for claim_id, _ in SAMPLE]
    average = {role: sum(r["usage"][role]["total_tokens"] for r in done) / len(done) for role in ROLES}
    debate_per_claim = sum(average.values())
    baseline = json.loads(BASELINE_SAMPLE_PATH.read_text(encoding="utf-8")) if BASELINE_SAMPLE_PATH.exists() else {}
    baseline_per_claim = sum(r["usage"]["total_tokens"] for r in baseline.values()) / len(baseline) if baseline else 0

    # Stage 6 adds one more Judge call (arguments in swapped order). Its prompt has the same
    # content, so we estimate it at the measured Judge cost. Everything else is measured.
    pipeline_per_claim = average["prosecutor"] + average["defender"] + 2 * average["judge"]
    double_debate_per_claim = 2 * debate_per_claim
    stage11 = STAGE11_CLAIMS * (baseline_per_claim + pipeline_per_claim)
    stage11_double = STAGE11_CLAIMS * (baseline_per_claim + double_debate_per_claim)

    print("=" * 96)
    print("MEASURED TOKENS")
    for claim in done:
        print(f"  {claim['claim_id']}: " + ", ".join(f"{role} {claim['usage'][role]['total_tokens']}" for role in ROLES)
              + f" -> debate total {claim['usage']['total']['total_tokens']}")
    print("  average per claim: " + ", ".join(f"{role} {average[role]:,.0f}" for role in ROLES) + f" -> debate {debate_per_claim:,.0f}")
    print(f"  baseline average per claim (re-run Stage 4 sample, {len(baseline)} claims): {baseline_per_claim:,.0f}")
    print("STAGE 11 PROJECTION (40 claims)")
    print(f"  pipeline per claim  = prosecutor + defender + 2 x judge   = {pipeline_per_claim:,.0f} tokens (second judge estimated)")
    print(f"  baseline + pipeline = {STAGE11_CLAIMS} x ({baseline_per_claim:,.0f} + {pipeline_per_claim:,.0f}) = {stage11:,.0f} tokens, "
          f"{STAGE11_CLAIMS * 5} requests")
    print(f"  at {TOKENS_PER_MINUTE_LIMIT:,} tokens/minute that is at least {stage11 / TOKENS_PER_MINUTE_LIMIT:,.0f} minutes of pacing")
    print(f"  with FULL_DOUBLE_DEBATE: {stage11_double:,.0f} tokens, {STAGE11_CLAIMS * 7} requests, "
          f"at least {stage11_double / TOKENS_PER_MINUTE_LIMIT:,.0f} minutes")
    print(f"Requests sent in THIS run: {requests_this_run}")


if __name__ == "__main__":
    main()
