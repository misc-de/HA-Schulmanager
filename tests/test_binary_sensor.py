"""Unit tests for binary_sensor.py is_on and extra_state_attributes logic."""

from __future__ import annotations

import sys
from typing import Any


def _bs_mod():
    return sys.modules["custom_components.schulmanager.binary_sensor"]


def _make_sensor(coordinator_data: dict[str, Any] | None, key: str):
    """Build a SchulmanagerBinarySensor with minimal stubs."""
    mod = _bs_mod()

    class _FakeCoordinator:
        last_update_success = True
        data = coordinator_data

    class _FakeEntry:
        entry_id = "test_id"
        title = "Test"

    desc = mod.BINARY_SENSOR_TYPES[key]
    sensor = mod.SchulmanagerBinarySensor.__new__(mod.SchulmanagerBinarySensor)
    sensor.coordinator = _FakeCoordinator()
    sensor._entry = _FakeEntry()
    sensor.entity_description = desc
    return sensor


# ── stale_data ────────────────────────────────────────────────────────────────

def test_stale_data_is_on_when_any_module_stale() -> None:
    sensor = _make_sensor(
        {"meta": {"module_stale": {"schedules": True, "homework": False}}},
        "stale_data",
    )
    assert sensor.is_on is True


def test_stale_data_is_off_when_all_modules_fresh() -> None:
    sensor = _make_sensor(
        {"meta": {"module_stale": {"schedules": False, "homework": False}}},
        "stale_data",
    )
    assert sensor.is_on is False


def test_stale_data_is_off_when_meta_missing() -> None:
    sensor = _make_sensor({}, "stale_data")
    assert sensor.is_on is False


def test_stale_data_is_off_when_coordinator_data_none() -> None:
    sensor = _make_sensor(None, "stale_data")
    assert sensor.is_on is False


# ── module_errors ─────────────────────────────────────────────────────────────

def test_module_errors_is_on_with_real_error() -> None:
    sensor = _make_sensor(
        {"meta": {"module_errors": {"schedules": "TimeoutError: timed out"}}},
        "module_errors",
    )
    assert sensor.is_on is True


def test_module_errors_is_off_when_error_is_only_stale_marker() -> None:
    sensor = _make_sensor(
        {"meta": {"module_errors": {"schedules": "Using last known good data."}}},
        "module_errors",
    )
    assert sensor.is_on is False


def test_module_errors_is_off_with_no_errors() -> None:
    sensor = _make_sensor(
        {"meta": {"module_errors": {}}},
        "module_errors",
    )
    assert sensor.is_on is False


def test_module_errors_is_off_when_meta_missing() -> None:
    sensor = _make_sensor({}, "module_errors")
    assert sensor.is_on is False


# ── extra_state_attributes ────────────────────────────────────────────────────

def test_extra_state_attributes_exposes_meta_fields() -> None:
    sensor = _make_sensor(
        {
            "meta": {
                "module_errors": {"hw": "err"},
                "module_stale": {"hw": True},
                "last_successful_update": "2026-04-28T10:00:00+00:00",
                "last_attempted_update": "2026-04-28T10:01:00+00:00",
            }
        },
        "stale_data",
    )
    attrs = sensor.extra_state_attributes
    assert attrs["module_errors"] == {"hw": "err"}
    assert attrs["module_stale"] == {"hw": True}
    assert attrs["last_successful_update"] == "2026-04-28T10:00:00+00:00"
    assert attrs["last_attempted_update"] == "2026-04-28T10:01:00+00:00"


def test_extra_state_attributes_returns_empty_dicts_when_no_meta() -> None:
    sensor = _make_sensor({}, "module_errors")
    attrs = sensor.extra_state_attributes
    assert attrs["module_errors"] == {}
    assert attrs["module_stale"] == {}
