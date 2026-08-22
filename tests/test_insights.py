# test_insights.py
# Tests for rule-based insights and their minimum-data gates.

from __future__ import annotations

from datetime import timedelta

from perido import insights


def days_since_weekday(day_clock, target_weekday: int) -> int:
    """Days back to the most recent occurrence of a weekday (Mon=0)."""
    today = day_clock().astimezone().date().weekday()
    return (today - target_weekday) % 7


def test_no_insights_with_sparse_history(home, clock, seed):
    seed()
    seed(days_ago=1)
    assert insights.get_insights() == []


def test_streak_insight_fires_at_five(home, clock, seed):
    for days in range(5):
        seed(days_ago=4 - days)
    messages = insights.get_insights()
    assert any("in a row without stopping early" in m for m in messages)


def test_streak_broken_by_interruption(home, clock, seed):
    # All older than a week so the weekly-rate rule stays silent too.
    for days in range(5):
        seed(days_ago=14 - days)
    seed(days_ago=15, status="interrupted", actual_seconds=60)
    messages = insights.get_insights()
    assert not any("in a row" in m for m in messages)
    assert messages == []  # nothing else has enough data either


def test_skips_do_not_break_completion_streak(home, clock, seed):
    for _ in range(5):
        seed()
    seed(status="skipped")
    messages = insights.get_insights()
    assert any("in a row without stopping early" in m for m in messages)


def test_peak_hours_requires_ten_sessions(home, clock, seed):
    # Nine concentrated sessions: below the gate. All older than a
    # week, and the trailing interruption suppresses the streak rule.
    for index in range(9):
        seed(days_ago=8 + index, hour=20)
    assert not any("between" in m for m in insights.get_insights())
    seed(days_ago=17, hour=20)  # tenth session, still concentrated
    seed(days_ago=18, status="interrupted", actual_seconds=60)
    messages = insights.get_insights()
    assert any("between 8 PM and 11 PM" in m for m in messages)


def test_peak_hours_ignores_evenly_spread_history(home, clock, seed):
    hours = [7, 10, 13, 16, 19, 22, 1, 4, 9, 15]
    for index, hour in enumerate(hours):
        seed(days_ago=index % 8, hour=hour)
    messages = insights.get_insights()
    assert not any("between" in m for m in messages)


def test_week_rate_insight(home, clock, seed):
    for _ in range(4):
        seed()
    seed(status="interrupted", actual_seconds=300)  # 5 attempts, 80% done
    messages = insights.get_insights()
    assert any("80% of your Pomodoros" in m for m in messages)


def test_week_rate_needs_five_attempts(home, clock, seed):
    for _ in range(3):
        seed()
    seed(status="interrupted", actual_seconds=300)
    assert not any("of your Pomodoros" in m for m in insights.get_insights())


def test_extension_insight(home, clock, seed):
    # Ten completed sessions spread thin; four of them extended.
    for index in range(10):
        seed(
            days_ago=8 + index,
            minutes=25,
            extension_minutes=10 if index % 3 == 0 else 0,
            hour=(7 + index * 2) % 24,
        )
    # Trailing interruption suppresses the streak insight.
    seed(status="interrupted", actual_seconds=60)
    messages = insights.get_insights()
    assert any("extend 40% of your sessions" in m for m in messages)


def test_trimmed_sessions_do_not_trigger_extension_insight(home, clock, seed):
    for index in range(10):
        seed(
            days_ago=8 + index,
            minutes=25,
            extension_minutes=-5,
            hour=(7 + index * 2) % 24,
        )
    seed(status="interrupted", actual_seconds=60)
    assert not any("extend" in m for m in insights.get_insights())


def test_weak_day_insight(home, day_clock, seed):
    friday_back = days_since_weekday(day_clock, 4)  # Friday
    monday_back = days_since_weekday(day_clock, 0)
    tuesday_back = days_since_weekday(day_clock, 1)
    wednesday_back = days_since_weekday(day_clock, 2)

    # Keep every session at least a week old so the weekly-rate rule
    # stays silent, and end with an interruption to suppress the
    # streak rule — that leaves the cap free for the weak-day rule.
    for week in range(3):  # three short Fridays across three weeks
        seed(days_ago=friday_back + 7 + 7 * week, minutes=10)
    for week in range(3):  # longer sessions on other weekdays
        seed(days_ago=monday_back + 7 + 7 * week, minutes=30)
        seed(days_ago=tuesday_back + 7 + 7 * week, minutes=30)
        seed(days_ago=wednesday_back + 7 + 7 * week, minutes=30)
    seed(status="interrupted", actual_seconds=60)

    messages = insights.get_insights()
    assert any("least productive day" in m for m in messages)


def test_weak_day_needs_three_weeks(home, day_clock, seed):
    friday_back = days_since_weekday(day_clock, 4)
    for week in range(2):  # only two Fridays so far
        seed(days_ago=friday_back + 7 * week, minutes=10)
        seed(days_ago=(friday_back + 6) % 7 + 7 * week, minutes=30)
    assert not any("least productive" in m for m in insights.get_insights())


def test_at_most_two_insights(home, clock, seed):
    """Rich history still yields a bounded, prioritized list."""
    for index in range(12):
        seed(days_ago=index % 6, hour=20)
    assert len(insights.get_insights()) <= 2
