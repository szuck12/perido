# test_database.py
# Tests for the SQLite persistence layer.

from __future__ import annotations

from datetime import timedelta

from perido import database


def test_data_dir_respects_perido_home(home):
    assert database.data_dir() == home
    assert home.exists()


def test_connect_creates_schema(home):
    conn = database.connect()
    tables = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    assert {"sessions", "cycles"} <= tables
    conn.close()


def test_session_roundtrip(home, clock):
    conn = database.connect()
    session = database.create_session(
        conn, kind="focus", minutes=25, start=clock()
    )
    fetched = database.get_session(conn, session["id"])
    assert fetched == session
    assert fetched["status"] == "active"
    assert fetched["kind"] == "focus"
    assert fetched["planned_minutes"] == 25
    # end_time is scheduled start + planned minutes.
    end_delta = database.parse_ts(fetched["end_time"]) - clock()
    assert end_delta == timedelta(minutes=25)
    conn.close()


def test_get_active_session_returns_latest(home, clock):
    conn = database.connect()
    first = database.create_session(
        conn, kind="focus", minutes=25, start=clock()
    )
    database.update_session(conn, first["id"], status="completed")
    second = database.create_session(
        conn, kind="break", minutes=5, start=clock()
    )
    active = database.get_active_session(conn)
    assert active["id"] == second["id"]
    conn.close()


def test_get_active_session_none_when_all_finished(home, clock):
    conn = database.connect()
    session = database.create_session(
        conn, kind="focus", minutes=25, start=clock()
    )
    database.update_session(conn, session["id"], status="skipped")
    assert database.get_active_session(conn) is None
    conn.close()


def test_last_finished_session(home, clock):
    conn = database.connect()
    assert database.last_finished_session(conn) is None
    session = database.create_session(
        conn, kind="focus", minutes=25, start=clock()
    )
    database.update_session(conn, session["id"], status="interrupted")
    last = database.last_finished_session(conn)
    assert last["id"] == session["id"]
    conn.close()


def test_query_sessions_filters(home, clock):
    conn = database.connect()
    early = database.create_session(
        conn, kind="focus", minutes=25, start=clock()
    )
    database.update_session(conn, early["id"], status="completed")
    clock.advance(days=2)
    late_break = database.create_session(
        conn, kind="break", minutes=5, start=clock()
    )
    database.update_session(conn, late_break["id"], status="completed")

    everything = database.query_sessions(conn)
    assert len(everything) == 2

    only_late = database.query_sessions(
        conn, since=clock() - timedelta(hours=1), kinds=("break",)
    )
    assert [s["id"] for s in only_late] == [late_break["id"]]

    only_focus = database.query_sessions(conn, kinds=("focus",))
    assert [s["id"] for s in only_focus] == [early["id"]]

    asc = database.query_sessions(conn, order="ASC", limit=1)
    assert asc[0]["id"] == early["id"]

    until_filter = database.query_sessions(
        conn, until=clock() - timedelta(days=1)
    )
    assert [s["id"] for s in until_filter] == [early["id"]]

    by_status = database.query_sessions(conn, statuses=("active",))
    assert by_status == []


def test_cycle_crud(home, clock):
    conn = database.connect()
    plan = [{"kind": "focus", "minutes": 25}, {"kind": "break", "minutes": 5}]
    cycle_id = database.create_cycle(conn, "classic", plan, 0, clock())

    cycle = database.get_cycle(conn, cycle_id)
    assert cycle["name"] == "classic"
    assert cycle["status"] == "active"
    assert cycle["position"] == 0
    assert database.json_loads(cycle["plan"]) == plan

    database.update_cycle(conn, cycle_id, position=1, status="completed")
    cycle = database.get_cycle(conn, cycle_id)
    assert cycle["position"] == 1
    assert cycle["status"] == "completed"
    assert database.count_cycles(conn, "completed") == 1
    assert database.count_cycles(conn, "active") == 0
    conn.close()


def test_get_cycle_none_for_missing_or_null_id(home):
    conn = database.connect()
    assert database.get_cycle(conn, "nope") is None
    assert database.get_cycle(conn, None) is None
    conn.close()
