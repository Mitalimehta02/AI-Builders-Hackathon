"""
SQLite storage for submitted claims and their results (Stage 7).

One table, `claims`. Each row is one submission: the sanitized claim, its processing status, the
evidence, the debate steps saved after every model call, the final result, and any error. The
structured parts are stored as JSON text, exactly as the agents produce them.

The database file is backend/data/claimlens.db (gitignored). A fresh connection is opened for
each operation, which keeps it safe when the background worker and web requests use the
database at the same time.
"""

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from app.models import FAILED, FINISHED_STATUSES, PENDING

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "claimlens.db"

JSON_COLUMNS = ("claim", "evidence", "steps", "result")
UPDATABLE_COLUMNS = ("status", "evidence", "steps", "result", "error")

SCHEMA = """
CREATE TABLE IF NOT EXISTS claims (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id    TEXT NOT NULL,
    status      TEXT NOT NULL,
    claim       TEXT NOT NULL,
    evidence    TEXT,
    steps       TEXT,
    result      TEXT,
    error       TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
)
"""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    """Create the table if needed. Claims left unfinished by a server restart are marked failed,
    because the work that was processing them no longer exists."""
    with closing(_connect()) as connection, connection:
        connection.execute(SCHEMA)
        connection.execute(
            "UPDATE claims SET status = ?, error = ?, updated_at = ? WHERE status NOT IN (?, ?)",
            (FAILED, "processing was interrupted because the server stopped", _now(), *FINISHED_STATUSES),
        )


def create_claim(claim):
    """Store a new sanitized claim with status 'pending' and return its record id."""
    now = _now()
    with closing(_connect()) as connection, connection:
        cursor = connection.execute(
            "INSERT INTO claims (claim_id, status, claim, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (claim["claim_id"], PENDING, json.dumps(claim), now, now),
        )
        return cursor.lastrowid


def update_claim(record_id, **fields):
    """Update any of: status, evidence, steps, result, error."""
    unknown = set(fields) - set(UPDATABLE_COLUMNS)
    if unknown:
        raise ValueError(f"cannot update columns {sorted(unknown)}")
    values = {name: json.dumps(value) if name in JSON_COLUMNS else value for name, value in fields.items()}
    assignments = ", ".join(f"{name} = ?" for name in values)  # names come from UPDATABLE_COLUMNS only
    with closing(_connect()) as connection, connection:
        connection.execute(f"UPDATE claims SET {assignments}, updated_at = ? WHERE id = ?", (*values.values(), _now(), record_id))


def get_claim(record_id):
    """The stored record as a dict (JSON columns decoded), or None if it doesn't exist."""
    with closing(_connect()) as connection:
        row = connection.execute("SELECT * FROM claims WHERE id = ?", (record_id,)).fetchone()
    return _to_dict(row) if row else None


def list_claims(status=None):
    """All records, newest first, optionally only those with the given status."""
    query, parameters = "SELECT * FROM claims", ()
    if status is not None:
        query, parameters = query + " WHERE status = ?", (status,)
    with closing(_connect()) as connection:
        rows = connection.execute(query + " ORDER BY id DESC", parameters).fetchall()
    return [_to_dict(row) for row in rows]


def _to_dict(row):
    record = dict(row)
    for name in JSON_COLUMNS:
        record[name] = json.loads(record[name]) if record[name] is not None else None
    return record
