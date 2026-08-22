# insights.py
# Deterministic, rule-based observations about the user's focus history.

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from . import database, stats, timer
from .config import load as load_config

MIN_SESSIONS = 10
MAX_INSIGHTS = 2


def get_insights() -> list[str]:
    """Return up to MAX_INSIGHTS insight strings for the current history.

    Every rule has a minimum-data gate so that sparse histories never
    produce misleading claims.
    """
    conn = database.connect()
    try:
        rows = database.query_sessions(
            conn,
            kinds=("focus",),
            statuses=("completed", "interrupted", "skipped"),
        )
    finally:
        conn.close()
    now_local = timer.now().astimezone()
    messages: list[str] = []
    for rule in (
        _streak_rule,
        _week_rate_rule,
        _extension_rule,
        _peak_hours_rule,
        _weak_day_rule,
    ):
        message = rule(rows, now_local)
        if message:
            messages.append(message)
        if len(messages) == MAX_INSIGHTS:
            break
    return messages


def _completed(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["status"] == "completed"]


def _streak_rule(rows: list[dict], now_local) -> str | None:
    """Celebrate a run of consecutive completed sessions."""
    streak = 0
    for row in sorted(rows, key=lambda r: r["id"], reverse=True):
        if row["status"] == "completed":
            streak += 1
        elif row["status"] == "interrupted":
            break
        # Skipped rows are abandonments, not failed attempts.
    if streak >= 5:
        return (
            f"🔥 {streak} sessions completed in a row without"
            " stopping early."
        )
    return None


def _peak_hours_rule(rows: list[dict], now_local) -> str | None:
    """Find the 3-hour window holding the most focus time.

    Note:
        The window must hold at least 40% of all focus time so that
        evenly spread histories do not produce a hollow "peak".
    """
    completed = _completed(rows)
    if len(completed) < MIN_SESSIONS:
        return None
    by_hour: dict[int, float] = defaultdict(float)
    grand_total = 0.0
    for row in completed:
        hour = database.parse_ts(row["start_time"]).astimezone().hour
        seconds = row["actual_seconds"] or 0
        by_hour[hour] += seconds
        grand_total += seconds
    best_window, best_total = None, -1.0
    # ">=" breaks ties toward the latest window so the reported range
    # hugs the clustered hours instead of leading them.
    for start in range(22):  # linear windows; no midnight wrap-around
        total = sum(by_hour.get(start + offset, 0.0) for offset in range(3))
        if total >= best_total:
            best_window, best_total = start, total
    if best_total <= 0 or best_total / grand_total < 0.4:
        return None
    return (
        "💡 You tend to have your longest focus sessions between"
        f" {stats.format_hour(best_window)} and"
        f" {stats.format_hour(best_window + 3)}."
    )


def _week_rate_rule(rows: list[dict], now_local) -> str | None:
    """Highlight a strong completion rate over the trailing week."""
    week_ago = now_local - timedelta(days=7)
    attempts = [
        r
        for r in rows
        if r["status"] in ("completed", "interrupted")
        and database.parse_ts(r["start_time"]).astimezone() >= week_ago
    ]
    if len(attempts) < 5:
        return None
    done = sum(1 for r in attempts if r["status"] == "completed")
    rate = done / len(attempts)
    if rate < 0.8:
        return None
    return (
        f"💡 You've completed {round(rate * 100)}% of your Pomodoros"
        " this week without interruption."
    )


def _weak_day_rule(rows: list[dict], now_local) -> str | None:
    """Flag the least productive weekday once history is broad enough."""
    completed = _completed(rows)
    if len(completed) < 12:
        return None
    weeks = {
        database.parse_ts(r["start_time"]).astimezone().isocalendar()[:2]
        for r in completed
    }
    if len(weeks) < 3:
        return None
    totals: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    for row in completed:
        date = database.parse_ts(row["start_time"]).astimezone().date()
        name = stats.WEEKDAYS[date.weekday()]
        totals[name] += row["actual_seconds"] or 0
        counts[name] += 1
    if len(totals) < 4:
        return None
    candidates = {name: total for name, total in totals.items() if counts[name] >= 3}
    if not candidates:
        return None
    weakest = min(candidates, key=candidates.get)
    return f"💡 {weakest} is currently your least productive day."


def _extension_rule(rows: list[dict], now_local) -> str | None:
    """Notice a habit of extending sessions."""
    completed = _completed(rows)
    if len(completed) < MIN_SESSIONS:
        return None
    extended = sum(1 for r in completed if r["extension_minutes"] > 0)
    rate = extended / len(completed)
    if rate < 0.3:
        return None
    return (
        f"⏱ You extend {round(rate * 100)}% of your sessions —"
        " consider longer defaults."
    )
