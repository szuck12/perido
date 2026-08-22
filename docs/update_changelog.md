# Updating the Changelog

This document describes the process to follow whenever a change is made to
the project. It governs version numbering, changelog entries, README and
TODO updates, and release commits.

## Step 1 — Determine the New Version

Follow [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html):

| Bump | Rule | Example |
|------|------|---------|
| MAJOR | Backward-incompatible changes (removing a command, changing output scripts depend on, incompatible config or database migration) | 1.0.0 → 2.0.0 |
| MINOR | New backward-compatible functionality (new command, flag, cycle preset, insight rule) | 1.0.0 → 1.1.0 |
| PATCH | Bug fixes and small polish that add no functionality | 1.0.0 → 1.0.1 |

When a component is bumped, all components to its right reset to zero
(e.g. 1.2.3 → 2.0.0, 1.2.3 → 1.3.0).

While the project is pre-1.0, MINOR bumps may contain breaking changes —
but note them explicitly under a `### Changed` heading.

Record the choice by setting `__version__` in `perido/__init__.py` — it is
the single source of truth; `pyproject.toml` derives its version from it
automatically, so never pin a static version there.

## Step 2 — Update CHANGELOG.md

Add a new section at the top of `CHANGELOG.md`:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
### Changed
### Deprecated
### Removed
### Fixed
### Security
```

Include only the section headers that have entries. Omit empty sections.
The date is the release date (`YYYY-MM-DD`), not the commit date.

### What to include

- ✅ **User-facing changes** — new commands, flags, cycle presets, output,
    error messages, or changed behaviour of anything documented in the
    README.
- ✅ **Test infrastructure changes** — new fixtures or suites that affect
    how developers validate the project.
- ✅ **Documentation changes** that affect how users or contributors
    interact with the project (README usage sections, this process).
- ❌ **Internal refactoring** — renamed variables, reformatted code, moved
    files without changing behaviour.
- ❌ **Comment or whitespace-only changes** — docstring rewording that
    doesn't change meaning.
- ❌ **Routine test additions** — new test cases for existing behaviour,
    as opposed to infrastructure.
- ❌ **Dependency bumps** that don't change observable behaviour.

Each entry should be a single concise line describing the change from the
user's perspective — what they can now do, or what now behaves correctly.
Mention new/changed test counts only when a feature ships with them.

### Grouping

Group related changes under a single version. Most releases should contain
multiple changes rather than one per version — one release per meaningful
batch of work, not per commit.

## Step 3 — Update README.md

1. **Version badge** — update the badge line under the title:
   `Current version: **X.Y.Z**`

   The README only ever shows the current (latest) release version. Full
   version history lives exclusively in CHANGELOG.md — do not add a
   version list or past releases to the README.

2. **Project structure** — if files were added or removed, update the
   directory tree in the Project Structure section.

3. **Feature documentation** — if commands, flags, cycle presets, or usage
   examples changed, update the relevant sections so the README always
   describes released behaviour.

## Step 4 — Move Shipped Items in TODO.md

Move items that shipped out of TODO.md into its **Done** section with the
release date (see [maintain_todo.md](maintain_todo.md)). Reword any Ideas
or priority entries that described the old state of the project (e.g. "the
five built-in presets") so they stay accurate.

## Step 5 — Commit

First ensure the full test suite passes:

```bash
python3 -m pytest tests/
```

Then create a single commit with the message format:

```
Release X.Y.Z — <brief summary>
```

Example:

```
Release 1.1.0 — Add Bollinger Bands indicator
```
