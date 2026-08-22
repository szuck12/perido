# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com) and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-08-22

### Changed
- Project renamed from cli-pomodoro to **Perido**: the package, the
  `perido` command, the data directory (`~/Library/Application Support/perido/`
  and equivalents), the `perido.db` database file, and the `PERIDO_HOME`
  environment override. Existing data migrates by copying `pomodoro.db`
  and `config.json` into the new directory.
- Changelog release process rewritten as a numbered step-by-step guide in
  `docs/update_changelog.md`.
- Packaging derives its version dynamically from `perido.__version__`,
  removing the duplicate static version pin in `pyproject.toml`.

## [0.1.0] - 2026-08-20

### Added
- Passive Pomodoro timer with no daemon: every command reads state from a
  local SQLite database and lazily finalises sessions whose end time has
  passed, so the timer survives crashes and reboots.
- Focus sessions and breaks with four configurable presets (short, medium,
  long, extralong) plus exact `--duration` overrides; pause/resume,
  extend, stop (partial credit), and skip (no time recorded).
- Named multi-session cycles (`classic`, `short`, `sprint`, `deep`,
  `extended`) that auto-advance through alternating focus/break phases and
  complete with a summary; stopping or skipping mid-cycle abandons the rest.
- Live `--watch` mode for `start`, `break`, `cycle`, and `status`.
- `history` table with day labels, results, extension and cycle tags, and
  `--today` / `--week` / `--limit` filters.
- `stats` journey view — today, this week, all-time, and behaviour sections
  including streaks, completion rate, best hour/weekday, typical session,
  and extension totals.
- `week` bar chart of focus minutes over the last seven days.
- Rule-based insights (max two per run): completion streaks, weekly
  completion rate, extension habits, peak focus hours, weakest weekday.
- `config show/set/reset` for durations and cycle plans, persisted to
  `config.json`; `PERIDO_HOME` override for relocating all data.
- 135 tests covering config, database, timer, cycles, CLI rendering,
  statistics, and insights on a fake clock.
