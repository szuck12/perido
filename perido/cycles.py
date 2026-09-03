# cycles.py
# Pomodoro cycle presets and the focus/break transition state machine.

from __future__ import annotations

import sqlite3
from typing import Any

from . import PeridoError, database, timer
from .config import load as load_config


def available_names() -> list[str]:
    """Return sorted names of all configured cycles."""
    return sorted(load_config()["cycles"])


def plan_for(name: str) -> list[dict[str, Any]]:
    """Return the step list for a cycle name.

    Args:
        name: The cycle's name.

    Returns:
        The parsed step list for that cycle.

    Raises:
        PeridoError: If the name is not configured.
    """
    steps = load_config()["cycles"].get(name)
    if steps is None:
        raise PeridoError(
            f"Unknown cycle '{name}'.\n"
            f"Available cycles: {', '.join(available_names())}"
        )
    return steps


def start(name: str) -> dict[str, Any]:
    """Start a named cycle and its first focus session.

    Args:
        name: The cycle's preset name.

    Returns:
        Dict with "cycle" and "session" keys.

    Raises:
        PeridoError: If a session is already active or the cycle
            name is unknown.
    """
    steps = plan_for(name)
    timer.finalize_expired()
    conn = database.connect()
    try:
        existing = database.get_active_session(conn)
        if existing:
            raise PeridoError(timer.busy_error(existing))
        started = timer.now()
        cycle_id = database.create_cycle(conn, name, steps, 0, started)
        session = database.create_session(
            conn,
            kind="focus",
            minutes=steps[0]["minutes"],
            start=started,
            cycle_id=cycle_id,
            cycle_name=name,
            cycle_position=0,
        )
        return {
            "cycle": database.get_cycle(conn, cycle_id),
            "session": session,
        }
    finally:
        conn.close()


def advance(
    conn: sqlite3.Connection, cycle_id: str
) -> dict[str, Any] | None:
    """Move an active cycle to its next step after a phase completed.

    Starts the next focus/break session at the current moment, or
    completes the cycle when no steps remain. Re-syncing to real time
    here is deliberate: after an absence the finished phase is recorded
    and the next one begins fresh rather than backfilling missed time.

    Args:
        conn: An open database connection.
        cycle_id: The id of the running cycle to advance.

    Returns:
        An event dict for the CLI, or None if the cycle was already
        inactive.
    """
    cycle = database.get_cycle(conn, cycle_id)
    if not cycle or cycle["status"] != "active":
        return None
    steps = database.json_loads(cycle["plan"])
    nxt = cycle["position"] + 1
    if nxt >= len(steps):
        database.update_cycle(conn, cycle_id, status="completed")
        return {
            "event": "cycle_complete",
            "name": cycle["name"],
            "summary": summarize(steps),
        }
    step = steps[nxt]
    database.create_session(
        conn,
        kind=step["kind"],
        minutes=step["minutes"],
        start=timer.now(),
        cycle_id=cycle_id,
        cycle_name=cycle["name"],
        cycle_position=nxt,
    )
    database.update_cycle(conn, cycle_id, position=nxt)
    event: dict[str, Any] = {
        "event": "phase_start",
        "kind": step["kind"],
        "minutes": step["minutes"],
        "position": nxt,
        "total": len(steps),
        "final_break": step["kind"] == "break" and nxt == len(steps) - 1,
        "cycle_name": cycle["name"],
    }
    if step["kind"] == "break" and not event["final_break"]:
        event["break_slot"] = sum(
            1 for s in steps[:nxt] if s["kind"] == "break"
        ) + 1
        event["break_total"] = sum(
            1 for s in steps if s["kind"] == "break"
        )
    return event


def summarize(steps: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize a plan: focus counts and short/long break counts.

    The final break of a plan (when present) is considered the long
    break; all earlier breaks are short breaks.

    Args:
        steps: The parsed step list for a cycle.

    Returns:
        A dict of focus/break counts and totals.
    """
    focus = [s for s in steps if s["kind"] == "focus"]
    breaks = [s for s in steps if s["kind"] == "break"]
    long_breaks = 1 if steps and steps[-1]["kind"] == "break" else 0
    return {
        "focus_sessions": len(focus),
        "focus_minutes": sum(s["minutes"] for s in focus),
        "short_breaks": len(breaks) - long_breaks,
        "long_breaks": long_breaks,
    }


def next_step(cycle: dict[str, Any], position: int) -> dict[str, Any] | None:
    """Describe the step that follows position in a cycle's plan.

    Args:
        cycle: The stored cycle row, whose "plan" is JSON text.
        position: The current phase index in the plan.

    Returns:
        Dict with "kind", "minutes", "position", "total",
        "final_break", and — for focus steps — "slot" (1-based focus
        number) and "focus_total"; for non-final break steps —
        "break_slot" (1-based break number) and "break_total"; or None
        when the plan is exhausted.
    """
    steps = database.json_loads(cycle["plan"])
    nxt = position + 1
    if nxt >= len(steps):
        return None
    step = steps[nxt]
    info: dict[str, Any] = {
        "kind": step["kind"],
        "minutes": step["minutes"],
        "position": nxt,
        "total": len(steps),
        "final_break": step["kind"] == "break" and nxt == len(steps) - 1,
    }
    if step["kind"] == "focus":
        info["slot"] = sum(
            1 for s in steps[:nxt] if s["kind"] == "focus"
        ) + 1
        info["focus_total"] = sum(
            1 for s in steps if s["kind"] == "focus"
        )
    elif not info["final_break"]:
        info["break_slot"] = sum(
            1 for s in steps[:nxt] if s["kind"] == "break"
        ) + 1
        info["break_total"] = sum(
            1 for s in steps if s["kind"] == "break"
        )
    return info
