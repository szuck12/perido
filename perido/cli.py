# cli.py
# Argument parsing, terminal rendering, and the interactive watch loop.

from __future__ import annotations

import argparse
import math
import os
import re
import sqlite3
import sys
import time
from datetime import date, datetime, timedelta, timezone

from . import PeridoError, __version__, cycles, database, insights, stats, timer
from .config import (
    MAX_MINUTES,
    PRESETS,
    load as load_config,
    reset as reset_config,
    resolve_duration,
    set_value,
)

# ---------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------


def _color_enabled() -> bool:
    """Color is on for TTYs unless NO_COLOR is set."""
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def color(text: str, code: str) -> str:
    """Wrap text in an ANSI SGR code when color is enabled."""
    if not _color_enabled():
        return text
    return f"\033[{code}m{text}\033[0m"


def fmt_clock(seconds: float) -> str:
    """Format a countdown as M:SS or H:MM:SS (e.g. 17:34, 1:05:00)."""
    total = max(0, int(round(seconds)))
    if total >= 3600:
        return f"{total // 3600}:{total % 3600 // 60:02d}:{total % 60:02d}"
    return f"{total // 60}:{total % 60:02d}"


def fmt_span(seconds: float) -> str:
    """Format an elapsed span exactly: 2h 05m, 18m 42s, or 45s."""
    total = max(0, int(round(seconds)))
    if total >= 3600:
        return f"{total // 3600}h {total % 3600 // 60:02d}m"
    if total >= 60:
        return f"{total // 60}m {total % 60:02d}s"
    return f"{total}s"


def fmt_minutes(seconds: float) -> str:
    """Format a span rounded to minutes: 2h 05m, 25m, or 0m."""
    minutes = int(round(max(0.0, seconds) / 60))
    if minutes >= 60:
        return f"{minutes // 60}h {minutes % 60:02d}m"
    return f"{minutes}m"


def fmt_tod(moment: datetime) -> str:
    """Format a local wall-clock time like 8:42 PM."""
    return moment.strftime("%I:%M %p").lstrip("0")


def bar(ratio: float, width: int = 20) -> str:
    """Render a filled/empty progress bar."""
    filled = round(max(0.0, min(1.0, ratio)) * width)
    return "█" * filled + "░" * (width - filled)


def _local(moment: datetime) -> datetime:
    """Convert a stored UTC instant to the local zone."""
    return moment.astimezone()


def _day_label(day: date) -> str:
    """Human label for a local date: Today, Yesterday, or Aug 12."""
    today = _local(timer.now()).date()
    if day == today:
        return "Today"
    if day == today - timedelta(days=1):
        return "Yesterday"
    return f"{day.strftime('%b')} {day.day}"


def _trim(value: float) -> str:
    """Show 25.0 as 25 but keep 37.5 as 37.5."""
    return f"{value:g}"


_ANSI_CSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _clean_label(text: str) -> str:
    """Strip ANSI sequences and control chars from display labels."""
    text = _ANSI_CSI.sub("", text)
    return "".join(ch for ch in text if ch.isprintable())


def _focus_slot(steps: list[dict], position: int) -> tuple[int, int]:
    """Map a plan position to its 1-based focus index and focus total."""
    total = sum(1 for step in steps if step["kind"] == "focus")
    index = sum(1 for step in steps[:position] if step["kind"] == "focus")
    return index + 1, total


# ---------------------------------------------------------------------
# Event rendering (lazy completions and cycle transitions)
# ---------------------------------------------------------------------


def render_events(events: list[dict]) -> None:
    """Print finalize_expired() events with blank lines between blocks."""
    for event in events:
        print(_render_event(event))
        print()
        if event["event"] == "complete" and sys.stdout.isatty():
            print("\a", end="", flush=True)


def _render_event(event: dict) -> str:
    if event["event"] == "complete":
        if event["kind"] == "focus":
            minutes = _trim(event["minutes"])
            return f"🍅 SESSION COMPLETE!\n\n{minutes} minutes focused."
        block = "☕ BREAK COMPLETE!"
        if event.get("standalone"):
            block += "\n\nReady for the next focus session."
        return block
    if event["event"] == "phase_start":
        if event["kind"] == "break":
            label = "Long break" if event["final_break"] else "Break"
            return f"☕ {label} started."
        slot, total = _focus_slot_total(event)
        return (
            f"🍅 Focus session {slot} of {total} starting now.\n"
            f"{fmt_clock(event['minutes'] * 60)}"
        )
    if event["event"] == "cycle_complete":
        summary = event["summary"]
        long_breaks = summary["long_breaks"]
        plural = "s" if long_breaks != 1 else ""
        return (
            "🎉 CYCLE COMPLETE!\n"
            "\n"
            f"{summary['focus_sessions']} focus sessions\n"
            f"{_trim(summary['focus_minutes'])} minutes focused\n"
            f"{summary['short_breaks']} short breaks\n"
            f"{long_breaks} long break{plural}"
        )
    return ""


def _focus_slot_total(event: dict) -> tuple[int, int]:
    """Focus numbering derived from flat plan positions in an event."""
    # Focus steps sit at even positions (0, 2, 4, ...) in the plan.
    return (event["position"] // 2 + 1, (event["total"] + 1) // 2)


# ---------------------------------------------------------------------
# Status rendering
# ---------------------------------------------------------------------


def render_status() -> str:
    """Render the current session state (shared by status and watch)."""
    conn = database.connect()
    try:
        session = database.get_active_session(conn)
        if not session:
            return _idle_block(conn)
        paused = bool(session["paused_at"])
        title = (
            "🍅 FOCUSING" if session["kind"] == "focus" else "☕ ON BREAK"
        )
        cycle = database.get_cycle(conn, session["cycle_id"])
        lines = [color(title, "1")]
        steps = None
        if cycle:
            steps = database.json_loads(cycle["plan"])
            if session["kind"] == "focus":
                slot, total = _focus_slot(steps, session["cycle_position"])
                lines.append(f"Focus {slot} of {total}")
        lines.append("")
        lines.append(bar(timer.progress_fraction(session)))
        remaining = fmt_clock(timer.remaining_seconds(session))
        suffix = " remaining (paused)" if paused else " remaining"
        lines.append(remaining + suffix)
        lines.append("")
        started = _local(database.parse_ts(session["start_time"]))
        ends = _local(database.parse_ts(session["end_time"]))
        lines.append(f"Started: {fmt_tod(started)}")
        lines.append(f"Ends:    {fmt_tod(ends)}")
        if cycle:
            nxt = cycles.next_step(cycle, session["cycle_position"])
            if nxt:
                lines.append(f"Next: {_step_label(nxt)}")
        return "\n".join(lines)
    finally:
        conn.close()


def _step_label(step: dict) -> str:
    """Human label for an upcoming cycle step."""
    if step["kind"] == "break":
        if step["final_break"]:
            return "Long break"
        return f"{_trim(step['minutes'])}-minute break"
    return f"Focus {step['slot']} of {step['total']}"


def _idle_block(conn: sqlite3.Connection) -> str:
    """Status body shown when nothing is running."""
    last = database.last_finished_session(conn)
    if not last:
        return (
            "No active Pomodoro.\n\n"
            "No sessions yet — start one with:\n"
            "  perido start"
        )
    started = _local(database.parse_ts(last["start_time"]))
    seconds = last["actual_seconds"] or 0
    return (
        "No active Pomodoro.\n\n"
        "Last session:\n"
        f"{_day_label(started.date())} at {fmt_tod(started)} —"
        f" {fmt_minutes(seconds)} {_clean_label(last['status'])}"
    )


# ---------------------------------------------------------------------
# Watch mode
# ---------------------------------------------------------------------


def watch() -> None:
    """Live full-screen view that drives transitions in real time.

    Ctrl-C only stops watching; the session keeps running in the
    persisted state and any later command picks it up.
    """
    if not sys.stdout.isatty():
        raise PeridoError("--watch requires an interactive terminal.")
    while True:
        try:
            events = timer.finalize_expired()
            sys.stdout.write("\033[2J\033[H")
            render_events(events)
            session = timer.active_session()
            if not session:
                break
            print(render_status())
            time.sleep(1)
        except PeridoError as exc:
            print(color(_clean_label(str(exc)), "31"), file=sys.stderr)
            break
        except KeyboardInterrupt:
            print("\nWatch stopped — your session keeps running.")
            print("Run `perido status` to check on it.")
            break


# ---------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------


def _chosen_preset(args) -> str | None:
    """Return which preset flag was set, if any."""
    for preset in PRESETS:
        if getattr(args, preset):
            return preset
    return None


def cmd_start(args) -> int:
    minutes = resolve_duration("focus", _chosen_preset(args), args.duration)
    session = timer.start(minutes)
    started = _local(database.parse_ts(session["start_time"]))
    ends = _local(database.parse_ts(session["end_time"]))
    print("🍅 Focus session started")
    print("━" * 22)
    print(fmt_clock(minutes * 60))
    print()
    print(f"Started at {fmt_tod(started)}")
    print(f"Ends: {fmt_tod(ends)}")
    if args.watch:
        print()
        watch()
    return 0


def cmd_stop(args) -> int:
    session = timer.stop()
    print("Session stopped.")
    print()
    print(f"Duration: {fmt_span(session['actual_seconds'] or 0)}")
    print("Completed: No")
    progress = round(timer.progress_fraction(session) * 100)
    print(f"Progress: {progress}%")
    return 0


def cmd_pause(args) -> int:
    session = timer.pause()
    print("⏸ Timer paused")
    print(f"{fmt_clock(timer.remaining_seconds(session))} remaining")
    return 0


def cmd_resume(args) -> int:
    session = timer.resume()
    print("▶ Timer resumed")
    print(f"{fmt_clock(timer.remaining_seconds(session))} remaining")
    return 0


def cmd_extend(args) -> int:
    session = timer.extend(args.minutes)
    ends = _local(database.parse_ts(session["end_time"]))
    print(f"⏱ Session extended by {_trim(args.minutes)} minutes.")
    print()
    print(f"New end time: {fmt_tod(ends)}")
    print(f"Time remaining: {fmt_clock(timer.remaining_seconds(session))}")
    return 0


def cmd_shorten(args) -> int:
    session = timer.shorten(args.minutes)
    ends = _local(database.parse_ts(session["end_time"]))
    print(f"⏱ Session shortened by {_trim(args.minutes)} minutes.")
    print()
    print(f"New end time: {fmt_tod(ends)}")
    print(f"Time remaining: {fmt_clock(timer.remaining_seconds(session))}")
    return 0


def cmd_skip(args) -> int:
    timer.skip()
    print("Session skipped.")
    print("No focus time recorded.")
    return 0


def cmd_status(args) -> int:
    if args.watch:
        watch()
    else:
        print(render_status())
    return 0


def cmd_break(args) -> int:
    # Unlike focus sessions (medium default), breaks default to short.
    minutes = resolve_duration(
        "break", _chosen_preset(args) or "short", args.duration
    )
    timer.start(minutes, kind="break")
    print("☕ Break started")
    print()
    print(fmt_clock(minutes * 60))
    if args.watch:
        print()
        watch()
    return 0


def cmd_cycle(args) -> int:
    result = cycles.start(args.name)
    session = result["session"]
    steps = database.json_loads(result["cycle"]["plan"])
    focus_total = sum(1 for step in steps if step["kind"] == "focus")
    title = f"🍅 {_clean_label(args.name).upper()} POMODORO"
    print(color(title, "1"))
    print("─" * max(4, len(title) - 2))
    print()
    print(f"Focus 1 of {focus_total}")
    print(fmt_clock(session["planned_minutes"] * 60))
    if args.watch:
        print()
        watch()
    return 0


def cmd_history(args) -> int:
    since = None
    now_local = _local(timer.now())
    if args.today:
        midnight = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        since = midnight.astimezone(timezone.utc)
    elif args.week:
        midnight = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        since = (midnight - timedelta(days=6)).astimezone(timezone.utc)
    conn = database.connect()
    try:
        rows = database.query_sessions(
            conn,
            since=since,
            statuses=("completed", "interrupted", "skipped"),
            limit=args.limit,
        )
        table = [_history_row(conn, row) for row in rows]
    finally:
        conn.close()
    if not table:
        print("No sessions recorded yet.")
        return 0
    header = ("DATE", "START", "DURATION", "RESULT")
    widths = [
        max(len(header[i]), *(len(row[i]) for row in table)) for i in range(4)
    ]
    rule = "  ".join(header[i].ljust(widths[i]) for i in range(4)).rstrip()
    print(rule)
    print("─" * len(rule))
    for row in table:
        print("  ".join(row[i].ljust(widths[i]) for i in range(4)).rstrip())
    return 0


def _history_row(
    conn: sqlite3.Connection, row: dict
) -> tuple[str, str, str, str]:
    """Build one printable history table row."""
    started = _local(database.parse_ts(row["start_time"]))
    if row["status"] == "completed":
        total = (row["planned_minutes"] + row["extension_minutes"]) * 60
        duration = fmt_minutes(total)
        result = "✓ Complete"
    elif row["status"] == "interrupted":
        duration = fmt_span(row["actual_seconds"] or 0)
        result = "× Interrupted"
    else:
        duration = "—"
        result = "○ Skipped"
    tags = []
    ext = row["extension_minutes"]
    if ext > 0:
        tags.append(f"+{_trim(ext)}m ext")
    elif ext < 0:
        tags.append(f"-{_trim(-ext)}m trimmed")
    cycle = database.get_cycle(conn, row["cycle_id"])
    if cycle and row["kind"] == "focus":
        steps = database.json_loads(cycle["plan"])
        slot, total_focus = _focus_slot(steps, row["cycle_position"])
        name = _clean_label(row["cycle_name"]).title()
        tags.append(f"{name} {slot}/{total_focus}")
    if tags:
        result += "  " + "  ".join(tags)
    return (_day_label(started.date()), fmt_tod(started), duration, result)


def cmd_stats(args) -> int:
    data = stats.collect()
    print(color("FOCUS JOURNEY", "1"))
    print("─" * 28)
    for section, pairs in data.items():
        print()
        print(section)
        width = max(len(label) for label, _ in pairs)
        for label, value in pairs:
            print(f"  {label.ljust(width)}   {value}")
    for message in insights.get_insights():
        print()
        print(message)
    return 0


def cmd_week(args) -> int:
    days = stats.week_bars()
    peak = max((seconds for _, seconds in days), default=0.0)
    width = 22
    print(color("FOCUS — LAST 7 DAYS", "1"))
    print()
    longest_value = max(len(fmt_minutes(seconds)) for _, seconds in days)
    for day, seconds in days:
        blocks = ""
        if peak > 0 and seconds > 0:
            blocks = "█" * max(1, round(seconds / peak * width))
        value = fmt_minutes(seconds).rjust(longest_value)
        print(f"{day.strftime('%a')}  {blocks.ljust(width)}  {value}")
    return 0


def cmd_month(args) -> int:
    days = stats.month_bars()
    peak = max((seconds for _, seconds in days), default=0.0)
    width = 42
    print(color("FOCUS — LAST 30 DAYS", "1"))
    print()
    longest_value = max(len(fmt_minutes(seconds)) for _, seconds in days)
    previous = None
    for day, seconds in days:
        if previous is not None and day.month != previous.month:
            print(f"— {day.strftime('%b %Y')} —")
        previous = day
        blocks = ""
        if peak > 0 and seconds > 0:
            blocks = "█" * max(1, round(seconds / peak * width))
        value = fmt_minutes(seconds).rjust(longest_value)
        print(f"{day.day:>2}  {blocks.ljust(width)}  {value}")
    return 0


def cmd_config(args) -> int:
    parts = args.args
    if not parts:
        print(_render_config(load_config()))
        return 0
    if parts == ["reset"]:
        reset_config()
        print("Configuration reset to defaults.")
        return 0
    if len(parts) == 3 and parts[0] == "set":
        print(set_value(parts[1], parts[2]))
        return 0
    raise PeridoError(
        "Usage:\n"
        "  perido config\n"
        "  perido config set KEY VALUE\n"
        "  perido config reset"
    )


def _render_config(cfg: dict) -> str:
    """Format the configuration screen."""
    names = {
        "extrashort": "Extra-short",
        "short": "Short",
        "medium": "Medium",
        "long": "Long",
        "extralong": "Extra-long",
    }
    lines = [color("PERIDO CONFIGURATION", "1"), ""]
    for section, title in (("focus", "Focus"), ("break", "Break")):
        lines.append(title)
        for preset in PRESETS:
            label = names[preset] + ":"
            lines.append(f"  {label:<13}{_trim(cfg[section][preset])}m")
        lines.append("")
    lines.append("Cycles")
    for name in sorted(cfg["cycles"]):
        plan = "·".join(_trim(step["minutes"]) for step in cfg["cycles"][name])
        lines.append(f"  {_clean_label(name):<12}{plan} min")
    return "\n".join(lines)


# ---------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------


def _positive_minutes(text: str) -> float:
    """Argparse type for positive minute values."""
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{text}' is not a number") from None
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError("must be a positive number of minutes")
    if value > MAX_MINUTES:
        raise argparse.ArgumentTypeError(
            f"must be at most {MAX_MINUTES:g} minutes"
        )
    return value


def _add_duration_flags(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    for preset in PRESETS:
        group.add_argument(
            f"--{preset}",
            action="store_true",
            help=f"use the configured {preset} duration",
        )
    group.add_argument(
        "--duration",
        type=_positive_minutes,
        metavar="MINUTES",
        help="exact duration in minutes",
    )
    parser.add_argument(
        "-w",
        "--watch",
        action="store_true",
        help="stay in the terminal and watch the timer",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="perido",
        description="A command-line Pomodoro timer with named cycles, "
        "focus statistics, insights, and local SQLite storage.",
    )
    parser.add_argument(
        "--version", action="version", version=f"perido {__version__}"
    )
    sub = parser.add_subparsers(
        dest="command", metavar="command", required=True
    )

    p = sub.add_parser("start", help="start a focus session")
    _add_duration_flags(p)
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("stop", help="stop the active session early")
    p.set_defaults(func=cmd_stop)

    p = sub.add_parser("pause", help="pause the active session")
    p.set_defaults(func=cmd_pause)

    p = sub.add_parser("resume", help="resume a paused session")
    p.set_defaults(func=cmd_resume)

    p = sub.add_parser("extend", help="extend the active session")
    p.add_argument("minutes", type=_positive_minutes, metavar="MINUTES")
    p.set_defaults(func=cmd_extend)

    p = sub.add_parser("shorten", help="shorten the active session")
    p.add_argument("minutes", type=_positive_minutes, metavar="MINUTES")
    p.set_defaults(func=cmd_shorten)

    p = sub.add_parser(
        "skip", help="abandon the session without recording focus time"
    )
    p.set_defaults(func=cmd_skip)

    p = sub.add_parser("status", help="show the current session")
    p.add_argument(
        "-w", "--watch", action="store_true", help="live updating view"
    )
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("break", help="take a break")
    _add_duration_flags(p)
    p.set_defaults(func=cmd_break)

    p = sub.add_parser("cycle", help="start a multi-session Pomodoro cycle")
    p.add_argument(
        "name", metavar="NAME", help="cycle name (see `perido config`)"
    )
    p.add_argument(
        "-w",
        "--watch",
        action="store_true",
        help="stay in the terminal and watch the cycle",
    )
    p.set_defaults(func=cmd_cycle)

    p = sub.add_parser("history", help="show recent sessions")
    group = p.add_mutually_exclusive_group()
    group.add_argument(
        "--today", action="store_true", help="only today's sessions"
    )
    group.add_argument("--week", action="store_true", help="the last 7 days")
    p.add_argument(
        "--limit",
        type=int,
        default=20,
        metavar="N",
        help="maximum rows to show",
    )
    p.set_defaults(func=cmd_history)

    p = sub.add_parser("stats", help="show your focus journey")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("week", help="bar chart of the last 7 days")
    p.set_defaults(func=cmd_week)

    p = sub.add_parser("month", help="bar chart of the last 30 days")
    p.set_defaults(func=cmd_month)

    p = sub.add_parser("config", help="show or change configuration")
    p.add_argument(
        "args",
        nargs="*",
        metavar="ARG",
        help="nothing, 'set KEY VALUE', or 'reset'",
    )
    p.set_defaults(func=cmd_config)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns the process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        render_events(timer.finalize_expired())
        return args.func(args) or 0
    except PeridoError as exc:
        print(color(_clean_label(str(exc)), "31"), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
