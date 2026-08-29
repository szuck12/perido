# database.py
# SQLite persistence layer: data directory, schema, sessions, and cycles.

from __future__ import annotations

import json
import math
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import PeridoError

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
        base = Path(
            os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")
        )
        path = base / "perido"
    else:
        base = Path(
            os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
        )
        path = base / "perido"
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    """Return the path to the SQLite database file."""
    return data_dir() / "perido.db"


def connect() -> sqlite3.Connection:
    """Open a connection with the schema ensured and dict rows.

    If the database file is corrupt, it is moved aside and recreated
    so a hostile or damaged state file cannot crash the tool.
    """
    try:
        conn = sqlite3.connect(db_path())
        conn.row_factory = sqlite3.Row
        conn.executescript(_SCHEMA)
        return conn
    except sqlite3.DatabaseError:
        _recover_corrupt_db()
        conn = sqlite3.connect(db_path())
        conn.row_factory = sqlite3.Row
        conn.executescript(_SCHEMA)
        return conn


def _recover_corrupt_db() -> None:
    """Move a corrupt database aside and log a one-line warning."""
    path = db_path()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"perido.db.corrupt-{stamp}")
    try:
        for i in range(100):
            candidate = path.with_name(
                f"perido.db.corrupt-{stamp}{'-' + str(i) if i else ''}"
            )
            if not candidate.exists():
                backup = candidate
                break
        path.rename(backup)
    except OSError:
        try:
            path.unlink()
        except OSError:
            pass
    print(
        "Warning: perido.db was corrupt and has been reset. "
        "The damaged file was kept as backup.",
        file=sys.stderr,
    )


def iso(dt: datetime) -> str:
    """Format an aware datetime as an ISO-8601 UTC string.

    Args:
        dt: The aware datetime to store.

    Returns:
        A string suitable for the timestamp columns.
    """
    return dt.isoformat()


def parse_ts(value: str) -> datetime:
    """Parse a stored ISO-8601 timestamp back into a datetime.

    Args:
        value: A timestamp produced by `iso`.

    Returns:
        The parsed aware datetime.

    Raises:
        PeridoError: If the value is not a valid ISO-8601 timestamp,
            so a hand-edited database fails cleanly instead of
            crashing callers with a traceback.
    """
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise PeridoError(
            "A recorded timestamp is unreadable; the database may be"
            " corrupt."
        ) from None


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

    Args:
        conn: An open database connection.
        kind: "focus" or "break".
        minutes: Planned length in minutes.
        start: The session's start instant.
        cycle_id: Id of the owning cycle, if a cycle phase.
        cycle_name: Snapshot of the cycle's name, if a cycle phase.
        cycle_position: Index of this step in the cycle plan.

    Returns:
        The inserted session row.

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


def get_session(
    conn: sqlite3.Connection, session_id: int
) -> dict[str, Any] | None:
    """Return one session by id, or None.

    Args:
        conn: An open database connection.
        session_id: The session's row id.

    Returns:
        The session dict, or None if it does not exist.
    """
    row = (
        conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        .fetchone()
    )
    return dict(row) if row else None


def get_active_session(conn: sqlite3.Connection) -> dict[str, Any] | None:
    """Return the most recent active session, or None.

    Args:
        conn: An open database connection.

    Returns:
        The newest active session dict, or None.
    """
    row = conn.execute(
        "SELECT * FROM sessions WHERE status = 'active'"
        " ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return dict(row) if row else None


def last_finished_session(conn: sqlite3.Connection) -> dict[str, Any] | None:
    """Return the most recently created non-active session, or None.

    Args:
        conn: An open database connection.

    Returns:
        The newest finished session dict, or None.
    """
    row = conn.execute(
        "SELECT * FROM sessions WHERE status != 'active'"
        " ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return dict(row) if row else None


def update_session(
    conn: sqlite3.Connection, session_id: int, **fields: Any
) -> None:
    """Set columns on a session and commit.

    Args:
        conn: An open database connection.
        session_id: The session's row id.
        fields: Column names and values to update.
    """
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
    if order not in ("ASC", "DESC"):
        raise ValueError(f"unsupported order: {order!r}")
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        f"SELECT * FROM sessions{where} ORDER BY start_time {order}"  # noqa: S608
    )
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
    """Insert a new active cycle and return its generated id.

    Args:
        conn: An open database connection.
        name: The cycle's preset name.
        plan: The alternating focus/break step list.
        position: The index of the currently running phase.
        created_at: When the cycle started.

    Returns:
        The generated cycle id.
    """
    cycle_id = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO cycles (id, name, plan, position, status, created_at)"
        " VALUES (?, ?, ?, ?, 'active', ?)",
        (cycle_id, name, json_dumps(plan), position, iso(created_at)),
    )
    conn.commit()
    return cycle_id


def get_cycle(
    conn: sqlite3.Connection, cycle_id: str | None
) -> dict[str, Any] | None:
    """Return one cycle by id, or None.

    Args:
        conn: An open database connection.
        cycle_id: The cycle's id, possibly None.

    Returns:
        The cycle dict, or None if the id is missing or unknown.
    """
    if cycle_id is None:
        return None
    row = (
        conn.execute("SELECT * FROM cycles WHERE id = ?", (cycle_id,))
        .fetchone()
    )
    return dict(row) if row else None


def update_cycle(
    conn: sqlite3.Connection, cycle_id: str, **fields: Any
) -> None:
    """Set columns on a cycle and commit.

    Args:
        conn: An open database connection.
        cycle_id: The cycle's id.
        fields: Column names and values to update.
    """
    assignments = ", ".join(f"{key} = ?" for key in fields)
    conn.execute(
        f"UPDATE cycles SET {assignments} WHERE id = ?",  # noqa: S608
        (*fields.values(), cycle_id),
    )
    conn.commit()


def count_cycles(conn: sqlite3.Connection, status: str) -> int:
    """Count cycles with the given status.

    Args:
        conn: An open database connection.
        status: The cycle status to count.

    Returns:
        The number of matching cycles.
    """
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM cycles WHERE status = ?", (status,)
    ).fetchone()
    return int(row["n"])


def json_dumps(value: Any) -> str:
    """Serialize plan structures to compact JSON text.

    Args:
        value: The structure to serialize.

    Returns:
        A compact JSON string.
    """
    return json.dumps(value, separators=(",", ":"))


def json_loads(value: str) -> Any:
    """Deserialize a stored cycle plan, validating its shape.

    Args:
        value: A JSON string from the `plan` column.

    Returns:
        The list of step dicts in the plan.

    Raises:
        PeridoError: If the value is not a JSON list of step dicts
            with numeric minute values, so a hand-edited database
            fails cleanly instead of crashing callers with a
            traceback.
    """
    try:
        steps = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        raise PeridoError(
            "A stored cycle plan is unreadable; the database may be"
            " corrupt."
        ) from None
    if not _is_plan(steps):
        raise PeridoError(
            "A stored cycle plan has an unexpected shape; the database"
            " may be corrupt."
        )
    return steps


def _is_plan(value: Any) -> bool:
    """True if value is a list of valid focus/break step dicts."""
    return isinstance(value, list) and all(
        isinstance(step, dict)
        and "kind" in step
        and "minutes" in step
        and isinstance(step["minutes"], (int, float))
        and not isinstance(step["minutes"], bool)
        and math.isfinite(step["minutes"])
        for step in value
    )
