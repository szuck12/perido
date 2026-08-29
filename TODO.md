# TODO

## In Progress


## Done

- [x] 2026-08-28 — CI lint and audit tooling pinned (`ruff==0.16.5`,
      `pip-audit==2.10.1`); lint findings fixed against ruff 0.16.5's
      expanded default rules (#infra, #test)
- [x] 2026-08-28 — README test instructions now run from the project
      `.venv`, matching what `setup.sh` creates (#docs)
- [x] 2026-08-28 — Release 1.4.3: reproducible CI tooling and venv-based
      test docs (#docs, #infra)

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
      adjusting the eighteen built-in presets (#cycles, #cli)
- [ ] Desktop notifications when a session or cycle phase ends (#cli)
- [ ] Export history to CSV for external analysis (#stats)
