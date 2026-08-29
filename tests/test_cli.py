# test_cli.py
# Tests for command output, error paths, and exit codes.

from __future__ import annotations

import pytest

from perido import cli, database, timer


def test_start_banner(home, clock, capsys):
    code = cli.main(["start"])
    out = capsys.readouterr().out
    assert code == 0
    assert "🍅 Focus session started" in out
    assert "25:00" in out
    assert "Started at" in out and "Ends:" in out


def test_start_custom_duration(home, clock, capsys):
    cli.main(["start", "--duration", "35"])
    assert "35:00" in capsys.readouterr().out


def test_start_preset_flags(home, clock, capsys):
    cli.main(["start", "--short"])
    assert "15:00" in capsys.readouterr().out
    timer.stop()
    cli.main(["break", "--extralong"])
    assert "30:00" in capsys.readouterr().out


def test_start_extrashort_preset(home, clock, capsys):
    cli.main(["start", "--extrashort"])
    out = capsys.readouterr().out
    assert "10:00" in out
    timer.stop()
    cli.main(["break", "--extrashort"])
    assert "3:00" in capsys.readouterr().out


def test_start_rejects_conflicting_flags(home, clock):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["start", "--short", "--long"])
    assert excinfo.value.code == 2


def test_double_start_error(home, clock, capsys):
    cli.main(["start"])
    capsys.readouterr()
    code = cli.main(["start"])
    err = capsys.readouterr().err
    assert code == 1
    assert "already active" in err
    assert "perido stop" in err


def test_extend_without_session(home, clock, capsys):
    code = cli.main(["extend", "10"])
    err = capsys.readouterr().err
    assert code == 1
    assert "No active Pomodoro session to extend." in err
    assert "perido start" in err


@pytest.mark.parametrize("bad", ["abc", "-5", "0", "nan", "inf", "-inf"])
def test_extend_invalid_values(home, clock, bad):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["extend", bad])
    assert excinfo.value.code == 2


@pytest.mark.parametrize("bad", ["nan", "inf"])
def test_start_duration_rejects_non_finite(home, clock, capsys, bad):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["start", "--duration", bad])
    assert excinfo.value.code == 2
    assert "positive number of minutes" in capsys.readouterr().err


def test_extend_output(home, clock, capsys):
    cli.main(["start"])
    clock.advance(minutes=20)
    capsys.readouterr()
    code = cli.main(["extend", "10"])
    out = capsys.readouterr().out
    assert code == 0
    assert "extended by 10 minutes" in out
    assert "New end time:" in out
    assert "15:00" in out


def test_shorten_output(home, clock, capsys):
    cli.main(["start"])
    clock.advance(minutes=5)
    capsys.readouterr()
    code = cli.main(["shorten", "10"])
    out = capsys.readouterr().out
    assert code == 0
    assert "shortened by 10 minutes" in out
    assert "New end time:" in out
    assert "10:00" in out


def test_shorten_without_session(home, clock, capsys):
    code = cli.main(["shorten", "10"])
    err = capsys.readouterr().err
    assert code == 1
    assert "No active Pomodoro session to shorten." in err
    assert "perido start" in err


@pytest.mark.parametrize("bad", ["abc", "-5", "0"])
def test_shorten_invalid_values(home, clock, bad):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["shorten", bad])
    assert excinfo.value.code == 2


def test_shorten_more_than_remaining(home, clock, capsys):
    cli.main(["start"])
    clock.advance(minutes=20)
    capsys.readouterr()
    code = cli.main(["shorten", "30"])
    err = capsys.readouterr().err
    assert code == 1
    assert "only has 05:00 remaining" in err


def test_pause_and_resume_outputs(home, clock, capsys):
    cli.main(["start"])
    clock.advance(minutes=7)
    capsys.readouterr()
    code = cli.main(["pause"])
    out = capsys.readouterr().out
    assert code == 0
    assert "⏸ Timer paused" in out
    assert "18:00 remaining" in out
    clock.advance(minutes=9)
    code = cli.main(["resume"])
    out = capsys.readouterr().out
    assert code == 0
    assert "▶ Timer resumed" in out
    assert "18:00 remaining" in out


def test_pause_without_session(home, clock, capsys):
    code = cli.main(["pause"])
    assert code == 1
    assert "No active" in capsys.readouterr().err


def test_resume_without_paused_session(home, clock, capsys):
    code = cli.main(["resume"])
    assert code == 1
    assert "No paused Pomodoro session to resume." in capsys.readouterr().err


def test_stop_output(home, clock, capsys):
    cli.main(["start"])
    clock.advance(minutes=18, seconds=42)
    capsys.readouterr()
    code = cli.main(["stop"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Session stopped." in out
    assert "Duration: 18m 42s" in out
    assert "Completed: No" in out
    assert "Progress: 75%" in out


def test_stop_without_session(home, clock, capsys):
    code = cli.main(["stop"])
    assert code == 1
    assert "No active Pomodoro session." in capsys.readouterr().err


def test_skip_output(home, clock, capsys):
    cli.main(["start"])
    capsys.readouterr()
    code = cli.main(["skip"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Session skipped." in out
    assert "No focus time recorded." in out


def test_status_active(home, clock, capsys):
    cli.main(["start"])
    clock.advance(minutes=7, seconds=26)
    capsys.readouterr()
    code = cli.main(["status"])
    out = capsys.readouterr().out
    assert code == 0
    assert "🍅 FOCUSING" in out
    assert "█" in out and "░" in out
    assert "17:34 remaining" in out
    assert "Started:" in out and "Ends:" in out


def test_status_idle_after_stop(home, clock, capsys):
    cli.main(["start"])
    cli.main(["stop"])
    capsys.readouterr()
    code = cli.main(["status"])
    out = capsys.readouterr().out
    assert code == 0
    assert "No active Pomodoro." in out
    assert "Last session:" in out
    assert "interrupted" in out


def test_status_idle_fresh(home, clock, capsys):
    code = cli.main(["status"])
    out = capsys.readouterr().out
    assert code == 0
    assert "No sessions yet" in out
    assert "perido start" in out


def test_break_conflict_with_focus(home, clock, capsys):
    cli.main(["start"])
    capsys.readouterr()
    code = cli.main(["break"])
    assert code == 1
    assert "already active" in capsys.readouterr().err


def test_break_ok(home, clock, capsys):
    code = cli.main(["break"])
    out = capsys.readouterr().out
    assert code == 0
    assert "☕ Break started" in out
    assert "5:00" in out


def test_break_custom_duration(home, clock, capsys):
    cli.main(["break", "--duration", "8"])
    assert "8:00" in capsys.readouterr().out


def test_cycle_banner(home, clock, capsys):
    code = cli.main(["cycle", "classic"])
    out = capsys.readouterr().out
    assert code == 0
    assert "🍅 CLASSIC POMODORO" in out
    assert "Focus 1 of 4" in out
    assert "25:00" in out


def test_cycle_unknown_name_lists_available(home, clock, capsys):
    code = cli.main(["cycle", "mythical"])
    err = capsys.readouterr().err
    assert code == 1
    assert "Unknown cycle 'mythical'" in err
    for known in ("classic", "monolith", "sprint", "summit"):
        assert known in err


def test_cycle_transition_events_rendered_by_next_command(home, clock, capsys):
    cli.main(["cycle", "sprint"])
    clock.advance(minutes=10)
    capsys.readouterr()
    code = cli.main(["status"])
    out = capsys.readouterr().out
    assert code == 0
    assert "🍅 SESSION COMPLETE!" in out
    assert "10 minutes focused." in out
    assert "☕ Break started." in out
    assert "☕ ON BREAK" in out


def test_cycle_completion_summary(home, clock, capsys):
    cli.main(["cycle", "sprint"])  # 10F 2B 10F 2B 10F
    for _ in range(2):
        clock.advance(minutes=10)
        cli.main(["status"])
        clock.advance(minutes=2)
        cli.main(["status"])
    clock.advance(minutes=10)
    code = cli.main(["status"])
    out = capsys.readouterr().out
    assert code == 0
    assert "🎉 CYCLE COMPLETE!" in out
    assert "3 focus sessions" in out
    assert "30 minutes focused" in out
    assert "2 short breaks" in out
    assert "0 long breaks" in out


def test_history_table(home, clock, seed, capsys):
    seed(status="completed")
    seed(status="interrupted", actual_seconds=600)
    seed(status="skipped")
    code = cli.main(["history"])
    out = capsys.readouterr().out
    assert code == 0
    for token in ("DATE", "START", "DURATION", "RESULT",
                  "✓ Complete", "× Interrupted", "○ Skipped"):
        assert token in out


def test_history_cycle_and_extension_tags(home, clock, seed, capsys):
    seed(extension_minutes=10)
    conn = database.connect()
    plan = [
        {"kind": "focus", "minutes": 25},
        {"kind": "break", "minutes": 5},
        {"kind": "focus", "minutes": 25},
        {"kind": "break", "minutes": 5},
        {"kind": "focus", "minutes": 25},
        {"kind": "break", "minutes": 5},
        {"kind": "focus", "minutes": 25},
        {"kind": "break", "minutes": 15},
    ]
    cycle_id = database.create_cycle(conn, "classic", plan, 0, clock())
    row = seed(cycle_name="classic", cycle_position=0)
    database.update_session(conn, row["id"], cycle_id=cycle_id)
    conn.close()
    cli.main(["history"])
    out = capsys.readouterr().out
    assert "+10m ext" in out
    assert "Classic 1/4" in out


def test_history_shows_trimmed_tag(home, clock, seed, capsys):
    # Seed stores planned = minutes + extension, so a 25-minute session
    # trimmed by 10 is seeded as minutes=35 with extension -10.
    seed(minutes=35, extension_minutes=-10)
    cli.main(["history"])
    out = capsys.readouterr().out
    assert "-10m trimmed" in out
    # Duration column reflects the shortened window: planned + ext.
    assert "15m" in out


def test_history_today_filter(home, clock, seed, capsys):
    seed(days_ago=0)
    seed(days_ago=1)
    cli.main(["history", "--today"])
    out = capsys.readouterr().out
    assert out.count("✓ Complete") == 1
    assert "Today" in out


def test_completion_event_before_any_command(home, clock, capsys):
    cli.main(["start"])
    clock.advance(minutes=26)
    capsys.readouterr()
    cli.main(["stats"])
    out = capsys.readouterr().out
    assert "🍅 SESSION COMPLETE!" in out
    assert "25 minutes focused." in out
    assert "FOCUS JOURNEY" in out
    assert out.index("SESSION COMPLETE") < out.index("FOCUS JOURNEY")


def test_stats_sections(home, clock, seed, capsys):
    seed()
    code = cli.main(["stats"])
    out = capsys.readouterr().out
    assert code == 0
    for section in ("Today", "This week", "All time", "Behavior"):
        assert section in out
    for label in ("Sessions", "Focus time", "Current streak", "Best streak",
                  "Completion rate", "Extensions"):
        assert label in out


def test_week_chart(home, clock, seed, capsys):
    seed(actual_seconds=3600)
    seed(days_ago=1, actual_seconds=1800)
    code = cli.main(["week"])
    out = capsys.readouterr().out
    assert code == 0
    assert "FOCUS — LAST 7 DAYS" in out
    assert "█" * 22 in out  # peak day fills the full width
    assert "1h 00m" in out and "30m" in out


def test_month_chart(home, clock, seed, capsys):
    seed(actual_seconds=3600)
    seed(days_ago=1, actual_seconds=1800)
    code = cli.main(["month"])
    out = capsys.readouterr().out
    assert code == 0
    assert "FOCUS — LAST 30 DAYS" in out
    assert "█" * 42 in out  # peak day fills the full width
    assert "1h 00m" in out and "30m" in out


def test_month_chart_renders_30_rows(home, clock, seed, capsys):
    for offset in (0, 1, 15, 29):
        seed(days_ago=offset, actual_seconds=600)
    cli.main(["month"])
    out = capsys.readouterr().out
    # A data row is a right-justified day-of-month followed by two
    # spaces before the bar column.
    rows = [
        line for line in out.splitlines()
        if len(line) >= 3 and line[:2].strip().isdigit()
    ]
    assert len(rows) == 30
    filled = [line for line in rows if "█" in line]
    assert len(filled) == 4  # exactly the four seeded days


def test_month_chart_labels_day_of_month(home, clock, seed, capsys):
    seed(actual_seconds=600)
    cli.main(["month"])
    out = capsys.readouterr().out
    # Today's day-of-month appears as a row label.
    today_num = str(timer.now().astimezone().date().day)
    assert today_num in out


def test_config_show(home, clock, capsys):
    code = cli.main(["config"])
    out = capsys.readouterr().out
    assert code == 0
    assert "PERIDO CONFIGURATION" in out
    assert "Medium:" in out and "25m" in out
    assert "classic" in out


def test_config_set_and_reset(home, clock, capsys):
    code = cli.main(["config", "set", "focus.short", "20"])
    assert code == 0
    assert "Set focus.short = 20" in capsys.readouterr().out
    code = cli.main(["config", "reset"])
    assert code == 0
    assert "reset to defaults" in capsys.readouterr().out
    cli.main(["config"])
    assert "15m" in capsys.readouterr().out


def test_config_bad_usage(home, clock, capsys):
    code = cli.main(["config", "set", "onlykey"])
    assert code == 1
    assert "Usage:" in capsys.readouterr().err


def test_history_break_rows_carry_no_cycle_tag(home, clock, seed, capsys):
    """Only focus rows show 'Name slot/total'; breaks stay untagged."""
    conn = database.connect()
    plan = [
        {"kind": "focus", "minutes": 25},
        {"kind": "break", "minutes": 5},
    ]
    cycle_id = database.create_cycle(conn, "sprint", plan, 0, clock())
    row = seed(kind="break", minutes=5, cycle_name="sprint", cycle_position=1)
    database.update_session(conn, row["id"], cycle_id=cycle_id)
    conn.close()
    cli.main(["history"])
    out = capsys.readouterr().out
    assert "Sprint" not in out
    assert "✓ Complete" in out


def test_watch_requires_tty(home, clock, capsys):
    code = cli.main(["status", "--watch"])
    assert code == 1
    assert "interactive terminal" in capsys.readouterr().err


def test_no_command_is_required():
    with pytest.raises(SystemExit) as excinfo:
        cli.main([])
    assert excinfo.value.code == 2


def test_clean_label_strips_control_chars():
    assert cli._clean_label("abc\x1b[31mred\x1b[0m") == "abcred"
    assert cli._clean_label("ok\x00\x07") == "ok"
    assert cli._clean_label("plain") == "plain"


def _write_config(contents: str):
    data_dir = database.data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "config.json").write_text(contents, encoding="utf-8")


def test_config_render_sanitizes_cycle_name(home, clock, capsys):
    _write_config('{"cycles": {"\\u001b[31mred\\u001b[0m": [25, 5]}}')
    cli.main(["config"])
    out = capsys.readouterr().out
    assert "red" in out
    assert "\x1b" not in out
    assert "classic" in out  # defaults still present


def test_cycle_banner_sanitizes_name(home, clock, capsys):
    _write_config('{"cycles": {"\\u001b[31mred\\u001b[0m": [25, 5]}}')
    code = cli.main(["cycle", "\x1b[31mred\x1b[0m"])
    out = capsys.readouterr().out
    assert code == 0
    assert "RED POMODORO" in out
    assert "\x1b" not in out


def test_history_sanitizes_cycle_name(home, clock, seed, capsys):
    conn = database.connect()
    plan = [{"kind": "focus", "minutes": 25}]
    cycle_id = database.create_cycle(
        conn, "\x1b[31mred\x1b[0m", plan, 0, clock()
    )
    row = seed(minutes=25, cycle_name="\x1b[31mred\x1b[0m", cycle_position=0)
    database.update_session(conn, row["id"], cycle_id=cycle_id)
    conn.close()
    cli.main(["history"])
    out = capsys.readouterr().out
    assert "Red" in out or "red" in out
    assert "\x1b" not in out


def test_error_message_sanitizes_cycle_name(home, clock, capsys):
    code = cli.main(["cycle", "\x1b[31mExploit\x1b[0m"])
    out = capsys.readouterr().err
    assert code == 1
    assert "Exploit" in out
    assert "\x1b" not in out


def test_idle_block_sanitizes_status(home, clock, seed, capsys):
    seed(status="\x1b[31mHACKED\x1b[0m")
    code = cli.main(["status"])
    out = capsys.readouterr().out
    assert code == 0
    assert "HACKED" in out
    assert "\x1b" not in out


def test_start_rejects_huge_duration(home):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["start", "--duration", "1e300"])
    assert excinfo.value.code == 2


def test_extend_rejects_huge_minutes(home):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["extend", "1e300"])
    assert excinfo.value.code == 2


def test_config_set_rejects_huge_duration(home, capsys):
    code = cli.main(["config", "set", "focus.short", "1e300"])
    assert code == 1
    assert "at most 100000" in capsys.readouterr().err


def test_status_with_garbage_timestamp_exits_cleanly(home, clock, capsys):
    conn = database.connect()
    conn.execute(
        "INSERT INTO sessions"
        " (start_time, end_time, planned_minutes, status, kind)"
        " VALUES (?, ?, ?, ?, ?)",
        ("not-a-date", "also-bad", 25.0, "active", "focus"),
    )
    conn.commit()
    conn.close()
    code = cli.main(["status"])
    err = capsys.readouterr().err
    assert code == 1
    assert "unreadable" in err
    assert "Traceback" not in err


def test_history_with_corrupt_plan_exits_cleanly(home, clock, seed, capsys):
    conn = database.connect()
    cycle_id = database.create_cycle(
        conn, "hostile", [{"kind": "focus", "minutes": 25}], 0, clock()
    )
    conn.execute(
        "UPDATE cycles SET plan = ? WHERE id = ?", ("{not json", cycle_id)
    )
    conn.commit()
    row = seed(minutes=25, cycle_name="hostile", cycle_position=0)
    database.update_session(conn, row["id"], cycle_id=cycle_id)
    conn.close()
    code = cli.main(["history"])
    err = capsys.readouterr().err
    assert code == 1
    assert "unreadable" in err
    assert "Traceback" not in err
