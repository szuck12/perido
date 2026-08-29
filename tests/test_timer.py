# test_timer.py
# Tests for the session lifecycle state machine.

from __future__ import annotations

from datetime import timedelta

import pytest

from perido import PeridoError, database, timer

# ---------------------------------------------------------------------
# Starting
# ---------------------------------------------------------------------


def test_start_creates_active_focus_session(home, clock):
    session = timer.start(25)
    assert session["status"] == "active"
    assert session["kind"] == "focus"
    assert session["planned_minutes"] == 25
    assert session["extension_minutes"] == 0
    assert session["paused_at"] is None
    assert timer.active_session()["id"] == session["id"]


def test_start_break_kind(home, clock):
    session = timer.start(5, kind="break")
    assert session["kind"] == "break"


def test_second_start_is_rejected(home, clock):
    timer.start(25)
    with pytest.raises(PeridoError, match="already active"):
        timer.start(25)
    # A break cannot be started over a focus session either.
    with pytest.raises(PeridoError, match="already active"):
        timer.start(5, kind="break")


def test_busy_error_mentions_remaining_time(home, clock):
    timer.start(25)
    clock.advance(minutes=10)
    with pytest.raises(PeridoError) as excinfo:
        timer.start(25)
    assert "15:00" in str(excinfo.value)


# ---------------------------------------------------------------------
# Remaining / focus / progress maths
# ---------------------------------------------------------------------


def test_remaining_counts_down(home, clock):
    timer.start(25)
    clock.advance(minutes=10)
    session = timer.active_session()
    assert timer.remaining_seconds(session) == 15 * 60


def test_remaining_never_negative(home, clock):
    timer.start(25)
    clock.advance(hours=3)
    session = timer.active_session()
    assert timer.remaining_seconds(session) == 0.0


def test_focused_seconds_excludes_pauses(home, clock):
    timer.start(25)
    clock.advance(minutes=10)
    timer.pause()
    clock.advance(minutes=30)
    session = timer.active_session()
    assert timer.focused_seconds(session) == 10 * 60


def test_progress_fraction(home, clock):
    timer.start(25)
    clock.advance(minutes=12.5)
    session = timer.active_session()
    assert timer.progress_fraction(session) == pytest.approx(0.5)


# ---------------------------------------------------------------------
# Pause / resume
# ---------------------------------------------------------------------


def test_pause_and_resume_preserve_remaining(home, clock):
    timer.start(25)
    clock.advance(minutes=10)
    paused = timer.pause()
    assert paused["paused_at"] is not None

    clock.advance(minutes=7)
    resumed = timer.resume()
    assert resumed["paused_at"] is None
    # The 7 paused minutes did not count.
    assert timer.remaining_seconds(resumed) == 15 * 60
    assert resumed["pause_seconds"] == 7 * 60


def test_pause_without_session(home, clock):
    with pytest.raises(PeridoError, match="No active"):
        timer.pause()


def test_double_pause_rejected(home, clock):
    timer.start(25)
    timer.pause()
    with pytest.raises(PeridoError, match="already paused"):
        timer.pause()


def test_resume_without_paused_session(home, clock):
    with pytest.raises(PeridoError, match="No paused"):
        timer.resume()
    timer.start(25)
    with pytest.raises(PeridoError, match="No paused"):
        timer.resume()


def test_long_pause_shifts_end_time(home, clock):
    timer.start(25)
    start = timer.active_session()
    original_end = start["end_time"]
    timer.pause()
    clock.advance(hours=2)
    resumed = timer.resume()
    shifted = database.parse_ts(resumed["end_time"]) - database.parse_ts(
        original_end
    )
    assert shifted == timedelta(hours=2)


# ---------------------------------------------------------------------
# Extend
# ---------------------------------------------------------------------


def test_extend_adds_minutes(home, clock):
    timer.start(25)
    clock.advance(minutes=20)
    extended = timer.extend(10)
    assert timer.remaining_seconds(extended) == 15 * 60
    assert extended["extension_minutes"] == 10
    # Planned window grew: 20 focused + 15 remaining = 35 total.
    assert timer.planned_seconds(extended) == 35 * 60


def test_extend_while_paused(home, clock):
    timer.start(25)
    timer.pause()
    extended = timer.extend(5)
    assert extended["extension_minutes"] == 5
    timer.resume()
    assert timer.remaining_seconds(extended) == 30 * 60


def test_extend_requires_positive(home, clock):
    for bad in (0, -5, -0.5):
        with pytest.raises(PeridoError, match="positive"):
            timer.extend(bad)


def test_extend_without_session(home, clock):
    with pytest.raises(
        PeridoError, match="No active Pomodoro session to extend"
    ):
        timer.extend(10)


def test_extended_session_completes_at_new_end(home, clock):
    timer.start(25)
    timer.extend(10)
    clock.advance(minutes=25)
    events = timer.finalize_expired()
    assert events == []  # still 10 minutes left
    clock.advance(minutes=10)
    events = timer.finalize_expired()
    assert [e["event"] for e in events] == ["complete"]
    conn = database.connect()
    rows = database.query_sessions(conn, statuses=("completed",))
    conn.close()
    assert rows[0]["actual_seconds"] == 35 * 60


# ---------------------------------------------------------------------
# Shorten
# ---------------------------------------------------------------------


def test_shorten_pulls_end_time_earlier(home, clock):
    timer.start(25)
    clock.advance(minutes=5)
    shortened = timer.shorten(10)
    assert timer.remaining_seconds(shortened) == 10 * 60
    # Recorded as negative extension so planned totals stay consistent.
    assert shortened["extension_minutes"] == -10
    assert timer.planned_seconds(shortened) == 15 * 60


def test_shortened_session_completes_at_new_end(home, clock):
    timer.start(25)
    timer.shorten(20)
    clock.advance(minutes=6)
    events = timer.finalize_expired()
    assert [e["event"] for e in events] == ["complete"]
    conn = database.connect()
    rows = database.query_sessions(conn, statuses=("completed",))
    conn.close()
    assert rows[0]["actual_seconds"] == 5 * 60


def test_shorten_while_paused(home, clock):
    timer.start(25)
    timer.pause()
    shortened = timer.shorten(5)
    assert shortened["extension_minutes"] == -5
    timer.resume()
    assert timer.remaining_seconds(shortened) == 20 * 60


def test_extend_then_shorten_roundtrip(home, clock):
    timer.start(25)
    timer.extend(10)
    restored = timer.shorten(10)
    assert restored["extension_minutes"] == 0
    assert timer.planned_seconds(restored) == 25 * 60


def test_shorten_requires_positive(home, clock):
    timer.start(25)
    for bad in (0, -5, -0.5):
        with pytest.raises(PeridoError, match="positive"):
            timer.shorten(bad)


def test_shorten_without_session(home, clock):
    with pytest.raises(
        PeridoError, match="No active Pomodoro session to shorten"
    ):
        timer.shorten(10)


def test_shorten_more_than_remaining_rejected(home, clock):
    timer.start(25)
    clock.advance(minutes=10)  # 15 minutes left
    with pytest.raises(PeridoError, match="only has 15:00 remaining"):
        timer.shorten(15)  # exactly the remainder would leave nothing
    with pytest.raises(PeridoError, match="only has 15:00 remaining"):
        timer.shorten(20)


# ---------------------------------------------------------------------
# Stop / skip
# ---------------------------------------------------------------------


def test_stop_records_interrupted_with_progress(home, clock):
    timer.start(25)
    clock.advance(minutes=18, seconds=42)
    stopped = timer.stop()
    assert stopped["status"] == "interrupted"
    assert stopped["actual_seconds"] == pytest.approx(18 * 60 + 42)
    fraction = timer.progress_fraction(stopped)
    assert fraction == pytest.approx((18 * 60 + 42) / (25 * 60))
    assert timer.active_session() is None


def test_stop_while_paused_credits_only_focused_time(home, clock):
    timer.start(25)
    clock.advance(minutes=5)
    timer.pause()
    clock.advance(minutes=50)
    stopped = timer.stop()
    assert stopped["actual_seconds"] == pytest.approx(5 * 60)


def test_stop_without_session(home, clock):
    with pytest.raises(PeridoError, match="No active"):
        timer.stop()


def test_skip_records_zero_focus_credit(home, clock):
    timer.start(25)
    clock.advance(minutes=20)
    skipped = timer.skip()
    assert skipped["status"] == "skipped"
    assert skipped["actual_seconds"] == 0.0
    assert timer.active_session() is None


def test_skip_without_session(home, clock):
    with pytest.raises(PeridoError, match="No active"):
        timer.skip()


# ---------------------------------------------------------------------
# Lazy completion and recovery
# ---------------------------------------------------------------------


def test_expired_session_finalizes_on_next_call(home, clock):
    timer.start(25)
    clock.advance(minutes=24)
    assert timer.finalize_expired() == []
    clock.advance(minutes=1)
    events = timer.finalize_expired()
    assert [e["event"] for e in events] == ["complete"]
    assert events[0]["kind"] == "focus"
    assert events[0]["standalone"] is True
    assert timer.active_session() is None
    conn = database.connect()
    rows = database.query_sessions(conn, statuses=("completed",))
    conn.close()
    assert len(rows) == 1
    assert rows[0]["actual_seconds"] == 25 * 60


def test_finalize_is_idempotent(home, clock):
    timer.start(25)
    clock.advance(minutes=26)
    assert timer.finalize_expired()
    assert timer.finalize_expired() == []


def test_paused_session_never_auto_completes(home, clock):
    timer.start(25)
    clock.advance(minutes=24)
    timer.pause()
    clock.advance(hours=5)
    assert timer.finalize_expired() == []
    session = timer.active_session()
    assert session is not None and session["paused_at"]
    # Resuming restores the frozen remainder.
    resumed = timer.resume()
    assert timer.remaining_seconds(resumed) == 60.0


def test_recovery_after_process_death(home, clock):
    """Simulates a crash: state lives in SQLite, not in the process."""
    timer.start(25)
    clock.advance(minutes=40)
    # A brand-new command (any op) discovers and finalizes the session.
    events = timer.finalize_expired()
    assert [e["event"] for e in events] == ["complete"]
    conn = database.connect()
    last = database.last_finished_session(conn)
    conn.close()
    assert last["status"] == "completed"


def test_stale_session_finalizes_before_new_start(home, clock):
    timer.start(25)
    clock.advance(minutes=30)
    fresh = timer.start(15)
    assert fresh["planned_minutes"] == 15
    conn = database.connect()
    rows = database.query_sessions(conn, statuses=("completed",))
    conn.close()
    assert len(rows) == 1
