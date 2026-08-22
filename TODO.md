# TODO

## In Progress


## Done

- [x] 2026-08-20 — Initial release: passive timer core, cycles, history,
      stats, insights, and config (#timer, #cycles, #stats, #insights, #cli)
- [x] 2026-08-20 — SQLite persistence layer with lazy finalisation and
      crash-safe state (#timer, #infra)
- [x] 2026-08-20 — Fake-clock test harness with isolated data directory
      (#test, #infra)
- [x] 2026-08-22 — Renamed the project from cli-pomodoro to Perido:
      package, command, data directory, database file, and env override
      (#infra, #docs)
- [x] 2026-08-22 — Changelog process rewritten as numbered release steps;
      package version now sourced dynamically from `perido.__version__`
      (#docs, #infra)
- [x] 2026-08-22 — Eleven new shape-based default cycles (16 presets
      total): ladder, descent, twist, clockwork, passion, marathon,
      tabata, warmup, flow, zen, grind (#cycles)
- [x] 2026-08-22 — `perido shorten MINUTES` trims an active session,
      recorded across history and stats as trimmed time (#timer, #cli,
      #stats)

## High Priority

(Important changes that should be done soon.)

## Medium Priority

(Should get done, not urgent.)

## Low Priority

(Nice-to-haves.)

- [ ] Add shell completion scripts for bash/zsh/fish (#cli)

## Ideas

(Interesting ideas not yet committed to implementation.)

- [ ] Custom cycles with user-chosen names — define new named cycles
      (e.g. `perido cycle new "thesis" 45,10,45,15`) instead of only
      adjusting the sixteen built-in presets (#cycles, #cli)
- [ ] Desktop notifications when a session or cycle phase ends (#cli)
- [ ] Export history to CSV for external analysis (#stats)
