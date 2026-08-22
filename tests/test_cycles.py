# test_cycles.py
# Tests for cycle presets, automatic transitions, and recovery.

from __future__ import annotations

import pytest

from perido import PeridoError, cycles, database, timer


def active():
    conn = database.connect()
    try:
        return database.get_active_session(conn)
    finally:
        conn.close()


def finished_statuses():
    conn = database.connect()
    try:
        return [s["status"] for s in database.query_sessions(conn)]
    finally:
        conn.close()


def cycle_row(cycle_id):
    conn = database.connect()
    try:
        return database.get_cycle(conn, cycle_id)
    finally:
        conn.close()


# ---------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "focus_minutes", "breaks"),
    [
        ("classic", [25, 25, 25, 25], [5, 5, 5, 15]),
        ("short", [15, 15, 15], [5, 5]),
        ("sprint", [10, 10, 10], [2, 2]),
        ("deep", [50, 50, 50], [10, 10, 30]),
        ("extended", [90, 90], [20, 30]),
    ],
)
def test_preset_plans(home, clock, name, focus_minutes, breaks):
    steps = cycles.plan_for(name)
    assert [s["minutes"] for s in steps if s["kind"] == "focus"] == focus_minutes
    assert [s["minutes"] for s in steps if s["kind"] == "break"] == breaks


def test_unknown_cycle_lists_available(home, clock):
    with pytest.raises(PeridoError) as excinfo:
        cycles.plan_for("marathon")
    message = str(excinfo.value)
    for known in ("classic", "short", "sprint", "deep", "extended"):
        assert known in message


# ---------------------------------------------------------------------
# Starting and transitions
# ---------------------------------------------------------------------


def test_start_creates_cycle_and_first_focus(home, clock):
    result = cycles.start("classic")
    session = result["session"]
    assert session["kind"] == "focus"
    assert session["cycle_name"] == "classic"
    assert session["cycle_position"] == 0
    assert session["planned_minutes"] == 25
    cycle = result["cycle"]
    assert cycle["status"] == "active"
    assert cycle["position"] == 0
    assert timer.active_session()["id"] == session["id"]


def test_start_rejected_when_session_active(home, clock):
    timer.start(25)
    with pytest.raises(PeridoError, match="already active"):
        cycles.start("classic")


def test_focus_completes_into_break_automatically(home, clock):
    cycles.start("classic")
    clock.advance(minutes=25)
    events = timer.finalize_expired()
    assert [e["event"] for e in events] == ["complete", "phase_start"]
    phase = events[1]
    assert phase["kind"] == "break"
    assert phase["minutes"] == 5
    assert phase["position"] == 1
    assert phase["total"] == 8
    assert phase["final_break"] is False
    current = active()
    assert current["kind"] == "break"
    assert current["cycle_position"] == 1


def test_break_completes_into_next_focus(home, clock):
    cycles.start("classic")
    clock.advance(minutes=25)
    timer.finalize_expired()
    clock.advance(minutes=5)
    events = timer.finalize_expired()
    assert [e["event"] for e in events] == ["complete", "phase_start"]
    phase = events[1]
    assert phase["kind"] == "focus"
    assert phase["position"] == 2
    assert phase["total"] == 8
    current = active()
    assert current["kind"] == "focus"
    assert current["planned_minutes"] == 25


def test_final_break_is_marked_long(home, clock):
    cycles.start("classic")
    for _ in range(3):  # focus 1-3, each into a short break
        clock.advance(minutes=25)
        events = timer.finalize_expired()
        assert events[-1]["final_break"] is False
        clock.advance(minutes=5)
        timer.finalize_expired()
    # Fourth focus flows into the long break.
    clock.advance(minutes=25)
    events = timer.finalize_expired()
    final = events[-1]
    assert final["kind"] == "break"
    assert final["minutes"] == 15
    assert final["final_break"] is True


def test_full_classic_cycle_completes_with_summary(home, clock):
    cycles.start("classic")
    # 4 x (25 focus + 5 break), last break is the long one.
    for _ in range(3):
        clock.advance(minutes=25)
        timer.finalize_expired()
        clock.advance(minutes=5)
        timer.finalize_expired()
    clock.advance(minutes=25)
    events = timer.finalize_expired()  # focus 4 -> long break
    assert events[-1]["event"] == "phase_start"
    clock.advance(minutes=15)
    events = timer.finalize_expired()
    assert [e["event"] for e in events] == ["complete", "cycle_complete"]
    summary = events[-1]["summary"]
    assert summary == {
        "focus_sessions": 4,
        "focus_minutes": 100,
        "short_breaks": 3,
        "long_breaks": 1,
    }
    assert active() is None
    assert cycle_row(events[-2]["cycle_id"])["status"] == "completed"


def test_cycle_without_trailing_break_ends_on_last_focus(home, clock):
    """Sprint ends with focus: no long break, cycle completes directly."""
    cycles.start("sprint")  # 10F 2B 10F 2B 10F
    for _ in range(2):
        clock.advance(minutes=10)
        timer.finalize_expired()
        clock.advance(minutes=2)
        timer.finalize_expired()
    clock.advance(minutes=10)
    events = timer.finalize_expired()
    kinds = [e["event"] for e in events]
    assert kinds == ["complete", "cycle_complete"]
    assert events[-1]["summary"]["long_breaks"] == 0
    assert events[-1]["summary"]["short_breaks"] == 2
    assert active() is None


# ---------------------------------------------------------------------
# Interruption, abandonment, and recovery
# ---------------------------------------------------------------------


def test_stop_mid_cycle_abandons_cycle(home, clock):
    result = cycles.start("classic")
    clock.advance(minutes=10)
    stopped = timer.stop()
    assert stopped["status"] == "interrupted"
    assert cycle_row(result["cycle"]["id"])["status"] == "abandoned"
    # No further advancement happens.
    clock.advance(hours=1)
    assert timer.finalize_expired() == []
    assert active() is None


def test_skip_mid_cycle_abandons_cycle(home, clock):
    result = cycles.start("deep")
    timer.skip()
    assert cycle_row(result["cycle"]["id"])["status"] == "abandoned"


def test_cycle_state_survives_process_restart(home, clock):
    """Every step uses fresh connections; state lives only in SQLite."""
    cycles.start("classic")
    clock.advance(minutes=25)
    first = timer.finalize_expired()
    assert first[1]["event"] == "phase_start"
    # Simulate a brand-new process discovering the running break.
    current = active()
    assert current["kind"] == "break"
    clock.advance(minutes=5)
    second = timer.finalize_expired()
    assert second[1]["event"] == "phase_start"
    assert second[1]["position"] == 2


def test_absence_resyncs_to_real_time(home, clock):
    """After a long absence the next phase starts from now, not backdated."""
    cycles.start("classic")
    clock.advance(minutes=25 + 47)  # focus ended 47 minutes ago
    events = timer.finalize_expired()
    assert events[0]["event"] == "complete"
    assert events[1]["event"] == "phase_start"
    current = active()
    # Break starts when the user returned, not when focus ended.
    began = database.parse_ts(current["start_time"])
    assert abs((began - clock()).total_seconds()) < 1.0
    assert timer.remaining_seconds(current) == 5 * 60


def test_extended_focus_within_cycle(home, clock):
    cycles.start("short")  # 15F 5B ...
    timer.extend(5)
    clock.advance(minutes=19)
    assert timer.finalize_expired() == []  # still one minute left
    clock.advance(minutes=1)
    events = timer.finalize_expired()
    assert events[0]["event"] == "complete"
    conn = database.connect()
    rows = database.query_sessions(conn, statuses=("completed",))
    conn.close()
    assert rows[0]["actual_seconds"] == 20 * 60


# ---------------------------------------------------------------------
# Summaries and labels
# ---------------------------------------------------------------------


def test_summarize_shapes():
    assert cycles.summarize([{"kind": "focus", "minutes": 10}]) == {
        "focus_sessions": 1,
        "focus_minutes": 10,
        "short_breaks": 0,
        "long_breaks": 0,
    }


def test_next_step_labels(home, clock):
    result = cycles.start("classic")
    nxt = cycles.next_step(result["cycle"], 0)
    assert nxt == {
        "kind": "break",
        "minutes": 5,
        "position": 1,
        "total": 8,
        "final_break": False,
    }
    assert cycles.next_step(result["cycle"], 7) is None
