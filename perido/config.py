# config.py
# Configuration defaults, JSON persistence, and duration resolution.

from __future__ import annotations

import copy
import json
import math
from typing import Any

from . import PeridoError, database

PRESETS = ("extrashort", "short", "medium", "long", "extralong")

# Longest accepted duration in minutes (~69 days, far beyond any use) so
# oversized values are rejected before they can overflow time arithmetic.
MAX_MINUTES = 100_000

DEFAULTS: dict[str, Any] = {
    "focus": {
        "extrashort": 10,
        "short": 15,
        "medium": 25,
        "long": 50,
        "extralong": 90,
    },
    "break": {
        "extrashort": 3,
        "short": 5,
        "medium": 10,
        "long": 15,
        "extralong": 30,
    },
    "cycles": {
        # Alternating focus/break minutes, always starting with focus.
        # Each preset name describes its plan's shape.
        "classic": [25, 5, 25, 5, 25, 5, 25, 15],
        "clockwork": [20, 5, 20, 5, 20, 5, 20, 5, 20],
        "deep": [50, 10, 50, 10, 50, 30],
        "descent": [40, 5, 25, 5, 15],
        "extended": [90, 20, 90, 30],
        "flow": [60, 10, 60],
        "grind": [25, 3, 25, 3, 25, 3, 25, 3, 25],
        "ladder": [10, 2, 20, 3, 30, 5],
        "marathon": [30, 5, 30, 5, 30, 5, 30, 5, 30, 5, 30, 20],
        "monolith": [180],
        "passion": [60],
        "short": [15, 5, 15, 5, 15],
        "sprint": [10, 2, 10, 2, 10],
        "summit": [100, 15, 100, 20],
        "twist": [45, 10, 15, 5, 45, 10],
        "ultra": [150, 20, 150, 30],
        "warmup": [10, 5, 15, 5],
        "zen": [45, 5, 45, 5, 45],
    },
}


def config_path():
    """Return the path to the user's configuration file."""
    return database.data_dir() / "config.json"


def parse_plan(steps) -> list[dict[str, Any]]:
    """Parse an alternating minute list into cycle steps.

    Args:
        steps: Sequence of positive numbers alternating focus and break
            minutes, always starting with a focus step. An odd length
            ends with focus; an even length ends with a break.

    Returns:
        List of step dicts with "kind" ("focus" or "break") and
        "minutes" keys.

    Raises:
        PeridoError: If the list is empty, non-numeric, or contains
            a non-positive value.
    """
    try:
        values = [float(value) for value in steps]
    except (TypeError, ValueError):
        raise PeridoError(
            "Cycle steps must be comma-separated numbers, e.g. 25,5,25,5"
        ) from None
    if not values:
        raise PeridoError("A cycle needs at least one focus step.")
    if any(value <= 0 or not math.isfinite(value) for value in values):
        raise PeridoError("Cycle steps must be positive numbers of minutes.")
    if any(value > MAX_MINUTES for value in values):
        raise PeridoError(
            f"Cycle steps must be at most {MAX_MINUTES:g} minutes."
        )
    return [
        {"kind": "focus" if index % 2 == 0 else "break", "minutes": value}
        for index, value in enumerate(values)
    ]


def load() -> dict[str, Any]:
    """Load configuration, merging saved values over the defaults.

    Unknown or invalid entries in the file are ignored so that a
    hand-edited config can never break the application.
    """
    cfg = copy.deepcopy(DEFAULTS)
    # Normalize default plans into step dicts so callers always see the
    # same shape whether values came from defaults or the user file.
    for name in list(cfg["cycles"]):
        cfg["cycles"][name] = parse_plan(cfg["cycles"][name])
    path = config_path()
    if not path.exists():
        return cfg
    try:
        user = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return cfg
    if not isinstance(user, dict):
        return cfg
    for section in ("focus", "break"):
        values = user.get(section)
        if isinstance(values, dict):
            for key in PRESETS:
                value = values.get(key)
                if (
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and math.isfinite(value)
                    and value > 0
                ):
                    cfg[section][key] = value
    cycles = user.get("cycles")
    if isinstance(cycles, dict):
        for name, steps in cycles.items():
            try:
                cfg["cycles"][name] = parse_plan(steps)
            except PeridoError:
                continue
    return cfg


def save(cfg: dict[str, Any]) -> None:
    """Write configuration back to disk as readable JSON.

    Args:
        cfg: The configuration dict to persist.

    Note:
        Cycle plans are stored as plain alternating minute lists
        (e.g. [25, 5, 25, 5]) regardless of their in-memory shape, so
        the file format stays simple for hand editing.
    """
    stored = copy.deepcopy(cfg)
    for name, steps in stored["cycles"].items():
        if steps and isinstance(steps[0], dict):
            stored["cycles"][name] = [step["minutes"] for step in steps]
    path = config_path()
    path.write_text(json.dumps(stored, indent=2) + "\n", encoding="utf-8")


def reset() -> None:
    """Restore default configuration and persist it."""
    save(copy.deepcopy(DEFAULTS))


def _number(raw: str, label: str) -> float:
    """Parse a positive number, raising a friendly error otherwise."""
    try:
        value = float(raw)
    except ValueError:
        raise PeridoError(f"{label} must be a number (got '{raw}').") from None
    if not math.isfinite(value) or value <= 0:
        raise PeridoError(f"{label} must be positive (got {value:g}).")
    if value > MAX_MINUTES:
        raise PeridoError(f"{label} must be at most {MAX_MINUTES:g} minutes.")
    return value


def set_value(key: str, raw: str) -> str:
    """Set one configuration value and persist the file.

    Args:
        key: Dotted key such as "focus.short" or "cycles.classic".
        raw: Raw string value; a positive number for durations,
            comma-separated numbers for cycle plans.

    Returns:
        A human-readable confirmation line.

    Raises:
        PeridoError: If the key or value is invalid.
    """
    cfg = load()
    parts = key.split(".")
    if len(parts) != 2:
        raise PeridoError(_key_help())
    section, name = parts
    if section in ("focus", "break"):
        if name not in PRESETS:
            raise PeridoError(
                f"Unknown preset '{name}'."
                f" Use one of: {', '.join('focus.' + p for p in PRESETS)},"
                f" {', '.join('break.' + p for p in PRESETS)}."
            )
        value = _number(raw, f"{section}.{name}")
        cfg[section][name] = int(value) if value == int(value) else value
        shown = f"{value:g}"
    elif section == "cycles":
        if name not in cfg["cycles"]:
            known = ", ".join(sorted(cfg["cycles"]))
            raise PeridoError(f"Unknown cycle '{name}'. Known cycles: {known}.")
        cfg["cycles"][name] = parse_plan(raw.split(","))
        shown = raw.replace(",", ", ")
    else:
        raise PeridoError(_key_help())
    save(cfg)
    return f"Set {section}.{name} = {shown}"


def _key_help() -> str:
    """Build the list of valid configuration keys for error messages."""
    duration_keys = ", ".join(
        f"{section}.{preset}"
        for section in ("focus", "break")
        for preset in PRESETS
    )
    cycle_keys = ", ".join(
        f"cycles.{name}" for name in sorted(DEFAULTS["cycles"])
    )
    return f"Unknown key. Valid keys:\n  {duration_keys}\n  {cycle_keys}"


def resolve_duration(
    kind: str, preset: str | None = None, duration: float | None = None
) -> float:
    """Resolve a focus/break duration in minutes.

    Args:
        kind: "focus" or "break".
        preset: One of PRESETS, or None for the medium default.
        duration: Exact duration in minutes; takes priority over preset.

    Returns:
        The duration in minutes.

    Raises:
        PeridoError: If an exact duration is not positive.
    """
    if duration is not None:
        if not math.isfinite(duration) or duration <= 0:
            raise PeridoError("Duration must be a positive number of minutes.")
        if duration > MAX_MINUTES:
            raise PeridoError(
                f"Duration must be at most {MAX_MINUTES:g} minutes."
            )
        return float(duration)
    return float(load()[kind][preset or "medium"])
