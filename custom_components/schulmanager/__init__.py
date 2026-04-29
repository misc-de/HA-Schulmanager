"""The Schulmanager integration."""

from __future__ import annotations

INTEGRATION_BUILD = "0.3.33"

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

try:
    from homeassistant.components.http import StaticPathConfig
except ImportError:  # pragma: no cover - older Home Assistant fallback
    StaticPathConfig = None  # type: ignore[assignment]

try:
    from homeassistant.components.frontend import add_extra_js_url
except ImportError:  # pragma: no cover - older Home Assistant fallback
    add_extra_js_url = None  # type: ignore[assignment]

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
FRONTEND_URL = "/schulmanager_static"
FRONTEND_DIR = Path(__file__).parent / "www"
FRONTEND_CARD_URL = f"{FRONTEND_URL}/schulmanager-timetable-card.js?v={INTEGRATION_BUILD}"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Schulmanager from yaml."""
    hass.data.setdefault(DOMAIN, {})
    await _async_register_frontend(hass)

    async def _async_handle_refresh_service(call: ServiceCall) -> None:
        entry_id = call.data.get("entry_id")
        targets: list[tuple[str, SchulmanagerCoordinator]] = []
        for current_entry_id, payload in hass.data.get(DOMAIN, {}).items():
            if not isinstance(payload, dict):
                continue
            if entry_id and current_entry_id != entry_id:
                continue
            coordinator = payload.get("coordinator")
            if coordinator is not None:
                targets.append((current_entry_id, coordinator))

        if not targets:
            raise HomeAssistantError(
                f"Keine Schulmanager-Online-Integration für entry_id='{entry_id}' gefunden."
                if entry_id
                else "Keine Schulmanager-Online-Integration zum Aktualisieren gefunden."
            )

        for current_entry_id, coordinator in targets:
            _LOGGER.info("Manual Schulmanager refresh requested for entry '%s'", current_entry_id)
            try:
                await coordinator.async_request_refresh()
            except Exception as err:  # noqa: BLE001
                _LOGGER.exception(
                    "Manual Schulmanager refresh failed for entry '%s'",
                    current_entry_id,
                )
                raise HomeAssistantError(
                    f"Schulmanager Online konnte nicht aktualisiert werden: {err}"
                ) from err

    if not hass.services.has_service(DOMAIN, SERVICE_REFRESH):
        hass.services.async_register(
            DOMAIN,
            SERVICE_REFRESH,
            _async_handle_refresh_service,
            schema=SERVICE_SCHEMA,
        )

    return True


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Expose Schulmanager frontend assets."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("frontend_registered"):
        return

    if hasattr(hass.http, "async_register_static_paths") and StaticPathConfig is not None:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(FRONTEND_URL, str(FRONTEND_DIR), True)]
        )
    else:
        hass.http.register_static_path(FRONTEND_URL, str(FRONTEND_DIR), True)

    registered = await _async_add_lovelace_resource(hass, FRONTEND_CARD_URL)
    if not registered and add_extra_js_url is not None:
        add_extra_js_url(hass, FRONTEND_CARD_URL)
        _LOGGER.info("Registered Schulmanager frontend module via add_extra_js_url: %s", FRONTEND_CARD_URL)
    elif not registered:
        _LOGGER.warning(
            "Could not register Lovelace resource automatically. "
            "Add manually via Settings → Dashboards → Resources: %s (type: module)",
            FRONTEND_CARD_URL,
        )

    domain_data["frontend_registered"] = True
    _LOGGER.info("Registered Schulmanager frontend assets at %s", FRONTEND_URL)


async def _async_add_lovelace_resource(hass: HomeAssistant, url: str) -> bool:
    """Register the card JS in Lovelace resource storage (storage-mode dashboards only)."""
    try:
        lovelace_data = hass.data.get("lovelace")
        if lovelace_data is None:
            return False
        resources = getattr(lovelace_data, "resources", None)
        if resources is None or not callable(getattr(resources, "async_items", None)):
            return False
        base_url = url.split("?")[0]
        for item in resources.async_items():
            if item.get("url", "").split("?")[0] == base_url:
                _LOGGER.debug("Lovelace resource already registered: %s", base_url)
                return True
        await resources.async_create_item({"res_type": "module", "url": url})
        _LOGGER.info("Registered Lovelace resource: %s", url)
        return True
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Could not register Lovelace resource: %s", err)
        return False


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
