"""Binary sensors for Schulmanager."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SchulmanagerCoordinator


@dataclass(frozen=True, kw_only=True)
class SchulmanagerBinarySensorDescription(BinarySensorEntityDescription):
    """Description for Schulmanager binary sensors."""


BINARY_SENSOR_TYPES = {
    "stale_data": SchulmanagerBinarySensorDescription(
        key="stale_data",
        name="Daten veraltet",
        icon="mdi:cloud-alert",
    ),
    "module_errors": SchulmanagerBinarySensorDescription(
        key="module_errors",
        name="Modulfehler",
        icon="mdi:alert-circle",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Schulmanager binary sensors."""
    coordinator: SchulmanagerCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        [SchulmanagerBinarySensor(entry, coordinator, description) for description in BINARY_SENSOR_TYPES.values()]
    )


class SchulmanagerBinarySensor(CoordinatorEntity[SchulmanagerCoordinator], BinarySensorEntity):
    """Binary sensor representing Schulmanager health."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: SchulmanagerCoordinator,
        description: SchulmanagerBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_translation_key = description.key
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_name = description.name
        self._attr_icon = description.icon

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
    def is_on(self) -> bool:
        meta = self._meta
        if self.entity_description.key == "stale_data":
            stale = meta.get("module_stale", {})
            return any(bool(v) for v in stale.values()) if isinstance(stale, dict) else False
        if self.entity_description.key == "module_errors":
            errors = meta.get("module_errors", {})
            return any(bool(v) and v != "Using last known good data." for v in errors.values()) if isinstance(errors, dict) else False
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        meta = self._meta
        return {
            "module_errors": meta.get("module_errors", {}),
            "module_stale": meta.get("module_stale", {}),
            "last_successful_update": meta.get("last_successful_update"),
            "last_attempted_update": meta.get("last_attempted_update"),
        }

    @property
    def _meta(self) -> dict[str, Any]:
        data = self.coordinator.data if isinstance(self.coordinator.data, dict) else {}
        meta = data.get("meta", {})
        return meta if isinstance(meta, dict) else {}
