"""Schulmanager JSON-API client for the add-on bridge.

Replaces the Selenium scraper. The web app talks to a JSON API, so the bridge
does too: one login yields a JWT that stays valid for about an hour, and every
module is fetched through a single batched ``/api/calls`` request.

The returned payload keeps the exact shape the scraper produced, so sensors,
binary sensors and the Lovelace card need no changes.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import logging
import re
import threading
import time
from typing import Any
import urllib.error
import urllib.request

WEEKDAY_NAMES = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://login.schulmanager-online.de"
SALT_URL = f"{BASE_URL}/api/get-salt"
LOGIN_URL = f"{BASE_URL}/api/login"
CALLS_URL = f"{BASE_URL}/api/calls"

# The web app derives the password hash with these parameters; the server
# rejects anything else, so they are not tunable.
PBKDF2_ITERATIONS = 99999
PBKDF2_DKLEN = 512

# The API accepts a dummy bundle version — the real one only matters to the
# web app's own cache busting.
BUNDLE_VERSION = "0000000000"

REQUEST_TIMEOUT = 60
# Renew a little before the token actually expires so a long fetch cannot run
# past the deadline mid-flight.
TOKEN_LEEWAY = timedelta(minutes=5)
FALLBACK_TOKEN_LIFETIME = timedelta(minutes=50)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
)

# How far the calendar and exam queries look ahead.
CALENDAR_LOOKAHEAD_DAYS = 90
EXAM_LOOKAHEAD_DAYS = 90

# Lesson types that are not plain scheduled teaching, with the label the
# timetable should show for them.
LESSON_CHANGE_LABELS = {
    "cancelledLesson": "Entfall",
    "substitution": "Vertretung",
    "changedLesson": "Geänderter Unterricht",
    "roomChange": "Raumänderung",
    "teacherChange": "Lehrervertretung",
    "specialLesson": "Sonderstunde",
    "irregularLesson": "Unregelmäßige Stunde",
}
CANCELLED_LESSON_TYPES = {"cancelledLesson"}


class SchulmanagerError(Exception):
    """Base exception for the integration."""


class SchulmanagerAuthError(SchulmanagerError):
    """Raised when Schulmanager refuses the credentials."""


class SchulmanagerConnectionError(SchulmanagerError):
    """Raised when the API cannot be reached or answers unexpectedly."""


@dataclass(slots=True)
class LoginInfo:
    """Minimal account information used during setup."""

    unique_id: str
    title: str
    account: dict[str, Any]


@dataclass
class _Session:
    """A logged-in API session, cached across requests."""

    jwt: str
    expires_at: datetime
    user: dict[str, Any] = field(default_factory=dict)
    students: list[dict[str, Any]] = field(default_factory=list)

    def is_valid(self) -> bool:
        return bool(self.jwt) and datetime.now(timezone.utc) < self.expires_at - TOKEN_LEEWAY


# Sessions are shared across requests so the expensive PBKDF2 step runs about
# once an hour instead of on every fetch. FastAPI serves sync endpoints from a
# thread pool, hence the lock.
_SESSIONS: dict[str, _Session] = {}
_SESSION_LOCK = threading.Lock()


def _session_key(username: str, password: str) -> str:
    digest = hashlib.sha256(f"{username}\0{password}".encode()).hexdigest()
    return digest[:32]


def _jwt_expiry(token: str) -> datetime:
    """Read the expiry claim without verifying the signature.

    Only the server can validate the token; we read ``exp`` purely to know when
    to fetch a new one.
    """
    try:
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        exp = payload.get("exp")
        if isinstance(exp, (int, float)):
            return datetime.fromtimestamp(exp, tz=timezone.utc)
    except Exception:  # noqa: BLE001
        _LOGGER.debug("Could not read JWT expiry; using fallback lifetime", exc_info=True)
    return datetime.now(timezone.utc) + FALLBACK_TOKEN_LIFETIME


class SchulmanagerClient:
    """Client for the Schulmanager JSON API."""

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password
        self._key = _session_key(username, password)

    # ── public API (same surface the scraper exposed) ─────────────────────────

    def validate_login(self) -> LoginInfo:
        """Validate credentials and return account information."""
        _LOGGER.info("Validating Schulmanager login for %s", self._username)
        session = self._authenticate(force_fresh=True)
        account = self._build_account(session)
        return LoginInfo(
            unique_id=self._username.lower(),
            title=f"Schulmanager ({account.get('full_name') or self._username})",
            account=account,
        )

    def fetch_data(self, modules: list[str], debug: bool = False) -> dict[str, Any]:
        """Fetch all selected modules in one batched API call."""
        _LOGGER.info("Starting data fetch for %s with modules=%s", self._username, ", ".join(modules))
        started = time.perf_counter()

        session = self._get_session()
        data: dict[str, Any] = {
            "meta": {
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "modules": modules,
                "module_errors": {},
            }
        }

        student = self._primary_student(session)
        plan = self._build_request_plan(modules, student)

        if plan:
            results = self._calls([spec["request"] for spec in plan], session)
            for spec, result in zip(plan, results):
                self._apply_result(data, spec, result, debug=debug)

        if "account" in modules:
            data["account"] = self._build_account(session)

        # Modules with no API mapping still need a well-formed, empty payload so
        # downstream sensors keep their shape.
        for module in modules:
            if module not in data:
                data[module] = {"items": [], "today": []}
                data["meta"]["module_errors"].setdefault(
                    module, f"Module '{module}' is not available through the API bridge."
                )

        _LOGGER.info(
            "Finished data fetch for %s in %.1f ms",
            self._username,
            (time.perf_counter() - started) * 1000,
        )
        return data

    # ── authentication ────────────────────────────────────────────────────────

    def _get_session(self) -> _Session:
        with _SESSION_LOCK:
            session = _SESSIONS.get(self._key)
            if session is not None and session.is_valid():
                _LOGGER.debug("Reusing cached Schulmanager session")
                return session
        return self._authenticate()

    def _authenticate(self, force_fresh: bool = False) -> _Session:
        """Log in and cache the resulting session."""
        if not force_fresh:
            with _SESSION_LOCK:
                session = _SESSIONS.get(self._key)
                if session is not None and session.is_valid():
                    return session

        salt = self._fetch_salt()
        started = time.perf_counter()
        password_hash = hashlib.pbkdf2_hmac(
            "sha512",
            self._password.encode("latin-1", errors="strict"),
            salt.encode("utf-8"),
            PBKDF2_ITERATIONS,
            dklen=PBKDF2_DKLEN,
        ).hex()
        _LOGGER.debug("Derived password hash in %.0f ms", (time.perf_counter() - started) * 1000)

        payload = self._post(
            LOGIN_URL,
            {
                "emailOrUsername": self._username,
                "password": self._password,
                "hash": password_hash,
                "mobileApp": False,
                "userId": None,
                "twoFactorCode": None,
                "institutionId": None,
            },
        )

        if "multipleAccounts" in payload:
            raise SchulmanagerConnectionError(
                "This account belongs to several schools, which the bridge cannot pick between yet."
            )

        token = payload.get("jwt")
        if not token:
            raise SchulmanagerAuthError("Schulmanager refused the credentials.")

        user = payload.get("user") or {}
        session = _Session(
            jwt=token,
            expires_at=_jwt_expiry(token),
            user=user,
            students=self._extract_students(user),
        )
        with _SESSION_LOCK:
            _SESSIONS[self._key] = session
        _LOGGER.info(
            "Schulmanager login succeeded for %s; %d student(s), token valid until %s",
            self._username,
            len(session.students),
            session.expires_at.isoformat(timespec="seconds"),
        )
        return session

    def _fetch_salt(self) -> str:
        salt = self._post(
            SALT_URL,
            {"emailOrUsername": self._username, "userId": None, "institutionId": None},
        )
        if not isinstance(salt, str) or not salt:
            # An unknown user yields no usable salt, which is already a
            # credential problem rather than a transport one.
            raise SchulmanagerAuthError("Schulmanager did not return a salt for this user.")
        return salt

    @staticmethod
    def _extract_students(user: dict[str, Any]) -> list[dict[str, Any]]:
        """Collect students from a parent account or a student's own account."""
        students: list[dict[str, Any]] = []
        for parent in user.get("associatedParents") or []:
            student = (parent or {}).get("student") or {}
            if student.get("id"):
                students.append(student)
        own = user.get("associatedStudent")
        if isinstance(own, dict) and own.get("id"):
            students.append(own)
        return students

    def _primary_student(self, session: _Session) -> dict[str, Any]:
        if not session.students:
            raise SchulmanagerConnectionError(
                "The account has no associated student, so there is no data to fetch."
            )
        return session.students[0]

    # ── HTTP plumbing ─────────────────────────────────────────────────────────

    def _post(self, url: str, payload: dict[str, Any], token: str | None = None) -> Any:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as err:
            body = err.read().decode(errors="replace")[:300]
            if err.code in (401, 403):
                _LOGGER.warning("Schulmanager rejected the request to %s: %s", url, body)
                raise SchulmanagerAuthError("Schulmanager refused the credentials.") from err
            _LOGGER.error("Schulmanager request to %s failed with %s: %s", url, err.code, body)
            raise SchulmanagerConnectionError(
                f"Schulmanager returned HTTP {err.code} for {url}."
            ) from err
        except urllib.error.URLError as err:
            _LOGGER.error("Schulmanager could not be reached at %s: %s", url, err.reason)
            raise SchulmanagerConnectionError(f"Schulmanager could not be reached: {err.reason}") from err
        except TimeoutError as err:
            _LOGGER.error("Schulmanager request to %s timed out", url)
            raise SchulmanagerConnectionError("Schulmanager request timed out.") from err
        except json.JSONDecodeError as err:
            _LOGGER.error("Schulmanager returned no JSON for %s", url)
            raise SchulmanagerConnectionError("Schulmanager returned an unreadable response.") from err

    def _calls(self, requests: list[dict[str, Any]], session: _Session) -> list[dict[str, Any]]:
        """Run a batch of module requests, refreshing the token once if needed."""
        payload = {"bundleVersion": BUNDLE_VERSION, "requests": requests}
        try:
            response = self._post(CALLS_URL, payload, token=session.jwt)
        except SchulmanagerAuthError:
            # The cached token was rejected. Drop it and try once with a fresh
            # login before treating this as a credential problem.
            _LOGGER.info("Cached Schulmanager token was rejected; logging in again")
            with _SESSION_LOCK:
                _SESSIONS.pop(self._key, None)
            fresh = self._authenticate(force_fresh=True)
            response = self._post(CALLS_URL, payload, token=fresh.jwt)

        results = response.get("results")
        if not isinstance(results, list):
            raise SchulmanagerConnectionError("Schulmanager returned no results for the batch request.")
        return results

    # ── request planning ──────────────────────────────────────────────────────

    def _build_request_plan(self, modules: list[str], student: dict[str, Any]) -> list[dict[str, Any]]:
        """Map the requested modules onto API calls, in batch order."""
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        student_ref = {
            "id": student.get("id"),
            "firstname": student.get("firstname", ""),
            "lastname": student.get("lastname", ""),
            "classId": student.get("classId"),
        }

        plan: list[dict[str, Any]] = []
        if "schedules" in modules:
            plan.append(
                {
                    "module": "schedules",
                    "collector": self._collect_schedules,
                    "context": {"monday": monday, "today": today},
                    "request": {
                        "moduleName": "schedules",
                        "endpointName": "get-actual-lessons",
                        "parameters": {
                            "student": {"id": student.get("id")},
                            "start": monday.isoformat(),
                            "end": (monday + timedelta(days=6)).isoformat(),
                        },
                    },
                }
            )
        if "homework" in modules:
            plan.append(
                {
                    "module": "homework",
                    "collector": self._collect_homework,
                    "context": {"today": today},
                    "request": {
                        "moduleName": "classbook",
                        "endpointName": "get-homework",
                        "parameters": {"student": {"id": student.get("id")}},
                    },
                }
            )
        if "exams" in modules:
            plan.append(
                {
                    "module": "exams",
                    "collector": self._collect_exams,
                    "context": {"today": today},
                    "request": {
                        "moduleName": "exams",
                        "endpointName": "get-exams",
                        "parameters": {
                            "student": student_ref,
                            "start": today.isoformat(),
                            "end": (today + timedelta(days=EXAM_LOOKAHEAD_DAYS)).isoformat(),
                        },
                    },
                }
            )
        if "activities" in modules:
            plan.append(
                {
                    "module": "activities",
                    "collector": self._collect_activities,
                    "context": {"today": today, "student_id": student.get("id")},
                    "request": {
                        "moduleName": None,
                        "endpointName": "poqa",
                        "parameters": {
                            "action": {
                                "model": "modules/electives/election",
                                "action": "findAll",
                                "parameters": [{"where": {"finalized": True}}],
                            }
                        },
                    },
                }
            )
        if "calendar" in modules:
            plan.append(
                {
                    "module": "calendar",
                    "collector": self._collect_calendar,
                    "context": {"today": today},
                    "request": {
                        "moduleName": None,
                        "endpointName": "poqa",
                        "parameters": {
                            "action": {
                                "model": "modules/calendar/event",
                                "action": "findAll",
                                "parameters": [
                                    {
                                        "where": {
                                            "start": {
                                                "$gte": today.isoformat(),
                                                "$lte": (
                                                    today + timedelta(days=CALENDAR_LOOKAHEAD_DAYS)
                                                ).isoformat(),
                                            }
                                        }
                                    }
                                ],
                            }
                        },
                    },
                }
            )
        return plan

    def _apply_result(
        self,
        data: dict[str, Any],
        spec: dict[str, Any],
        result: Any,
        debug: bool = False,
    ) -> None:
        """Turn one batch result into its module payload.

        A failing module must not take the whole fetch down, so each one falls
        back to an empty payload plus an entry in ``meta.module_errors``.
        """
        module = spec["module"]
        status = result.get("status") if isinstance(result, dict) else None
        if status is not None and status != 200:
            _LOGGER.warning("Schulmanager module '%s' returned status %s", module, status)
            data[module] = {"items": [], "today": []}
            data["meta"]["module_errors"][module] = f"API returned status {status}."
            return

        payload = result.get("data") if isinstance(result, dict) else result
        try:
            data[module] = spec["collector"](payload, spec["context"])
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Failed to parse Schulmanager module '%s'", module)
            data[module] = {"items": [], "today": []}
            data["meta"]["module_errors"][module] = f"{type(err).__name__}: {err}"
            return

        if debug:
            data[module]["debug"] = {"raw_sample": json.dumps(payload, ensure_ascii=False)[:2000]}

    # ── module collectors (output matches the scraper's shape) ────────────────

    def _build_account(self, session: _Session) -> dict[str, Any]:
        user = session.user
        first = (user.get("firstname") or "").strip()
        last = (user.get("lastname") or "").strip()
        full_name = " ".join(part for part in (first, last) if part) or self._username

        student_names = [
            " ".join(
                part
                for part in ((s.get("firstname") or "").strip(), (s.get("lastname") or "").strip())
                if part
            )
            for s in session.students
        ]
        student_names = [name for name in student_names if name]

        return {
            "full_name": full_name,
            "first_name": first,
            "surname": last,
            "class_year": "",
            "branch": "",
            "raw": "Angemeldet als {name}{students}".format(
                name=full_name,
                students=" — Schüler: " + ", ".join(student_names) if student_names else "",
            ),
        }

    def _collect_schedules(self, payload: Any, context: dict[str, Any]) -> dict[str, Any]:
        lessons = payload if isinstance(payload, list) else []
        monday: date = context["monday"]
        today: date = context["today"]

        week: dict[str, list[str]] = {name: [] for name in WEEKDAY_NAMES}
        week_details: dict[str, list[dict[str, Any]]] = {name: [] for name in WEEKDAY_NAMES}
        day_dates: dict[str, str] = {
            WEEKDAY_NAMES[offset]: (monday + timedelta(days=offset)).isoformat()
            for offset in range(5)
        }

        for lesson in sorted(lessons, key=self._lesson_sort_key):
            entry = self._format_lesson(lesson)
            if entry is None:
                continue
            weekday = entry.pop("_weekday")
            entry["cell_index"] = len(week_details[weekday])
            week_details[weekday].append(entry)
            number = entry["lesson_number"]
            week[weekday].append(f"{number}. {entry['raw']}".rstrip() if number else entry["raw"])

        today_name = WEEKDAY_NAMES[today.weekday()]
        return {
            "today_name": today_name,
            "today": list(week.get(today_name, [])),
            "today_details": list(week_details.get(today_name, [])),
            "week": week,
            "week_details": week_details,
            "day_dates": day_dates,
            "schedule_parser": {
                "source": "api",
                "headers_seen": len(day_dates),
                "entries_seen": len(lessons),
            },
        }

    @staticmethod
    def _lesson_sort_key(lesson: dict[str, Any]) -> tuple[str, int]:
        raw_number = ((lesson.get("classHour") or {}).get("number") or "0")
        digits = re.sub(r"\D", "", str(raw_number))
        return (str(lesson.get("date") or ""), int(digits) if digits else 0)

    def _format_lesson(self, lesson: dict[str, Any]) -> dict[str, Any] | None:
        """Render one API lesson into the scraper's entry shape."""
        if not isinstance(lesson, dict):
            return None
        raw_date = lesson.get("date")
        try:
            lesson_date = date.fromisoformat(str(raw_date))
        except (TypeError, ValueError):
            return None

        lesson_type = lesson.get("type") or "regularLesson"
        number = str((lesson.get("classHour") or {}).get("number") or "").strip()

        actual = lesson.get("actualLesson") or {}
        event = lesson.get("event") or {}
        source = actual or event

        if event and not actual:
            subject = (event.get("text") or "").strip()
            rooms = [r.get("name") for r in (event.get("rooms") or []) if r.get("name")]
            room = ", ".join(rooms)
        else:
            subject = (
                (source.get("subjectLabel") or "").strip()
                or ((source.get("subject") or {}).get("abbreviation") or "").strip()
                or ((source.get("subject") or {}).get("name") or "").strip()
            )
            room = ((source.get("room") or {}).get("name") or "").strip()

        teachers = ", ".join(
            (t.get("abbreviation") or f"{t.get('firstname', '')} {t.get('lastname', '')}".strip())
            for t in (source.get("teachers") or [])
            if isinstance(t, dict)
        )

        cancelled = lesson_type in CANCELLED_LESSON_TYPES
        if cancelled and not subject:
            # A cancellation carries the dropped lesson in originalLessons.
            original = (lesson.get("originalLessons") or [{}])[0]
            subject = ((original.get("subject") or {}).get("abbreviation") or "").strip()

        label = LESSON_CHANGE_LABELS.get(lesson_type)
        if label and lesson_type != "event":
            subject = f"{subject} ({label})" if subject else label

        # ``raw`` is the bare cell text, matching what the scraper stored; the
        # lesson number is prefixed only on the week line built by the caller.
        raw = " ".join(part for part in (subject, teachers, room) if part)

        return {
            "_weekday": WEEKDAY_NAMES[lesson_date.weekday()],
            "lesson_number": number,
            "date": lesson_date.isoformat(),
            "subject": subject,
            "teacher": teachers,
            "room": room,
            "cancelled": cancelled,
            "raw": raw,
        }

    def _collect_homework(self, payload: Any, context: dict[str, Any]) -> dict[str, Any]:
        entries = payload if isinstance(payload, list) else []
        today_str = context["today"].isoformat()
        by_date: dict[str, list[str]] = {}

        for item in entries:
            if not isinstance(item, dict):
                continue
            due = self._first_date(item, ("date", "dueDate", "homeworkDueDate", "day"))
            if due is None:
                continue
            text = self._first_text(item, ("homework", "text", "description", "comment", "content"))
            subject = self._subject_label(item)
            line = f"{subject}: {text}" if subject and text else (text or subject)
            if line:
                by_date.setdefault(due.isoformat(), []).append(line)

        items = [{"date": day, "entries": lines} for day, lines in sorted(by_date.items())]
        return {
            "items": items,
            "today": [item for item in items if item["date"] == today_str],
            "parser": {"source": "api", "entries_seen": len(entries), "days_seen": len(items)},
        }

    def _collect_exams(self, payload: Any, context: dict[str, Any]) -> dict[str, Any]:
        entries = payload if isinstance(payload, list) else []
        today_str = context["today"].isoformat()
        items: list[dict[str, Any]] = []

        for exam in entries:
            if not isinstance(exam, dict):
                continue
            exam_date = self._first_date(exam, ("date", "start", "day"))
            if exam_date is None:
                continue
            subject = self._subject_label(exam)
            title = self._first_text(exam, ("comment", "text", "description", "type"))
            start = self._time_of(exam.get("startTime") or exam.get("start"))
            end = self._time_of(exam.get("endTime") or exam.get("end"))
            span = f"{start}-{end} " if start and end else (f"{start} " if start else "")
            label = " ".join(part for part in (subject, title) if part)
            items.append({"date": exam_date.isoformat(), "entry": f"{span}{label}".strip()})

        items.sort(key=lambda item: item["date"])
        return {"items": items, "today": [i for i in items if i["date"] == today_str]}

    def _collect_activities(self, payload: Any, context: dict[str, Any]) -> dict[str, Any]:
        """Elective courses (AGs) the student is assigned to."""
        elections = payload if isinstance(payload, list) else []
        today_str = context["today"].isoformat()
        student_id = context.get("student_id")
        by_date: dict[str, list[str]] = {}

        for election in elections:
            if not isinstance(election, dict):
                continue
            for elective in election.get("electives") or []:
                name = self._first_text(elective, ("name", "title"))
                for instance in elective.get("instances") or []:
                    assignments = instance.get("studentAssignments") or []
                    if student_id is not None and assignments:
                        if not any(a.get("studentId") == student_id for a in assignments if isinstance(a, dict)):
                            continue
                    for slot in instance.get("slots") or [{}]:
                        slot_date = self._first_date(slot, ("date", "start", "day"))
                        day = slot_date.isoformat() if slot_date else self._first_text(election, ("start",))[:10]
                        start = self._time_of(slot.get("start") or slot.get("startTime"))
                        line = f"{start} {name}".strip() if start else name
                        if day and line:
                            by_date.setdefault(day, []).append(line)

        items = [{"date": day, "entries": lines} for day, lines in sorted(by_date.items())]
        return {"items": items, "today": [i for i in items if i["date"] == today_str]}

    def _collect_calendar(self, payload: Any, context: dict[str, Any]) -> dict[str, Any]:
        events = payload if isinstance(payload, list) else []
        today_str = context["today"].isoformat()
        items: list[dict[str, Any]] = []

        for event in events:
            if not isinstance(event, dict):
                continue
            event_date = self._first_date(event, ("start", "date", "from"))
            if event_date is None:
                continue
            title = self._first_text(event, ("summary", "title", "text", "description"))
            if not title:
                continue
            items.append(
                {
                    "date": event_date.isoformat(),
                    "time": self._time_of(event.get("start")),
                    "title": title,
                }
            )

        items.sort(key=lambda item: (item["date"], item["time"]))
        return {"items": items, "today": [i for i in items if i["date"] == today_str]}

    # ── small parsing helpers ─────────────────────────────────────────────────

    @staticmethod
    def _first_date(source: dict[str, Any], keys: tuple[str, ...]) -> date | None:
        """Read the first of ``keys`` that holds a usable ISO date."""
        for key in keys:
            value = source.get(key)
            if isinstance(value, str) and len(value) >= 10:
                try:
                    return date.fromisoformat(value[:10])
                except ValueError:
                    continue
        return None

    @staticmethod
    def _first_text(source: dict[str, Any], keys: tuple[str, ...]) -> str:
        for key in keys:
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _time_of(value: Any) -> str:
        """Extract HH:MM from a timestamp or time string, if it carries one."""
        if not isinstance(value, str):
            return ""
        match = re.search(r"(?:T|\s)?(\d{2}:\d{2})", value)
        if not match:
            return ""
        # A midnight stamp on an all-day entry is noise, not a time.
        if match.group(1) == "00:00" and "T" in value:
            return ""
        return match.group(1)

    @staticmethod
    def _subject_label(source: dict[str, Any]) -> str:
        subject = source.get("subject")
        if isinstance(subject, dict):
            return (subject.get("abbreviation") or subject.get("name") or "").strip()
        if isinstance(subject, str):
            return subject.strip()
        course = source.get("course")
        if isinstance(course, dict):
            return (course.get("name") or "").strip()
        return ""
