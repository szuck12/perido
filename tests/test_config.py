# test_config.py
# Tests for configuration defaults, persistence, and validation.

from __future__ import annotations

import copy
import json

import pytest

from perido import PeridoError, config


def test_defaults_when_no_file(home):
    cfg = config.load()
    assert cfg["focus"] == {
        "extrashort": 10,
        "short": 15,
        "medium": 25,
        "long": 50,
        "extralong": 90,
    }
    assert cfg["break"] == {
        "extrashort": 3,
        "short": 5,
        "medium": 10,
        "long": 15,
        "extralong": 30,
    }
    assert cfg["cycles"]["classic"] == [
        {"kind": "focus", "minutes": 25},
        {"kind": "break", "minutes": 5},
        {"kind": "focus", "minutes": 25},
        {"kind": "break", "minutes": 5},
        {"kind": "focus", "minutes": 25},
        {"kind": "break", "minutes": 5},
        {"kind": "focus", "minutes": 25},
        {"kind": "break", "minutes": 15},
    ]


def test_cycle_plan_shapes(home):
    """Every default cycle alternates focus/break starting with focus."""
    cycles = config.load()["cycles"]
    for name, steps in cycles.items():
        kinds = [step["kind"] for step in steps]
        assert kinds[0] == "focus", name
        assert all(a != b for a, b in zip(kinds, kinds[1:])), name
    # Plans ending with focus have no trailing break (short, sprint).
    assert len(cycles["short"]) % 2 == 1
    assert len(cycles["sprint"]) % 2 == 1
    # Classic ends with the long break.
    assert cycles["classic"][-1] == {"kind": "break", "minutes": 15}


def test_save_and_load_roundtrip(home):
    cfg = config.load()
    cfg["focus"]["medium"] = 30
    config.save(cfg)
    assert config.load()["focus"]["medium"] == 30
    assert config.config_path().exists()


def test_corrupt_file_falls_back_to_defaults(home):
    config.config_path().write_text("{not json")
    expected = copy.deepcopy(config.DEFAULTS)
    for name in expected["cycles"]:
        expected["cycles"][name] = config.parse_plan(expected["cycles"][name])
    assert config.load() == expected


def test_invalid_entries_in_file_are_ignored(home):
    config.config_path().write_text(
        json.dumps(
            {
                "focus": {"short": -5, "medium": 40, "bogus": 99},
                "cycles": {"sprint": [10], "broken": "nope"},
                "junk": True,
            }
        )
    )
    cfg = config.load()
    assert cfg["focus"]["short"] == 15  # invalid value ignored
    assert cfg["focus"]["medium"] == 40  # valid override applied
    assert "bogus" not in cfg["focus"]
    assert cfg["cycles"]["sprint"] == [{"kind": "focus", "minutes": 10}]
    assert "broken" not in cfg["cycles"]


def test_non_finite_and_boolean_entries_are_ignored(home):
    config.config_path().write_text(
        json.dumps(
            {
                "focus": {"short": float("nan"), "long": float("inf")},
                "break": {"short": True, "long": False},
                "cycles": {"weird": [float("inf")]},
            }
        )
    )
    cfg = config.load()
    assert cfg["focus"]["short"] == 15
    assert cfg["focus"]["long"] == 50
    assert cfg["break"]["short"] == 5
    assert cfg["break"]["long"] == 15
    assert "weird" not in cfg["cycles"]


def test_set_value_rejects_non_finite(home):
    with pytest.raises(PeridoError):
        config.set_value("focus.medium", "nan")
    with pytest.raises(PeridoError):
        config.set_value("focus.medium", "inf")


def test_reset_restores_defaults(home):
    config.set_value("focus.medium", "42")
    assert config.load()["focus"]["medium"] == 42
    config.reset()
    assert config.load()["focus"]["medium"] == 25


def test_set_value_duration(home):
    message = config.set_value("focus.short", "20")
    assert "focus.short" in message
    assert config.load()["focus"]["short"] == 20


def test_set_value_fractional_duration(home):
    config.set_value("break.long", "12.5")
    assert config.load()["break"]["long"] == 12.5


def test_set_value_rejects_bad_number(home):
    with pytest.raises(PeridoError):
        config.set_value("focus.short", "abc")
    with pytest.raises(PeridoError):
        config.set_value("focus.short", "-3")
    with pytest.raises(PeridoError):
        config.set_value("focus.short", "0")


def test_set_value_rejects_unknown_keys(home):
    with pytest.raises(PeridoError):
        config.set_value("focus.huge", "60")
    with pytest.raises(PeridoError):
        config.set_value("theme.color", "dark")
    with pytest.raises(PeridoError):
        config.set_value("nodot", "1")


def test_set_value_cycle_plan(home):
    config.set_value("cycles.deep", "45,9,45,9")
    plan = config.load()["cycles"]["deep"]
    assert [(s["kind"], s["minutes"]) for s in plan] == [
        ("focus", 45),
        ("break", 9),
        ("focus", 45),
        ("break", 9),
    ]


def test_set_value_rejects_unknown_cycle_name(home):
    with pytest.raises(PeridoError, match="Unknown cycle"):
        config.set_value("cycles.mystery", "10,2")


def test_parse_plan_validation():
    with pytest.raises(PeridoError):
        config.parse_plan([])
    with pytest.raises(PeridoError):
        config.parse_plan(["a", "b"])
    with pytest.raises(PeridoError):
        config.parse_plan([10, 0])
    with pytest.raises(PeridoError):
        config.parse_plan([10, -2])
    with pytest.raises(PeridoError):
        config.parse_plan([float("nan"), 5])
    with pytest.raises(PeridoError):
        config.parse_plan([10, float("inf")])
    assert config.parse_plan([30]) == [{"kind": "focus", "minutes": 30.0}]


def test_resolve_duration_presets_and_exact(home):
    assert config.resolve_duration("focus") == 25
    assert config.resolve_duration("focus", "extrashort") == 10
    assert config.resolve_duration("focus", "long") == 50
    assert config.resolve_duration("break", "extrashort") == 3
    assert config.resolve_duration("break", "extralong") == 30
    assert config.resolve_duration("focus", duration=37) == 37.0


def test_unknown_preset_error_lists_all_presets(home):
    with pytest.raises(PeridoError) as excinfo:
        config.set_value("focus.giant", "120")
    message = str(excinfo.value)
    for preset in ("extrashort", "short", "medium", "long", "extralong"):
        assert f"break.{preset}" in message


def test_resolve_duration_rejects_nonpositive(home):
    with pytest.raises(PeridoError):
        config.resolve_duration("focus", duration=0)
    with pytest.raises(PeridoError):
        config.resolve_duration("focus", duration=-10)


def test_resolve_duration_uses_custom_config(home):
    config.set_value("focus.medium", "35")
    assert config.resolve_duration("focus") == 35
