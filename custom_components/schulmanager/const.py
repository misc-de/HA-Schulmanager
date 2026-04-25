"""Constants for the Schulmanager integration."""

from __future__ import annotations

DOMAIN = "schulmanager"
PLATFORMS = ["sensor", "binary_sensor"]

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_BRIDGE_URL = "bridge_url"
CONF_BRIDGE_SECRET = "bridge_secret"
CONF_MODULES = "modules"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_BRIDGE_URL = "http://local-schulmanager-bridge:8099"
DEFAULT_SCAN_INTERVAL = 60

MODULE_ACCOUNT = "account"
MODULE_SCHEDULES = "schedules"
MODULE_HOMEWORK = "homework"
MODULE_CALENDAR = "calendar"
MODULE_EXAMS = "exams"
MODULE_MEAL = "meal"
MODULE_ACTIVITIES = "activities"

MODULE_OPTIONS = {
    MODULE_ACCOUNT: "Kontodaten",
    MODULE_SCHEDULES: "Stundenplan",
    MODULE_HOMEWORK: "Hausaufgaben",
    MODULE_CALENDAR: "Kalender",
    MODULE_EXAMS: "Klausuren",
    MODULE_MEAL: "Speiseplan",
    MODULE_ACTIVITIES: "AGs / Veranstaltungen",
}
