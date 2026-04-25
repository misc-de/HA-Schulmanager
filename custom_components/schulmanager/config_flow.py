"""Config flow for Schulmanager."""

from __future__ import annotations

BUILD_ID = "0.3.21-optionsflow"

from typing import Any
from urllib.parse import urlparse

import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LoginInfo, SchulmanagerAuthError, SchulmanagerClient, SchulmanagerConnectionError
from .const import (
    CONF_BRIDGE_URL,
    CONF_BRIDGE_SECRET,
    CONF_MODULES,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    DEFAULT_BRIDGE_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MODULE_OPTIONS,
)

_LOGGER = logging.getLogger(__name__)
_LOGGER.warning("Loaded Schulmanager config flow build %s", BUILD_ID)


def _default_bridge_url(hass: HomeAssistant) -> str:
    """Build a sensible default bridge URL from the HA host."""
    candidates: list[str | None] = []

    api = getattr(hass.config, "api", None)
    candidates.extend(
        [
            getattr(api, "local_ip", None),
            getattr(api, "host", None),
        ]
    )

    for configured_url in (
        getattr(hass.config, "internal_url", None),
        getattr(hass.config, "external_url", None),
    ):
        if configured_url:
            parsed = urlparse(configured_url)
            candidates.append(parsed.hostname)

    for host in candidates:
        if not host or host in {"0.0.0.0", "::", "::1"}:
            continue
        return f"http://{host}:8099"

    return DEFAULT_BRIDGE_URL



class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> LoginInfo:
    """Validate the user input allows us to connect."""
    _LOGGER.info(
        "Validating Schulmanager config flow for bridge %s",
        data[CONF_BRIDGE_URL],
    )
    client = SchulmanagerClient(
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        bridge_url=data[CONF_BRIDGE_URL],
        bridge_secret=data.get(CONF_BRIDGE_SECRET, ""),
    )
    try:
        return await client.validate_login(async_get_clientsession(hass))
    except SchulmanagerAuthError as err:
        _LOGGER.warning("Schulmanager config flow failed due to invalid credentials")
        raise InvalidAuth from err
    except SchulmanagerConnectionError as err:
        _LOGGER.error("Schulmanager config flow could not connect: %s", err)
        raise CannotConnect from err


class SchulmanagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Schulmanager."""

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "SchulmanagerOptionsFlowHandler":
        """Create the options flow."""
        _LOGGER.warning("Creating Schulmanager options flow build %s", BUILD_ID)
        return SchulmanagerOptionsFlowHandler()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during Schulmanager config flow")
                errors["base"] = "unknown"
            else:
                _LOGGER.info("Schulmanager config flow succeeded for %s", info.unique_id)
                await self.async_set_unique_id(info.unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info.title,
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                    options={
                        CONF_BRIDGE_URL: user_input[CONF_BRIDGE_URL],
                        CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                        CONF_MODULES: user_input[CONF_MODULES],
                        CONF_BRIDGE_SECRET: user_input.get(CONF_BRIDGE_SECRET, ""),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self._build_user_schema(user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await validate_input(
                    self.hass,
                    {
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_BRIDGE_URL: user_input[CONF_BRIDGE_URL],
                        CONF_BRIDGE_SECRET: user_input.get(CONF_BRIDGE_SECRET, ""),
                    },
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during Schulmanager reconfigure flow")
                errors["base"] = "unknown"
            else:
                _LOGGER.info("Schulmanager reconfigure flow succeeded for %s", entry.title)
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        **entry.data,
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                    options={
                        **entry.options,
                        CONF_BRIDGE_URL: user_input[CONF_BRIDGE_URL],
                        CONF_BRIDGE_SECRET: user_input.get(CONF_BRIDGE_SECRET, ""),
                    },
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=entry.data.get(CONF_USERNAME, ""),
                    ): str,
                    vol.Required(
                        CONF_PASSWORD,
                        default=entry.data.get(CONF_PASSWORD, ""),
                    ): str,
                    vol.Required(
                        CONF_BRIDGE_URL,
                        default=entry.options.get(
                            CONF_BRIDGE_URL, _default_bridge_url(self.hass)
                        ),
                    ): str,
                    vol.Optional(
                        CONF_BRIDGE_SECRET,
                        default=entry.options.get(CONF_BRIDGE_SECRET, ""),
                    ): str,
                }
            ),
            errors=errors,
        )

    def _build_user_schema(self, user_input: dict[str, Any] | None) -> vol.Schema:
        modules_default = list(MODULE_OPTIONS.keys())
        if user_input is not None:
            modules_default = user_input.get(CONF_MODULES, modules_default)

        return vol.Schema(
            {
                vol.Required(
                    CONF_USERNAME,
                    default=(user_input or {}).get(CONF_USERNAME, ""),
                ): str,
                vol.Required(
                    CONF_PASSWORD,
                    default=(user_input or {}).get(CONF_PASSWORD, ""),
                ): str,
                vol.Required(
                    CONF_BRIDGE_URL,
                    default=(user_input or {}).get(
                        CONF_BRIDGE_URL, _default_bridge_url(self.hass)
                    ),
                ): str,
                vol.Optional(
                    CONF_BRIDGE_SECRET,
                    default=(user_input or {}).get(CONF_BRIDGE_SECRET, ""),
                ): str,
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=(user_input or {}).get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=240)),
                vol.Required(CONF_MODULES, default=modules_default): cv.multi_select(
                    MODULE_OPTIONS
                ),
            }
        )


class SchulmanagerOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Schulmanager."""

    def __init__(self) -> None:
        """Initialize options flow."""
        _LOGGER.warning("Initializing SchulmanagerOptionsFlowHandler build %s", BUILD_ID)

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            _LOGGER.info("Schulmanager options updated for %s", self.config_entry.title)
            return self.async_create_entry(title="", data=user_input)

        try:
            modules_default = list(self.config_entry.options.get(
                CONF_MODULES, list(MODULE_OPTIONS.keys())
            ))
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Could not read saved Schulmanager modules from options; using defaults")
            modules_default = list(MODULE_OPTIONS.keys())

        scan_interval_default = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        bridge_url_default = self.config_entry.options.get(
            CONF_BRIDGE_URL, DEFAULT_BRIDGE_URL
        )
        bridge_secret_default = self.config_entry.options.get(
            CONF_BRIDGE_SECRET, ""
        )

        _LOGGER.info(
            "Opening Schulmanager options flow for %s with modules=%s interval=%s bridge=%s",
            self.config_entry.title,
            ", ".join(modules_default),
            scan_interval_default,
            bridge_url_default,
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MODULES,
                        default=modules_default,
                    ): cv.multi_select(MODULE_OPTIONS),
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=scan_interval_default,
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=240)),
                    vol.Required(
                        CONF_BRIDGE_URL,
                        default=bridge_url_default,
                    ): str,
                    vol.Optional(
                        CONF_BRIDGE_SECRET,
                        default=bridge_secret_default,
                    ): str,
                }
            ),
        )
