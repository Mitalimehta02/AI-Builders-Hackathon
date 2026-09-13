"""
Stage 6 check: run the naive baseline AND the full ClaimLens pipeline (debate + order-swapped
Judge + confidence tier + gate) on the DEVELOPMENT SET ONLY (PROJECT_PLAN.md Part 5b).

Held-out claims are never loaded into this script's working data: require_dev_set() stops it
before anything runs if a held-out ID is requested.

Quota safety: progress is saved to backend/data/stage6_dev_results.json after EVERY model
call; a re-run resumes where it stopped and never repeats finished calls. Delete the file to
start over. Raw requests/responses are in backend/data/llm_logs/.

Run from the backend/ folder:
    .\\.venv\\Scripts\\python.exe -m app.synthetic.test_calibration
"""

import json
import sys
import textwrap
from pathlib import Path

from app.agents.calibration import STEPS, run_claimlens
from app.agents.evidence_agent import gather_evidence
from app.agents.naive_baseline_agent import run_naive_baseline
from app.agents.sanitize import sanitize_claim
from app.synthetic.eval_split import DEV_SET_IDS, require_dev_set

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CLAIMS_PATH = DATA_DIR / "synthetic_claims.json"
RESULTS_PATH = DATA_DIR / "stage6_dev_results.json"

RUN_IDS = DEV_SET_IDS
STAGE11_CLAIMS = 40
TOKENS_PER_MINUTE_LIMIT = 8000


def wrap(text, indent="      "):
    return textwrap.fill(text, width=96, initial_indent=indent, subsequent_indent=indent)


def main():
    sys.stdout.reconfigure(errors="replace")  # Windows consoles can't print every character models use
    require_dev_set(RUN_IDS)

    with open(CLAIMS_PATH, encoding="utf-8") as f:
        claims_by_id = {c["claim_id"]: c for c in json.load(f) if c["claim_id"] in RUN_IDS}
    results = json.loads(RESULTS_PATH.read_text(encoding="utf-8")) if RESULTS_PATH.exists() else {}

    def save():
        RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")

    requests_this_run = 0
    for claim_id in RUN_IDS:
        claim = sanitize_claim(claims_by_id[claim_id])
        entry = results.setdefault(claim_id, {})

        if "evidence" not in entry:
            entry["evidence"] = gather_evidence(claim)
            save()
        evidence = entry["evidence"]

        if "baseline" not in entry:
            entry["baseline"] = run_naive_baseline(claim, evidence)
            requests_this_run += entry["baseline"]["attempts"]
            save()

        pipeline = entry.get("claimlens", {})
        if pipeline.get("status") != "complete":
            already_done = pipeline.get("steps", {})

            def checkpoint(steps, entry=entry):
                entry["claimlens"] = {"status": "in_progress", "steps": steps}
                save()

            result = run_claimlens(claim, evidence, completed_steps=already_done, on_step=checkpoint)
            requests_this_run += sum(result["attempts"][name] for name in STEPS if name not in already_done)
            entry["claimlens"] = {"status": "complete", **result}
            save()

    print_details(claims_by_id, results)
    print_summary_table(claims_by_id, results)
    print_tokens(results)
    print(f"Requests sent in THIS run: {requests_this_run}")


def is_correct(decision, raw_claim):
    return (decision == "DENY") == raw_claim["ground_truth"]["is_fraud"]


def print_details(claims_by_id, results):
    for claim_id in RUN_IDS:
        raw, entry = claims_by_id[claim_id], results[claim_id]
        baseline, pipeline = entry["baseline"], entry["claimlens"]
        first, swapped = pipeline["transcript"]["judge_prosecutor_first"], pipeline["transcript"]["judge_defender_first"]
        print("=" * 100)
        print(f"{claim_id}  (answer for reference only: is_fraud={raw['ground_truth']['is_fraud']})")
        print(f"  BASELINE             {baseline['decision']} ({baseline['confidence']})")
        print(wrap(baseline["reasoning"]))
        print(f"  JUDGE, prosecutor 1st {first['decision']} / {first['verbalized_confidence']}")
        print(wrap(first["reasoning"]))
        print(wrap(f"confidence: {first['confidence_justification']}"))
        print(f"  JUDGE, defender 1st   {swapped['decision']} / {swapped['verbalized_confidence']}")
        print(wrap(swapped["reasoning"]))
        print(wrap(f"confidence: {swapped['confidence_justification']}"))
        print(f"  TIER {pipeline['confidence_tier']}   GATE {pipeline['gate']}   orderings agree: {pipeline['orderings_agree']}")


def print_summary_table(claims_by_id, results):
    print("=" * 100)
    print(f"{'claim':<9} {'fraud?':<6} {'baseline':<13} {'judge P-first':<15} {'judge D-first':<15} {'agree':<6} {'tier':<7} {'gate':<14} {'baseline':<9} {'claimlens'}")
    for claim_id in RUN_IDS:
        raw, entry = claims_by_id[claim_id], results[claim_id]
        baseline, pipeline = entry["baseline"], entry["claimlens"]
        first, swapped = pipeline["transcript"]["judge_prosecutor_first"], pipeline["transcript"]["judge_defender_first"]
        print(f"{claim_id:<9} {str(raw['ground_truth']['is_fraud']):<6} "
              f"{baseline['decision'] + ' ' + str(baseline['confidence']):<13} "
              f"{first['decision'] + ' ' + first['verbalized_confidence']:<15} "
              f"{swapped['decision'] + ' ' + swapped['verbalized_confidence']:<15} "
              f"{'yes' if pipeline['orderings_agree'] else 'NO':<6} {pipeline['confidence_tier']:<7} {pipeline['gate']:<14} "
              f"{'right' if is_correct(baseline['decision'], raw) else 'WRONG':<9} "
              f"{'right' if is_correct(pipeline['decision'], raw) else 'WRONG'}")


def print_tokens(results):
    print("=" * 100)
    print("MEASURED TOKENS PER CLAIM")
    print(f"{'claim':<9} {'baseline':>9} " + " ".join(f"{name:>21}" for name in STEPS) + f" {'pipeline total':>15}")
    for claim_id in RUN_IDS:
        entry = results[claim_id]
        usage = entry["claimlens"]["usage"]
        print(f"{claim_id:<9} {entry['baseline']['usage']['total_tokens']:>9,} "
              + " ".join(f"{usage[name]['total_tokens']:>21,}" for name in STEPS)
              + f" {usage['total']['total_tokens']:>15,}")
    count = len(RUN_IDS)
    baseline_avg = sum(results[c]["baseline"]["usage"]["total_tokens"] for c in RUN_IDS) / count
    step_avg = {name: sum(results[c]["claimlens"]["usage"][name]["total_tokens"] for c in RUN_IDS) / count for name in STEPS}
    pipeline_avg = sum(step_avg.values())
    print(f"{'average':<9} {baseline_avg:>9,.0f} " + " ".join(f"{step_avg[name]:>21,.0f}" for name in STEPS) + f" {pipeline_avg:>15,.0f}")
    stage11 = STAGE11_CLAIMS * (baseline_avg + pipeline_avg)
    print(f"Stage 11 projection from these measurements: {STAGE11_CLAIMS} x ({baseline_avg:,.0f} + {pipeline_avg:,.0f}) = "
          f"{stage11:,.0f} tokens, {STAGE11_CLAIMS * (1 + len(STEPS))} requests, "
          f"at least {stage11 / TOKENS_PER_MINUTE_LIMIT:,.0f} minutes at {TOKENS_PER_MINUTE_LIMIT:,} tokens/minute")


if __name__ == "__main__":
    main()
