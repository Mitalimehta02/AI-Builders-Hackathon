"""
Stage 4 check: run the naive baseline on a fixed, documented sample of 5 claims.

The sample was chosen by claim ID before anything was run, and is hardcoded so it is
reproducible (the notes are for humans only; the agent only ever sees sanitized input):
  CLM-0030  fraud (easy): policy 3-14 days old, big repair bill for a low-speed bump, no photos
  CLM-0019  fraud (hard): theft cover added days before the car was reported stolen
  CLM-0006  legitimate (easy): small sink leak, nothing unusual
  CLM-0027  legitimate (hard): car theft 11 days into a new policy, with innocent explanations
  CLM-0035  ambiguous: a "frozen pipe" in Miami in July

Quota safety: each result is saved to backend/data/stage4_baseline_sample.json as soon as it
arrives, and claims already in that file are skipped on re-runs (no requests spent). Delete
the file to run the sample again from scratch. Full raw requests/responses are in
backend/data/llm_logs/.

Run from the backend/ folder:
    .\\.venv\\Scripts\\python.exe -m app.synthetic.test_baseline
"""

import json
import sys
import textwrap
from pathlib import Path

from app.agents.evidence_agent import gather_evidence
from app.agents.naive_baseline_agent import BASELINE_HIGH_CONFIDENCE_THRESHOLD, run_naive_baseline
from app.agents.sanitize import sanitize_claim

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CLAIMS_PATH = DATA_DIR / "synthetic_claims.json"
RESULTS_PATH = DATA_DIR / "stage4_baseline_sample.json"

SAMPLE = [
    ("CLM-0030", "fraud (easy)"),
    ("CLM-0019", "fraud (hard)"),
    ("CLM-0006", "legitimate (easy)"),
    ("CLM-0027", "legitimate (hard, innocent look-alike flags)"),
    ("CLM-0035", "ambiguous"),
]


def main():
    # Windows consoles can't print some characters models use (e.g. non-breaking hyphens);
    # show a "?" for those instead of crashing. The saved JSON keeps the exact text.
    sys.stdout.reconfigure(errors="replace")

    with open(CLAIMS_PATH, encoding="utf-8") as f:
        claims_by_id = {c["claim_id"]: c for c in json.load(f)}
    results = json.loads(RESULTS_PATH.read_text(encoding="utf-8")) if RESULTS_PATH.exists() else {}

    requests_this_run = 0
    tokens_this_run = {"prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0}
    last_rate_limit = {}

    for claim_id, sample_note in SAMPLE:
        raw_claim = claims_by_id[claim_id]
        if claim_id in results:
            status = "saved result from an earlier run (no request spent now)"
        else:
            claim = sanitize_claim(raw_claim)
            result = run_naive_baseline(claim, gather_evidence(claim))
            results[claim_id] = result
            RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")  # checkpoint
            requests_this_run += result["attempts"]
            for key in tokens_this_run:
                tokens_this_run[key] += result["usage"][key]
            last_rate_limit = result["rate_limit"] or last_rate_limit
            status = f"live call ({result['attempts']} request(s), {result['usage']['total_tokens']} tokens)"

        result = results[claim_id]
        truth = raw_claim["ground_truth"]
        correct = (result["decision"] == "DENY") == truth["is_fraud"]
        print("=" * 78)
        print(f"{claim_id}  [{sample_note}]  - {status}")
        print(f"  decision:   {result['decision']}")
        print(f"  confidence: {result['confidence']}  "
              f"({'HIGH' if result['high_confidence'] else 'not high'}; threshold >= {BASELINE_HIGH_CONFIDENCE_THRESHOLD})")
        print("  reasoning:")
        print(textwrap.fill(result["reasoning"], width=76, initial_indent="    ", subsequent_indent="    "))
        print(f"  answer (reference only, never shown to the agent): is_fraud={truth['is_fraud']} -> "
              f"baseline was {'CORRECT' if correct else 'WRONG'}")

    all_results = [results[claim_id] for claim_id, _ in SAMPLE]
    print("=" * 78)
    print(f"Requests sent in THIS run: {requests_this_run} (tokens: {tokens_this_run})")
    print(f"Requests for the whole 5-claim sample: {sum(r['attempts'] for r in all_results)}, "
          f"tokens: {sum(r['usage']['total_tokens'] for r in all_results)}")
    if last_rate_limit:
        print(f"Groq rate-limit headers after the last call: {last_rate_limit}")


if __name__ == "__main__":
    main()
