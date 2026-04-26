"""Unit tests for Schulmanager bridge parser helpers."""

from __future__ import annotations

from datetime import date
import importlib.util
from pathlib import Path
import sys
from typing import Any


MODULE_PATH = Path(__file__).parents[1] / "addons" / "schulmanager_bridge" / "scraper_client.py"


def load_scraper_module():
    spec = importlib.util.spec_from_file_location("scraper_client_under_test", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_extract_german_date_from_mixed_markup() -> None:
    module = load_scraper_module()

    parsed = module.SchulmanagerClient._extract_german_date(
        'Freitag, 24.04.2026 </div><div class="tile-body">'
    )

    assert parsed == date(2026, 4, 24)


def test_homework_html_parser_keeps_only_recent_items() -> None:
    module = load_scraper_module()
    client = module.SchulmanagerClient("user", "password")
    stats: dict[str, bool | int | str] = {
        "html_tiles_seen": 0,
        "html_without_date": 0,
        "html_older_than_cutoff": 0,
        "html_without_entries": 0,
    }

    result = client._parse_homework_html(
        """
        <div class="tile"><div class="tile-header"> Freitag, 24.04.2026 </div>
          <div class="tile-body">
            <div><h4>Lateinisch ab Kl. 7</h4>
              <p class="homework-paragraph"><span style="white-space: pre-wrap;">AB zum Wortschatz
Berichtigung KA</span></p>
            </div>
            <div><h4>Deutsch</h4>
              <p class="homework-paragraph"><span style="white-space: pre-wrap;">S. 122 Nr 2</span></p>
            </div>
          </div>
        </div>
        <div class="tile"><div class="tile-header"> Mittwoch, 22.04.2026 </div>
          <div class="tile-body">
            <div><h4>Mathematik</h4>
              <p class="homework-paragraph"><span style="white-space: pre-wrap;">S. 153|5
Und die Aufgabe aus dem Unterricht zu Ende</span></p>
            </div>
          </div>
        </div>
        <div class="tile"><div class="tile-header"> Dienstag, 24.03.2026 </div>
          <div class="tile-body">
            <div><h4>Deutsch</h4>
              <p class="homework-paragraph"><span style="white-space: pre-wrap;">-/-</span></p>
            </div>
          </div>
        </div>
        """,
        cutoff=date(2026, 4, 11),
        parser_stats=stats,
    )

    assert [item["date"] for item in result] == ["2026-04-24", "2026-04-22"]
    assert result[0]["entries"] == [
        "Lateinisch ab Kl. 7: AB zum Wortschatz\nBerichtigung KA",
        "Deutsch: S. 122 Nr 2",
    ]
    assert stats["html_tiles_seen"] == 3
    assert stats["html_older_than_cutoff"] == 1


def test_clean_html_text_decodes_entities_and_keeps_lines() -> None:
    module = load_scraper_module()

    result = module.SchulmanagerClient._clean_html_text(
        "Gegenstromprinzip &mdash;&gt;<br>Funktionsweise/Vorteil"
    )

    assert result == "Gegenstromprinzip —>\nFunktionsweise/Vorteil"


def test_schedule_header_date_and_format_changed_room() -> None:
    module = load_scraper_module()

    assert module.SchulmanagerClient._extract_schedule_header_date("Freitag 24.04. 2026") == "2026-04-24"
    assert module.SchulmanagerClient._format_schedule_entry(
        {
            "lesson_number": "1",
            "subject": "WiPo",
            "teacher": "FAB",
            "room": "A -1.01",
            "room_old": "A 1.04",
            "room_changed": True,
        }
    ) == "1. WiPo FAB A 1.04 -> A -1.01"


def test_collect_schedule_details_dom_normalizes_entries() -> None:
    module = load_scraper_module()
    client = module.SchulmanagerClient("user", "password")

    class FakeDriver:
        def execute_script(self, script: str) -> dict[str, Any]:
            return {
                "headers": [
                    {"label": "Montag 20.04. 2026"},
                    {"label": "Dienstag 21.04. 2026"},
                ],
                "entries": [
                    {
                        "day_index": 0,
                        "lesson_number": "1",
                        "cell_index": 0,
                        "subject": "M",
                        "teacher": "HOM",
                        "room": "A 1.04",
                        "cancelled": False,
                        "raw": "M HOM A 1.04",
                    },
                    {
                        "day_index": 1,
                        "lesson_number": "2",
                        "cell_index": 0,
                        "subject": "E5",
                        "teacher": "HMA",
                        "room": "A 1.04",
                        "cancelled": True,
                        "raw": "E5 HMA A 1.04",
                    },
                ],
            }

    result = client._collect_schedule_details_dom(FakeDriver())

    assert result["day_dates"]["monday"] == "2026-04-20"
    assert result["day_dates"]["tuesday"] == "2026-04-21"
    assert result["week_details"]["monday"][0]["subject"] == "M"
    assert result["week_details"]["tuesday"][0]["cancelled"] is True
    assert result["parser"] == {"source": "dom", "headers_seen": 2, "entries_seen": 2}
