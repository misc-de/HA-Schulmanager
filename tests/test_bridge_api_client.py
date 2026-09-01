"""Unit tests for the JSON-API bridge client (api_client.py).

The fixtures are real responses captured from the Schulmanager API, so these
tests pin the mapping onto the payload shape the sensors and the Lovelace card
already expect.
"""

from __future__ import annotations

import base64
import importlib.util
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys


MODULE_PATH = Path(__file__).parents[1] / "addons" / "schulmanager_bridge" / "api_client.py"


def load_api_module():
    spec = importlib.util.spec_from_file_location("api_client_under_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _client():
    return load_api_module().SchulmanagerClient("user@test.de", "pw")


# Captured from GET schedules/get-actual-lessons on 2026-09-01.
REGULAR_LESSON = {
    "date": "2026-09-04",
    "classHour": {"id": 52866, "number": "5"},
    "type": "regularLesson",
    "actualLesson": {
        "room": {"id": 304179, "name": "E 1.04"},
        "subject": {"id": 439826, "abbreviation": "KR", "name": "Religionslehre"},
        "teachers": [{"id": 622354, "abbreviation": "FÖ", "firstname": "Judith", "lastname": "Föcker"}],
        "classes": [{"id": 547725, "name": "9B"}],
        "subjectLabel": "31 KRb",
    },
}

EVENT_LESSON = {
    "date": "2026-09-02",
    "classHour": {"id": 52862, "number": "1"},
    "type": "event",
    "event": {
        "text": "Klassenleiterstunde",
        "teachers": [
            {"abbreviation": "HOM", "firstname": "Jona", "lastname": "Hoffmann"},
            {"abbreviation": "HIL", "firstname": "Anabell", "lastname": "Hilberer"},
        ],
        "rooms": [{"id": 304150, "name": "A 1.04"}],
    },
}


# ── _format_lesson ────────────────────────────────────────────────────────────

def test_format_regular_lesson_uses_subject_label_teacher_room() -> None:
    entry = _client()._format_lesson(REGULAR_LESSON)
    assert entry["raw"] == "5. 31 KRb FÖ E 1.04"
    assert entry["lesson_number"] == "5"
    assert entry["date"] == "2026-09-04"
    assert entry["subject"] == "31 KRb"
    assert entry["teacher"] == "FÖ"
    assert entry["room"] == "E 1.04"
    assert entry["cancelled"] is False
    assert entry["_weekday"] == "friday"


def test_format_event_lesson_reads_text_and_rooms() -> None:
    entry = _client()._format_lesson(EVENT_LESSON)
    assert entry["subject"] == "Klassenleiterstunde"
    assert entry["teacher"] == "HOM, HIL"
    assert entry["room"] == "A 1.04"
    assert entry["raw"] == "1. Klassenleiterstunde HOM, HIL A 1.04"


def test_format_cancelled_lesson_is_marked_and_falls_back_to_original() -> None:
    lesson = {
        "date": "2026-09-03",
        "classHour": {"number": "2"},
        "type": "cancelledLesson",
        "originalLessons": [{"subject": {"abbreviation": "M"}}],
    }
    entry = _client()._format_lesson(lesson)
    assert entry["cancelled"] is True
    assert "Entfall" in entry["subject"]
    assert "M" in entry["subject"]


def test_format_lesson_rejects_entries_without_a_usable_date() -> None:
    assert _client()._format_lesson({"classHour": {"number": "1"}}) is None
    assert _client()._format_lesson({"date": "kein-datum"}) is None
    assert _client()._format_lesson("nonsense") is None


# ── _collect_schedules ────────────────────────────────────────────────────────

def test_collect_schedules_matches_the_scraper_payload_shape() -> None:
    client = _client()
    context = {"monday": date(2026, 8, 31), "today": date(2026, 9, 2)}
    result = client._collect_schedules([REGULAR_LESSON, EVENT_LESSON], context)

    assert sorted(result) == [
        "day_dates", "schedule_parser", "today", "today_details",
        "today_name", "week", "week_details",
    ]
    assert result["today_name"] == "wednesday"
    assert result["day_dates"]["monday"] == "2026-08-31"
    assert result["day_dates"]["friday"] == "2026-09-04"
    assert sorted(result["week"]) == sorted(
        ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    )
    assert result["week"]["wednesday"] == ["1. Klassenleiterstunde HOM, HIL A 1.04"]
    assert result["week"]["friday"] == ["5. 31 KRb FÖ E 1.04"]
    # today mirrors the matching weekday
    assert result["today"] == result["week"]["wednesday"]
    assert result["today_details"] == result["week_details"]["wednesday"]
    assert result["schedule_parser"] == {"source": "api", "headers_seen": 5, "entries_seen": 2}


def test_collect_schedules_orders_by_lesson_number_and_indexes_cells() -> None:
    lessons = [
        {"date": "2026-09-02", "classHour": {"number": "9"}, "type": "regularLesson",
         "actualLesson": {"subjectLabel": "SP", "teachers": [], "room": {"name": "H1"}}},
        {"date": "2026-09-02", "classHour": {"number": "2"}, "type": "regularLesson",
         "actualLesson": {"subjectLabel": "M", "teachers": [], "room": {"name": "A1"}}},
    ]
    result = _client()._collect_schedules(lessons, {"monday": date(2026, 8, 31), "today": date(2026, 9, 2)})
    details = result["week_details"]["wednesday"]
    assert [d["lesson_number"] for d in details] == ["2", "9"]
    assert [d["cell_index"] for d in details] == [0, 1]


def test_collect_schedules_survives_an_empty_week() -> None:
    result = _client()._collect_schedules([], {"monday": date(2026, 8, 31), "today": date(2026, 9, 1)})
    assert result["week"]["monday"] == []
    assert result["today"] == []
    assert result["today_name"] == "tuesday"


# ── other collectors ──────────────────────────────────────────────────────────

def test_collect_calendar_maps_to_date_time_title() -> None:
    events = [
        {"summary": "3. Lehrerkonferenz", "start": "2026-09-15T16:00:00.000Z", "organizer": "FRI"},
        {"summary": "Wandertag", "start": "2026-09-10"},
        {"start": "2026-09-11"},  # no title → skipped
    ]
    result = _client()._collect_calendar(events, {"today": date(2026, 9, 10)})
    assert result["items"] == [
        {"date": "2026-09-10", "time": "", "title": "Wandertag"},
        {"date": "2026-09-15", "time": "16:00", "title": "3. Lehrerkonferenz"},
    ]
    assert result["today"] == [{"date": "2026-09-10", "time": "", "title": "Wandertag"}]


def test_collect_homework_groups_entries_per_due_date() -> None:
    entries = [
        {"date": "2026-09-03", "homework": "S. 12 Nr. 4", "subject": {"abbreviation": "M"}},
        {"date": "2026-09-03", "homework": "Vokabeln", "subject": {"abbreviation": "E"}},
        {"dueDate": "2026-09-05", "text": "Referat"},
    ]
    result = _client()._collect_homework(entries, {"today": date(2026, 9, 3)})
    assert result["items"] == [
        {"date": "2026-09-03", "entries": ["M: S. 12 Nr. 4", "E: Vokabeln"]},
        {"date": "2026-09-05", "entries": ["Referat"]},
    ]
    assert result["today"] == [{"date": "2026-09-03", "entries": ["M: S. 12 Nr. 4", "E: Vokabeln"]}]
    assert result["parser"]["source"] == "api"


def test_collect_exams_builds_entry_strings_with_times() -> None:
    exams = [
        {"date": "2026-09-20", "subject": {"abbreviation": "M"}, "comment": "Klausur 1",
         "startTime": "08:00:00", "endTime": "09:30:00"},
        {"date": "2026-09-12", "subject": {"abbreviation": "D"}},
    ]
    result = _client()._collect_exams(exams, {"today": date(2026, 9, 12)})
    assert result["items"][0] == {"date": "2026-09-12", "entry": "D"}
    assert result["items"][1] == {"date": "2026-09-20", "entry": "08:00-09:30 M Klausur 1"}
    assert result["today"] == [{"date": "2026-09-12", "entry": "D"}]


def test_collect_activities_keeps_only_the_students_own_assignments() -> None:
    payload = [{
        "start": "2026-09-01T00:00:00.000Z",
        "electives": [{
            "name": "AG Volleyball",
            "instances": [
                {"studentAssignments": [{"studentId": 5117756}],
                 "slots": [{"date": "2026-09-04", "start": "2026-09-04T14:30:00.000Z"}]},
                {"studentAssignments": [{"studentId": 999999}],
                 "slots": [{"date": "2026-09-04"}]},
            ],
        }],
    }]
    result = _client()._collect_activities(payload, {"today": date(2026, 9, 4), "student_id": 5117756})
    assert result["items"] == [{"date": "2026-09-04", "entries": ["14:30 AG Volleyball"]}]
    assert result["today"] == result["items"]


def test_collectors_tolerate_a_non_list_payload() -> None:
    client = _client()
    ctx = {"today": date(2026, 9, 1), "student_id": 1}
    for collect in (client._collect_calendar, client._collect_homework,
                    client._collect_exams, client._collect_activities):
        result = collect(None, ctx)
        assert result["items"] == []
        assert result["today"] == []


# ── helpers ───────────────────────────────────────────────────────────────────

def test_time_of_ignores_midnight_on_all_day_entries() -> None:
    client = _client()
    assert client._time_of("2026-09-15T16:00:00.000Z") == "16:00"
    assert client._time_of("2026-09-15T00:00:00.000Z") == ""
    assert client._time_of("08:00:00") == "08:00"
    assert client._time_of(None) == ""
    assert client._time_of("2026-09-15") == ""


def test_first_date_picks_the_first_parsable_key() -> None:
    client = _client()
    assert client._first_date({"start": "2026-09-15T10:00:00Z"}, ("date", "start")) == date(2026, 9, 15)
    assert client._first_date({"date": "unbekannt", "day": "2026-09-16"}, ("date", "day")) == date(2026, 9, 16)
    assert client._first_date({}, ("date",)) is None


def test_jwt_expiry_reads_the_exp_claim() -> None:
    module = load_api_module()
    exp = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode().rstrip("=")
    token = f"header.{payload}.signature"
    parsed = module._jwt_expiry(token)
    assert abs((parsed - datetime.fromtimestamp(exp, tz=timezone.utc)).total_seconds()) < 2


def test_jwt_expiry_falls_back_when_the_token_is_unreadable() -> None:
    module = load_api_module()
    parsed = module._jwt_expiry("not-a-jwt")
    assert parsed > datetime.now(timezone.utc) + timedelta(minutes=40)


def test_session_is_only_valid_before_the_leeway_window() -> None:
    module = load_api_module()
    now = datetime.now(timezone.utc)
    assert module._Session("t", now + timedelta(hours=1)).is_valid() is True
    assert module._Session("t", now + timedelta(minutes=2)).is_valid() is False
    assert module._Session("", now + timedelta(hours=1)).is_valid() is False


def test_build_account_names_the_user_and_lists_students() -> None:
    module = load_api_module()
    client = module.SchulmanagerClient("user@test.de", "pw")
    session = module._Session(
        "t", datetime.now(timezone.utc) + timedelta(hours=1),
        user={"firstname": "Khrystyna", "lastname": "Buiukli"},
        students=[{"id": 1, "firstname": "Emilia", "lastname": "Mahlig"}],
    )
    account = client._build_account(session)
    assert account["full_name"] == "Khrystyna Buiukli"
    assert account["first_name"] == "Khrystyna"
    assert account["surname"] == "Buiukli"
    assert "Emilia Mahlig" in account["raw"]
    # keys the sensor reads must all be present
    assert set(account) >= {"full_name", "first_name", "surname", "class_year", "branch", "raw"}


# ── fetch_data: batching and per-module failure isolation ─────────────────────

def _stub_client(module, results, students=None):
    """Client whose session and batch call are pre-seeded, so no HTTP happens."""
    client = module.SchulmanagerClient("user@test.de", "pw")
    session = module._Session(
        "token", datetime.now(timezone.utc) + timedelta(hours=1),
        user={"firstname": "Khrystyna", "lastname": "Buiukli"},
        students=students if students is not None else [{"id": 5117756, "firstname": "Emilia", "lastname": "Mahlig"}],
    )
    sent: dict[str, list] = {"requests": []}

    def fake_calls(requests, _session):
        sent["requests"] = requests
        return results

    client._get_session = lambda: session
    client._calls = fake_calls
    return client, sent


def test_fetch_data_batches_every_module_into_one_call() -> None:
    module = load_api_module()
    results = [{"status": 200, "data": []} for _ in range(4)]
    client, sent = _stub_client(module, results)

    data = client.fetch_data(["schedules", "homework", "exams", "activities"])

    assert len(sent["requests"]) == 4, "all modules must travel in a single batch"
    assert [r.get("moduleName") for r in sent["requests"]] == ["schedules", "classbook", "exams", None]
    assert [r.get("endpointName") for r in sent["requests"]] == [
        "get-actual-lessons", "get-homework", "get-exams", "poqa",
    ]
    assert sorted(data) == ["activities", "exams", "homework", "meta", "schedules"]
    assert data["meta"]["module_errors"] == {}
    assert data["meta"]["modules"] == ["schedules", "homework", "exams", "activities"]


def test_fetch_data_isolates_a_failing_module() -> None:
    module = load_api_module()
    results = [{"status": 200, "data": []}, {"status": 500, "data": None}]
    client, _ = _stub_client(module, results)

    data = client.fetch_data(["schedules", "homework"])

    assert data["schedules"]["week"]["monday"] == []
    assert data["homework"] == {"items": [], "today": []}
    assert "500" in data["meta"]["module_errors"]["homework"]
    assert "schedules" not in data["meta"]["module_errors"]


def test_fetch_data_reports_a_parser_error_without_losing_other_modules() -> None:
    module = load_api_module()
    results = [{"status": 200, "data": [REGULAR_LESSON]}, {"status": 200, "data": [{"date": "2026-09-03"}]}]
    client, _ = _stub_client(module, results)
    client._collect_homework = lambda payload, ctx: (_ for _ in ()).throw(ValueError("kaputt"))

    data = client.fetch_data(["schedules", "homework"])

    assert data["schedules"]["week"]["friday"] == ["5. 31 KRb FÖ E 1.04"]
    assert data["homework"] == {"items": [], "today": []}
    assert data["meta"]["module_errors"]["homework"] == "ValueError: kaputt"


def test_fetch_data_fills_unmapped_modules_with_an_empty_payload() -> None:
    """'meal' has no API mapping yet; the sensor must still get its shape."""
    module = load_api_module()
    client, sent = _stub_client(module, [{"status": 200, "data": []}])

    data = client.fetch_data(["schedules", "meal"])

    assert len(sent["requests"]) == 1, "meal must not produce a request"
    assert data["meal"] == {"items": [], "today": []}
    assert "meal" in data["meta"]["module_errors"]


def test_fetch_data_includes_account_without_an_extra_request() -> None:
    module = load_api_module()
    client, sent = _stub_client(module, [])

    data = client.fetch_data(["account"])

    assert sent["requests"] == []
    assert data["account"]["full_name"] == "Khrystyna Buiukli"


def test_fetch_data_rejects_an_account_without_a_student() -> None:
    module = load_api_module()
    client, _ = _stub_client(module, [], students=[])
    try:
        client.fetch_data(["schedules"])
        assert False, "Expected SchulmanagerConnectionError"
    except module.SchulmanagerConnectionError as exc:
        assert "student" in str(exc).lower()


def test_extract_students_handles_parent_and_student_accounts() -> None:
    module = load_api_module()
    parent = {"associatedParents": [{"student": {"id": 5117756, "firstname": "Emilia"}}]}
    assert module.SchulmanagerClient._extract_students(parent)[0]["id"] == 5117756

    own = {"associatedStudent": {"id": 42, "firstname": "Max"}}
    assert module.SchulmanagerClient._extract_students(own)[0]["id"] == 42

    assert module.SchulmanagerClient._extract_students({}) == []
