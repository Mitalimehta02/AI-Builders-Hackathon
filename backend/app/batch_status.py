"""
Shared status of the Stage 11 batch run (backend/data/stage11_batch_status.json, gitignored).

The batch script writes it on every step and at least once a minute while waiting for the daily
token allowance to refill. The API reads it: while a batch is running, live claim submissions are
switched off by default so they cannot use up the allowance the batch depends on.

If the batch process dies without saying so, its status goes stale and stops counting as running
after STALE_AFTER_SECONDS.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

STATUS_PATH = Path(__file__).resolve().parents[1] / "data" / "stage11_batch_status.json"
STALE_AFTER_SECONDS = 15 * 60  # the batch writes at least once a minute; model calls take at most a few minutes


def read_status():
    try:
        return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write_status(**fields):
    """Merge fields into the status file (written atomically) and stamp the update time."""
    status = {**read_status(), **fields, "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATUS_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(status, indent=2), encoding="utf-8")
    os.replace(temporary, STATUS_PATH)
    return status


def batch_is_running(status=None):
    """True if the status says running and has been updated recently."""
    status = read_status() if status is None else status
    if not status.get("running") or not status.get("updated_at"):
        return False
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(status["updated_at"])).total_seconds()
    return age < STALE_AFTER_SECONDS


# Live submissions are refused while the batch runs, unless this environment variable is set to "1".
LIVE_OVERRIDE_ENV = "CLAIMLENS_ALLOW_LIVE_DURING_BATCH"
# Pipeline only (a live submission doesn't run the baseline): Prosecutor + Defender + 2 Judge calls.
ESTIMATED_TOKENS_PER_LIVE_CLAIM = 17_000


def live_submission_state():
    """Whether POST /claims is allowed right now, and why not. Read by the API and the intake page."""
    status = read_status()
    running = batch_is_running(status)
    override = os.environ.get(LIVE_OVERRIDE_ENV) == "1"
    reason = None
    if running:
        reason = ("The Stage 11 evaluation batch is running. It depends on the same limited daily model "
                  "allowance, so live submissions are switched off until it finishes.")
    return {
        "live_submission_enabled": (not running) or override,
        "batch_running": running,
        "override_active": running and override,
        "reason": reason,
        "estimated_tokens_per_live_claim": ESTIMATED_TOKENS_PER_LIVE_CLAIM,
        "batch": {
            key: status.get(key)
            for key in ("claims_finished", "claims_total", "current_claim", "waiting_until", "updated_at")
        } if status else None,
    }
