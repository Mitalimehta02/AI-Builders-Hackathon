"""
Stage 11 batch run on the pre-registered evaluation sample (PROJECT_PLAN.md Part 5b).

Runs each of the 15 pre-registered held-out claims (backend/data/stage11_sample.json) through
  (a) the naive baseline - one model call - and
  (b) the full ClaimLens pipeline - Prosecutor, Defender, Judge, order-swapped Judge, tier, cap, gate -
with the same sanitized claim, the same evidence object, the same model and the same settings.

Built for a refill-limited daily token allowance:
- Every model result is saved as soon as it arrives (results_naive.json, results_claimlens.json).
  On restart, finished claims and finished debate steps are skipped, so nothing is paid for twice.
- When Groq refuses a call because the allowance is used up, the script sleeps until Groq says it
  has refilled and carries on. It does not exit, so it can run continuously until all 15 are done.
- Progress is printed as it goes and mirrored in stage11_batch_status.json, which the API reads to
  keep live claim submissions switched off while this batch runs.

Before running anything it checks the pre-registration: the claim IDs and the frozen claim data
must match the hashes recorded in stage11_sample.json, and a resumed run must use the same model
and settings it started with.

This script only runs the claims; the comparison table is computed once all 15 are complete.

Run from the backend/ folder (safe to stop and start again):
    .\\.venv\\Scripts\\python.exe -u -m app.synthetic.run_full_batch
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app import batch_status
from app.agents.calibration import STEPS, run_claimlens
from app.agents.evidence_agent import gather_evidence
from app.agents.llm_client import GENERATION_SETTINGS, MODEL, LLMError
from app.agents.naive_baseline_agent import run_naive_baseline
from app.agents.sanitize import sanitize_claim
from app.synthetic.stage11_sample import SAMPLE_PATH, data_hash, ids_hash

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CLAIMS_PATH = DATA_DIR / "synthetic_claims.json"
NAIVE_PATH = DATA_DIR / "results_naive.json"
CLAIMLENS_PATH = DATA_DIR / "results_claimlens.json"

MAX_FAILURES_PER_CLAIM = 3        # failures other than rate limits (e.g. unusable replies) before giving up on a claim
FAILURE_PAUSE_SECONDS = 30
REFILL_MARGIN_SECONDS = 30        # extra wait on top of Groq's retry-after
DEFAULT_RATE_LIMIT_WAIT = 5 * 60  # if Groq gives no retry-after
FINISHED = ("complete", "failed")


def log(message):
    print(f"[{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC] {message}", flush=True)


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def save_json(path, data):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def run_settings():
    return {"model": MODEL, "settings": GENERATION_SETTINGS}


def new_results_file(sample):
    return {
        "meta": {**run_settings(), "sample_claim_ids_sha256": sample["claim_ids_sha256"],
                 "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
        "claims": {},
    }


def verify_preregistration(sample, all_claims, results_files):
    if ids_hash(sample["claim_ids"]) != sample["claim_ids_sha256"]:
        sys.exit("STOP: the sample's claim IDs no longer match the pre-registered hash")
    if data_hash(all_claims) != sample["claims_data_sha256"]:
        sys.exit("STOP: the claim data has changed since the sample was pre-registered")
    for results in results_files:
        meta = results["meta"]
        if meta["sample_claim_ids_sha256"] != sample["claim_ids_sha256"] or {k: meta[k] for k in ("model", "settings")} != run_settings():
            sys.exit("STOP: existing results were produced with a different sample, model or settings; they must not be mixed")


def tokens_and_requests(naive, claimlens):
    tokens = requests = 0
    for entry in naive["claims"].values():
        if "result" in entry:
            tokens += entry["result"]["usage"]["total_tokens"]
            requests += entry["result"]["attempts"]
    for entry in claimlens["claims"].values():
        for step in (entry.get("steps") or {}).values():
            tokens += step["usage"]["total_tokens"]
            requests += step["attempts"]
    return tokens, requests


class Batch:
    def __init__(self, sample, claims_by_id, naive, claimlens):
        self.sample, self.claims_by_id = sample, claims_by_id
        self.naive, self.claimlens = naive, claimlens
        self.total = len(sample["claim_ids"])

    def is_finished(self, claim_id):
        return (self.naive["claims"].get(claim_id, {}).get("status") in FINISHED
                and self.claimlens["claims"].get(claim_id, {}).get("status") in FINISHED)

    def complete_count(self):
        return sum(self.is_finished(claim_id) for claim_id in self.sample["claim_ids"])

    def save(self):
        save_json(NAIVE_PATH, self.naive)
        save_json(CLAIMLENS_PATH, self.claimlens)

    def heartbeat(self, **fields):
        tokens, requests = tokens_and_requests(self.naive, self.claimlens)
        batch_status.write_status(running=True, pid=os.getpid(), claims_total=self.total,
                                  claims_finished=self.complete_count(), tokens_used=tokens, requests_accepted=requests, **fields)

    def run(self):
        log(f"Stage 11 batch: {self.total} pre-registered claims; model {MODEL}; settings {GENERATION_SETTINGS}")
        log(f"already finished: {self.complete_count()} of {self.total}")
        while self.complete_count() < self.total:
            for number, claim_id in enumerate(self.sample["claim_ids"], start=1):
                if self.is_finished(claim_id):
                    continue
                try:
                    self.run_claim(number, claim_id)
                except LLMError as error:
                    if error.rate_limited:
                        self.wait_for_refill(error)
                        break  # start the pass again, so this claim resumes first
                    self.record_failure(number, claim_id, error)
                except ValueError as error:  # a reply that was valid JSON but not a usable argument or ruling
                    self.record_failure(number, claim_id, error)
        tokens, requests = tokens_and_requests(self.naive, self.claimlens)
        failed = [c for c in self.sample["claim_ids"]
                  if "failed" in (self.naive["claims"][c]["status"], self.claimlens["claims"][c]["status"])]
        log(f"BATCH COMPLETE: {self.total} claims, {requests} accepted requests, {tokens:,} tokens; failed claims: {failed or 'none'}")

    def run_claim(self, number, claim_id):
        claim = sanitize_claim(self.claims_by_id[claim_id])
        naive_entry = self.naive["claims"].setdefault(claim_id, {"status": "in_progress"})
        lens_entry = self.claimlens["claims"].setdefault(claim_id, {"status": "in_progress", "steps": {}})
        prefix = f"claim {number} of {self.total} ({claim_id})"

        if "evidence" not in lens_entry:
            self.heartbeat(current_claim=claim_id, current_step="gathering_evidence", waiting_until=None)
            lens_entry["evidence"] = gather_evidence(claim)
            naive_entry["evidence"] = lens_entry["evidence"]  # both systems get the identical evidence object
            self.save()
        evidence = lens_entry["evidence"]

        if naive_entry["status"] not in FINISHED:
            self.heartbeat(current_claim=claim_id, current_step="baseline", waiting_until=None)
            result = run_naive_baseline(claim, evidence)
            naive_entry.update(status="complete", result=result)
            self.save()
            log(f"{prefix}: baseline {result['decision']} ({result['confidence']}), {result['usage']['total_tokens']:,} tokens")

        if lens_entry["status"] not in FINISHED:
            def checkpoint(steps):
                lens_entry["steps"] = steps
                self.save()
                latest = list(steps)[-1]
                self.heartbeat(current_claim=claim_id, current_step=latest, waiting_until=None)
                log(f"{prefix}: {latest} done, {steps[latest]['usage']['total_tokens']:,} tokens")

            self.heartbeat(current_claim=claim_id, current_step="claimlens", waiting_until=None)
            result = run_claimlens(claim, evidence, completed_steps=lens_entry["steps"], on_step=checkpoint)
            lens_entry.update(status="complete", result=result)
            self.save()
            log(f"{prefix}: ClaimLens {result['decision']}, tier {result['confidence_tier']}"
                f"{' (capped from HIGH)' if result['cap_applied'] else ''}, {result['gate']}, "
                f"{result['usage']['total']['total_tokens']:,} tokens")

        tokens, requests = tokens_and_requests(self.naive, self.claimlens)
        log(f"PROGRESS: {self.complete_count()} of {self.total} claims finished; {requests} accepted requests, {tokens:,} tokens so far")
        self.heartbeat(current_claim=None, current_step=None, waiting_until=None)

    def wait_for_refill(self, error):
        seconds = (error.retry_after_seconds or DEFAULT_RATE_LIMIT_WAIT) + REFILL_MARGIN_SECONDS
        resume_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)
        log(f"token allowance used up; waiting {seconds / 60:.1f} minutes, resuming at {resume_at:%H:%M:%S} UTC ({str(error)[:160]})")
        while datetime.now(timezone.utc) < resume_at:
            self.heartbeat(waiting_until=resume_at.isoformat(timespec="seconds"))
            time.sleep(min(60, max(1, (resume_at - datetime.now(timezone.utc)).total_seconds())))
        self.heartbeat(waiting_until=None)

    def record_failure(self, number, claim_id, error):
        lens_entry = self.claimlens["claims"].setdefault(claim_id, {"status": "in_progress", "steps": {}})
        failures = lens_entry.setdefault("failures", [])
        failures.append({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "error": f"{error.__class__.__name__}: {error}"})
        log(f"claim {number} of {self.total} ({claim_id}): failure {len(failures)} of {MAX_FAILURES_PER_CLAIM}: {str(error)[:200]}")
        if len(failures) >= MAX_FAILURES_PER_CLAIM:
            lens_entry["status"] = "failed" if lens_entry["status"] != "complete" else "complete"
            naive_entry = self.naive["claims"].setdefault(claim_id, {"status": "in_progress"})
            if naive_entry["status"] != "complete":
                naive_entry["status"] = "failed"
            log(f"claim {number} of {self.total} ({claim_id}): giving up after {MAX_FAILURES_PER_CLAIM} failures; it will be reported as failed")
        self.save()
        time.sleep(FAILURE_PAUSE_SECONDS)


def main():
    sample = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    all_claims = json.loads(CLAIMS_PATH.read_text(encoding="utf-8"))
    naive = load_json(NAIVE_PATH) or new_results_file(sample)
    claimlens = load_json(CLAIMLENS_PATH) or new_results_file(sample)
    verify_preregistration(sample, all_claims, (naive, claimlens))

    status = batch_status.read_status()
    if batch_status.batch_is_running(status) and status.get("pid") != os.getpid():
        sys.exit(f"STOP: another batch (pid {status.get('pid')}) reported progress at {status.get('updated_at')}")

    claims_by_id = {c["claim_id"]: c for c in all_claims if c["claim_id"] in sample["claim_ids"]}  # the 15 only
    batch = Batch(sample, claims_by_id, naive, claimlens)
    batch.save()
    try:
        batch.run()
    finally:
        batch_status.write_status(running=False, pid=os.getpid(), current_claim=None, current_step=None, waiting_until=None,
                                  claims_finished=batch.complete_count())


if __name__ == "__main__":
    main()
