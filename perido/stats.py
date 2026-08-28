# stats.py
# Focus journey statistics: daily, weekly, all-time, and behavioural.

from __future__ import annotations

from datetime import date, timedelta
from statistics import median

from . import database, timer

WEEKDAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


def format_hour(hour: int) -> str:
    """Format an hour-of-day like 8 PM or 12 AM.

    Args:
        hour: The 0-23 hour-of-day value.

    Returns:
        A human-readable local label.
    """
    suffix = "AM" if hour < 12 else "PM"
    twelve = hour % 12 or 12
    return f"{twelve} {suffix}"


def _local_date(row: dict) -> date:
    """Local calendar date of a session's start."""
    return database.parse_ts(row["start_time"]).astimezone().date()


def _local_hour(row: dict) -> int:
    """Local hour-of-day of a session's start."""
    return database.parse_ts(row["start_time"]).astimezone().hour


def _focus_seconds(rows: list[dict]) -> float:
    """Sum actual focus seconds (skipped rows contribute zero)."""
    return sum(row["actual_seconds"] or 0 for row in rows)


def _rate(completed: int, interrupted: int) -> str:
    """Completion rate string; skipped sessions are not attempts."""
    attempts = completed + interrupted
    if not attempts:
        return "—"
    return f"{round(completed / attempts * 100)}%"


def current_streak(dates: set[date], today: date) -> int:
    """Consecutive active days ending today or yesterday.

    Args:
        dates: The set of local dates with finished sessions.
        today: The current local date.

    Returns:
        The number of consecutive active days, capped by the grace
        day that a still-running today provides.
    """
    day = today if today in dates else today - timedelta(days=1)
    streak = 0
    while day in dates:
        streak += 1
        day -= timedelta(days=1)
    return streak


def best_streak(dates: set[date]) -> int:
    """Longest run of consecutive active days ever recorded.

    Args:
        dates: The set of local dates with finished sessions.

    Returns:
        The length of the longest uninterrupted active run.
    """
    best = 0
    for day in dates:
        if day - timedelta(days=1) in dates:
            continue  # not the start of a run
        length = 1
        while day + timedelta(days=length) in dates:
            length += 1
        best = max(best, length)
    return best


def _load() -> tuple[list[dict], list[dict], list[dict], int]:
    """Load finalized focus sessions and completed-cycle count.

    Returns:
        Tuple of (completed, interrupted, all_finalized_focus,
        cycles_completed).
    """
    conn = database.connect()
    try:
        rows = database.query_sessions(
            conn,
            kinds=("focus",),
            statuses=("completed", "interrupted", "skipped"),
        )
        cycles_done = database.count_cycles(conn, "completed")
    finally:
        conn.close()
    completed = [r for r in rows if r["status"] == "completed"]
    interrupted = [r for r in rows if r["status"] == "interrupted"]
    return completed, interrupted, rows, cycles_done


def collect() -> dict[str, list[tuple[str, str]]]:
    """Compute every stats section for the CLI.

    Note:
        Focus-time totals include partial time from interrupted
        sessions; per-session aggregates (average, longest, typical)
        consider completed sessions only. Skipped sessions are not
        counted as completion-rate attempts.
    """
    from .cli import fmt_minutes

    completed, interrupted, rows, cycles_done = _load()
    focused = completed + interrupted
    today = timer.now().astimezone().date()
    week_dates = {today - timedelta(days=offset) for offset in range(7)}

    today_done = [r for r in completed if _local_date(r) == today]
    today_focused = [r for r in focused if _local_date(r) == today]
    today_interrupted = [r for r in interrupted if _local_date(r) == today]

    week_done = [r for r in completed if _local_date(r) in week_dates]
    week_focused = [r for r in focused if _local_date(r) in week_dates]

    by_day: dict[date, float] = {}
    for row in week_focused:
        day = _local_date(row)
        by_day[day] = by_day.get(day, 0.0) + (row["actual_seconds"] or 0)
    best_day = max(by_day, key=by_day.get) if by_day else None

    active_dates = {_local_date(r) for r in completed}
    longest = (
        max((r["actual_seconds"] or 0) for r in completed) if completed else 0.0
    )
    avg_session = (
        sum(r["actual_seconds"] or 0 for r in completed) / len(completed)
        if completed
        else 0.0
    )

    hour_totals: dict[int, float] = {}
    weekday_totals: dict[str, float] = {}
    for row in focused:
        hour = _local_hour(row)
        hour_totals[hour] = hour_totals.get(hour, 0.0) + (
            row["actual_seconds"] or 0
        )
        name = WEEKDAYS[_local_date(row).weekday()]
        weekday_totals[name] = weekday_totals.get(name, 0.0) + (
            row["actual_seconds"] or 0
        )

    extended = [r for r in rows if r["extension_minutes"] > 0]
    today_avg = (
        sum(r["actual_seconds"] or 0 for r in today_done) / len(today_done)
        if today_done
        else None
    )
    today_longest = (
        max((r["actual_seconds"] or 0) for r in today_done)
        if today_done
        else None
    )

    return {
        "Today": [
            ("Sessions", str(len(today_done))),
            ("Focus time", fmt_minutes(_focus_seconds(today_focused))),
            ("Average session", fmt_minutes(today_avg) if today_avg else "—"),
            (
                "Longest session",
                fmt_minutes(today_longest) if today_longest else "—",
            ),
            ("Interrupted", str(len(today_interrupted))),
            ("Completion rate", _rate(len(today_done), len(today_interrupted))),
        ],
        "This week": [
            ("Sessions", str(len(week_done))),
            ("Focus time", fmt_minutes(_focus_seconds(week_focused))),
            ("Best day", best_day.strftime("%A") if best_day else "—"),
            ("Daily average", fmt_minutes(_focus_seconds(week_focused) / 7)),
            ("Current streak", f"{current_streak(active_dates, today)} days"),
        ],
        "All time": [
            ("Sessions", str(len(completed))),
            ("Focus time", fmt_minutes(_focus_seconds(focused))),
            ("Average session", fmt_minutes(avg_session)),
            ("Longest session", fmt_minutes(longest) if longest else "—"),
            ("Interrupted", str(len(interrupted))),
            ("Completion rate", _rate(len(completed), len(interrupted))),
            ("Best streak", f"{best_streak(active_dates)} days"),
            ("Cycles completed", str(cycles_done)),
        ],
        "Behavior": [
            (
                "Best hour",
                format_hour(max(hour_totals, key=hour_totals.get))
                if hour_totals
                else "—",
            ),
            (
                "Best weekday",
                max(weekday_totals, key=weekday_totals.get)
                if weekday_totals
                else "—",
            ),
            (
                "Avg. sessions/active day",
                f"{len(completed) / len(active_dates):.1f}"
                if active_dates
                else "—",
            ),
            (
                "Typical session",
                fmt_minutes(
                    median([r["actual_seconds"] or 0 for r in completed])
                )
                if completed
                else "—",
            ),
            ("Extensions", str(len(extended))),
            (
                "Extended time",
                fmt_minutes(sum(r["extension_minutes"] for r in extended) * 60),
            ),
        ],
    }


def _daily_bars(window_days: int) -> list[tuple[date, float]]:
    """Focus seconds per local day for a trailing window, oldest first.

    Args:
        window_days: Number of days to span, ending today.

    Returns:
        (local_date, focus_seconds) pairs, oldest first, with zero for
        days that have no focus time.
    """
    _, _, rows, _ = _load()
    focused = [r for r in rows if r["status"] != "skipped"]
    today = timer.now().astimezone().date()
    totals: dict[date, float] = {}
    for row in focused:
        day = _local_date(row)
        totals[day] = totals.get(day, 0.0) + (row["actual_seconds"] or 0)
    return [
        (day, totals.get(day, 0.0))
        for day in (
            today - timedelta(days=offset)
            for offset in range(window_days - 1, -1, -1)
        )
    ]


def week_bars() -> list[tuple[date, float]]:
    """Focus seconds per local day for the last 7 days, oldest first."""
    return _daily_bars(7)


def month_bars() -> list[tuple[date, float]]:
    """Focus seconds per local day for the last 30 days, oldest first."""
    return _daily_bars(30)
