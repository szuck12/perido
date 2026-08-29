# TODO

## In Progress


## Done

- [x] 2026-08-22 — `perido shorten MINUTES` trims an active session,
      recorded across history and stats as trimmed time (#timer, #cli,
      #stats)
- [x] 2026-08-22 — Added `--extrashort` preset (10 min focus / 3 min
      break) (#config, #cli)
- [x] 2026-08-22 — Cycle roster reworked: removed tabata; added monolith,
      summit, and ultra long-block cycles; lengthened clockwork and grind
      to five focus periods (18 cycles total, documented alphabetically)
      (#cycles, #docs)
- [x] 2026-08-22 — README overhaul: consolidated cycle tables into one
      reference with work/break totals and expanded test instructions
      (#docs)
- [x] 2026-08-22 — Release 1.4.0: changelog history restated as releases
      1.0.0 through 1.4.0 (#docs)
- [x] 2026-08-22 — Security audit section added to the code review guide;
      numeric inputs now validate finiteness across argv and config
      parsing (#docs, #config, #cli, #bug)
- [x] 2026-08-26 — `month` command with a bar chart of focus minutes over
      the last 30 days, grouped by month (#stats, #cli, #test)
- [x] 2026-08-28 — Terminal output hardened: control characters and
      escape sequences stripped from config- and state-derived labels
      (#config, #cli, #bug)
- [x] 2026-08-28 — Release 1.4.2: corrupt-database recovery, numeric caps
      for durations, hostile state-file guards, pinned dev dependency,
      SECURITY.md, dependabot, and CI (#docs, #infra, #bug)

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
