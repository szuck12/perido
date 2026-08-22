# Perido

Current version: **0.3.0** — [Changelog](CHANGELOG.md)

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

The timer is a **passive state machine**. `perido start` writes a session
row with an end time; nothing runs in the background. Every subsequent
command first checks the database for sessions whose end time has passed,
finalises them (recording completions, advancing cycles), and then reports
the current state. If you start a 25-minute session and close the laptop,
returning an hour later shows the session completed and — if you were in a
cycle — the next phase already started.

## Installation

Requires Python 3.10+ (tested on 3.12). No third-party runtime dependencies.

```bash
git clone https://github.com/szuck12/perido.git perido
cd perido
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
```

Verify:

```bash
perido --version               # perido 0.3.0
```

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

`start` and `break` accept a preset flag (`--short`, `--medium`, `--long`,
`--extralong`) or an exact duration (`--duration 40`). With no flag they use
the configured medium duration — except `break`, which defaults to short.

Add `-w` / `--watch` to `start`, `break`, or `status` to stay in the
terminal and watch the timer count down live. Ctrl-C stops watching only;
the session keeps running.

### Cycles

A cycle is a named sequence of alternating focus and break steps. When a
focus step ends, the next break starts automatically, and so on until the
final step completes the cycle.

| Command | Description |
|---------|-------------|
| `perido cycle NAME` | Start cycle NAME (see table below) |
| `perido config` | List available cycles and their plans |

Built-in cycles — each name describes its plan's shape:

| Cycle | Plan (focus · break minutes) | Character |
|-------|------------------------------|-----------|
| `classic` | 25·5·25·5·25·5·25·15 | The standard Pomodoro day |
| `short` | 15·5·15·5·15 | Three gentle sessions |
| `sprint` | 10·2·10·2·10 | Tight bursts, minimal breaks |
| `deep` | 50·10·50·10·50·30 | Long stretches of concentration |
| `extended` | 90·20·90·30 | Two marathon blocks |
| `ladder` | 10·2·20·3·30·5 | Focus climbs each round |
| `descent` | 40·5·25·5·15 | Winds down to a close |
| `twist` | 45·10·15·5·45·10 | Alternates long and short |
| `clockwork` | 20·5·20·5·20·5·20 | Metronomic uniform blocks |
| `passion` | 60 | One immersive focus block |
| `marathon` | 30·5 repeated, closing with 30·20 | Six sessions, ~3 hours |
| `tabata` | 5·1·5·1·5·1·5·1 | High-intensity micro-bursts |
| `warmup` | 10·5·15·5 | A gentle entry into work |
| `flow` | 60·10·60 | Two long, connected blocks |
| `zen` | 45·5·45·5·45 | Deep work, barely interrupted |
| `grind` | 25·3·25·3·25 | Steady slog, short breathers |

Stopping or skipping mid-cycle abandons the rest of that cycle. Cycles
never backfill missed time: if you walk away mid-cycle, one phase completes
at its boundary and the next phase starts when you return.

### History and Statistics

| Command | Description |
|---------|-------------|
| `perido history` | Recent sessions table (`--today`, `--week`, `--limit N`) |
| `perido stats` | Your focus journey: today, this week, all time, behaviour |
| `perido week` | Bar chart of focus minutes over the last 7 days |

`stats` also prints up to two short insights — streaks, weekly completion
rate, extension habits, peak focus hours, weakest weekday — once enough
history exists to make them meaningful.

### Configuration

| Command | Description |
|---------|-------------|
| `perido config` | Show current configuration |
| `perido config set KEY VALUE` | Change one value |
| `perido config reset` | Restore all defaults |

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
| `short` | 15 min | 5 min |
| `medium` | 25 min | 10 min |
| `long` | 50 min | 15 min |
| `extralong` | 90 min | 30 min |

### Cycle Lengths

Cycles are comma-separated lists of step lengths in minutes. They must
alternate focus/break and start with focus; the last step's break counts as
the long break. Defaults:

| Cycle | Plan | Total |
|-------|------|-------|
| `classic` | 25, 5, 25, 5, 25, 5, 25, 15 | 2h 10m |
| `short` | 15, 5, 15, 5, 15 | 55m |
| `sprint` | 10, 2, 10, 2, 10 | 34m |
| `deep` | 50, 10, 50, 10, 50, 30 | 3h 20m |
| `extended` | 90, 20, 90, 30 | 3h 50m |
| `ladder` | 10, 2, 20, 3, 30, 5 | 1h 10m |
| `descent` | 40, 5, 25, 5, 15 | 1h 30m |
| `twist` | 45, 10, 15, 5, 45, 10 | 2h 10m |
| `clockwork` | 20, 5, 20, 5, 20, 5, 20 | 1h 35m |
| `passion` | 60 | 1h |
| `marathon` | 30, 5, 30, 5, 30, 5, 30, 5, 30, 5, 30, 20 | 3h 45m |
| `tabata` | 5, 1, 5, 1, 5, 1, 5, 1 | 24m |
| `warmup` | 10, 5, 15, 5 | 35m |
| `flow` | 60, 10, 60 | 2h 10m |
| `zen` | 45, 5, 45, 5, 45 | 2h 25m |
| `grind` | 25, 3, 25, 3, 25 | 1h 21m |

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
| `No paused Pomodoro session to resume.` | The session isn't paused. |
| `Unknown cycle 'name'.` | Run `perido config` to list valid cycle names. |
| `Unknown key. Valid keys: ...` | Config keys are dotted presets like `focus.long` or `cycles.classic`. |
| `--watch requires an interactive terminal.` | `--watch` needs a real TTY; run it directly in your shell. |

## Project Structure

```
perido/
├── CHANGELOG.md
├── LICENSE
├── README.md
├── TODO.md
├── docs/
│   ├── code_review_guide.md
│   ├── commenting_guidelines.md
│   ├── maintain_todo.md
│   └── update_changelog.md
├── perido/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── cycles.py
│   ├── database.py
│   ├── insights.py
│   ├── stats.py
│   └── timer.py
├── pyproject.toml
├── requirements.txt
└── tests/
    ├── conftest.py
    ├── test_cli.py
    ├── test_config.py
    ├── test_cycles.py
    ├── test_database.py
    ├── test_insights.py
    ├── test_stats.py
    ├── test_timer.py
    └── test_version.py
```

## Tests

```bash
pip install -r requirements.txt
python3 -m pytest tests/
```

The suite uses a fake clock and an isolated data directory, so it never
touches your real data and always finishes in under a second.

## License

[MIT](LICENSE) — Copyright (c) 2026 Sam Zuckerman
