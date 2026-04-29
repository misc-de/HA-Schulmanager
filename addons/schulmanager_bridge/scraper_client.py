"""Schulmanager scraper client for the add-on bridge."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import html as html_utils
import logging
import os
import re
import shutil
import tempfile
import time
from typing import Any

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

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

LOGIN_URL = "https://login.schulmanager-online.de/#/login"
DASHBOARD_URL = "https://login.schulmanager-online.de/#/dashboard"
ACCOUNT_URL = "https://login.schulmanager-online.de/#/account"
HOMEWORK_URL = "https://login.schulmanager-online.de/#/modules/classbook/homework/"
CALENDAR_URL = "https://login.schulmanager-online.de/#/modules/calendar/overview"
SCHEDULE_URL = "https://login.schulmanager-online.de/#/modules/schedules/view//"
HOMEWORK_MAX_AGE_DAYS = 14
GERMAN_DATE_PATTERN = re.compile(r"(?P<day>\d{1,2})\.(?P<month>\d{1,2})\.(?P<year>\d{2,4})")


class SchulmanagerError(Exception):
    """Base exception for the integration."""


class SchulmanagerAuthError(SchulmanagerError):
    """Raised when authentication fails."""


class SchulmanagerConnectionError(SchulmanagerError):
    """Raised when the webdriver or page loading fails."""


@dataclass(slots=True)
class LoginInfo:
    """Minimal account information used during setup."""

    unique_id: str
    title: str
    account: dict[str, Any]


class SchulmanagerClient:
    """Client for scraping Schulmanager with a local Chromium driver."""

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password

    def validate_login(self) -> LoginInfo:
        """Validate credentials and return title information for HA setup."""
        _LOGGER.info("Starting login validation for %s", self._username)
        started = time.perf_counter()
        driver = self._build_driver()
        try:
            self._login(driver)
            try:
                account = self._get_account(driver)
            except Exception as err:  # noqa: BLE001
                _LOGGER.exception("Account parsing failed after successful login; using fallback account info")
                account = {
                    "full_name": self._username,
                    "first_name": "",
                    "surname": "",
                    "class_year": "",
                    "branch": "",
                    "raw": f"fallback_after_parse_error: {type(err).__name__}: {err}",
                }
        finally:
            self._close_driver(driver)

        full_name = account.get("full_name") or self._username
        unique_id = self._username.lower()
        _LOGGER.info("Login validation finished for %s in %.1f ms", unique_id, (time.perf_counter() - started) * 1000)
        return LoginInfo(unique_id=unique_id, title=f"Schulmanager ({full_name})", account=account)

    def _safe_collect_module(self, data: dict[str, Any], module: str, collector, *args) -> dict[str, Any]:
        try:
            return collector(*args)
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Module '%s' failed", module)
            return self._module_error_result(data, module, err)

    def _module_error_result(self, data: dict[str, Any], module: str, err: Exception) -> dict[str, Any]:
        data.setdefault("meta", {}).setdefault("module_errors", {})[module] = f"{type(err).__name__}: {err}"
        if module == "account":
            return {
                "full_name": self._username,
                "first_name": "",
                "surname": "",
                "class_year": "",
                "branch": "",
                "raw": f"module_error: {type(err).__name__}: {err}",
                "error": f"{type(err).__name__}: {err}",
            }
        if module == "schedules":
            return {
                "week": {},
                "today_name": WEEKDAY_NAMES[date.today().weekday()],
                "today": [],
                "error": f"{type(err).__name__}: {err}",
            }
        return {
            "items": [],
            "today": [],
            "error": f"{type(err).__name__}: {err}",
        }

    def fetch_data(self, modules: list[str], debug: bool = False) -> dict[str, Any]:
        """Fetch all selected modules in one browser session.

        A single parser failure must not break the whole Home Assistant entry.
        """
        _LOGGER.info("Starting data fetch for %s with modules=%s", self._username, ", ".join(modules))
        started = time.perf_counter()
        driver = self._build_driver()
        try:
            self._login(driver)
            data: dict[str, Any] = {
                "meta": {
                    "fetched_at": datetime.utcnow().isoformat() + "Z",
                    "modules": modules,
                    "module_errors": {},
                }
            }

            if "account" in modules:
                data["account"] = self._safe_collect_module(data, "account", self._get_account, driver)

            dashboard_required = any(
                module in modules for module in ("activities", "exams", "meal")
            )
            dashboard_html = ""
            if dashboard_required:
                try:
                    self._load_dashboard(driver)
                    dashboard_html = driver.page_source
                except Exception as err:  # noqa: BLE001
                    _LOGGER.exception("Dashboard load failed")
                    for module in ("activities", "exams", "meal"):
                        if module in modules:
                            data[module] = self._module_error_result(data, module, err)

            if "activities" in modules and "activities" not in data:
                data["activities"] = self._safe_collect_module(data, "activities", self._collect_activities, dashboard_html, driver)
            if "exams" in modules and "exams" not in data:
                data["exams"] = self._safe_collect_module(data, "exams", self._collect_exams, dashboard_html)
            if "meal" in modules and "meal" not in data:
                data["meal"] = self._safe_collect_module(data, "meal", self._collect_meal, dashboard_html, driver if debug else None)

            if "schedules" in modules:
                data["schedules"] = self._safe_collect_module(data, "schedules", self._collect_schedules, driver, "", debug)
            if "homework" in modules:
                data["homework"] = self._safe_collect_module(data, "homework", self._collect_homework, driver, debug)
            if "calendar" in modules:
                data["calendar"] = self._safe_collect_module(data, "calendar", self._collect_calendar, driver, debug)

            _LOGGER.info("Finished data fetch for %s in %.1f ms", self._username, (time.perf_counter() - started) * 1000)
            return data
        finally:
            self._close_driver(driver)

    def _build_driver(self) -> WebDriver:
        _LOGGER.debug("Creating local Chromium webdriver")
        chromium_binary = self._detect_chromium_binary()
        chromedriver_binary = self._detect_chromedriver_binary()

        last_error: WebDriverException | None = None
        for headless_arg in ("--headless=new", "--headless"):
            user_data_dir = tempfile.mkdtemp(prefix="schulmanager-chrome-")
            log_file = tempfile.NamedTemporaryFile(
                prefix="schulmanager-chromedriver-",
                suffix=".log",
                delete=False,
            )
            log_path = log_file.name
            log_file.close()

            options = self._build_chrome_options(
                chromium_binary=chromium_binary,
                headless_arg=headless_arg,
                user_data_dir=user_data_dir,
            )
            service = Service(chromedriver_binary, log_output=log_path)

            try:
                _LOGGER.debug(
                    "Starting Chromium with %s and user-data-dir=%s",
                    headless_arg,
                    user_data_dir,
                )
                driver = webdriver.Chrome(service=service, options=options)
                setattr(driver, "_schulmanager_user_data_dir", user_data_dir)
                setattr(driver, "_schulmanager_chromedriver_log", log_path)
                _LOGGER.debug("Local Chromium webdriver created successfully")
                return driver
            except WebDriverException as err:
                last_error = err
                log_excerpt = self._read_file_excerpt(log_path)
                _LOGGER.warning(
                    "Could not start Chromium with %s: %s%s",
                    headless_arg,
                    err,
                    f" chromedriver_log={log_excerpt}" if log_excerpt else "",
                )
                shutil.rmtree(user_data_dir, ignore_errors=True)
                try:
                    os.unlink(log_path)
                except OSError:
                    pass

        raise SchulmanagerConnectionError(
            f"Local Chromium WebDriver could not be started: {last_error}"
        ) from last_error

    @staticmethod
    def _build_chrome_options(
        chromium_binary: str,
        headless_arg: str,
        user_data_dir: str,
    ) -> Options:
        options = Options()
        options.binary_location = chromium_binary
        options.add_argument(headless_arg)
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-setuid-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-sync")
        options.add_argument("--metrics-recording-only")
        options.add_argument("--mute-audio")
        options.add_argument("--no-first-run")
        options.add_argument("--no-zygote")
        options.add_argument("--remote-debugging-port=0")
        options.add_argument(f"--user-data-dir={user_data_dir}")
        options.add_argument(
            "user-agent=HomeAssistant-Schulmanager-Bridge/0.3.34 (+addon bridge)"
        )
        return options

    @staticmethod
    def _detect_chromium_binary() -> str:
        candidates = [
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/usr/bin/google-chrome",
        ]
        for candidate in candidates:
            try:
                with open(candidate, "rb"):
                    return candidate
            except OSError:
                continue
        raise SchulmanagerConnectionError("No Chromium/Chrome binary found in bridge container.")

    @staticmethod
    def _detect_chromedriver_binary() -> str:
        candidates = [
            "/usr/bin/chromedriver",
            "/usr/lib/chromium/chromedriver",
        ]
        for candidate in candidates:
            try:
                with open(candidate, "rb"):
                    return candidate
            except OSError:
                continue
        raise SchulmanagerConnectionError("No chromedriver binary found in bridge container.")

    def _close_driver(self, driver: WebDriver) -> None:
        try:
            driver.quit()
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Driver quit failed", exc_info=True)
        user_data_dir = getattr(driver, "_schulmanager_user_data_dir", None)
        if isinstance(user_data_dir, str):
            shutil.rmtree(user_data_dir, ignore_errors=True)
        log_path = getattr(driver, "_schulmanager_chromedriver_log", None)
        if isinstance(log_path, str):
            try:
                os.unlink(log_path)
            except OSError:
                pass

    @staticmethod
    def _read_file_excerpt(path: str, limit: int = 2000) -> str:
        try:
            with open(path, encoding="utf-8", errors="replace") as file:
                content = file.read()
        except OSError:
            return ""
        return content[-limit:].replace("\n", " ").strip()

    def _login(self, driver: WebDriver) -> None:
        _LOGGER.debug("Opening Schulmanager login page")
        driver.get(LOGIN_URL)

        try:
            WebDriverWait(driver, 7).until(
                EC.presence_of_element_located((By.TAG_NAME, "widgets-container"))
            )
            _LOGGER.debug("Existing Schulmanager session is already active")
            return
        except TimeoutException:
            pass

        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.ID, "emailOrUsername"))
            )
        except TimeoutException as err:
            raise SchulmanagerConnectionError(
                "Login form could not be loaded."
            ) from err

        _LOGGER.debug("Submitting Schulmanager credentials")
        driver.find_element(By.ID, "emailOrUsername").clear()
        driver.find_element(By.ID, "emailOrUsername").send_keys(self._username)
        driver.find_element(By.ID, "password").clear()
        driver.find_element(By.ID, "password").send_keys(self._password + Keys.RETURN)

        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.ID, "accountDropdown"))
            )
            _LOGGER.debug("Schulmanager login succeeded")
        except TimeoutException as err:
            page_excerpt = self._strip_tags(driver.page_source)[:500]
            _LOGGER.warning(
                "Schulmanager login did not reach the account menu in time; current_url=%s excerpt=%s",
                driver.current_url,
                page_excerpt,
            )
            raise SchulmanagerAuthError("Authentication failed.") from err

    def _load_dashboard(self, driver: WebDriver) -> None:
        _LOGGER.debug("Opening Schulmanager dashboard")
        driver.get(DASHBOARD_URL)
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "widgets-container"))
            )
        except TimeoutException as err:
            raise SchulmanagerConnectionError("Dashboard could not be loaded.") from err

    def _get_account(self, driver: WebDriver) -> dict[str, Any]:
        _LOGGER.debug("Opening Schulmanager account page")
        driver.get(ACCOUNT_URL)
        try:
            WebDriverWait(driver, 15).until(
                EC.any_of(
                    lambda current_driver: "Angemeldet" in current_driver.page_source,
                    lambda current_driver: "#/account" in current_driver.current_url,
                )
            )
        except TimeoutException as err:
            raise SchulmanagerConnectionError("Account page could not be loaded.") from err

        html = driver.page_source
        if "Angemeldet" not in html:
            _LOGGER.debug(
                "Account details not visible after first load; retrying account route from %s",
                driver.current_url,
            )
            driver.execute_script("window.location.href = arguments[0];", ACCOUNT_URL)
            try:
                WebDriverWait(driver, 10).until(
                    lambda current_driver: "Angemeldet" in current_driver.page_source
                )
            except TimeoutException:
                time.sleep(3)
            html = driver.page_source

        if "Angemeldet" not in html:
            _LOGGER.warning(
                "Account details are not available; using username fallback. current_url=%s excerpt=%s",
                driver.current_url,
                self._strip_tags(html)[:300],
            )
            return {
                "full_name": self._username,
                "first_name": "",
                "surname": "",
                "class_year": "",
                "branch": "",
                "raw": "fallback_no_account_details",
                "error": "Account details are not available.",
            }

        try:
            details = html.split("Angemeldet", 1)[1]
            details = details.split("<br ", 1)[1].split(">", 1)[1]
            details = details.split("</div", 1)[0]
            details = details.replace("\n", "")
            while details.startswith(" "):
                details = details[1:]

            surname = details.split(",", 1)[0].strip()
            first_name = details.split(", ", 1)[1].split(" (", 1)[0].strip()
            class_year = ""
            branch = ""
            if "(" in details and ")" in details:
                class_data = details.split("(", 1)[1].split(")", 1)[0].strip()
                class_year = class_data[:2].strip()
                branch = class_data[2:].strip()

            account = {
                "full_name": f"{first_name} {surname}".strip(),
                "first_name": first_name,
                "surname": surname,
                "class_year": class_year,
                "branch": branch,
                "raw": details,
            }
            _LOGGER.debug("Parsed account data for %s", account["full_name"])
            return account
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "Account parser fallback used. current_url=%s excerpt=%s error=%s",
                driver.current_url,
                self._strip_tags(html)[:300],
                err,
            )
            return {
                "full_name": self._username,
                "first_name": "",
                "surname": "",
                "class_year": "",
                "branch": "",
                "raw": f"fallback_parse_error: {type(err).__name__}: {err}",
                "error": f"{type(err).__name__}: {err}",
            }


    def _page_debug(self, driver: WebDriver, html: str | None = None, note: str = "") -> dict[str, Any]:
        if html is None:
            html = driver.page_source
        excerpt = self._strip_tags(html)[:1200]
        lowered = html.lower()
        return {
            "note": note,
            "current_url": driver.current_url,
            "page_title": driver.title,
            "html_excerpt": excerpt,
            "markers": {
                "contains_table": "<table" in lowered,
                "contains_class_hour_calendar": "class-hour-calendar" in lowered,
                "contains_speiseplan": "speiseplan" in lowered,
                "contains_stundenplan": "stundenplan" in lowered,
                "contains_hausaufgaben": "hausaufgaben" in lowered,
                "contains_calendar": "calendar" in lowered or "kalender" in lowered,
                "contains_widgets_container": "widgets-container" in lowered,
            },
        }

    def _collect_calendar(self, driver: WebDriver, debug: bool = False) -> dict[str, Any]:
        _LOGGER.debug("Collecting calendar data")
        driver.get(CALENDAR_URL)
        try:
            WebDriverWait(driver, 8).until(
                EC.any_of(
                    EC.presence_of_element_located((By.TAG_NAME, "calendar")),
                    EC.presence_of_element_located((By.TAG_NAME, "body")),
                )
            )
        except TimeoutException as err:
            _LOGGER.warning("Calendar page timeout. current_url=%s excerpt=%s", driver.current_url, self._strip_tags(driver.page_source)[:300])
            if debug:
                details = self._page_debug(driver, note="calendar_timeout")
                raise SchulmanagerConnectionError(f"Calendar page could not be loaded. debug={details}") from err
            raise SchulmanagerConnectionError("Calendar page could not be loaded.") from err

        html = driver.page_source
        if "data-date=\"" not in html and "fc-event" not in html:
            _LOGGER.info("Calendar page loaded without expected event markers; returning empty result")
            result = {"items": [], "today": []}
            if debug:
                result["debug"] = self._page_debug(driver, note="calendar_no_event_markers")
            return result

        entities = html.split('data-date="')
        if len(entities) <= 2:
            result = {"items": [], "today": []}
            if debug:
                result["debug"] = self._page_debug(driver, html, note="calendar_too_few_entities")
            return result
        del entities[0]
        del entities[-1]

        output: list[dict[str, str]] = []
        for entity in entities:
            if "<!--" not in entity:
                continue
            try:
                event_date = entity.split('"', 1)[0]
                event_time = "00:00"
                if 'class="fc-event-time">' in entity:
                    event_time = (
                        entity.split('class="fc-event-time">', 1)[1]
                        .split("<", 1)[0]
                        .replace(" ", "")
                        .replace("\n", "")
                    )
                title = entity.split('class="fc-event-title fc-sticky">', 1)[1]
                title = title.split("<", 1)[0]
                title = title.split("\n")[1][6:].strip()
                output.append(
                    {
                        "date": event_date,
                        "time": event_time,
                        "title": self._strip_tags(title),
                    }
                )
            except (IndexError, ValueError):
                _LOGGER.debug("Could not parse calendar entry", exc_info=True)

        today_str = date.today().isoformat()
        result = {
            "items": output,
            "today": [item for item in output if item["date"] == today_str],
        }
        if debug:
            result["debug"] = self._page_debug(driver, html, note="calendar_result")
        _LOGGER.debug("Collected %s calendar entries", len(result["items"]))
        return result

    def _collect_homework(self, driver: WebDriver, debug: bool = False) -> dict[str, Any]:
        _LOGGER.debug("Collecting homework data")
        driver.get(HOMEWORK_URL)
        try:
            WebDriverWait(driver, 15).until(
                lambda current_driver: (
                    bool(current_driver.find_elements(By.CSS_SELECTOR, ".tile"))
                    or bool(GERMAN_DATE_PATTERN.search(current_driver.page_source))
                    or "Keine Hausaufgaben" in current_driver.page_source
                )
            )
        except TimeoutException as err:
            _LOGGER.warning("Homework page timeout. current_url=%s excerpt=%s", driver.current_url, self._strip_tags(driver.page_source)[:300])
            if debug:
                details = self._page_debug(driver, note="homework_timeout")
                raise SchulmanagerConnectionError(f"Homework page could not be loaded. debug={details}") from err
            raise SchulmanagerConnectionError("Homework page could not be loaded.") from err

        if "Hausaufgaben" not in driver.page_source:
            time.sleep(1)
            if "Hausaufgaben" not in driver.page_source:
                _LOGGER.info("Homework page loaded without expected homework content; returning empty result")
                result = {"items": [], "today": []}
                if debug:
                    result["debug"] = self._page_debug(driver, note="homework_no_content")
                return result

        html = driver.page_source
        output: list[dict[str, Any]] = []
        cutoff = date.today() - timedelta(days=HOMEWORK_MAX_AGE_DAYS)
        parser_stats = {
            "source": "dom",
            "html_fallback_used": False,
            "tiles_seen": 0,
            "without_date": 0,
            "older_than_cutoff": 0,
            "without_entries": 0,
            "cutoff_date": cutoff.isoformat(),
        }

        for tile in driver.find_elements(By.CSS_SELECTOR, ".tile"):
            parser_stats["tiles_seen"] += 1
            due_date = self._extract_german_date(tile.text)
            if due_date is None:
                parser_stats["without_date"] += 1
                continue
            if due_date < cutoff:
                parser_stats["older_than_cutoff"] += 1
                continue

            entries = self._extract_homework_entries_from_tile(tile)
            if not entries:
                parser_stats["without_entries"] += 1
                continue
            output.append({"date": due_date.isoformat(), "entries": entries})

        if not output:
            parser_stats["source"] = "html"
            parser_stats["html_fallback_used"] = True
            parser_stats["html_tiles_seen"] = 0
            parser_stats["html_without_date"] = 0
            parser_stats["html_older_than_cutoff"] = 0
            parser_stats["html_without_entries"] = 0
            output = self._parse_homework_html(html, cutoff, parser_stats)

        today_str = date.today().isoformat()
        result = {
            "items": output,
            "today": [item for item in output if item["date"] == today_str],
            "parser": parser_stats,
        }
        if debug:
            result["debug"] = self._page_debug(driver, html, note="homework_result")
        _LOGGER.debug(
            "Collected %s homework entries with parser stats %s",
            len(result["items"]),
            parser_stats,
        )
        return result

    def _parse_homework_html(
        self,
        html: str,
        cutoff: date,
        parser_stats: dict[str, bool | int | str],
    ) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        blocks = re.split(
            r'<div\b[^>]*class="[^"]*\btile-header\b[^"]*"[^>]*>',
            html,
            flags=re.IGNORECASE,
        )

        for block in blocks[1:]:
            parser_stats["html_tiles_seen"] = int(parser_stats.get("html_tiles_seen", 0)) + 1
            due_date = self._extract_german_date(block[:600])
            if due_date is None:
                parser_stats["html_without_date"] = int(parser_stats.get("html_without_date", 0)) + 1
                continue
            if due_date < cutoff:
                parser_stats["html_older_than_cutoff"] = int(parser_stats.get("html_older_than_cutoff", 0)) + 1
                continue

            lesson_names = [
                self._clean_html_text(match, single_line=True)
                for match in re.findall(r"<h4\b[^>]*>(.*?)</h4>", block, flags=re.IGNORECASE | re.DOTALL)
            ]
            task_values = [
                self._clean_html_text(match)
                for match in re.findall(
                    r'<span\b[^>]*style="[^"]*white-space:\s*pre-wrap[^"]*"[^>]*>(.*?)</span>',
                    block,
                    flags=re.IGNORECASE | re.DOTALL,
                )
            ]

            entries = [
                f"{lesson_names[idx]}: {task_values[idx]}"
                for idx in range(min(len(lesson_names), len(task_values)))
                if lesson_names[idx] or task_values[idx]
            ]
            if entries:
                output.append({"date": due_date.isoformat(), "entries": entries})
            else:
                parser_stats["html_without_entries"] = int(parser_stats.get("html_without_entries", 0)) + 1
        return output

    def _extract_homework_entries_from_tile(self, tile) -> list[str]:
        script = """
            return Array.from(arguments[0].querySelectorAll('h4')).map((heading) => {
                const container = heading.parentElement || arguments[0];
                const task = container.querySelector('.homework-paragraph')
                    || container.querySelector('p')
                    || heading.nextElementSibling;
                return {
                    lesson: heading.innerText || heading.textContent || '',
                    task: task ? (task.innerText || task.textContent || '') : ''
                };
            });
        """
        try:
            rows = tile.parent.execute_script(script, tile)
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Could not read homework tile via DOM script", exc_info=True)
            return []

        entries: list[str] = []
        if not isinstance(rows, list):
            return entries
        for row in rows:
            if not isinstance(row, dict):
                continue
            lesson = self._clean_plain_text(str(row.get("lesson", "")), single_line=True)
            task = self._clean_plain_text(str(row.get("task", "")))
            if lesson or task:
                entries.append(f"{lesson}: {task}" if lesson and task else lesson or task)
        return entries

    def _collect_exams(self, html: str) -> dict[str, Any]:
        _LOGGER.debug("Collecting exam data from dashboard")
        if "<table " not in html:
            return {"items": [], "today": []}

        text = html.split("<table ", 1)[1].split("</table>", 1)[0]
        rows = text.split("<tr ")
        if rows:
            rows.pop(0)

        output: list[dict[str, str]] = []
        for row in rows:
            try:
                lesson = row.split("<strong ", 1)[1].split(">", 1)[1].split("<", 1)[0]
                row_after_lesson = row.split(lesson, 1)[1]
                raw_date = (
                    row_after_lesson.split("<td ", 1)[1]
                    .split(">", 1)[1]
                    .split("\n")[1]
                    .split("\n")[0]
                    .split(", ", 1)[1]
                    .split(",", 1)[0]
                )
                if str(date.today().year) not in raw_date:
                    raw_date = raw_date + str(date.today().year)
                begin = (
                    row_after_lesson.split("<br", 1)[1]
                    .split(">", 1)[1]
                    .split("<", 1)[0]
                    .replace(" ", "")
                    .replace("\n", "")
                )
                end = " - " + row_after_lesson.split("- ", 1)[1].split("\n", 1)[0]
                output.append(
                    {
                        "date": self._ddmmyyyy_to_iso(raw_date),
                        "entry": f"{begin}{end} {lesson}",
                    }
                )
            except (IndexError, ValueError):
                _LOGGER.debug("Could not parse exam row", exc_info=True)

        today_str = date.today().isoformat()
        result = {
            "items": output,
            "today": [item for item in output if item["date"] == today_str],
        }
        _LOGGER.debug("Collected %s exam entries", len(result["items"]))
        return result

    def _collect_meal(self, html: str, driver: WebDriver | None = None) -> dict[str, Any]:
        try:
            tiles = html.split('<div class="tile-header">')
        except Exception:  # noqa: BLE001
            return {"items": [], "today": []}

        plan = ""
        for tile in tiles:
            test_tile = tile.replace(" ", "")
            if "<!---->\nSpeiseplan\n</div>" in test_tile:
                plan = tile
                break

        if not plan:
            result = {"items": [], "today": []}
            if driver is not None:
                result["debug"] = self._page_debug(driver, html, note="meal_tile_not_found")
            return result

        rows = plan.split("<u>")
        if rows:
            rows.pop(0)

        output: list[dict[str, str]] = []
        for row in rows:
            try:
                raw_date = row.split("</u>", 1)[0].split(", ", 1)[1]
                meals = row.split("</u>", 1)[1].split("<strong")
                menu_entries: list[str] = []
                for meal in meals:
                    if ":" not in meal:
                        continue
                    menu_name = meal.split(">", 1)[1].split(":", 1)[0] + ": "
                    menu_text = meal.split(": </strong>", 1)[1].split("<", 1)[0]
                    menu_entries.append(menu_name + menu_text)
                if not menu_entries:
                    continue
                output.append(
                    {
                        "date": self._ddmmyyyy_to_iso(raw_date),
                        "menu": "\n\n".join(menu_entries),
                    }
                )
            except (IndexError, ValueError):
                _LOGGER.debug("Could not parse meal row", exc_info=True)

        today_str = date.today().isoformat()
        result = {
            "items": output,
            "today": [item for item in output if item["date"] == today_str],
        }
        if driver is not None:
            result["debug"] = self._page_debug(driver, html, note="meal_result")
        return result

    def _collect_activities(self, html: str, driver: WebDriver | None = None) -> dict[str, Any]:
        if "Kommende Termine" not in html:
            return {"items": [], "today": []}

        if driver is not None:
            output = self._collect_activities_dom(driver)
        else:
            _LOGGER.debug("No driver available for activities; using HTML fallback parser")
            output = self._collect_activities_html(html)

        today_str = date.today().isoformat()
        return {
            "items": output,
            "today": [item for item in output if item["date"] == today_str],
        }

    def _collect_activities_dom(self, driver: WebDriver) -> list[dict[str, Any]]:
        script = """
            const clean = (v) => (v || '').replace(/\\s+/g, ' ').trim();
            const txt = (n) => clean(n ? (n.innerText || n.textContent || '') : '');
            const dateRe = /(\\d{1,2})\\.(\\d{1,2})\\.(\\d{4})/;
            const timeRe = /\\b(\\d{1,2}:\\d{2})\\b/;
            const agRe = /\\bAG\\s+\\S[^\\n\\r]*/;

            const containers = Array.from(document.querySelectorAll('widgets-container'));
            const container = containers.find(c => c.textContent.includes('Kommende Termine'));
            if (!container) return [];

            // Flatten DOM into a linear sequence of date-header / event-column records.
            const elements = [];
            function collect(node) {
                if (!node || node.nodeType !== 1) return;
                if (node.tagName === 'STRONG') {
                    const t = txt(node);
                    if (dateRe.test(t)) {
                        elements.push({ type: 'date', text: t });
                        return;
                    }
                }
                if (node.classList && node.classList.contains('col-2')) {
                    elements.push({ type: 'event', text: txt(node) });
                    return;
                }
                node.childNodes.forEach(collect);
            }
            container.childNodes.forEach(collect);

            // Group events by the date header that precedes them.
            const results = [];
            let currentDate = null;
            let currentEntries = [];

            function flush() {
                if (currentDate && currentEntries.length > 0) {
                    results.push({ raw_date: currentDate, entries: currentEntries.slice() });
                }
            }

            elements.forEach(el => {
                if (el.type === 'date') {
                    flush();
                    currentDate = el.text.match(dateRe)[0];
                    currentEntries = [];
                } else if (el.type === 'event' && currentDate) {
                    const t = el.text;
                    if (!t.includes('AG ')) return;
                    const agMatch = t.match(agRe);
                    if (!agMatch) return;
                    const timeMatch = t.match(timeRe);
                    const time = timeMatch ? timeMatch[1] : '';
                    currentEntries.push(time ? `${time} ${clean(agMatch[0])}` : clean(agMatch[0]));
                }
            });
            flush();

            return results;
        """
        try:
            raw = driver.execute_script(script)
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Activities DOM script failed; returning empty list", exc_info=True)
            return []

        if not isinstance(raw, list):
            return []

        output: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            raw_date = str(item.get("raw_date") or "").strip()
            entries = [str(e) for e in (item.get("entries") or []) if str(e).strip()]
            if not raw_date or not entries:
                continue
            try:
                output.append({"date": self._ddmmyyyy_to_iso(raw_date), "entries": entries})
            except ValueError:
                _LOGGER.debug("Activities: could not parse date %r", raw_date)

        _LOGGER.debug("Collected %s activity entries via DOM", len(output))
        return output

    def _collect_activities_html(self, html: str) -> list[dict[str, Any]]:
        """Legacy HTML-string fallback for _collect_activities (used when no driver is available)."""
        html = html.split("Kommende Termine", 1)[1]
        html = html.split("</widgets-container>", 1)[0]
        days = html.split("<strong ")

        output: list[dict[str, Any]] = []
        for day_block in days:
            if "AG " not in day_block:
                continue
            try:
                raw_date = day_block.split("\n")[1][-10:]
                events = day_block.split("col-2")
                events.pop(0)
                entries: list[str] = []
                for event in events:
                    event_time = event.split("\n")[1][-5:]
                    entity = event.split("\n")[6]
                    if "AG " not in entity:
                        continue
                    entries.append(f"{event_time} {entity[13:]}")
                output.append({"date": self._ddmmyyyy_to_iso(raw_date), "entries": entries})
            except (IndexError, ValueError):
                _LOGGER.debug("Could not parse activity block (HTML fallback)", exc_info=True)
        return output

    def _collect_schedules(self, driver: WebDriver, start_date: str = "", debug: bool = False) -> dict[str, Any]:
        driver.get(SCHEDULE_URL + start_date)
        try:
            WebDriverWait(driver, 15).until(
                EC.any_of(
                    EC.presence_of_element_located((By.TAG_NAME, "class-hour-calendar")),
                    EC.presence_of_element_located((By.TAG_NAME, "table")),
                )
            )
        except TimeoutException:
            html = driver.page_source
            _LOGGER.warning(
                "Schedule page could not be loaded; returning empty schedule. current_url=%s excerpt=%s",
                driver.current_url,
                self._strip_tags(html)[:300],
            )
            today_name = WEEKDAY_NAMES[date.today().weekday()]
            result = {
                "week": {name: [] for name in WEEKDAY_NAMES},
                "today_name": today_name,
                "today": [],
                "error": "Schedule page could not be loaded.",
            }
            if debug:
                result["debug"] = self._page_debug(driver, html, note="schedule_timeout")
            return result

        html = driver.page_source
        if "<table" not in html:
            _LOGGER.warning(
                "Schedule table missing; returning empty schedule. current_url=%s excerpt=%s",
                driver.current_url,
                self._strip_tags(html)[:300],
            )
            today_name = WEEKDAY_NAMES[date.today().weekday()]
            result = {
                "week": {name: [] for name in WEEKDAY_NAMES},
                "today_name": today_name,
                "today": [],
                "error": "Schedule table is not available.",
            }
            if debug:
                result["debug"] = self._page_debug(driver, html, note="schedule_table_missing")
            return result

        detailed_schedule = self._collect_schedule_details_dom(driver)
        if detailed_schedule.get("week_details"):
            week_details = detailed_schedule["week_details"]
            week = {
                day_name: [
                    self._format_schedule_entry(entry)
                    for entry in week_details.get(day_name, [])
                ]
                for day_name in WEEKDAY_NAMES
            }
            today_name = WEEKDAY_NAMES[date.today().weekday()]
            result = {
                "week": week,
                "today_name": today_name,
                "today": week.get(today_name, []),
                "week_details": week_details,
                "today_details": week_details.get(today_name, []),
                "day_dates": detailed_schedule.get("day_dates", {}),
                "schedule_parser": detailed_schedule.get("parser", {}),
            }
            if debug:
                note = "schedule_dom_result_empty" if not any(week.values()) else "schedule_dom_result"
                result["debug"] = self._page_debug(driver, note=note)
            return result

        html = html.split("<table", 1)[1]
        html = html.split("</table>", 1)[0]
        rows = html.split("<tr>")
        if len(rows) < 3:
            today_name = WEEKDAY_NAMES[date.today().weekday()]
            result = {
                "week": {name: [] for name in WEEKDAY_NAMES},
                "today_name": today_name,
                "today": [],
                "error": "Schedule table did not contain lesson rows.",
            }
            if debug:
                result["debug"] = self._page_debug(driver, html, note="schedule_no_rows")
            return result
        del rows[0]
        del rows[0]

        weekdays: list[list[str]] = [[] for _ in range(7)]
        for row in rows:
            td = row.split("<td>")
            for idx, column in enumerate(td):
                if 1 <= idx <= 7:
                    weekdays[idx - 1].append(column.split("</td>", 1)[0])

        parsed_week: list[list[str]] = []
        for day in weekdays:
            parsed_day: list[str] = []
            for entity in day:
                if "span" not in entity:
                    parsed_day.append("")
                    continue
                try:
                    parsed_day.append(self._parse_schedule_cell(entity))
                except Exception:  # noqa: BLE001
                    _LOGGER.debug("Could not parse schedule cell", exc_info=True)
                    parsed_day.append("")
            parsed_week.append(parsed_day)

        week = {
            WEEKDAY_NAMES[idx]: [lesson for lesson in parsed_week[idx] if lesson]
            for idx in range(7)
        }
        today_name = WEEKDAY_NAMES[date.today().weekday()]
        result = {
            "week": week,
            "today_name": today_name,
            "today": week[today_name],
        }
        if debug:
            note = "schedule_result_empty" if not any(week.values()) else "schedule_result"
            result["debug"] = self._page_debug(driver, note=note)
        return result

    def _collect_schedule_details_dom(self, driver: WebDriver) -> dict[str, Any]:
        script = """
            const table = document.querySelector('table.calendar-table');
            if (!table) return {headers: [], entries: []};

            const clean = (value) => (value || '').replace(/\\s+/g, ' ').trim();
            const text = (node) => clean(node ? (node.innerText || node.textContent || '') : '');
            const directText = (node) => {
                if (!node) return '';
                let parts = [];
                node.childNodes.forEach((child) => {
                    if (child.nodeType === Node.TEXT_NODE) {
                        parts.push(child.textContent || '');
                    } else if (child.nodeType === Node.ELEMENT_NODE && child.tagName !== 'VISUAL-DIFF') {
                        parts.push(child.innerText || child.textContent || '');
                    } else if (child.nodeType === Node.ELEMENT_NODE) {
                        parts.push(child.innerText || child.textContent || '');
                    }
                });
                return clean(parts.join(' '));
            };
            const diffValue = (node) => {
                if (!node) return {current: '', old: '', changed: false};
                const red = Array.from(node.querySelectorAll('span[style*="red"]')).map(text).filter(Boolean);
                const green = Array.from(node.querySelectorAll('span[style*="green"]')).map(text).filter(Boolean);
                const oldValue = clean(red.join(' ').replace(/[()]/g, ''));
                const currentValue = green.length ? clean(green.join(' ')) : directText(node);
                return {current: currentValue, old: oldValue, changed: Boolean(oldValue || green.length)};
            };

            const headers = Array.from(table.querySelectorAll('thead th')).slice(1).map((header, index) => ({
                day_index: index,
                label: text(header),
            }));

            const entries = [];
            Array.from(table.querySelectorAll('tbody tr')).forEach((row) => {
                const lessonNumber = text(row.querySelector('th'));
                Array.from(row.querySelectorAll('td')).forEach((column, dayIndex) => {
                    Array.from(column.querySelectorAll('.lesson-cell')).forEach((cell, cellIndex) => {
                        const subject = diffValue(cell.querySelector('.timetable-left'));
                        const teacher = diffValue(cell.querySelector('.timetable-right'));
                        const room = diffValue(cell.querySelector('.timetable-bottom'));
                        entries.push({
                            day_index: dayIndex,
                            lesson_number: lessonNumber,
                            cell_index: cellIndex,
                            subject: subject.current,
                            subject_old: subject.old,
                            subject_changed: subject.changed,
                            teacher: teacher.current,
                            teacher_old: teacher.old,
                            teacher_changed: teacher.changed,
                            room: room.current,
                            room_old: room.old,
                            room_changed: room.changed,
                            cancelled: cell.classList.contains('cancelled'),
                            raw: text(cell),
                        });
                    });
                });
            });

            return {headers, entries};
        """
        try:
            raw = driver.execute_script(script)
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Could not collect structured schedule via DOM", exc_info=True)
            return {}

        if not isinstance(raw, dict):
            return {}

        headers = raw.get("headers", [])
        raw_entries = raw.get("entries", [])
        if not isinstance(headers, list) or not isinstance(raw_entries, list):
            return {}

        day_dates: dict[str, str | None] = {}
        day_by_index: dict[int, str] = {}
        for index, header in enumerate(headers):
            day_name = WEEKDAY_NAMES[index] if index < len(WEEKDAY_NAMES) else f"day_{index}"
            day_by_index[index] = day_name
            label = header.get("label", "") if isinstance(header, dict) else ""
            day_dates[day_name] = self._extract_schedule_header_date(label)

        week_details: dict[str, list[dict[str, Any]]] = {
            day_name: [] for day_name in WEEKDAY_NAMES
        }
        for raw_entry in raw_entries:
            if not isinstance(raw_entry, dict):
                continue
            day_index = raw_entry.get("day_index")
            if not isinstance(day_index, int):
                continue
            day_name = day_by_index.get(day_index)
            if day_name is None:
                continue
            entry = {
                "lesson_number": raw_entry.get("lesson_number") or "",
                "date": day_dates.get(day_name),
                "subject": raw_entry.get("subject") or "",
                "teacher": raw_entry.get("teacher") or "",
                "room": raw_entry.get("room") or "",
                "cancelled": bool(raw_entry.get("cancelled")),
                "cell_index": raw_entry.get("cell_index", 0),
                "raw": raw_entry.get("raw") or "",
            }
            for field in ("subject", "teacher", "room"):
                old_value = raw_entry.get(f"{field}_old") or ""
                changed = bool(raw_entry.get(f"{field}_changed"))
                if old_value:
                    entry[f"{field}_old"] = old_value
                if changed:
                    entry[f"{field}_changed"] = True
            week_details[day_name].append(entry)

        return {
            "week_details": week_details,
            "day_dates": day_dates,
            "parser": {
                "source": "dom",
                "headers_seen": len(headers),
                "entries_seen": len(raw_entries),
            },
        }

    @staticmethod
    def _format_schedule_entry(entry: dict[str, Any]) -> str:
        parts: list[str] = []
        lesson_number = str(entry.get("lesson_number") or "").strip()
        if lesson_number:
            parts.append(f"{lesson_number}.")
        if entry.get("cancelled"):
            parts.append("ausgefallen")

        subject = str(entry.get("subject") or "").strip()
        teacher = str(entry.get("teacher") or "").strip()
        room = str(entry.get("room") or "").strip()
        if subject:
            parts.append(subject)
        if teacher:
            parts.append(teacher)
        if room:
            room_old = str(entry.get("room_old") or "").strip()
            if room_old and room_old != room:
                parts.append(f"{room_old} -> {room}")
            else:
                parts.append(room)
        return " ".join(parts).strip()

    @staticmethod
    def _extract_schedule_header_date(value: str) -> str | None:
        match = re.search(r"(\d{1,2})\.(\d{1,2})\.\s*(\d{4})", value)
        if match is None:
            return None
        day, month, year = match.groups()
        try:
            return date(int(year), int(month), int(day)).isoformat()
        except ValueError:
            return None

    def _parse_schedule_cell(self, entity: str) -> str:
        if (
            not ('<span style="color' in entity and "Inter" not in entity)
            and "lesson-cell cancelled" not in entity
        ):
            lesson = (
                entity.split('timetable-left">', 1)[1]
                .split("timetable-right", 1)[0]
                .split(">")[2]
                .split("<", 1)[0]
                .replace(" ", "")
                .replace("\n", "")
            )
            teacher = (
                entity.split('timetable-right">', 1)[1]
                .split("timetable-bottom", 1)[0]
                .split(">")[5]
                .split("<", 1)[0]
                .replace(" ", "")
                .replace("\n", "")
            )
            room = (
                entity.split('timetable-bottom">', 1)[1]
                .split(">")[3]
                .split("<", 1)[0]
                .replace(" ", "")
                .replace("\n", "")
            )
            if "fa-info-circle" in entity:
                teacher = f"({teacher})"
                lesson = lesson + " → selbst."
                room = f"({room})"
            return self._strip_tags(f"{lesson} {teacher} {room}").strip()

        if "lesson-cell cancelled" in entity:
            lesson = entity.split('lesson-cell cancelled">', 1)[1]
            lesson = lesson.split('timetable-left">', 1)[1].split("timetable-right", 1)[0]
            lesson = lesson.split("</", 1)[0]
            block = entity.split("lesson-cell cancelled", 1)[1].split("</div>", 1)[0]
            block_lines = block.split("\n")
            teacher = block_lines[7].split("<", 1)[0][18:]
            room = block_lines[14][22:]
            return self._strip_tags(f"ausgefallen {lesson} {teacher} {room}").strip()

        lesson_section = entity.split('timetable-left">', 1)[1].split("timetable-right", 1)[0]
        if '<span style="color:' not in lesson_section:
            lesson = (
                lesson_section.split(">")[2]
                .split("<", 1)[0]
                .replace(" ", "")
                .replace("\n", "")
            )
        else:
            old = lesson_section.split('red;">')[2].split("<", 1)[0].replace(" ", "").replace("\n", "")
            new = lesson_section.split('green;">')[1].split("<", 1)[0].replace(" ", "").replace("\n", "")
            lesson = f"{old} → {new}"

        teacher_section = entity.split('timetable-right">', 1)[1].split("timetable-bottom", 1)[0]
        if '<span style="color:' not in teacher_section:
            teacher = (
                teacher_section.split(">")[5]
                .split("<", 1)[0]
                .replace(" ", "")
                .replace("\n", "")
            )
        else:
            old = teacher_section.split('red;">')[1].split("<", 1)[0].replace(" ", "").replace("\n", "")
            new = teacher_section.split('green;">')[1].split("<", 1)[0].replace(" ", "").replace("\n", "")
            teacher = f"{old} → {new}"

        room_section = entity.split('timetable-bottom">', 1)[1]
        if 'timetable-bottom">' in room_section:
            room_section = room_section.split('timetable-bottom">', 1)[1]
        if '<span style="color:' not in room_section:
            room = room_section.split(">")[3].split("<", 1)[0].replace(" ", "").replace("\n", "")
        elif 'red;">' in room_section:
            old = room_section.split('red;">')[2].split("<", 1)[0].replace(" ", "").replace("\n", "")
            new = room_section.split('green;">')[1].split("<", 1)[0].replace(" ", "").replace("\n", "")
            room = f"{old} → {new}"
        elif 'green;">' in room_section:
            room = room_section.split('green;">')[1].split("<", 1)[0].replace(" ", "").replace("\n", "")
        else:
            room = ""

        return self._strip_tags(f"{lesson} {teacher} {room}").strip()

    @staticmethod
    def _ddmmyyyy_to_iso(raw_date: str) -> str:
        raw_date = raw_date.strip()
        parts = raw_date.split(".")
        if len(parts) != 3:
            raise ValueError(f"Unsupported date format: {raw_date}")
        day, month, year = parts
        return f"{year.zfill(4)}-{month.zfill(2)}-{day.zfill(2)}"

    @staticmethod
    def _extract_german_date(value: str) -> date | None:
        match = GERMAN_DATE_PATTERN.search(value)
        if match is None:
            return None
        year = int(match.group("year"))
        if year < 100:
            year += 2000
        try:
            return date(year, int(match.group("month")), int(match.group("day")))
        except ValueError:
            return None

    @staticmethod
    def _clean_html_text(value: str, single_line: bool = False) -> str:
        value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
        value = re.sub(r"</p\s*>", "\n", value, flags=re.IGNORECASE)
        value = re.sub(r"<[^>]+>", "", value)
        value = html_utils.unescape(value)
        return SchulmanagerClient._clean_plain_text(value, single_line=single_line)

    @staticmethod
    def _clean_plain_text(value: str, single_line: bool = False) -> str:
        value = html_utils.unescape(value)
        lines = [
            re.sub(r"[ \t]+", " ", line).strip()
            for line in value.splitlines()
        ]
        lines = [line for line in lines if line]
        separator = " " if single_line else "\n"
        return separator.join(lines).strip()

    @staticmethod
    def _strip_tags(value: str) -> str:
        value = re.sub(r"<[^>]+>", "", value)
        value = re.sub(r"\s+", " ", value)
        return value.strip()
