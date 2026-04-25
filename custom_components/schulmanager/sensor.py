"""Sensor platform for Schulmanager."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SchulmanagerCoordinator

MAX_STATE_LENGTH = 255
WEEKDAY_SHORT = {
    "Montag": "Mo",
    "Dienstag": "Di",
    "Mittwoch": "Mi",
    "Donnerstag": "Do",
    "Freitag": "Fr",
    "Samstag": "Sa",
    "Sonntag": "So",
    "monday": "Mo",
    "tuesday": "Di",
    "wednesday": "Mi",
    "thursday": "Do",
    "friday": "Fr",
    "saturday": "Sa",
    "sunday": "So",
}


@dataclass(frozen=True, kw_only=True)
class SchulmanagerSensorDescription(SensorEntityDescription):
    """Description for Schulmanager sensors."""

    source_module: str
    variant: str = "default"


SENSOR_TYPES: dict[str, SchulmanagerSensorDescription] = {
    "account": SchulmanagerSensorDescription(
        key="account",
        name="Konto",
        icon="mdi:account-school",
        source_module="account",
    ),
    "schedules": SchulmanagerSensorDescription(
        key="schedules",
        name="Stundenplan Heute",
        icon="mdi:calendar-clock",
        source_module="schedules",
    ),
    "schedules_week": SchulmanagerSensorDescription(
        key="schedules_week",
        name="Stundenplan Woche",
        icon="mdi:calendar-week",
        source_module="schedules",
        variant="week",
    ),
    "homework": SchulmanagerSensorDescription(
        key="homework",
        name="Hausaufgaben",
        icon="mdi:book-education",
        source_module="homework",
    ),
    "calendar": SchulmanagerSensorDescription(
        key="calendar",
        name="Kalender",
        icon="mdi:calendar-month",
        source_module="calendar",
    ),
    "exams": SchulmanagerSensorDescription(
        key="exams",
        name="Klausuren",
        icon="mdi:clipboard-text-clock",
        source_module="exams",
    ),
    "meal": SchulmanagerSensorDescription(
        key="meal",
        name="Speiseplan Heute",
        icon="mdi:silverware-fork-knife",
        source_module="meal",
    ),
    "activities": SchulmanagerSensorDescription(
        key="activities",
        name="AGs",
        icon="mdi:account-group",
        source_module="activities",
    ),
}


def _truncate_state(value: str) -> str:
    if len(value) <= MAX_STATE_LENGTH:
        return value
    return value[: MAX_STATE_LENGTH - 1].rstrip() + "…"


def _join_lines(lines: list[str]) -> str:
    cleaned = [line.strip() for line in lines if isinstance(line, str) and line.strip()]
    if not cleaned:
        return "Keine Einträge"
    return _truncate_state(" | ".join(cleaned))


def _meal_lines(items: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in items:
        if isinstance(item, dict):
            menu = item.get("menu")
            if isinstance(menu, str) and menu.strip():
                compact = " ".join(part.strip() for part in menu.splitlines() if part.strip())
                if compact:
                    lines.append(compact)
        elif isinstance(item, str) and item.strip():
            lines.append(item.strip())
    return lines


def _week_summary(week: dict[str, list[str]]) -> str:
    parts: list[str] = []
    for day_name, lessons in week.items():
        short = WEEKDAY_SHORT.get(day_name, day_name[:2])
        if lessons:
            parts.append(f"{short}: {', '.join(lessons[:2])}{' …' if len(lessons) > 2 else ''}")
        else:
            parts.append(f"{short}: -")
    return _truncate_state(" | ".join(parts)) if parts else "Keine Einträge"


def _week_formatted(week: dict[str, list[str]]) -> str:
    lines: list[str] = []
    for day_name, lessons in week.items():
        label = WEEKDAY_SHORT.get(day_name, day_name)
        if lessons:
            lines.append(f"{label}: " + " | ".join(lessons))
        else:
            lines.append(f"{label}: Keine Einträge")
    return "\n".join(lines)


def _week_rows(week: dict[str, list[str]]) -> list[dict[str, str]]:
    order = [
        ("Mo", week.get("monday") or week.get("Montag") or []),
        ("Di", week.get("tuesday") or week.get("Dienstag") or []),
        ("Mi", week.get("wednesday") or week.get("Mittwoch") or []),
        ("Do", week.get("thursday") or week.get("Donnerstag") or []),
        ("Fr", week.get("friday") or week.get("Freitag") or []),
    ]
    max_len = max((len(values) for _, values in order), default=0)
    rows: list[dict[str, str]] = []
    for index in range(max_len):
        row: dict[str, str] = {"lesson": str(index + 1)}
        for label, values in order:
            row[label] = values[index] if index < len(values) else ""
        rows.append(row)
    return rows


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: SchulmanagerCoordinator = data["coordinator"]

    entities: list[SchulmanagerModuleSensor] = []
    for module in coordinator.modules:
        if module in SENSOR_TYPES:
            entities.append(SchulmanagerModuleSensor(entry, coordinator, SENSOR_TYPES[module]))
        if module == "schedules":
            entities.append(SchulmanagerModuleSensor(entry, coordinator, SENSOR_TYPES["schedules_week"]))

    async_add_entities(entities)


class SchulmanagerModuleSensor(CoordinatorEntity[SchulmanagerCoordinator], SensorEntity):
    """Single sensor representing one Schulmanager module."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: SchulmanagerCoordinator,
        description: SchulmanagerSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_translation_key = description.key
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_name = description.name
        self._attr_icon = description.icon

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self._module_data is not None

    @property
    def device_info(self) -> DeviceInfo:
        title = self._entry.title or "Schulmanager"
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=title,
            manufacturer="Schulmanager Online",
            model="Web Portal",
            entry_type=None,
        )

    @property
    def _module_data(self) -> dict[str, Any] | None:
        data = self.coordinator.data
        if not isinstance(data, dict):
            return None
        module_data = data.get(self.entity_description.source_module)
        if isinstance(module_data, dict):
            return module_data
        return None

    @property
    def native_value(self) -> str | int | None:
        data = self._module_data
        if data is None:
            return None

        key = self.entity_description.key
        if key == "account":
            return data.get("full_name") or data.get("raw") or "Verfügbar"
        if key == "schedules":
            return _join_lines(data.get("today", []))
        if key == "schedules_week":
            week = data.get("week", {}) if isinstance(data.get("week"), dict) else {}
            return _week_summary(week) if week else "Keine Einträge"
        if key == "meal":
            return _join_lines(_meal_lines(data.get("today", [])))
        if key in {"homework", "calendar", "exams", "activities"}:
            return len(data.get("items", []))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._module_data
        if data is None:
            return {"error": "Noch keine Daten geladen.", "data_stale": False}

        coordinator_data = self.coordinator.data if isinstance(self.coordinator.data, dict) else {}
        meta = coordinator_data.get("meta", {}) if isinstance(coordinator_data.get("meta"), dict) else {}
        key = self.entity_description.source_module
        module_errors = meta.get("module_errors", {}) if isinstance(meta.get("module_errors"), dict) else {}
        module_stale = meta.get("module_stale", {}) if isinstance(meta.get("module_stale"), dict) else {}
        module_error = module_errors.get(key) or data.get("error")
        stale = bool(module_stale.get(key, False))
        common = {
            "error": module_error,
            "data_stale": stale,
            "last_successful_update": meta.get("last_successful_update"),
            "last_attempted_update": meta.get("last_attempted_update"),
        }
        if key == "account":
            return {
                "first_name": data.get("first_name"),
                "surname": data.get("surname"),
                "class_year": data.get("class_year"),
                "branch": data.get("branch"),
                "raw": data.get("raw"),
                **common,
            }
        if self.entity_description.key == "schedules":
            week = data.get("week", {}) if isinstance(data.get("week"), dict) else {}
            return {
                "today_name": data.get("today_name"),
                "today": data.get("today", []),
                "formatted_today": _join_lines(data.get("today", [])),
                "week": week,
                "formatted_week": _week_formatted(week),
                "week_rows": _week_rows(week),
                **common,
            }
        if self.entity_description.key == "schedules_week":
            week = data.get("week", {}) if isinstance(data.get("week"), dict) else {}
            return {
                "today_name": data.get("today_name"),
                "week": week,
                "formatted_week": _week_formatted(week),
                "week_rows": _week_rows(week),
                **common,
            }
        if key == "meal":
            today_items = data.get("today", [])
            return {
                "today": today_items,
                "items": data.get("items", []),
                "formatted_today": _join_lines(_meal_lines(today_items)),
                **common,
            }
        return {
            "items": data.get("items", []),
            "today": data.get("today", []),
            "parser": data.get("parser"),
            **common,
        }
