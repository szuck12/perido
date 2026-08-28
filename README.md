# Perido

Current version: **1.5.0** — [Changelog](CHANGELOG.md)

A local-first Pomodoro timer for the command line. Start focus sessions and
breaks, run multi-session cycles, and watch your focus journey take shape
through history, statistics, and gentle insights. There is no daemon, no
background process, and no network access — every command reads the timer's
state from a small SQLite database on disk, so the timer survives terminal
crashes, reboots, and days away from the machine.

```
$ perido start
🍅 Focus session started
━━━━━━━━━━━━━━━━━━━━━━
25:00

Started at 10:58 PM
Ends: 11:23 PM

$ perido status
🍅 FOCUSING

████████████░░░░░░░░
17:34 remaining

Started: 10:58 PM
Ends:    11:23 PM
```

## How It Works

The timer is a **passive state machine** — nothing ever runs in the
background:

1. **Write.** Starting a session, break, or cycle inserts one row into the
   SQLite database with its planned end time; the process then exits.
2. **Finalize lazily.** Every command first checks for sessions whose end
   time has passed and completes them: results are recorded, cycle phases
   advance starting from *now* (missed time is never backfilled), and
   finished cycles close with a summary.
3. **Report.** The command then prints the current state.

If you start a 25-minute session and close the laptop, returning an hour
later shows the session completed and — if you were in a cycle — the next
phase already started.

## Installation

Requires Python 3.10+ (tested on 3.12). No third-party runtime dependencies.

### Quick install

```bash
git clone https://github.com/szuck12/perido.git perido
cd perido
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install .
```

Verify:

```bash
perido --version               # perido 1.4.1
```

`requirements.txt` installs pytest for running the test suite; it is not
needed to use the tool itself.

### Development (editable install)

If you plan to modify perido's source code, use an editable install so
changes take effect immediately:

```bash
./setup.sh                     # handles macOS iCloud UF_HIDDEN fix
source .venv/bin/activate
```

The `setup.sh` script creates a venv, runs `pip install -e .`, and
automatically fixes a macOS iCloud Drive issue that can break editable
installs (see Troubleshooting below).

## Command-Line Usage

### Sessions

| Command | Description |
|---------|-------------|
| `perido start` | Start a focus session (medium length by default) |
| `perido break` | Take a break (short break by default) |
| `perido stop` | Stop the active session early; partial time still counts |
| `perido pause` | Pause the active session (pausing freezes the end time) |
| `perido resume` | Resume a paused session |
| `perido extend MINUTES` | Push the end time later by MINUTES |
| `perido shorten MINUTES` | Pull the end time earlier by MINUTES (error if less remains) |
| `perido skip` | Abandon the session without recording any focus time |
| `perido status` | Show the current session, or why there isn't one |

`start` and `break` accept a preset flag (`--extrashort`, `--short`,
`--medium`, `--long`, `--extralong`) or an exact duration (`--duration 40`).
With no flag they use the configured medium duration — except `break`,
which defaults to short.

Add `-w` / `--watch` to `start`, `break`, `cycle`, or `status` to stay in
the terminal and watch the timer count down live. Ctrl-C stops watching
only; the session keeps running.

### Cycles

A cycle is a named sequence of alternating focus and break steps. When a
focus step ends, the next break starts automatically, and so on until the
final step completes the cycle.

| Command | Description |
|---------|-------------|
| `perido cycle NAME` | Start cycle NAME (see table below) |
| `perido config` | List available cycles and their plans |

Built-in cycles — each name describes its plan's shape:

| Cycle | Plan (minutes) | Work | Break | Total |
|-------|----------------|------|-------|-------|
| `classic` | 25, 5, 25, 5, 25, 5, 25, 15 | 1h 40m | 30m | 2h 10m |
| `clockwork` | 20, 5, 20, 5, 20, 5, 20, 5, 20 | 1h 40m | 20m | 2h |
| `deep` | 50, 10, 50, 10, 50, 30 | 2h 30m | 50m | 3h 20m |
| `descent` | 40, 5, 25, 5, 15 | 1h 20m | 10m | 1h 30m |
| `extended` | 90, 20, 90, 30 | 3h | 50m | 3h 50m |
| `flow` | 60, 10, 60 | 2h | 10m | 2h 10m |
| `grind` | 25, 3, 25, 3, 25, 3, 25, 3, 25 | 2h 05m | 12m | 2h 17m |
| `ladder` | 10, 2, 20, 3, 30, 5 | 1h | 10m | 1h 10m |
| `marathon` | 30, 5, 30, 5, 30, 5, 30, 5, 30, 5, 30, 20 | 3h | 45m | 3h 45m |
| `monolith` | 180 | 3h | 0m | 3h |
| `passion` | 60 | 1h | 0m | 1h |
| `short` | 15, 5, 15, 5, 15 | 45m | 10m | 55m |
| `sprint` | 10, 2, 10, 2, 10 | 30m | 4m | 34m |
| `summit` | 100, 15, 100, 20 | 3h 20m | 35m | 3h 55m |
| `twist` | 45, 10, 15, 5, 45, 10 | 1h 45m | 25m | 2h 10m |
| `ultra` | 150, 20, 150, 30 | 5h | 50m | 5h 50m |
| `warmup` | 10, 5, 15, 5 | 25m | 10m | 35m |
| `zen` | 45, 5, 45, 5, 45 | 2h 15m | 10m | 2h 25m |

Stopping or skipping mid-cycle abandons the rest of that cycle. Cycles
never backfill missed time: if you walk away mid-cycle, one phase completes
at its boundary and the next phase starts when you return.

### History and Statistics

| Command | Description |
|---------|-------------|
| `perido history` | Recent sessions table (`--today`, `--week`, `--limit N`) |
| `perido stats` | Your focus journey: today, this week, all time, behaviour |
| `perido week` | Bar chart of focus minutes over the last 7 days |
| `perido month` | Bar chart of focus minutes over the last 30 days |

`stats` also prints up to two short insights — streaks, weekly completion
rate, extension habits, peak focus hours, weakest weekday — once enough
history exists to make them meaningful.

### Configuration

| Command | Description |
|---------|-------------|
| `perido config` | Show current configuration |
| `perido config set KEY VALUE` | Change one value |
| `perido config reset` | Restore all defaults |

### Example Session

```bash
# A quick 10-minute focus sprint
perido start --extrashort

# Check what is running and how long is left
perido status

# Need more time? Push the end out five minutes
perido extend 5

# Wrapping up sooner than planned? Pull the end in three minutes
perido shorten 3

# Stop now — the minutes already completed still count
perido stop

# Take a break with the 3-minute preset
perido break --extrashort

# Or run the full classic Pomodoro day, watched live
perido cycle classic -w

# Review your progress
perido history --today
perido stats
perido week
perido month

# Tune defaults without editing any files
perido config set focus.medium 30
perido config set cycles.sprint 15,3,15
```

## Configuration

### Durations

Five presets are available for both focus and breaks. Adjust any of them:

```bash
perido config set focus.medium 30     # default focus becomes 30 min
perido config set break.short 3       # short breaks become 3 min
```

Defaults:

| Preset | Focus | Break |
|--------|-------|-------|
| `extrashort` | 10 min | 3 min |
| `short` | 15 min | 5 min |
| `medium` | 25 min | 10 min |
| `long` | 50 min | 15 min |
| `extralong` | 90 min | 30 min |

### Cycle Lengths

Cycles are comma-separated lists of step lengths in minutes. They must
alternate focus/break and start with focus; the last step's break counts as
the long break. The default plans are listed in the Cycles table above.

Adjust any built-in cycle by rewriting its plan:

```bash
perido config set cycles.classic 30,5,30,5,30,5,30,20
perido config set cycles.sprint 15,3,15
```

The change applies to cycles started afterwards; running cycles keep the
plan they started with.

## Where Data Lives

Everything is stored locally — no accounts, no sync, no telemetry.

| Platform | Location |
|----------|----------|
| macOS | `~/Library/Application Support/perido/` |
| Linux | `${XDG_DATA_HOME:-~/.local/share}/perido/` |
| Windows | `%APPDATA%\perido\` |

Two files: `perido.db` (sessions and cycles) and `config.json`
(overrides). Delete them to start fresh. Set `PERIDO_HOME` to relocate
the whole directory (useful for testing):

```bash
PERIDO_HOME=/tmp/demo perido start
```

## Troubleshooting

| Message | Meaning and fix |
|---------|-----------------|
| `A Pomodoro session is already active.` | Only one session can run at a time. Check `perido status`, then `stop`, `skip`, or wait it out. |
| `No active Pomodoro session.` | `stop` / `pause` / `extend` / `shorten` / `skip` need a running session. |
| `Cannot shorten by N minutes — ...` | The session has less time left than requested. Use a smaller number, or `extend` first if you meant to reshape it. |
| `No paused Pomodoro session to resume.` | The session isn't paused. Check `perido status`. |
| `Timer is already paused.` | Nothing is ticking right now. `resume` continues the session. |
| `No active Pomodoro session to pause.` | Pause needs a running session; start one first. |
| `Unknown cycle 'name'.` | Run `perido config` to list valid cycle names. |
| `Unknown key. Valid keys: ...` | Config keys are dotted presets like `focus.long` or `cycles.classic`. |
| `--watch requires an interactive terminal.` | `--watch` needs a real TTY; run it directly in your shell. |
| `ModuleNotFoundError: No module named 'perido'` | This only affects editable installs (`pip install -e .`) on macOS with iCloud Drive sync enabled. iCloud's File Provider sets the `UF_HIDDEN` flag on `.venv` files, causing Python to skip the editable finder. Fix: `chflags -R nohidden .venv` then reinstall with `pip install -e .`. Or use `./setup.sh` which handles this automatically. Alternatively, use a non-editable install (`pip install .`) which is not affected. |

## Project Structure

```
perido/
├── CHANGELOG.md                   # Version history and release notes.
├── LICENSE                        # MIT license.
├── README.md                      # This file.
├── TODO.md                        # Planned work, priorities, and ideas
│                                  # (see docs/maintain_todo.md).
├── setup.sh                       # One-command install script (handles
│                                  # macOS iCloud UF_HIDDEN fix).
├── docs/
│   ├── code_review_guide.md       # Pre-release architectural audit checklist.
│   ├── commenting_guidelines.md   # Docstring and inline comment conventions.
│   ├── maintain_todo.md           # How to keep TODO.md up to date.
│   └── update_changelog.md        # Numbered release and changelog workflow.
├── perido/
│   ├── __init__.py                # Package marker: __version__ and PeridoError.
│   ├── cli.py                     # Argument parsing, terminal rendering, and
│   │                              # the interactive watch loop.
│   ├── config.py                  # Configuration defaults, JSON persistence,
│   │                              # and duration resolution.
│   ├── cycles.py                  # Cycle presets and the focus/break
│   │                              # transition state machine.
│   ├── database.py                # SQLite persistence layer: data directory,
│   │                              # schema, sessions, and cycles.
│   ├── insights.py                # Deterministic, rule-based observations
│   │                              # about the user's focus history.
│   ├── stats.py                   # Focus journey statistics: daily, weekly,
│   │                              # all-time, and behavioural.
│   └── timer.py                   # Session lifecycle state machine: start,
│                                  # pause, resume, extend, shorten, stop,
│                                  # skip, and lazy finalization of expired
│                                  # sessions.
├── pyproject.toml                 # Packaging; version sourced dynamically
│                                  # from perido.__version__.
├── requirements.txt               # Test-only dependency: pytest.
└── tests/
    ├── conftest.py                # Shared fixtures: isolated data directory,
    │                              # fake clock, session seeder.
    ├── test_cli.py                # Command dispatch, rendering, flag
    │                              # handling, and error output.
    ├── test_config.py             # Defaults, persistence, key/value validation.
    ├── test_cycles.py             # Plans, automatic transitions, abandonment,
    │                              # and recovery.
    ├── test_database.py           # Schema, queries, and finalization
    │                              # primitives.
    ├── test_insights.py           # Trigger conditions for each insight rule.
    ├── test_stats.py              # Streaks, completion rates, hours, and
    │                              # weekday aggregates.
    ├── test_timer.py              # Session semantics including extend,
    │                              # shorten, and pause behaviour.
    └── test_version.py            # Installed metadata matches __version__.
```

## Tests

Run the full suite:

```bash
pip install -r requirements.txt
python3 -m pytest tests/
```

Run a single test file:

```bash
python3 -m pytest tests/test_timer.py
```

Run one test by node id or keyword:

```bash
python3 -m pytest tests/test_timer.py::test_shorten_pulls_end_time_earlier
python3 -m pytest tests/test_timer.py -k shorten
```

Add `-v` for verbose output. The suite uses a fake clock and an isolated
data directory, so it never touches your real data and always finishes in
under a second.

## License

[MIT](LICENSE) — Copyright (c) 2026 Sam Zuckerman
