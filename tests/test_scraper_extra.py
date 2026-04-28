"""Additional unit tests for scraper_client pure helpers."""

from __future__ import annotations

from datetime import date
import importlib.util
from pathlib import Path
import sys
from typing import Any


MODULE_PATH = Path(__file__).parents[1] / "addons" / "schulmanager_bridge" / "scraper_client.py"


def load_scraper_module():
    spec = importlib.util.spec_from_file_location("scraper_client_under_test2", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ── _ddmmyyyy_to_iso ──────────────────────────────────────────────────────────

def test_ddmmyyyy_to_iso_typical_date() -> None:
    module = load_scraper_module()
    assert module.SchulmanagerClient._ddmmyyyy_to_iso("25.04.2026") == "2026-04-25"


def test_ddmmyyyy_to_iso_single_digit_day_month() -> None:
    module = load_scraper_module()
    assert module.SchulmanagerClient._ddmmyyyy_to_iso("1.3.2026") == "2026-03-01"


def test_ddmmyyyy_to_iso_strips_whitespace() -> None:
    module = load_scraper_module()
    assert module.SchulmanagerClient._ddmmyyyy_to_iso("  7.11.2026  ") == "2026-11-07"


def test_ddmmyyyy_to_iso_raises_on_bad_format() -> None:
    module = load_scraper_module()
    import pytest
    with pytest.raises(ValueError):
        module.SchulmanagerClient._ddmmyyyy_to_iso("2026-04-25")


def test_ddmmyyyy_to_iso_raises_on_too_few_parts() -> None:
    module = load_scraper_module()
    import pytest
    with pytest.raises(ValueError):
        module.SchulmanagerClient._ddmmyyyy_to_iso("25.04")


# ── _strip_tags ───────────────────────────────────────────────────────────────

def test_strip_tags_removes_all_html() -> None:
    module = load_scraper_module()
    result = module.SchulmanagerClient._strip_tags("<p>Hello <b>World</b></p>")
    assert result == "Hello World"


def test_strip_tags_collapses_whitespace() -> None:
    module = load_scraper_module()
    result = module.SchulmanagerClient._strip_tags("<div>  foo   bar  </div>")
    assert result == "foo bar"


def test_strip_tags_empty_string() -> None:
    module = load_scraper_module()
    assert module.SchulmanagerClient._strip_tags("") == ""


def test_strip_tags_no_tags() -> None:
    module = load_scraper_module()
    assert module.SchulmanagerClient._strip_tags("plain text") == "plain text"


# ── _clean_plain_text ─────────────────────────────────────────────────────────

def test_clean_plain_text_joins_lines_with_newline() -> None:
    module = load_scraper_module()
    result = module.SchulmanagerClient._clean_plain_text("line1\nline2\nline3")
    assert result == "line1\nline2\nline3"


def test_clean_plain_text_single_line_joins_with_space() -> None:
    module = load_scraper_module()
    result = module.SchulmanagerClient._clean_plain_text("line1\nline2", single_line=True)
    assert result == "line1 line2"


def test_clean_plain_text_collapses_inner_spaces() -> None:
    module = load_scraper_module()
    result = module.SchulmanagerClient._clean_plain_text("  foo   bar  ")
    assert result == "foo bar"


def test_clean_plain_text_drops_blank_lines() -> None:
    module = load_scraper_module()
    result = module.SchulmanagerClient._clean_plain_text("a\n\n\nb")
    assert result == "a\nb"


def test_clean_plain_text_decodes_html_entities() -> None:
    module = load_scraper_module()
    result = module.SchulmanagerClient._clean_plain_text("foo &amp; bar")
    assert result == "foo & bar"


# ── _extract_german_date edge cases ───────────────────────────────────────────

def test_extract_german_date_two_digit_year_gets_2000_added() -> None:
    module = load_scraper_module()
    result = module.SchulmanagerClient._extract_german_date("Termin am 15.6.26")
    assert result == date(2026, 6, 15)


def test_extract_german_date_returns_none_when_no_match() -> None:
    module = load_scraper_module()
    assert module.SchulmanagerClient._extract_german_date("no date here") is None


def test_extract_german_date_returns_none_for_invalid_date() -> None:
    module = load_scraper_module()
    # 32.13.2026 is not a valid date
    assert module.SchulmanagerClient._extract_german_date("32.13.2026") is None


# ── _collect_exams ────────────────────────────────────────────────────────────

_EXAMS_NO_TABLE_HTML = "<div>Keine Klausuren</div>"

_EXAMS_HTML = """<table class="exams-table">
<tr ><th>Fach</th><th>Datum</th><th>Zeit</th></tr>
<tr class="row"><td><strong class="subj">Mathematik</strong></td>
<td class="date">
Freitag, 25.04.
2026
</td>
<td><br>08:00</td>
<td>- 09:30
</td>
</tr></table>"""


def test_collect_exams_no_table_returns_empty() -> None:
    module = load_scraper_module()
    client = module.SchulmanagerClient("user", "pw")
    result = client._collect_exams(_EXAMS_NO_TABLE_HTML)
    assert result == {"items": [], "today": []}


def test_collect_exams_parses_exam_entry() -> None:
    module = load_scraper_module()
    client = module.SchulmanagerClient("user", "pw")
    result = client._collect_exams(_EXAMS_HTML)
    assert len(result["items"]) == 1
    assert result["items"][0]["date"] == "2026-04-25"
    assert "Mathematik" in result["items"][0]["entry"]
    assert "08:00" in result["items"][0]["entry"]


# ── _collect_meal ─────────────────────────────────────────────────────────────

_MEAL_NO_TILE_HTML = "<div>Keine Mensa-Daten</div>"

_MEAL_HTML = (
    '<div class="tile-header"><!---->\nSpeiseplan\n</div>\n'
    "<u>Montag, 28.04.2026</u>\n"
    "<strong>Menü 1: </strong>Nudeln\n"
    "<u>Dienstag, 29.04.2026</u>\n"
    "<strong>Menü 1: </strong>Reis\n"
)


def test_collect_meal_no_speiseplan_tile_returns_empty() -> None:
    module = load_scraper_module()
    client = module.SchulmanagerClient("user", "pw")
    result = client._collect_meal(_MEAL_NO_TILE_HTML)
    assert result == {"items": [], "today": []}


def test_collect_meal_parses_items() -> None:
    module = load_scraper_module()
    client = module.SchulmanagerClient("user", "pw")
    result = client._collect_meal(_MEAL_HTML)
    assert len(result["items"]) == 2
    assert result["items"][0]["date"] == "2026-04-28"
    assert "Menü 1" in result["items"][0]["menu"]
    assert "Nudeln" in result["items"][0]["menu"]


# ── _collect_activities ───────────────────────────────────────────────────────

_ACTIVITIES_NO_MARKER_HTML = "<div>Kein Dashboard</div>"

_ACTIVITIES_HTML = (
    "Kommende Termine\n"
    '<strong class="header">\n'
    "Freitag, 25.04.2026\n"
    "</strong>\n"
    '<div class="col-2 time-col">\n'
    "14:30\n"
    "line2\n"
    "line3\n"
    "line4\n"
    "line5\n"
    "             AG Volleyball\n"
    "</div>\n"
    "</widgets-container>"
)


def test_collect_activities_no_marker_returns_empty() -> None:
    module = load_scraper_module()
    client = module.SchulmanagerClient("user", "pw")
    result = client._collect_activities(_ACTIVITIES_NO_MARKER_HTML)
    assert result == {"items": [], "today": []}


def test_collect_activities_parses_ag_entry() -> None:
    module = load_scraper_module()
    client = module.SchulmanagerClient("user", "pw")
    result = client._collect_activities(_ACTIVITIES_HTML)
    assert len(result["items"]) == 1
    assert result["items"][0]["date"] == "2026-04-25"
    assert any("Volleyball" in e for e in result["items"][0]["entries"])


# ── _module_error_result ──────────────────────────────────────────────────────

def test_module_error_result_account() -> None:
    module = load_scraper_module()
    client = module.SchulmanagerClient("testuser", "pw")
    data: dict[str, Any] = {}
    err = ValueError("network error")
    result = client._module_error_result(data, "account", err)
    assert result["full_name"] == "testuser"
    assert "error" in result
    assert "meta" in data
    assert "account" in data["meta"]["module_errors"]


def test_module_error_result_schedules() -> None:
    module = load_scraper_module()
    client = module.SchulmanagerClient("user", "pw")
    data: dict[str, Any] = {}
    result = client._module_error_result(data, "schedules", RuntimeError("timeout"))
    assert result["week"] == {}
    assert isinstance(result["today"], list)
    assert "error" in result


def test_module_error_result_generic_module() -> None:
    module = load_scraper_module()
    client = module.SchulmanagerClient("user", "pw")
    data: dict[str, Any] = {}
    result = client._module_error_result(data, "homework", Exception("oops"))
    assert result["items"] == []
    assert result["today"] == []
    assert "error" in result
