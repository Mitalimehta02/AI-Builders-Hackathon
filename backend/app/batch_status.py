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
