# Commenting Guidelines

## 1. Module / File Headers

Every `.py` file starts with a brief comment describing the module's purpose.

```python
# timer.py
# Session lifecycle: start, pause/resume, extend/shorten, stop/skip,
# and the lazy finalisation that turns expired rows into results.
```

## 2. Google-Style Docstrings

All public functions, methods, and classes must have a docstring following
the Google style.

```python
def start(minutes: float, kind: str = "focus") -> dict:
    """Start a new session of the given kind.

    Args:
        minutes: Planned length in minutes; must be positive.
        kind: Either "focus" or "break".

    Returns:
        The inserted session row as a dict.

    Raises:
        PeridoError: If a session is already active.
    """
```

- Always include `Args:`, `Returns:`, and `Raises:` when applicable.
- Describe the *what* and *why*, not the implementation detail.

### Attributes

Include an `Attributes:` section in class docstrings for all instance
variables.

```python
class FakeClock:
    """Deterministic stand-in for timer.now() in tests.

    Attributes:
        moment: Current simulated UTC datetime.
    """
```

## 3. Type Hints

Annotate every function signature with type hints. This reduces the need
for inline comments about expected types.

```python
def advance(conn: sqlite3.Connection, cycle_id: str) -> dict | None:
```

## 4. Inline Comments

Use inline comments sparingly. When used, they must explain *why*, not
*what*. For complex blocks of code, inline comments can be used sparingly
to describe what the code is doing.

```python
# Good — explains the reasoning
# Paused sessions never auto-complete: their end time is frozen, so an
# expired pause must not be mistaken for a finished session.
if row["status"] == "paused":
    continue

# Bad — states the obvious
if row["status"] == "paused":  # check if status is paused
    continue
```

## 5. Block Comments

For multi-step algorithms or complex logic, use block comments above the
code block.

```python
# -------------------------------------------------------------------
# Lazy finalisation
# 1. Find active sessions whose end time has passed
# 2. Mark them completed (or advance their cycle)
# 3. Return the events so the CLI can render transitions
# -------------------------------------------------------------------
```

## 6. TODO / FIXME Markers

Standardize markers for incomplete or flagged code.

```python
# TODO(szuck12): support half-minute durations in cycle plans
# FIXME: midnight wrap-around in peak-hour windows
```

## 7. Deprecation Annotation

Mark deprecated functions with a `Deprecated:` section in the docstring
and a `warnings.warn` call.

```python
import warnings


def old_start() -> None:
    """Start a session the old way.

    Deprecated:
        Use `start()` instead. Will be removed in v1.0.
    """
    warnings.warn("old_start is deprecated, use start", DeprecationWarning, stacklevel=2)
```

## 8. Line Length / Formatting

Restrict all comments, docstrings, and code to **80 characters maximum**.

- Break long inline comments onto a separate line above the code.
- Wrap docstring lines to stay under the limit.
- Use parentheses or backslashes for implicit line continuation when needed.

```python
# Good — broken before 80 chars
remaining = end - now
# The grace window keeps streaks unbroken when a session finishes just
# after midnight local time.

# Bad — exceeds limit
remaining = end - now  # this comment goes way past 80 characters and should be broken up
```

## 9. Note / Warning Callouts

Use `Note:` and `Warning:` in docstrings to flag edge cases or important
caveats.

```python
def finalize_expired() -> list[dict]:
    """Complete any sessions whose end time has passed.

    Note:
        Paused sessions are never finalised here — resuming shifts
        their end time by the paused duration instead.

    Warning:
        Callers must render the returned events in order; cycle
        phase-start events assume their completion event was shown
        first.
    """
```

## 10. What NOT to Comment

- Self-documenting code (e.g. `total = focus + break  # calculate total`)
- Obvious control flow (e.g. `i += 1  # increment i`)
- Type information already covered by type hints

## 11. Vertical Spacing

Use blank lines to separate logical sections for readability.

- **Two blank lines** between top-level definitions (functions,
  classes) — standard PEP 8.
- **One blank line** between import groups (stdlib, third-party,
  local).
- **One blank line** between separate logical phases within a
  function or `__main__` block (e.g. parse, dispatch, render).

```python
def cmd_stop(args) -> int:
    """Stop the active session early."""
    events = timer.finalize_expired()
    render_events(events)

    session = timer.stop()
    print(f"Session stopped.")
    return 0
```

## 12. README Project Structure Tree

The file tree in the **Project Structure** section of `README.md` must
list files in alphabetical order within each directory. This avoids PR
drift where new files are appended at the end.

When adding a new file to the tree:
- Insert it in the correct alphabetical position, not at the end.
- Match the indentation style of neighbouring entries.
