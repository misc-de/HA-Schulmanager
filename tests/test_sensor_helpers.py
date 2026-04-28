"""Unit tests for sensor.py pure helper functions."""

from __future__ import annotations

import sys


def _sensor():
    return sys.modules["custom_components.schulmanager.sensor"]


# ── _truncate_state ───────────────────────────────────────────────────────────

def test_truncate_state_within_limit() -> None:
    fn = _sensor()._truncate_state
    short = "hello"
    assert fn(short) == "hello"


def test_truncate_state_exactly_at_limit() -> None:
    fn = _sensor()._truncate_state
    at_limit = "x" * 255
    assert fn(at_limit) == at_limit


def test_truncate_state_above_limit_adds_ellipsis() -> None:
    fn = _sensor()._truncate_state
    too_long = "a" * 300
    result = fn(too_long)
    assert len(result) == 255
    assert result.endswith("…")


def test_truncate_state_strips_trailing_space_before_ellipsis() -> None:
    fn = _sensor()._truncate_state
    # Pad to 256 chars so it's one over; the 255th char becomes a space
    # The function rstrips before appending the ellipsis
    value = "a" * 253 + "   extra"  # total > 255
    result = fn(value)
    assert not result[:-1].endswith(" ")
    assert result.endswith("…")


# ── _join_lines ───────────────────────────────────────────────────────────────

def test_join_lines_empty_list() -> None:
    fn = _sensor()._join_lines
    assert fn([]) == "Keine Einträge"


def test_join_lines_single_item() -> None:
    fn = _sensor()._join_lines
    assert fn(["1. Mathe HOM A1.04"]) == "1. Mathe HOM A1.04"


def test_join_lines_multiple_items_joined_with_pipe() -> None:
    fn = _sensor()._join_lines
    result = fn(["1. Mathe", "2. Deutsch"])
    assert result == "1. Mathe | 2. Deutsch"


def test_join_lines_filters_blank_strings() -> None:
    fn = _sensor()._join_lines
    result = fn(["Mathe", "", "  ", "Deutsch"])
    assert result == "Mathe | Deutsch"


def test_join_lines_truncates_long_result() -> None:
    fn = _sensor()._join_lines
    items = ["x" * 50] * 10  # would produce 500+ chars joined
    result = fn(items)
    assert len(result) <= 255


# ── _meal_lines ───────────────────────────────────────────────────────────────

def test_meal_lines_dict_items_with_menu() -> None:
    fn = _sensor()._meal_lines
    items = [{"menu": "Menü 1: Nudeln\n\nMenü 2: Salat"}, {"menu": "Menü 1: Reis"}]
    result = fn(items)
    assert len(result) == 2
    assert "Nudeln" in result[0]
    assert "Salat" in result[0]
    assert "Reis" in result[1]


def test_meal_lines_skips_items_without_menu_key() -> None:
    fn = _sensor()._meal_lines
    items = [{"date": "2026-04-28"}, {"menu": "Nudeln"}]
    result = fn(items)
    assert result == ["Nudeln"]


def test_meal_lines_handles_string_items() -> None:
    fn = _sensor()._meal_lines
    result = fn(["Nudeln", "  ", "Reis"])
    assert result == ["Nudeln", "Reis"]


def test_meal_lines_empty_menu_string_skipped() -> None:
    fn = _sensor()._meal_lines
    result = fn([{"menu": "   "}])
    assert result == []


def test_meal_lines_empty_list() -> None:
    fn = _sensor()._meal_lines
    assert fn([]) == []


# ── _week_summary ─────────────────────────────────────────────────────────────

def test_week_summary_shows_first_two_lessons_per_day() -> None:
    fn = _sensor()._week_summary
    week = {
        "monday": ["1. Mathe", "2. Deutsch", "3. Englisch"],
        "tuesday": ["1. Bio"],
        "wednesday": [],
    }
    result = fn(week)
    assert "Mo: 1. Mathe, 2. Deutsch …" in result
    assert "Di: 1. Bio" in result
    assert "Mi: -" in result


def test_week_summary_empty_week() -> None:
    fn = _sensor()._week_summary
    result = fn({})
    assert result == "Keine Einträge"


def test_week_summary_translates_german_day_names() -> None:
    fn = _sensor()._week_summary
    week = {"Montag": ["1. Mathe"], "Dienstag": []}
    result = fn(week)
    assert "Mo:" in result
    assert "Di:" in result


# ── _week_formatted ───────────────────────────────────────────────────────────

def test_week_formatted_one_day_with_lessons() -> None:
    fn = _sensor()._week_formatted
    week = {"monday": ["1. Mathe HOM", "2. Deutsch SAL"]}
    result = fn(week)
    assert "Mo: 1. Mathe HOM | 2. Deutsch SAL" in result


def test_week_formatted_empty_day_shows_placeholder() -> None:
    fn = _sensor()._week_formatted
    week = {"monday": []}
    result = fn(week)
    assert "Mo: Keine Einträge" in result


def test_week_formatted_multiline_output() -> None:
    fn = _sensor()._week_formatted
    week = {"monday": ["Mathe"], "tuesday": ["Bio"]}
    lines = fn(week).splitlines()
    assert len(lines) == 2


# ── _week_rows ────────────────────────────────────────────────────────────────

def test_week_rows_creates_correct_number_of_rows() -> None:
    fn = _sensor()._week_rows
    week = {
        "monday": ["1. Mathe", "2. Deutsch", "3. Englisch"],
        "tuesday": ["1. Bio"],
    }
    rows = fn(week)
    assert len(rows) == 3  # max of all day lengths


def test_week_rows_fills_missing_slots_with_empty_string() -> None:
    fn = _sensor()._week_rows
    week = {"monday": ["1. Mathe", "2. Deutsch"], "tuesday": ["1. Bio"]}
    rows = fn(week)
    assert rows[1]["Di"] == ""  # tuesday only has 1 lesson


def test_week_rows_adds_lesson_number_field() -> None:
    fn = _sensor()._week_rows
    week = {"monday": ["A", "B", "C"]}
    rows = fn(week)
    assert [r["lesson"] for r in rows] == ["1", "2", "3"]


def test_week_rows_empty_week_returns_empty_list() -> None:
    fn = _sensor()._week_rows
    assert fn({}) == []


def test_week_rows_resolves_both_english_and_german_day_keys() -> None:
    fn = _sensor()._week_rows
    # German keys should also be found
    week = {"Montag": ["Mathe"], "Dienstag": ["Bio"]}
    rows = fn(week)
    assert len(rows) == 1
    assert rows[0]["Mo"] == "Mathe"
    assert rows[0]["Di"] == "Bio"
