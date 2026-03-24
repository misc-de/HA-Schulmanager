"""The Schulmanager integration."""

from __future__ import annotations

INTEGRATION_BUILD = "0.3.18"

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .api import SchulmanagerClient
from .const import (
    CONF_BRIDGE_URL,
    CONF_BRIDGE_SECRET,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEFAULT_BRIDGE_URL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import SchulmanagerCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_REFRESH = "refresh"
SERVICE_SCHEMA = vol.Schema({vol.Optional("entry_id"): cv.string})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Schulmanager from yaml."""
    hass.data.setdefault(DOMAIN, {})

    async def _async_handle_refresh_service(call: ServiceCall) -> None:
        entry_id = call.data.get("entry_id")
        targets: list[tuple[str, SchulmanagerCoordinator]] = []
        for current_entry_id, payload in hass.data.get(DOMAIN, {}).items():
            if entry_id and current_entry_id != entry_id:
                continue
            coordinator = payload.get("coordinator")
            if coordinator is not None:
                targets.append((current_entry_id, coordinator))

        for current_entry_id, coordinator in targets:
            _LOGGER.info("Manual Schulmanager refresh requested for entry '%s'", current_entry_id)
            await coordinator.async_request_refresh()

    if not hass.services.has_service(DOMAIN, SERVICE_REFRESH):
        hass.services.async_register(
            DOMAIN,
            SERVICE_REFRESH,
            _async_handle_refresh_service,
            schema=SERVICE_SCHEMA,
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Schulmanager from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    bridge_url = entry.options.get(CONF_BRIDGE_URL, DEFAULT_BRIDGE_URL)
    _LOGGER.warning("Setting up Schulmanager integration build %s", INTEGRATION_BUILD)
    _LOGGER.info(
        "Setting up Schulmanager entry '%s' via bridge %s",
        entry.title or entry.entry_id,
        bridge_url,
    )

    client = SchulmanagerClient(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        bridge_url=bridge_url,
        bridge_secret=entry.options.get(CONF_BRIDGE_SECRET, ""),
    )
    coordinator = SchulmanagerCoordinator(hass, entry, client)

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Do the first refresh in the background. The Schulmanager scrape can take
    # 30+ seconds, which otherwise makes config flows and reloads hit reverse
    # proxy timeouts. Entities are created immediately and will become
    # available as soon as the coordinator returns data.
    hass.async_create_task(_async_initial_refresh(coordinator, entry))

    _LOGGER.info(
        "Schulmanager entry '%s' set up successfully",
        entry.title or entry.entry_id,
    )
    return True


async def _async_initial_refresh(
    coordinator: SchulmanagerCoordinator,
    entry: ConfigEntry,
) -> None:
    """Run the first data refresh without blocking setup."""
    try:
        await coordinator.async_refresh()
        _LOGGER.info(
            "Initial background refresh for Schulmanager entry '%s' completed",
            entry.title or entry.entry_id,
        )
    except Exception:  # noqa: BLE001
        _LOGGER.exception(
            "Initial background refresh for Schulmanager entry '%s' failed",
            entry.title or entry.entry_id,
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Schulmanager entry '%s'", entry.title or entry.entry_id)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN] and hass.services.has_service(DOMAIN, SERVICE_REFRESH):
            hass.services.async_remove(DOMAIN, SERVICE_REFRESH)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    _LOGGER.info("Reloading Schulmanager entry '%s'", entry.title or entry.entry_id)
    await hass.config_entries.async_reload(entry.entry_id)
