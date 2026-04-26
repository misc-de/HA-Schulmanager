"""Test helpers for parser-only bridge tests.

The bridge imports Selenium at module import time, but the parser tests only
exercise pure helper methods. These lightweight stubs keep the tests runnable
without installing or starting Selenium/Chromium locally.
"""

from __future__ import annotations

import sys
import types


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
