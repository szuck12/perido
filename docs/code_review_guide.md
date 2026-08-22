# Code Review Guide

An occasional deep-dive architectural review of the perido codebase.
This is **not** a per-commit PR checklist — it is meant to be run before
releases, when a design question arises, or when cross-cutting structural
issues are suspected.

Cadence: before each release, or whenever the codebase undergoes
significant change (new command, state-machine redesign, etc.).

---

## How to Use

Read through each section and examine the actual codebase. Questions are
organised by increasing depth — start with Section 1 and stop if a blocker
is found. Many sections ask for a judgment call rather than a binary
yes/no.

When this guide references another doc in `docs/`, read that doc first to
establish the spec, then check the codebase against it.

---

## 1. Conventions Compliance Audit

Cross-reference the actual codebase against the specifications in the
other documentation files.

### 1a. Docstrings and Comments (docs/commenting_guidelines.md)

- [ ] Every public function has a Google-style docstring with `Args:`,
      `Returns:`, and `Raises:` sections where applicable.
- [ ] Docstrings describe *what* and *why*, not implementation detail.
- [ ] No inline comments that restate the obvious
      (e.g. `# increment i`).
- [ ] 80-character line limit enforced in both code and docstrings.
- [ ] Two blank lines between all top-level functions and classes
      (PEP 8).
- [ ] One blank line between import groups (stdlib, third-party,
      local) if more than one group exists.
- [ ] Block comments used for multi-step algorithms, not single-liners.
- [ ] No stale TODO/FIXME markers left in code (checked against
      `TODO.md`).

### 1b. Type Hints (docs/commenting_guidelines.md)

- [ ] Every function signature has type hints on all parameters and
      the return value.
- [ ] Return types accurately reflect all code paths — e.g. event
      lists that may be empty, `dict | None` cycle lookups.
- [ ] No type information in inline comments that duplicates what
      type hints already express.

### 1c. TODO Lifecycle (docs/maintain_todo.md)

- [ ] All entries use correct Markdown checkbox syntax:
      `- [ ]` for pending, `- [x]` for done.
- [ ] Tags are lowercase, single word, prefixed with `#`, and match
      the approved list (`#timer`, `#cycles`, `#stats`, `#insights`,
      `#cli`, `#config`, `#test`, `#bug`, `#docs`, `#refactor`,
      `#infra`).
- [ ] Items in **Done** that are already recorded in a CHANGELOG
      release have been pruned.
- [ ] No item appears in two sections simultaneously.
- [ ] Open items have a clear next step (not vague).

### 1d. Changelog and Versioning (docs/update_changelog.md)

- [ ] The README version badge matches the latest CHANGELOG entry and
      `perido/__init__.py.__version__`.
- [ ] The most recent version bump matches the type of change:

      | Change type | Bump | Example |
      |-------------|------|---------|
      | New command, new insight rule | MINOR | 0.1.0 → 0.2.0 |
      | Bug fixes, polish | PATCH | 0.2.0 → 0.2.1 |
      | Removed command / breaking output change | MAJOR | 0.x.x → 1.0.0 |

- [ ] Changelog entries include only user-facing changes — no internal
      refactoring or comment-only changes.
- [ ] Each entry is a single concise line from the user's perspective.
- [ ] Changelog date is accurate.

---

## 2. State Machine — Structural Audit

The timer is passive: all transitions happen inside
`timer.finalize_expired()` (and its callers). Every module must obey the
same rules.

### 2a. Time Access

- [ ] No module calls `datetime.now()` directly — everything reads
      `timer.now()`, which tests monkeypatch.
- [ ] Timestamps are stored ISO-8601 UTC; conversion to local time
      happens only at render time (`_local`, `_day_label`, `fmt_tod`).
- [ ] Day-boundary logic (streaks, "Today" filters) uses **local**
      dates, not UTC dates.

### 2b. Lazy Finalisation

- [ ] Every public mutation (`start`, `stop`, `pause`, `resume`,
      `extend`, `shorten`, `skip`, `break`, `cycle`) finalises expired
      sessions first — no zombie active sessions can survive a command.
- [ ] Paused sessions are never auto-completed by finalisation.
- [ ] Finalisation returns an ordered event list; the CLI renders
      events before rendering current state.

### 2c. Cycle Advancement

- [ ] A completed focus step starts the next break automatically;
      a completed break either advances to the next focus step or
      completes the cycle (final break only).
- [ ] Cycles re-sync to real time: exactly one phase completes per
      boundary crossing, and the next phase starts at the return
      moment — no backfilling of missed phases.
- [ ] Stop/skip on a session belonging to a cycle marks the whole
      cycle `abandoned`.
- [ ] A running cycle keeps the plan snapshot it started with;
      editing `cycles.NAME` affects future cycles only.

### 2d. Session Semantics

- [ ] `stop` records partial focus time (`actual_seconds`);
      `skip` records zero and status `skipped`.
- [ ] Completion rate counts `completed / (completed + interrupted)`;
      skips are excluded everywhere except raw history.
- [ ] Focus-time totals include interrupted partials; per-session
      aggregates (average, longest, typical/median) use completed
      sessions only.

---

## 3. Test Coverage

Against the suite in `tests/` (fake clock + isolated `PERIDO_HOME`).

### 3a. Required Categories

| Category | Where | Present? |
|----------|-------|----------|
| Config round-trip (load/save/reset) | `test_config.py` | |
| Invalid config keys/values rejected | `test_config.py` | |
| Schema creation and row helpers | `test_database.py` | |
| Start/stop/pause/resume/extend/shorten/skip lifecycle | `test_timer.py` | |
| Expired-session finalisation (incl. paused) | `test_timer.py` | |
| Cycle advance, completion, abandonment | `test_cycles.py` | |
| Cycle stall-and-resync across boundaries | `test_cycles.py` | |
| Every command's happy path via `cli.main` | `test_cli.py` | |
| Error paths print to stderr with exit 1 | `test_cli.py` | |
| Stats section values with seeded history | `test_stats.py` | |
| Insight gates and message content | `test_insights.py` | |

### 3b. Clock Discipline

- [ ] Tests never sleep; all time movement goes through
      `FakeClock.advance()` / `.set()`.
- [ ] Day-dependent tests use the local-noon anchor clock so they
      pass at any real-world hour.
- [ ] Weekday-relative tests compute offsets from
      `datetime.now().astimezone().weekday()`, not hardcoded dates.

### 3c. Cross-Cutting Concerns

- [ ] Each test gets a fresh data directory (function-scoped
      fixture) — no test can see another's rows.
- [ ] Insights tests suppress earlier rules explicitly (trailing
      interruptions, out-of-week seeding) so the rule under test
      isn't crowded out by the two-insight cap.
- [ ] No test depends on wall-clock ordering of inserts beyond what
      `id` guarantees.

---

## 4. Error Handling and Edge Cases

Systematic sweep of every failure mode across the codebase.

### 4a. Session-Level Errors

- [ ] Starting a session while one is active raises `PeridoError`
      with a helpful message (exit 1, stderr).
- [ ] Stopping/pausing/extending/shortening/skipping with no active
      session errors cleanly.
- [ ] Resuming a non-paused session errors cleanly.
- [ ] Extending by zero or negative minutes is rejected by argparse.
- [ ] Corrupt `config.json` falls back to defaults instead of
      crashing every command.

### 4b. Cycle-Level Errors

- [ ] Unknown cycle name lists the valid names.
- [ ] Cycle plans that don't alternate focus/break (or don't start
      with focus) are rejected at config-set time.
- [ ] Abandoning a cycle mid-phase leaves prior completed phases
      recorded (history keeps them).

### 4c. Data-Layer Errors

- [ ] Missing data directory is created on demand.
- [ ] `PERIDO_HOME` pointing at an unwritable path fails with a
      clear message, not a traceback.
- [ ] No bare `except:` blocks that could swallow real errors.

---

## 5. Cross-Cutting Concerns

### 5a. Rendering Consistency

- [ ] Durations render through `fmt_minutes` (rounded minutes) in
      stats/history and `fmt_span` (exact m/s) in live views — no
      ad-hoc formatting elsewhere.
- [ ] Tables pad columns consistently and trim overlong tags
      (`_trim`).
- [ ] Colour codes wrap whole lines and degrade gracefully when not
      a TTY.

### 5b. Module Boundaries

- [ ] `database.py` performs no business logic; `timer.py` owns the
      session state machine; `cycles.py` owns plan/advance logic;
      `stats.py`/`insights.py` are read-only; `cli.py` only parses,
      renders, and dispatches.
- [ ] `stats.py` imports formatters from `cli.py` lazily inside
      functions (or this circularity has been removed) — flag if the
      dependency graph has grown new cycles.
- [ ] No module other than `database.py` builds SQL strings.

### 5c. Dependency Risk

- [ ] The runtime remains stdlib-only; any proposed runtime
      dependency needs explicit justification.
- [ ] SQLite schema changes ship with a migration story (currently:
      delete the DB — acceptable pre-1.0, revisit later).

---

## 6. Documentation Consistency

Verify that documentation matches the actual code.

### 6a. README Accuracy

- [ ] Command table matches `build_parser()` exactly — no phantom
      commands, none missing.
- [ ] Default duration and cycle tables match `config.DEFAULTS`.
- [ ] Example outputs match actual output (spot-check 3–4).
- [ ] Project structure tree is alphabetical and complete.
- [ ] Version badge matches CHANGELOG.

### 6b. Cross-Reference Integrity

- [ ] All relative links between docs files work.
- [ ] `TODO.md` follows `docs/maintain_todo.md`.
- [ ] `CHANGELOG.md` follows `docs/update_changelog.md`.
- [ ] New entries are appended at the bottom of their TODO section,
      not inserted at the top.

### 6c. Stale or Duplicate Content

- [ ] No section of any doc describes behaviour changed in a later
      version.
- [ ] No doc duplicates content from another doc (cross-reference
      instead).
- [ ] No TODO item describes something already done.

---

## 7. Open-Ended: Creative and Structural Analysis

These questions require judgment and are the heart of the review. They
have no right answer — the goal is to identify improvements and surface
design drift.

### 7a. Module Boundaries and Cohesion

- `cli.py` is the largest module (~620 lines): parsing, rendering,
  and thirteen command handlers. Would splitting rendering helpers
  into a `render.py` reduce cognitive load without fragmenting the
  read-modify-render flow?
- Is the lazy-finalisation contract ("every mutation finalises
  first") documented in one place and enforced by tests, or spread
  as folklore?

### 7b. CLI Design

- Should `history` grow `--kind focus|break` and `--cycle NAME`
  filters as the database grows?
- Are exit codes stable enough for scripting (0 ok, 1 error,
  2 argparse)?
- Would a `perido undo` (revert last transition) be worth its
  complexity?

### 7c. Statistics Accuracy

- The median "typical session" ignores breaks — is that the right
  definition, or should long breaks count?
- Peak-hour windows don't wrap midnight; late-night users get
  split windows. Worth fixing?

### 7d. Test Economics

- The suite runs in under a second; keep it that way. Reject any
  test that sleeps or touches the network.
- Are there behaviours only covered by manual smoke tests (e.g.
  `--watch` redraw) that deserve a pty-based test?

### 7e. Next-Action Synthesis

Based on the findings above, produce a list of the top 3–5 actions.
Each entry must be one of two forms:

1. **Take** — a concrete action that is clearly worthwhile with no
   further debate needed. These can be added directly to `TODO.md`.
2. **Ask** — a question that needs a decision before work proceeds.
   These should be raised to the project owner.

This guide follows the project's commenting conventions
(see `docs/commenting_guidelines.md`): 80-character line limit,
section headers, and minimal inline annotation.
