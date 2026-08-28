# test_stats.py
# Tests for journey statistics, streaks, and the weekly chart.

from __future__ import annotations

from datetime import date, timedelta

from perido import database, stats


def day_offset_clock(day_clock, days: int, hour: int | None = None):
    """Move the fake clock to local noon of a relative day."""
    target = timer_now_local(day_clock) + timedelta(days=days)
    if hour is not None:
        target = target.replace(hour=hour)
    return target


def timer_now_local(day_clock):
    return day_clock().astimezone()


# ---------------------------------------------------------------------
# Streak maths (pure functions)
# ---------------------------------------------------------------------


def test_current_streak_counts_back_from_today():
    today = date(2026, 8, 20)
    dates = {today, today - timedelta(days=1), today - timedelta(days=2)}
    assert stats.current_streak(dates, today) == 3


def test_current_streak_grace_when_today_empty():
    today = date(2026, 8, 20)
    dates = {
        today - timedelta(days=1),
        today - timedelta(days=2),
        today - timedelta(days=3),
    }
    assert stats.current_streak(dates, today) == 3


def test_current_streak_zero_when_broken():
    today = date(2026, 8, 20)
    dates = {today - timedelta(days=3)}
    assert stats.current_streak(dates, today) == 0


def test_best_streak_finds_longest_run():
    base = date(2026, 1, 1)
    run = {base + timedelta(days=i) for i in range(5)}
    older = {base - timedelta(days=9)}
    assert stats.best_streak(run | older) == 5
    assert stats.best_streak(set()) == 0


# ---------------------------------------------------------------------
# collect() against seeded history
# ---------------------------------------------------------------------


def test_collect_empty_history(home, clock):
    sections = stats.collect()
    assert sections["Today"][0][1] == "0"  # Sessions
    assert sections["All time"][0][1] == "0"
    assert any(value == "—" for _, value in sections["Today"])


def test_collect_today_section(home, clock, seed):
    for _ in range(3):
        seed(hour=9)
    seed(status="interrupted", actual_seconds=600, hour=10)
    seed(status="skipped", hour=11)

    today = dict(stats.collect()["Today"])
    assert today["Sessions"] == "3"
    # 3 x 25m completed + 10m interrupted = 85m.
    assert today["Focus time"] == "1h 25m"
    assert today["Average session"] == "25m"
    assert today["Longest session"] == "25m"
    assert today["Interrupted"] == "1"
    assert today["Completion rate"] == "75%"  # skips are not attempts


def test_collect_week_and_all_time(home, clock, seed):
    seed(hour=9)  # today x3
    seed(hour=9)
    seed(hour=9)
    seed(days_ago=1, minutes=50, hour=10)
    seed(days_ago=1, minutes=50, hour=10)
    seed(days_ago=3, minutes=45, extension_minutes=10, hour=11)
    seed(days_ago=10, minutes=20, hour=12)  # outside the week

    sections = stats.collect()
    week = dict(sections["This week"])
    assert week["Sessions"] == "6"
    # 3x25m + 2x50m + 45m = 220m.
    assert week["Focus time"] == "3h 40m"
    assert week["Daily average"] == "31m"  # 220 / 7 rounded
    assert week["Best day"] in stats.WEEKDAYS
    # Active days: today, yesterday, 3 days ago -> streak of 2 with grace.
    assert week["Current streak"] == "2 days"

    all_time = dict(sections["All time"])
    assert all_time["Sessions"] == "7"
    assert all_time["Focus time"] == "4h 00m"  # + 20m outside the week
    assert all_time["Longest session"] == "50m"
    assert all_time["Completion rate"] == "100%"  # no interruptions seeded
    assert all_time["Cycles completed"] == "0"


def test_collect_behavior_section(home, clock, seed):
    seed(hour=9)
    seed(hour=9)
    seed(hour=9)
    seed(days_ago=1, minutes=50, hour=10)
    seed(days_ago=1, minutes=50, hour=10)
    seed(days_ago=3, minutes=45, extension_minutes=10, hour=11)
    seed(days_ago=10, minutes=20, hour=12)

    behavior = dict(stats.collect()["Behavior"])
    assert behavior["Best hour"] == "10 AM"  # 100m at 10 AM beats others
    assert behavior["Extensions"] == "1"
    assert behavior["Extended time"] == "10m"
    assert behavior["Avg. sessions/active day"] == "1.8"  # 7 sessions / 4 days
    assert behavior["Typical session"] == "25m"  # median of the 7 durations


def test_collect_cycles_completed(home, clock, seed):
    conn = database.connect()
    plan = [{"kind": "focus", "minutes": 25}]
    cycle_id = database.create_cycle(conn, "classic", plan, 0, clock())
    database.update_cycle(conn, cycle_id, status="completed")
    conn.close()
    sections = stats.collect()
    assert dict(sections["All time"])["Cycles completed"] == "1"


def test_negative_extensions_not_counted(home, clock, seed):
    seed(hour=9, extension_minutes=-10)
    seed(days_ago=1, hour=9)

    behavior = dict(stats.collect()["Behavior"])
    assert behavior["Extensions"] == "0"
    assert behavior["Extended time"] == "0m"


# ---------------------------------------------------------------------
# Weekly chart data
# ---------------------------------------------------------------------


def test_week_bars_shape_and_scaling(home, clock, seed):
    seed(actual_seconds=3600)  # today: peak
    seed(days_ago=1, actual_seconds=1800)
    seed(days_ago=9, actual_seconds=9999)  # outside window

    bars = stats.week_bars()
    assert len(bars) == 7
    assert bars[-1][0] == timer_now_local(clock).date()
    assert bars[-1][1] == 3600
    assert bars[-2][1] == 1800
    assert bars[0][1] == 0.0  # 6 days ago: nothing seeded


def test_week_bars_includes_interrupted_focus(home, clock, seed):
    seed(status="interrupted", actual_seconds=600)
    bars = stats.week_bars()
    assert bars[-1][1] == 600


def test_week_chart_renders_scaled_bars(home, clock, seed, capsys):
    from perido import cli

    seed(actual_seconds=3600)
    seed(days_ago=1, actual_seconds=1800)
    cli.main(["week"])
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if "█" in line]
    assert len(lines) == 2
    # Printed oldest first: yesterday is the half-width bar, today peaks.
    assert lines[0].count("█") == 11
    assert lines[-1].count("█") == 22  # peak day fills the full width


# ---------------------------------------------------------------------
# Monthly chart data
# ---------------------------------------------------------------------


def test_month_bars_shape_and_scaling(home, clock, seed):
    seed(actual_seconds=3600)  # today: peak
    seed(days_ago=1, actual_seconds=1800)
    seed(days_ago=29, actual_seconds=900)  # inside the window
    seed(days_ago=31, actual_seconds=9999)  # outside the window

    bars = stats.month_bars()
    assert len(bars) == 30
    assert bars[-1][0] == timer_now_local(clock).date()
    assert bars[-1][1] == 3600
    assert bars[-2][1] == 1800
    assert bars[0][1] == 900  # 29 days ago: inside, ordered oldest first
    assert bars[1][1] == 0.0  # 28 days ago: nothing seeded


def test_month_bars_includes_interrupted_focus(home, clock, seed):
    seed(status="interrupted", actual_seconds=600)
    bars = stats.month_bars()
    assert bars[-1][1] == 600


def test_month_bars_excludes_skipped(home, clock, seed):
    seed(status="skipped", actual_seconds=0)
    bars = stats.month_bars()
    assert bars[-1][1] == 0.0
