"""Coordinator for Schulmanager data updates."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SchulmanagerAuthError, SchulmanagerClient, SchulmanagerConnectionError
from .const import CONF_MODULES, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN, MODULE_OPTIONS

_LOGGER = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _module_has_meaningful_data(module: str, data: dict[str, Any] | None) -> bool:
    if not isinstance(data, dict):
        return False
    if module == "account":
        return bool(data.get("full_name") or data.get("raw"))
    if module == "schedules":
        week = data.get("week")
        today = data.get("today")
        if isinstance(today, list) and today:
            return True
        if isinstance(week, dict):
            return any(isinstance(v, list) and len(v) > 0 for v in week.values())
        return False
    if module == "meal":
        return bool(data.get("today") or data.get("items"))
    return bool(data.get("items") or data.get("today"))


class SchulmanagerCoordinator(DataUpdateCoordinator[dict]):
    """Fetch Schulmanager data on a fixed interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: SchulmanagerClient,
    ) -> None:
        modules = entry.options.get(CONF_MODULES, list(MODULE_OPTIONS.keys()))
        scan_interval = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        self.entry = entry
        self.client = client
        self.modules = list(modules)
        self._session = async_get_clientsession(hass)
        self._last_good_modules: dict[str, dict[str, Any]] = {}
        self._last_successful_update: str | None = None
        self._last_attempted_update: str | None = None
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(minutes=scan_interval),
        )
        _LOGGER.info(
            "Schulmanager coordinator created for '%s' with modules=%s interval=%s min",
            entry.title or entry.entry_id,
            ", ".join(self.modules),
            scan_interval,
        )

    async def _async_update_data(self) -> dict:
        self._last_attempted_update = _utc_now_iso()
        try:
            fresh_data = await self.client.fetch_data(self._session, self.modules)
            data = self._merge_with_last_good_data(fresh_data)
            _LOGGER.debug(
                "Schulmanager update successful for '%s'; keys=%s",
                self.entry.title or self.entry.entry_id,
                ", ".join(sorted(data.keys())),
            )
            self._last_successful_update = _utc_now_iso()
            return data
        except SchulmanagerAuthError as err:
            _LOGGER.warning(
                "Schulmanager authentication failed for '%s'",
                self.entry.title or self.entry.entry_id,
            )
            raise ConfigEntryAuthFailed(str(err)) from err
        except SchulmanagerConnectionError as err:
            _LOGGER.error(
                "Schulmanager update failed for '%s': %s",
                self.entry.title or self.entry.entry_id,
                err,
            )
            raise UpdateFailed(str(err)) from err
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception(
                "Unexpected Schulmanager update error for '%s'",
                self.entry.title or self.entry.entry_id,
            )
            raise UpdateFailed(f"Unexpected update error: {err}") from err

    def _merge_with_last_good_data(self, fresh_data: dict[str, Any]) -> dict[str, Any]:
        data = dict(fresh_data) if isinstance(fresh_data, dict) else {}
        meta = dict(data.get("meta", {})) if isinstance(data.get("meta"), dict) else {}
        module_errors = dict(meta.get("module_errors", {})) if isinstance(meta.get("module_errors"), dict) else {}
        stale_modules: dict[str, bool] = {}

        for module in self.modules:
            module_data = data.get(module)
            if _module_has_meaningful_data(module, module_data):
                self._last_good_modules[module] = module_data
                stale_modules[module] = False
                continue

            last_good = self._last_good_modules.get(module)
            if last_good is not None:
                data[module] = last_good
                stale_modules[module] = True
                if module not in module_errors:
                    module_errors[module] = "Using last known good data."
                _LOGGER.debug(
                    "Schulmanager module '%s' returned no useful data; reusing last good payload",
                    module,
                )
            else:
                stale_modules[module] = False

        meta["module_errors"] = module_errors
        meta["module_stale"] = stale_modules
        meta["last_successful_update"] = self._last_successful_update
        meta["last_attempted_update"] = self._last_attempted_update
        data["meta"] = meta
        return data
