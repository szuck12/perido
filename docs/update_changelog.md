# Updating the Changelog

This document describes when and how to update `CHANGELOG.md`, and how
version numbers are chosen.

## Principles

- Every user-facing change gets a changelog entry.
- Internal refactors, comment-only changes, and test-only tweaks do **not**
  get entries (unless they change test infrastructure in a way contributors
  would notice, e.g. a new shared fixture).
- One release per meaningful batch of work — not per commit.

## Version Numbering (Semantic Versioning)

Given a version `MAJOR.MINOR.PATCH`:

| Change type | Bump | Examples |
|-------------|------|----------|
| Bug fix, typo fix, small polish | PATCH | 0.1.0 → 0.1.1 |
| New feature, new command flag, new insight rule | MINOR | 0.1.1 → 0.2.0 |
| Breaking change: removed command, changed output format scripts depend on, incompatible config or database migration | MAJOR | 0.2.x → 1.0.0 |

While the project is pre-1.0, MINOR bumps may contain breaking changes —
but note them explicitly under a `### Changed` heading.

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

## Release Checklist

1. Ensure the full test suite passes: `python3 -m pytest tests/`.
2. Bump `__version__` in `perido/__init__.py`.
3. Add the release section at the **top** of `CHANGELOG.md` (below the
   header, above previous releases).
4. Update the version badge on line 3 of `README.md`
   (`Current version: **X.Y.Z**`) to match.
5. Move shipped items from `TODO.md`'s **Done** section if not already
   there (see [maintain_todo.md](maintain_todo.md)).
6. Commit the release as a single commit, e.g. `Release 0.2.0`.

## Relationship to Other Documentation

| File | Role |
|------|------|
| `TODO.md` | Forward-looking; items move out of it into the changelog when they ship. |
| `README.md` | Must always describe the released behaviour; its version badge mirrors the latest entry here. |
