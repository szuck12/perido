# timer.py
# Session lifecycle state machine: start, pause, resume, extend,
# shorten, stop, skip, and lazy finalization of expired sessions.

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from . import PeridoError, database
from .config import load as load_config


def now() -> datetime:
    """Return the current UTC time.

    Note:
        All other modules read time through this function so that the
        test suite can substitute a fake clock.
    """
    return datetime.now(timezone.utc)


def _parse(value: str) -> datetime:
    return database.parse_ts(value)


def _mmss(seconds: float) -> str:
    total = max(0, round(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


def busy_error(session: dict[str, Any]) -> str:
    """Build the error message shown when a session is already active."""
    label = "break" if session["kind"] == "break" else "Pomodoro"
    remaining = remaining_seconds(session)
    return (
        f"A {label} session is already active.\n"
        f"Time remaining: {_mmss(remaining)}\n"
        "Stop it first:\n"
        "  perido stop"
    )


# ---------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------


def active_session() -> dict[str, Any] | None:
    """Return the active session, or None."""
    conn = database.connect()
    try:
        return database.get_active_session(conn)
    finally:
        conn.close()


def remaining_seconds(
    session: dict[str, Any], at: datetime | None = None
) -> float:
    """Seconds left on a session's scheduled window (never negative).

    Args:
        session: The active or stored session row.
        at: Instant to measure from; defaults to the current clock.

    Returns:
        Remaining scheduled seconds, floored at zero.
    """
    moment = at or now()
    end = _parse(session["end_time"])
    return max(0.0, (end - moment).total_seconds())


def focused_seconds(
    session: dict[str, Any], at: datetime | None = None
) -> float:
    """Focus seconds accumulated so far, excluding paused time.

    While paused, time is only counted up to the pause instant.

    Args:
        session: The active or stored session row.
        at: Instant to measure from; defaults to the current clock.

    Returns:
        Accumulated focus seconds, never negative.
    """
    moment = at or now()
    if session["paused_at"]:
        moment = min(moment, _parse(session["paused_at"]))
    start = _parse(session["start_time"])
    end = min(moment, _parse(session["end_time"]))
    elapsed = (end - start).total_seconds()
    return max(0.0, elapsed - session["pause_seconds"])


def planned_seconds(session: dict[str, Any]) -> float:
    """Total planned seconds including any extensions.

    Args:
        session: The session row to measure.

    Returns:
        Planned window length in seconds.
    """
    return (session["planned_minutes"] + session["extension_minutes"]) * 60


def progress_fraction(
    session: dict[str, Any], at: datetime | None = None
) -> float:
    """Focused seconds as a fraction of the planned total, capped at 1.

    Args:
        session: The active or stored session row.
        at: Instant to measure from; defaults to the current clock.

    Returns:
        A fraction in [0, 1] describing how far through the session
        the user is.
    """
    planned = planned_seconds(session)
    if planned <= 0:
        return 0.0
    return min(1.0, focused_seconds(session, at) / planned)


# ---------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------


def start(
    minutes: float,
    kind: str = "focus",
    cycle_id: str | None = None,
    cycle_name: str | None = None,
    cycle_position: int | None = None,
) -> dict[str, Any]:
    """Start a new session of the given kind and duration in minutes.

    Any expired-but-unfinalized session is completed first, so a stale
    session never blocks a fresh start.

    Args:
        minutes: Planned length in minutes; must be positive.
        kind: Either "focus" or "break".
        cycle_id: Id of the owning cycle, if this is a cycle phase.
        cycle_name: Snapshot of the cycle's name, if a cycle phase.
        cycle_position: Index of this step in the cycle plan.

    Returns:
        The newly created active session row.

    Raises:
        PeridoError: If another live session is already active.
    """
    finalize_expired()
    conn = database.connect()
    try:
        existing = database.get_active_session(conn)
        if existing:
            raise PeridoError(busy_error(existing))
        load_config()  # touch config so a broken file surfaces early
        return database.create_session(
            conn,
            kind=kind,
            minutes=minutes,
            start=now(),
            cycle_id=cycle_id,
            cycle_name=cycle_name,
            cycle_position=cycle_position,
        )
    finally:
        conn.close()


def pause() -> dict[str, Any]:
    """Pause the active session; remaining time freezes.

    Raises:
        PeridoError: If nothing is active or it is already paused.
    """
    finalize_expired()
    conn = database.connect()
    try:
        session = database.get_active_session(conn)
        if not session:
            raise PeridoError("No active Pomodoro session to pause.")
        if session["paused_at"]:
            raise PeridoError("Timer is already paused.")
        database.update_session(conn, session["id"], paused_at=iso_now())
        return database.get_session(conn, session["id"])
    finally:
        conn.close()


def resume() -> dict[str, Any]:
    """Resume a paused session by shifting its end forward by the pause.

    Raises:
        PeridoError: If there is no paused session.
    """
    finalize_expired()
    conn = database.connect()
    try:
        session = database.get_active_session(conn)
        if not session or not session["paused_at"]:
            raise PeridoError("No paused Pomodoro session to resume.")
        delta = now() - _parse(session["paused_at"])
        new_end = _parse(session["end_time"]) + delta
        database.update_session(
            conn,
            session["id"],
            end_time=database.iso(new_end),
            pause_seconds=session["pause_seconds"] + delta.total_seconds(),
            paused_at=None,
        )
        return database.get_session(conn, session["id"])
    finally:
        conn.close()


def extend(minutes: float) -> dict[str, Any]:
    """Extend the active session by a positive number of minutes.

    Args:
        minutes: Number of minutes to push the end time later.

    Returns:
        The updated active session row.

    Raises:
        PeridoError: If nothing is active or minutes is not positive.
    """
    if minutes <= 0:
        raise PeridoError("Extension must be a positive number of minutes.")
    finalize_expired()
    conn = database.connect()
    try:
        session = database.get_active_session(conn)
        if not session:
            raise PeridoError(
                "No active Pomodoro session to extend.\n"
                "Start one with:\n"
                "  perido start"
            )
        new_end = _parse(session["end_time"]) + timedelta(minutes=minutes)
        database.update_session(
            conn,
            session["id"],
            end_time=database.iso(new_end),
            extension_minutes=session["extension_minutes"] + minutes,
        )
        return database.get_session(conn, session["id"])
    finally:
        conn.close()


def shorten(minutes: float) -> dict[str, Any]:
    """Shorten the active session by a positive number of minutes.

    The trim is recorded as negative extension time, so every derived
    total (planned + extension) stays consistent across history and
    statistics without schema changes.

    Args:
        minutes: Number of minutes to pull the end time earlier.

    Returns:
        The updated active session row.

    Raises:
        PeridoError: If nothing is active, minutes is not positive, or
            the session has less remaining time than requested.
    """
    if minutes <= 0:
        raise PeridoError("Shortening must be a positive number of minutes.")
    finalize_expired()
    conn = database.connect()
    try:
        session = database.get_active_session(conn)
        if not session:
            raise PeridoError(
                "No active Pomodoro session to shorten.\n"
                "Start one with:\n"
                "  perido start"
            )
        remaining = remaining_seconds(session)
        if minutes * 60 >= remaining:
            label = "break" if session["kind"] == "break" else "session"
            raise PeridoError(
                f"Cannot shorten by {minutes:g} minutes —"
                f" the {label} only has {_mmss(remaining)} remaining."
            )
        new_end = _parse(session["end_time"]) - timedelta(minutes=minutes)
        database.update_session(
            conn,
            session["id"],
            end_time=database.iso(new_end),
            extension_minutes=session["extension_minutes"] - minutes,
        )
        return database.get_session(conn, session["id"])
    finally:
        conn.close()


def stop() -> dict[str, Any]:
    """Stop the active session early, recording it as interrupted.

    Focus time accumulated before stopping is preserved. Stopping a
    cycle session abandons the rest of the cycle.

    Raises:
        PeridoError: If nothing is active.
    """
    return _finalize_active("interrupted")


def skip() -> dict[str, Any]:
    """Abandon the active session with no focus time recorded.

    Raises:
        PeridoError: If nothing is active.
    """
    return _finalize_active("skipped", zero_credit=True)


def _finalize_active(status: str, zero_credit: bool = False) -> dict[str, Any]:
    """Close out the active session with the given final status."""
    finalize_expired()
    conn = database.connect()
    try:
        session = database.get_active_session(conn)
        if not session:
            raise PeridoError("No active Pomodoro session.")
        actual = 0.0 if zero_credit else focused_seconds(session)
        database.update_session(
            conn,
            session["id"],
            status=status,
            actual_seconds=actual,
            end_time=iso_now(),
        )
        if session["cycle_id"]:
            database.update_cycle(conn, session["cycle_id"], status="abandoned")
        return database.get_session(conn, session["id"])
    finally:
        conn.close()


# ---------------------------------------------------------------------
# Lazy completion
# ---------------------------------------------------------------------


def finalize_expired() -> list[dict[str, Any]]:
    """Complete any active sessions whose scheduled window has passed.

    Returns:
        Event dicts describing what happened, in order, for the CLI to
        render: {"event": "complete", ...}, then cycle transitions such
        as {"event": "phase_start", ...} or
        {"event": "cycle_complete", ...}.

    Note:
        Paused sessions are never auto-completed — pausing freezes the
        schedule until the user resumes. Cycle advancement re-syncs to
        real time: each missed boundary completes one phase and starts
        the next from the current moment.
    """
    events: list[dict[str, Any]] = []
    conn = database.connect()
    try:
        while True:
            session = database.get_active_session(conn)
            if not session or session["paused_at"]:
                break
            end = _parse(session["end_time"])
            if end > now():
                break
            actual = (
                (end - _parse(session["start_time"])).total_seconds()
                - session["pause_seconds"]
            )
            database.update_session(
                conn,
                session["id"],
                status="completed",
                actual_seconds=max(0.0, actual),
            )
            events.append(
                {
                    "event": "complete",
                    "kind": session["kind"],
                    "minutes": planned_seconds(session) / 60,
                    "cycle_id": session["cycle_id"],
                    "standalone": session["cycle_id"] is None,
                }
            )
            if session["cycle_id"]:
                # Deferred import avoids a module import cycle.
                from . import cycles

                event = cycles.advance(conn, session["cycle_id"])
                if event:
                    events.append(event)
    finally:
        conn.close()
    return events


def iso_now() -> str:
    """Format the current clock reading for storage."""
    return database.iso(now())
