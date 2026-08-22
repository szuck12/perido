# database.py
# SQLite persistence layer: data directory, schema, sessions, and cycles.

from __future__ import annotations

import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time TEXT NOT NULL,
    end_time TEXT,
    planned_minutes REAL NOT NULL,
    actual_seconds REAL,
    status TEXT NOT NULL DEFAULT 'active',
    paused_at TEXT,
    pause_seconds REAL NOT NULL DEFAULT 0,
    extension_minutes REAL NOT NULL DEFAULT 0,
    kind TEXT NOT NULL DEFAULT 'focus',
    cycle_id TEXT,
    cycle_name TEXT,
    cycle_position INTEGER
);
CREATE TABLE IF NOT EXISTS cycles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    plan TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL
);
"""


def data_dir() -> Path:
    """Return the application data directory, creating it if needed.

    Respects the PERIDO_HOME environment variable (used by tests);
    otherwise picks an OS-appropriate per-user location.
    """
    root = os.environ.get("PERIDO_HOME")
    if root:
        path = Path(root)
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "perido"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        path = base / "perido"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        path = base / "perido"
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    """Return the path to the SQLite database file."""
    return data_dir() / "perido.db"


def connect() -> sqlite3.Connection:
    """Open a connection with the schema ensured and dict rows."""
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def iso(dt: datetime) -> str:
    """Format an aware datetime as an ISO-8601 UTC string."""
    return dt.isoformat()


def parse_ts(value: str) -> datetime:
    """Parse a stored ISO-8601 timestamp back into a datetime."""
    return datetime.fromisoformat(value)


# ---------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------


def create_session(
    conn: sqlite3.Connection,
    *,
    kind: str,
    minutes: float,
    start: datetime,
    cycle_id: str | None = None,
    cycle_name: str | None = None,
    cycle_position: int | None = None,
) -> dict[str, Any]:
    """Insert a new active session and return it.

    Note:
        `end_time` holds the scheduled end while the session is active.
        When a session is stopped or skipped early it is overwritten
        with the actual finish moment; natural completion leaves the
        scheduled value in place.
    """
    cur = conn.execute(
        "INSERT INTO sessions (start_time, end_time, planned_minutes, status,"
        " kind, cycle_id, cycle_name, cycle_position)"
        " VALUES (?, ?, ?, 'active', ?, ?, ?, ?)",
        (
            iso(start),
            iso(start + timedelta(minutes=minutes)),
            minutes,
            kind,
            cycle_id,
            cycle_name,
            cycle_position,
        ),
    )
    conn.commit()
    return get_session(conn, cur.lastrowid)  # type: ignore[return-value]


def get_session(conn: sqlite3.Connection, session_id: int) -> dict[str, Any] | None:
    """Return one session by id, or None."""
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return dict(row) if row else None


def get_active_session(conn: sqlite3.Connection) -> dict[str, Any] | None:
    """Return the most recent active session, or None."""
    row = conn.execute(
        "SELECT * FROM sessions WHERE status = 'active'"
        " ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return dict(row) if row else None


def last_finished_session(conn: sqlite3.Connection) -> dict[str, Any] | None:
    """Return the most recently created non-active session, or None."""
    row = conn.execute(
        "SELECT * FROM sessions WHERE status != 'active'"
        " ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return dict(row) if row else None


def update_session(conn: sqlite3.Connection, session_id: int, **fields: Any) -> None:
    """Set columns on a session and commit."""
    assignments = ", ".join(f"{key} = ?" for key in fields)
    conn.execute(
        f"UPDATE sessions SET {assignments} WHERE id = ?",  # noqa: S608
        (*fields.values(), session_id),
    )
    conn.commit()


def query_sessions(
    conn: sqlite3.Connection,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    kinds: tuple[str, ...] | None = None,
    statuses: tuple[str, ...] | None = None,
    limit: int | None = None,
    order: str = "DESC",
) -> list[dict[str, Any]]:
    """Query finalized-able sessions with optional filters.

    Args:
        since: Only sessions starting at or after this instant.
        until: Only sessions starting before this instant.
        kinds: Restrict to these session kinds ('focus', 'break').
        statuses: Restrict to these statuses.
        limit: Maximum number of rows to return.
        order: 'ASC' or 'DESC' ordering on start time.

    Returns:
        Session dicts ordered by start time.
    """
    clauses: list[str] = []
    params: list[Any] = []
    if since is not None:
        clauses.append("start_time >= ?")
        params.append(iso(since))
    if until is not None:
        clauses.append("start_time < ?")
        params.append(iso(until))
    if kinds is not None:
        clauses.append(f"kind IN ({', '.join('?' * len(kinds))})")
        params.extend(kinds)
    if statuses is not None:
        clauses.append(f"status IN ({', '.join('?' * len(statuses))})")
        params.extend(statuses)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM sessions{where} ORDER BY start_time {order}"  # noqa: S608
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------
# Cycles
# ---------------------------------------------------------------------


def create_cycle(
    conn: sqlite3.Connection,
    name: str,
    plan: list[dict[str, Any]],
    position: int,
    created_at: datetime,
) -> str:
    """Insert a new active cycle and return its generated id."""
    cycle_id = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO cycles (id, name, plan, position, status, created_at)"
        " VALUES (?, ?, ?, ?, 'active', ?)",
        (cycle_id, name, json_dumps(plan), position, iso(created_at)),
    )
    conn.commit()
    return cycle_id


def get_cycle(conn: sqlite3.Connection, cycle_id: str | None) -> dict[str, Any] | None:
    """Return one cycle by id, or None."""
    if cycle_id is None:
        return None
    row = conn.execute("SELECT * FROM cycles WHERE id = ?", (cycle_id,)).fetchone()
    return dict(row) if row else None


def update_cycle(conn: sqlite3.Connection, cycle_id: str, **fields: Any) -> None:
    """Set columns on a cycle and commit."""
    assignments = ", ".join(f"{key} = ?" for key in fields)
    conn.execute(
        f"UPDATE cycles SET {assignments} WHERE id = ?",  # noqa: S608
        (*fields.values(), cycle_id),
    )
    conn.commit()


def count_cycles(conn: sqlite3.Connection, status: str) -> int:
    """Count cycles with the given status."""
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM cycles WHERE status = ?", (status,)
    ).fetchone()
    return int(row["n"])


def json_dumps(value: Any) -> str:
    """Serialize plan structures to compact JSON text."""
    return json.dumps(value, separators=(",", ":"))


def json_loads(value: str) -> Any:
    """Deserialize stored JSON text."""
    return json.loads(value)
