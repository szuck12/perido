# Maintaining TODO.md

This document describes how to keep `TODO.md` up to date and explains how
it relates to the other project documentation.

## Purpose

`TODO.md` tracks **planned** and **in-progress** work — features that
haven't shipped yet, bugs not yet fixed, ideas still being evaluated. It
looks forward.

For **historical** records of what has already shipped, see `CHANGELOG.md`.

## Sections and Their Lifecycles

| Section | Purpose | Lifecycle |
|---------|---------|-----------|
| **In Progress** | What's actively being worked on. | At most 1–2 items. When an item ships, move it to **Done** and record the release in `CHANGELOG.md`. |
| **Done** | Recently completed items. | Prune periodically — once an item is recorded in a release, it can be removed. |
| **High Priority** | Important changes that should be done soon. | Items arrive here when a clear need is identified (bug, requested feature, etc.). |
| **Medium Priority** | Should get done, not urgent. | Items may be promoted or demoted as priorities shift. |
| **Low Priority** | Nice-to-haves. | Items that are worth doing but have no urgency. |
| **Ideas** | Interesting ideas not yet committed to implementation. | When an idea solidifies into a concrete plan, move it to one of the priority sections. If it's rejected or becomes irrelevant, remove it. |

### Item Flow

```
Ideas → Priority (High/Medium/Low) → In Progress → Done → pruned
```

Items can skip the Ideas stage (e.g. a bug report goes straight to a
priority section). Items can be demoted or removed at any point.

## When to Update

- **A change is requested or a bug is found.** Add an unchecked item
  (`[ ]`) to the appropriate priority section based on importance.
- **An idea comes up.** Add it to **Ideas** with an unchecked box.
- **Work begins.** Move the item to **In Progress**.
- **Work ships.** Move the item to **Done**, check the box (`[x]`), and
  record the change in `CHANGELOG.md` following the
  [changelog process](update_changelog.md).
- **An item is no longer relevant.** Remove it (no need to leave zombie
  entries).

## Relationship to Other Documentation

| File | Role | How It Differs from TODO.md |
|------|------|-----------------------------|
| `CHANGELOG.md` | Records what shipped in each release. | Backward-looking. A TODO item moves here once completed. |
| `update_changelog.md` | Process for version bumps and changelog entries. | Works in tandem: when an item ships, move it in TODO.md *and* record it in CHANGELOG.md. |
| `README.md` | Describes current behaviour for users. | Documents what *is*; TODO.md tracks what *will be*. |

## Entry Conventions

Every entry is a Markdown checkbox list item:

```
- [ ] Brief action-oriented description (#tag)
```

Tags are lowercase, single word, prefixed with `#`. Use any tag that fits;
common ones:

| Tag | When to Use |
|-----|-------------|
| `#timer` | Session lifecycle: start/stop/pause/resume/extend/shorten/skip |
| `#cycles` | Multi-session cycle logic and plans |
| `#stats` | History, statistics, week chart |
| `#insights` | Rule-based insight messages |
| `#cli` | Command-line interface changes |
| `#config` | Configuration keys, presets, persistence |
| `#test` | Test changes (new tests, fixing tests) |
| `#bug` | Bug fixes |
| `#docs` | Documentation changes |
| `#refactor` | Code restructuring without behaviour change |
| `#infra` | Build, packaging, project config |

For completed items, check the box and prefix with the completion date
(`YYYY-MM-DD`):

```
- [x] 2026-08-20 — Initial release: passive timer core, cycles, history,
      stats, insights, and config (#timer, #cycles, #stats, #insights, #cli)
```

### Done Section Pruning

When the **Done** section has **10 or more** items, prune it to at most
**9** items by removing the oldest entries. This keeps the section focused
on recently completed work without accumulating historical noise.

Never remove items from **In Progress**, priority sections, or **Ideas**
— only the Done section is pruned.

Keep descriptions concise but clear enough that someone reading the TODO
understands what the task involves without needing additional context.

### Entry Ordering

New entries are appended at the **bottom** of their section (after any
existing entries), not inserted at the top. This preserves a rough
chronological order within each priority group and avoids merge conflicts
when multiple people add entries in the same session.
