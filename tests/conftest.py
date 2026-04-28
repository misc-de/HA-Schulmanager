"""Test helpers for all Schulmanager unit tests.

The bridge and HA integration import Selenium, aiohttp, and homeassistant at
module import time. These lightweight stubs keep tests runnable without those
packages installed locally.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from dataclasses import dataclass as _dc
from pathlib import Path
from typing import Any


def _install_selenium_stubs() -> None:
    selenium = types.ModuleType("selenium")
    webdriver = types.ModuleType("selenium.webdriver")
    common = types.ModuleType("selenium.common")
    exceptions = types.ModuleType("selenium.common.exceptions")
    chrome = types.ModuleType("selenium.webdriver.chrome")
    chrome_options = types.ModuleType("selenium.webdriver.chrome.options")
    chrome_service = types.ModuleType("selenium.webdriver.chrome.service")
    webdriver_common = types.ModuleType("selenium.webdriver.common")
    by = types.ModuleType("selenium.webdriver.common.by")
    keys = types.ModuleType("selenium.webdriver.common.keys")
    remote = types.ModuleType("selenium.webdriver.remote")
    remote_webdriver = types.ModuleType("selenium.webdriver.remote.webdriver")
    support = types.ModuleType("selenium.webdriver.support")
    expected_conditions = types.ModuleType("selenium.webdriver.support.expected_conditions")
    support_ui = types.ModuleType("selenium.webdriver.support.ui")

    class TimeoutException(Exception):
        pass

    class WebDriverException(Exception):
        pass

    class Options:
        def __init__(self) -> None:
            self.binary_location = ""
            self.arguments: list[str] = []

        def add_argument(self, value: str) -> None:
            self.arguments.append(value)

    class Service:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

    class By:
        CSS_SELECTOR = "css selector"
        ID = "id"
        TAG_NAME = "tag name"

    class Keys:
        RETURN = "\n"

    class WebDriver:
        pass

    class WebDriverWait:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def until(self, method):
            return method

    expected_conditions.any_of = lambda *conditions: conditions
    expected_conditions.presence_of_element_located = lambda locator: locator
    expected_conditions.visibility_of_element_located = lambda locator: locator

    webdriver.Chrome = lambda *args, **kwargs: None
    exceptions.TimeoutException = TimeoutException
    exceptions.WebDriverException = WebDriverException
    chrome_options.Options = Options
    chrome_service.Service = Service
    by.By = By
    keys.Keys = Keys
    remote_webdriver.WebDriver = WebDriver
    support_ui.WebDriverWait = WebDriverWait

    modules = {
        "selenium": selenium,
        "selenium.webdriver": webdriver,
        "selenium.common": common,
        "selenium.common.exceptions": exceptions,
        "selenium.webdriver.chrome": chrome,
        "selenium.webdriver.chrome.options": chrome_options,
        "selenium.webdriver.chrome.service": chrome_service,
        "selenium.webdriver.common": webdriver_common,
        "selenium.webdriver.common.by": by,
        "selenium.webdriver.common.keys": keys,
        "selenium.webdriver.remote": remote,
        "selenium.webdriver.remote.webdriver": remote_webdriver,
        "selenium.webdriver.support": support,
        "selenium.webdriver.support.expected_conditions": expected_conditions,
        "selenium.webdriver.support.ui": support_ui,
    }
    for name, module in modules.items():
        sys.modules.setdefault(name, module)


_install_selenium_stubs()


# ── aiohttp stubs ─────────────────────────────────────────────────────────────

class _ClientError(Exception):
    pass


class _ClientResponseError(_ClientError):
    pass


class _ClientSession:
    pass


def _install_aiohttp_stubs() -> None:
    mod = types.ModuleType("aiohttp")
    mod.ClientError = _ClientError  # type: ignore[attr-defined]
    mod.ClientResponseError = _ClientResponseError  # type: ignore[attr-defined]
    mod.ClientSession = _ClientSession  # type: ignore[attr-defined]
    sys.modules.setdefault("aiohttp", mod)


_install_aiohttp_stubs()


# ── homeassistant stubs ───────────────────────────────────────────────────────

@_dc(frozen=True, kw_only=True)
class _SensorEntityDescription:
    key: str = ""
    name: str | None = None
    icon: str | None = None
    has_entity_name: bool = False
    translation_key: str | None = None


@_dc(frozen=True, kw_only=True)
class _BinarySensorEntityDescription:
    key: str = ""
    name: str | None = None
    icon: str | None = None
    has_entity_name: bool = False
    translation_key: str | None = None


class _SensorEntity:
    _attr_has_entity_name: bool = False
    _attr_unique_id: str | None = None
    _attr_name: str | None = None
    _attr_icon: str | None = None
    _attr_translation_key: str | None = None


class _BinarySensorEntity:
    _attr_has_entity_name: bool = False
    _attr_unique_id: str | None = None
    _attr_name: str | None = None
    _attr_icon: str | None = None
    _attr_translation_key: str | None = None


class _DataUpdateCoordinator:
    last_update_success: bool = True
    data: Any = None

    def __init__(self, hass: Any, logger: Any, *, name: str, update_interval: Any) -> None:
        self.hass = hass
        self.name = name
        self.update_interval = update_interval
        self.last_update_success = True
        self.data = None

    @classmethod
    def __class_getitem__(cls, item: Any) -> type:
        return cls


class _CoordinatorEntity:
    def __init__(self, coordinator: Any) -> None:
        self.coordinator = coordinator

    @classmethod
    def __class_getitem__(cls, item: Any) -> type:
        return cls


class _ConfigEntryAuthFailed(Exception):
    pass


class _UpdateFailed(Exception):
    pass


class _HomeAssistantError(Exception):
    pass


class _DeviceInfo(dict):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)


def _mk(name: str, **attrs: Any) -> types.ModuleType:
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules.setdefault(name, mod)
    return mod


def _install_homeassistant_stubs() -> None:
    _mk("homeassistant")
    _mk("homeassistant.components")
    _mk("homeassistant.components.sensor", SensorEntity=_SensorEntity, SensorEntityDescription=_SensorEntityDescription)
    _mk("homeassistant.components.binary_sensor", BinarySensorEntity=_BinarySensorEntity, BinarySensorEntityDescription=_BinarySensorEntityDescription)
    _mk("homeassistant.components.http")
    _mk("homeassistant.components.frontend")
    class _ConfigEntry:
        def __init__(self, entry_id: str = "test_id", title: str = "Test", options: dict | None = None, data: dict | None = None) -> None:
            self.entry_id = entry_id
            self.title = title
            self.options = options or {}
            self.data = data or {}

    _mk("homeassistant.config_entries", ConfigEntry=_ConfigEntry)

    class _HomeAssistant:
        def __init__(self) -> None:
            self.data: dict = {}

    _mk("homeassistant.core", HomeAssistant=_HomeAssistant, ServiceCall=object)
    _mk("homeassistant.exceptions", ConfigEntryAuthFailed=_ConfigEntryAuthFailed, HomeAssistantError=_HomeAssistantError)
    _mk("homeassistant.helpers")
    _mk("homeassistant.helpers.aiohttp_client", async_get_clientsession=lambda hass: _ClientSession())
    _mk("homeassistant.helpers.entity", DeviceInfo=_DeviceInfo)
    _mk("homeassistant.helpers.entity_platform", AddEntitiesCallback=object)
    _mk("homeassistant.helpers.update_coordinator", DataUpdateCoordinator=_DataUpdateCoordinator, CoordinatorEntity=_CoordinatorEntity, UpdateFailed=_UpdateFailed)
    _mk("homeassistant.helpers.typing")
    _mk("homeassistant.helpers.config_validation")
    _mk("voluptuous", Schema=lambda x: x, Optional=lambda *a, **kw: a[0] if a else None, Required=lambda x: x)


_install_homeassistant_stubs()


# ── Load custom_components modules in dependency order ─────────────────────────

_CC_BASE = Path(__file__).parent.parent / "custom_components" / "schulmanager"

_mk("custom_components")
_mk("custom_components.schulmanager")


def _load_cc(module_name: str) -> types.ModuleType:
    """Load custom_components/schulmanager/<module_name>.py into sys.modules."""
    full_name = f"custom_components.schulmanager.{module_name}"
    if full_name in sys.modules:
        return sys.modules[full_name]
    spec = importlib.util.spec_from_file_location(full_name, _CC_BASE / f"{module_name}.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "custom_components.schulmanager"
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


_load_cc("const")
_load_cc("api")
_load_cc("coordinator")
_load_cc("sensor")
_load_cc("binary_sensor")
