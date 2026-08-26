# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com) and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.1] - 2026-08-26

### Added
- `setup.sh` install script that handles the entire setup including an
  automatic fix for a macOS iCloud Drive issue where the File Provider
  daemon sets the `UF_HIDDEN` flag on `.venv` files, breaking the
  editable install.

### Fixed
- `ModuleNotFoundError: No module named 'perido'` on macOS systems with
  iCloud Drive Desktop & Documents sync enabled. The UF_HIDDEN flag on
  `.venv` files causes Python's `site` module to skip `.pth` files,
  preventing the editable finder from being registered.

## [1.4.0] - 2026-08-22

### Added
- `--extrashort` preset for quick sessions: 10 minutes of focus and
  3-minute breaks by default.
- Three long-form cycles with 100+-minute focus blocks (18 total):
  monolith (one 180-minute block), summit (100·15·100·20), and
  ultra (150·20·150·30).

### Changed
- `clockwork` and `grind` each lengthened to five focus periods.
- Built-in cycles are documented alphabetically in a single consolidated
  reference table showing every period plus work/break totals.
- README test instructions expanded with single-file and single-test
  invocations.
- 169 tests (was 165), covering the extrashort preset and every default
  cycle plan.

### Removed
- `tabata` cycle: its five-minute bursts were too short to plan real
  work around.

## [1.3.0] - 2026-08-21

### Added
- `perido shorten MINUTES` — pulls the active session's end time earlier;
  refuses with a clear error when less time remains than requested.
  Works on standalone sessions, breaks, and cycle phases.
- History rows mark shortened sessions with `-Nm trimmed`, mirroring the
  existing extension tag.
- Eleven new built-in cycles whose names describe their shape (16 total):
  clockwork, descent, flow, grind, ladder, marathon, passion, tabata,
  twist, warmup, and zen.
- 165 tests (was 136), covering shorten semantics, trimmed history tags,
  and every default cycle plan.

### Fixed
- Extension-habit statistics and insights no longer count shortened
  sessions as extensions.

## [1.2.0] - 2026-08-19

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

## [1.1.0] - 2026-08-11

### Added
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

## [1.0.0] - 2026-07-06

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
