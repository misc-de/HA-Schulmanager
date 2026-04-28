"""Unit tests for coordinator helper logic (no HA runtime required)."""

from __future__ import annotations

import sys
from typing import Any


def _coordinator_module():
    return sys.modules["custom_components.schulmanager.coordinator"]


def _const_module():
    return sys.modules["custom_components.schulmanager.const"]


# ── _module_has_meaningful_data ───────────────────────────────────────────────

def test_mhmd_account_with_full_name() -> None:
    fn = _coordinator_module()._module_has_meaningful_data
    assert fn("account", {"full_name": "Max Mustermann"}) is True


def test_mhmd_account_with_raw_only() -> None:
    fn = _coordinator_module()._module_has_meaningful_data
    assert fn("account", {"raw": "some_raw_data"}) is True


def test_mhmd_account_empty_dict() -> None:
    fn = _coordinator_module()._module_has_meaningful_data
    assert fn("account", {}) is False


def test_mhmd_schedules_today_nonempty() -> None:
    fn = _coordinator_module()._module_has_meaningful_data
    assert fn("schedules", {"today": ["1. Mathe HOM A1.04"]}) is True


def test_mhmd_schedules_week_with_entries() -> None:
    fn = _coordinator_module()._module_has_meaningful_data
    assert fn("schedules", {"week": {"monday": ["1. Mathe"], "tuesday": []}}) is True


def test_mhmd_schedules_empty_week_and_today() -> None:
    fn = _coordinator_module()._module_has_meaningful_data
    assert fn("schedules", {"week": {"monday": [], "tuesday": []}, "today": []}) is False


def test_mhmd_schedules_not_a_dict() -> None:
    fn = _coordinator_module()._module_has_meaningful_data
    assert fn("schedules", None) is False


def test_mhmd_meal_with_today() -> None:
    fn = _coordinator_module()._module_has_meaningful_data
    assert fn("meal", {"today": [{"menu": "Nudeln"}]}) is True


def test_mhmd_meal_with_items() -> None:
    fn = _coordinator_module()._module_has_meaningful_data
    assert fn("meal", {"items": [{"date": "2026-04-28", "menu": "Reis"}]}) is True


def test_mhmd_meal_empty() -> None:
    fn = _coordinator_module()._module_has_meaningful_data
    assert fn("meal", {"today": [], "items": []}) is False


def test_mhmd_generic_items_nonempty() -> None:
    fn = _coordinator_module()._module_has_meaningful_data
    assert fn("homework", {"items": [{"date": "2026-04-28", "entries": ["Mathe: S. 5"]}]}) is True


def test_mhmd_generic_today_nonempty() -> None:
    fn = _coordinator_module()._module_has_meaningful_data
    assert fn("calendar", {"today": [{"date": "2026-04-28", "title": "Schulausflug"}]}) is True


def test_mhmd_generic_empty_dict() -> None:
    fn = _coordinator_module()._module_has_meaningful_data
    assert fn("exams", {"items": [], "today": []}) is False


def test_mhmd_not_a_dict() -> None:
    fn = _coordinator_module()._module_has_meaningful_data
    assert fn("homework", ["not", "a", "dict"]) is False


# ── SchulmanagerCoordinator._merge_with_last_good_data ────────────────────────

def _make_coordinator(modules: list[str] | None = None):
    """Return a coordinator with given modules, no real HA needed."""
    coord_mod = _coordinator_module()
    const_mod = _const_module()

    class _Hass:
        data: dict = {}

    class _Entry:
        entry_id = "entry_test"
        title = "Test"
        options: dict[str, Any] = {
            const_mod.CONF_MODULES: modules or ["account", "schedules"],
            const_mod.CONF_SCAN_INTERVAL: 60,
        }

    class _Client:
        pass

    return coord_mod.SchulmanagerCoordinator(_Hass(), _Entry(), _Client())


def test_merge_fresh_meaningful_data_updates_last_good() -> None:
    coord = _make_coordinator(["account"])
    fresh = {"account": {"full_name": "Lisa Muster"}}
    result = coord._merge_with_last_good_data(fresh)

    assert result["account"]["full_name"] == "Lisa Muster"
    assert coord._last_good_modules["account"] == {"full_name": "Lisa Muster"}
    assert result["meta"]["module_stale"]["account"] is False


def test_merge_falls_back_to_last_good_when_no_fresh_data() -> None:
    coord = _make_coordinator(["homework"])
    coord._last_good_modules["homework"] = {"items": [{"date": "2026-04-25"}], "today": []}

    fresh: dict[str, Any] = {"homework": {}}  # empty → not meaningful
    result = coord._merge_with_last_good_data(fresh)

    assert result["homework"]["items"][0]["date"] == "2026-04-25"
    assert result["meta"]["module_stale"]["homework"] is True
    assert "homework" in result["meta"]["module_errors"]


def test_merge_no_fallback_when_no_history_available() -> None:
    coord = _make_coordinator(["calendar"])
    fresh: dict[str, Any] = {"calendar": {}}  # empty, no history

    result = coord._merge_with_last_good_data(fresh)

    assert result["meta"]["module_stale"]["calendar"] is False
    assert "calendar" not in result["meta"]["module_errors"]


def test_merge_preserves_existing_module_errors_from_fresh() -> None:
    coord = _make_coordinator(["exams"])
    fresh: dict[str, Any] = {
        "exams": {},
        "meta": {"module_errors": {"exams": "Some upstream error"}},
    }
    coord._last_good_modules["exams"] = {"items": [{"date": "2026-05-01", "entry": "Mathe"}], "today": []}

    result = coord._merge_with_last_good_data(fresh)

    assert result["meta"]["module_errors"]["exams"] == "Some upstream error"
    assert result["meta"]["module_stale"]["exams"] is True


def test_merge_always_populates_meta_timestamps() -> None:
    coord = _make_coordinator(["account"])
    coord._last_successful_update = "2026-04-28T10:00:00+00:00"
    coord._last_attempted_update = "2026-04-28T10:01:00+00:00"

    result = coord._merge_with_last_good_data({"account": {"full_name": "X"}})

    assert result["meta"]["last_successful_update"] == "2026-04-28T10:00:00+00:00"
    assert result["meta"]["last_attempted_update"] == "2026-04-28T10:01:00+00:00"


def test_merge_non_dict_fresh_data_treated_as_empty() -> None:
    coord = _make_coordinator(["account"])
    result = coord._merge_with_last_good_data(None)  # type: ignore[arg-type]
    assert "meta" in result
    assert result["meta"]["module_stale"]["account"] is False
