"""
Dev-set check: run the naive baseline AND the full ClaimLens pipeline (Prosecutor, Defender,
two Judge orderings, confidence tier, point-accounting cap, gate) on the
DEVELOPMENT SET ONLY (PROJECT_PLAN.md Part 5b), and compare with the previous Stage 6 dev run.

Held-out claims are never kept in this script's working data, and require_dev_set() stops the
script before anything runs if a held-out ID is requested.

Baseline reuse: a baseline result from the previous dev run is reused only if the request log
shows the baseline's input messages were byte-identical to what would be sent now. Otherwise
the baseline is run again.

Quota safety: progress is saved to backend/data/stage6_dev_results_v3.json after EVERY model
call; a re-run resumes where it stopped. Raw requests/responses are in backend/data/llm_logs/.

Run from the backend/ folder:
    .\\.venv\\Scripts\\python.exe -m app.synthetic.test_calibration
"""

import json
import sys
from pathlib import Path

from app.agents.calibration import STEPS, run_claimlens
from app.agents.evidence_agent import gather_evidence
from app.agents.naive_baseline_agent import build_messages as build_baseline_messages, run_naive_baseline
from app.agents.sanitize import sanitize_claim
from app.synthetic.eval_split import DEV_SET_IDS, require_dev_set

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CLAIMS_PATH = DATA_DIR / "synthetic_claims.json"
RESULTS_PATH = DATA_DIR / "stage6_dev_results_v3.json"  # v2 used the since-removed rebuttal round
PREVIOUS_RESULTS_PATH = DATA_DIR / "stage6_dev_results.json"
LOG_DIR = DATA_DIR / "llm_logs"

RUN_IDS = DEV_SET_IDS
STAGE11_CLAIMS = 40
TOKENS_PER_MINUTE_LIMIT = 8000


def latest_logged_baseline_inputs():
    """{claim_id: request messages of the most recent successful baseline call}."""
    latest = {}
    for path in sorted(LOG_DIR.glob("*.jsonl")):
        with open(path, encoding="utf-8") as f:
            for line in f:
                entry = json.loads(line)
                if entry["label"].startswith("naive_baseline:") and entry["status"] == "ok":
                    latest[entry["label"].split(":", 1)[1]] = entry["request_messages"]
    return latest


def main():
    sys.stdout.reconfigure(errors="replace")  # Windows consoles can't print every character models use
    require_dev_set(RUN_IDS)

    with open(CLAIMS_PATH, encoding="utf-8") as f:
        claims_by_id = {c["claim_id"]: c for c in json.load(f) if c["claim_id"] in RUN_IDS}
    results = json.loads(RESULTS_PATH.read_text(encoding="utf-8")) if RESULTS_PATH.exists() else {}
    previous = json.loads(PREVIOUS_RESULTS_PATH.read_text(encoding="utf-8")) if PREVIOUS_RESULTS_PATH.exists() else {}
    logged_inputs = latest_logged_baseline_inputs()

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
            current_input = build_baseline_messages(claim, evidence)
            if claim_id in previous and logged_inputs.get(claim_id) == current_input:
                entry["baseline"] = {**previous[claim_id]["baseline"], "reused_from_previous_run": True}
            else:
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
    print_table(claims_by_id, results)
    print_comparison(claims_by_id, results, previous)
    print_tokens(results)
    print(f"Requests sent in THIS run: {requests_this_run}")


def is_correct(decision, raw_claim):
    return (decision == "DENY") == raw_claim["ground_truth"]["is_fraud"]


def print_details(claims_by_id, results):
    for claim_id in RUN_IDS:
        pipeline = results[claim_id]["claimlens"]
        transcript = pipeline["transcript"]
        print("=" * 100)
        print(f"{claim_id}  (answer for reference only: is_fraud={claims_by_id[claim_id]['ground_truth']['is_fraud']})")
        for order in ("prosecutor_first", "defender_first"):
            ruling = transcript[f"judge_{order}"]
            print(f"  judge {order:<16} {ruling['decision']} / {ruling['verbalized_confidence']}   "
                  f"unresolved against its decision: {pipeline['unresolved_points'][order] or 'none'}")
        print(f"  tier before cap {pipeline['tier_before_cap']} -> final tier {pipeline['confidence_tier']}   gate {pipeline['gate']}")


def print_table(claims_by_id, results):
    print("=" * 100)
    print(f"{'claim':<9} {'fraud?':<6} {'baseline':<12} {'judge P-first':<15} {'judge D-first':<15} {'pre-cap':<8} {'tier':<7} {'gate':<14} {'baseline':<9} {'claimlens'}")
    for claim_id in RUN_IDS:
        raw, entry = claims_by_id[claim_id], results[claim_id]
        baseline, pipeline = entry["baseline"], entry["claimlens"]
        first, swapped = pipeline["transcript"]["judge_prosecutor_first"], pipeline["transcript"]["judge_defender_first"]
        print(f"{claim_id:<9} {str(raw['ground_truth']['is_fraud']):<6} {baseline['decision'] + ' ' + str(baseline['confidence']):<12} "
              f"{first['decision'] + ' ' + first['verbalized_confidence']:<15} {swapped['decision'] + ' ' + swapped['verbalized_confidence']:<15} "
              f"{pipeline['tier_before_cap']:<8} {pipeline['confidence_tier']:<7} {pipeline['gate']:<14} "
              f"{'right' if is_correct(baseline['decision'], raw) else 'WRONG':<9} {'right' if is_correct(pipeline['decision'], raw) else 'WRONG'}")

    def summary(name, decisions_and_high):
        right = sum(is_correct(decision, claims_by_id[c]) for c, decision, _ in decisions_and_high)
        high = [(c, decision) for c, decision, is_high in decisions_and_high if is_high]
        high_wrong = [c for c, decision in high if not is_correct(decision, claims_by_id[c])]
        print(f"  {name:<10} accuracy {right}/{len(decisions_and_high)}; high-confidence answers {len(high)}, "
              f"wrong {len(high_wrong)} {high_wrong}")

    print("DEV SET (13 claims; the set the system was tuned on)")
    summary("baseline", [(c, results[c]["baseline"]["decision"], results[c]["baseline"]["high_confidence"]) for c in RUN_IDS])
    summary("claimlens", [(c, results[c]["claimlens"]["decision"], results[c]["claimlens"]["confidence_tier"] == "HIGH") for c in RUN_IDS])
    auto = [c for c in RUN_IDS if results[c]["claimlens"]["gate"] == "auto_resolved"]
    print(f"  auto-resolved {len(auto)} {auto}; of which fraud: {[c for c in auto if claims_by_id[c]['ground_truth']['is_fraud']]}")
    print(f"  cap applied on: {[c for c in RUN_IDS if results[c]['claimlens']['cap_applied']]}")
    print(f"  orderings disagree on: {[c for c in RUN_IDS if not results[c]['claimlens']['orderings_agree']]}")


def print_comparison(claims_by_id, results, previous):
    compared = [c for c in RUN_IDS if c in previous]
    print("=" * 100)
    print(f"COMPARED WITH THE PREVIOUS STAGE 6 DEV RUN ({len(compared)} claims in both runs)")
    changed = [(c, previous[c]["claimlens"]["decision"], results[c]["claimlens"]["decision"]) for c in compared
               if previous[c]["claimlens"]["decision"] != results[c]["claimlens"]["decision"]]
    print(f"  ClaimLens decisions changed: {len(changed)} {changed}")
    was_high_wrong = [c for c in compared if previous[c]["claimlens"]["confidence_tier"] == "HIGH"
                      and not is_correct(previous[c]["claimlens"]["decision"], claims_by_id[c])]
    now = {c: (results[c]["claimlens"]["confidence_tier"], is_correct(results[c]["claimlens"]["decision"], claims_by_id[c])) for c in was_high_wrong}
    print(f"  previously HIGH and wrong: {was_high_wrong}; now (tier, correct): {now}")
    print(f"  HIGH-wrongs that are no longer HIGH: {[c for c, (tier, _) in now.items() if tier != 'HIGH']}")
    tiers = [(c, previous[c]["claimlens"]["confidence_tier"], results[c]["claimlens"]["confidence_tier"]) for c in compared]
    print(f"  tier changes: {[t for t in tiers if t[1] != t[2]]}")
    reused = [c for c in RUN_IDS if results[c]["baseline"].get("reused_from_previous_run")]
    print(f"  baseline results reused (identical input verified in the request log): {reused}")


def print_tokens(results):
    print("=" * 100)
    print("MEASURED TOKENS PER CLAIM (baseline shown only where it was run in this iteration)")
    print(f"{'claim':<9} {'baseline':>9} " + " ".join(f"{name:>20}" for name in STEPS) + f" {'pipeline':>9}")
    for claim_id in RUN_IDS:
        entry = results[claim_id]
        usage = entry["claimlens"]["usage"]
        baseline_tokens = entry["baseline"]["usage"]["total_tokens"]
        print(f"{claim_id:<9} {baseline_tokens:>9,} " + " ".join(f"{usage[name]['total_tokens']:>20,}" for name in STEPS)
              + f" {usage['total']['total_tokens']:>9,}")
    count = len(RUN_IDS)
    baseline_avg = sum(results[c]["baseline"]["usage"]["total_tokens"] for c in RUN_IDS) / count
    step_avg = {name: sum(results[c]["claimlens"]["usage"][name]["total_tokens"] for c in RUN_IDS) / count for name in STEPS}
    pipeline_avg = sum(step_avg.values())
    print(f"{'average':<9} {baseline_avg:>9,.0f} " + " ".join(f"{step_avg[name]:>20,.0f}" for name in STEPS) + f" {pipeline_avg:>9,.0f}")
    stage11 = STAGE11_CLAIMS * (baseline_avg + pipeline_avg)
    print(f"Stage 11 projection: {STAGE11_CLAIMS} x ({baseline_avg:,.0f} + {pipeline_avg:,.0f}) = {stage11:,.0f} tokens, "
          f"{STAGE11_CLAIMS * (1 + len(STEPS))} requests, at least {stage11 / TOKENS_PER_MINUTE_LIMIT:,.0f} minutes at "
          f"{TOKENS_PER_MINUTE_LIMIT:,} tokens/minute")


if __name__ == "__main__":
    main()
