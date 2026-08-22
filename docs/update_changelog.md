# Updating the Changelog

This document describes when and how to update `CHANGELOG.md`, and how
version numbers are chosen.

## Principles

Every change falls into one of two buckets: it either gets a changelog
entry, or it doesn't.

✅ **Include:**

- User-facing changes — new commands, flags, output, error messages, or
  changed behaviour of anything documented in the README.
- Test-infrastructure changes contributors would notice, e.g. a new
  shared fixture or a rewritten test runner.
- Documentation changes affecting how users or contributors interact
  with the project (README usage sections, this process,
  `maintain_todo.md`).

❌ **Exclude:**

- Internal refactoring — renamed variables, moved files, reformatted
  code with no behaviour change.
- Comment-only or whitespace-only changes, including docstring rewording
  that doesn't change meaning.
- Routine test additions or tweaks (as opposed to infrastructure
  changes).
- Dependency bumps that don't change observable behaviour.

One release per meaningful batch of work — not per commit.

## Version Numbering (Semantic Versioning)

Given a version `MAJOR.MINOR.PATCH`:

| Change type | Bump | Examples |
|-------------|------|----------|
| Bug fix, typo fix, small polish | PATCH | 0.1.0 → 0.1.1 |
| New feature, new command flag, new insight rule | MINOR | 0.1.1 → 0.2.0 |
| Breaking change: removed command, changed output format scripts depend on, incompatible config or database migration | MAJOR | 0.2.x → 1.0.0 |

When one component is bumped, every component to its right resets to
zero: `0.2.3 → 0.3.0`, `0.2.3 → 1.0.0`.

While the project is pre-1.0, MINOR bumps may contain breaking changes —
but note them explicitly under a `### Changed` heading.

## The `[Unreleased]` Section

Entries accumulate under `## [Unreleased]` at the top of `CHANGELOG.md`
as work merges, organised into the section headings described below. At
release time the section is promoted: its heading becomes
`[X.Y.Z] - YYYY-MM-DD`, and a fresh empty `## [Unreleased]` takes its
place above the new release. A release must never ship while entries are
still marked Unreleased.

## Entry Format

The format follows [Keep a Changelog](https://keepachangelog.com). Each
release looks like:

```markdown
## [0.2.0] - 2026-09-14

### Added
- `perido extend` now accepts fractional minutes.

### Fixed
- Week chart no longer mislabels days during DST shifts.
```

Rules:

- Sections used, in this order: `Added`, `Changed`, `Deprecated`,
  `Removed`, `Fixed`, `Security`. Omit empty ones.
- Each bullet is one concise line from the **user's perspective** — what
  they can now do, or what now behaves correctly.
- The date is the release date (`YYYY-MM-DD`), not the commit date.
- Mention new/changed test counts only when a feature ships with them.

Group related changes under a single version. Most releases should
contain several entries rather than being cut for each individual
change.

## Release Checklist

1. Ensure the full test suite passes: `python3 -m pytest tests/`.
2. Bump `__version__` in `perido/__init__.py`. Reset any components to
   the right of the bumped one.
3. Promote the `[Unreleased]` section in `CHANGELOG.md`: rename its
   heading to `[X.Y.Z] - <release date>` and start a fresh empty
   `## [Unreleased]` above it.
4. Update `README.md`:
   - Version badge on line 3 (`Current version: **X.Y.Z**`) to match.
   - Project Structure tree if files were added, removed, or renamed.
   - Usage sections if CLI syntax, options, or examples changed.
5. Move shipped items from `TODO.md`'s **Done** section if not already
   there (see [maintain_todo.md](maintain_todo.md)).
6. Commit the release as a single commit:

   ```
   Release X.Y.Z — <brief summary>
   ```

   For example:

   ```
   Release 0.2.0 — Add fractional-minute extends
   ```

## Relationship to Other Documentation

| File | Role |
|------|------|
| `TODO.md` | Forward-looking; items move out of it into the changelog when they ship. |
| `README.md` | Must always describe the released behaviour; its version badge mirrors the latest entry here. |
