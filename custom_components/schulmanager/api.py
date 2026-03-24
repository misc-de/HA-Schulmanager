"""HTTP bridge client for the Schulmanager integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession

_LOGGER = logging.getLogger(__name__)


class SchulmanagerError(Exception):
    """Base exception for the integration."""


class SchulmanagerAuthError(SchulmanagerError):
    """Raised when authentication fails."""


class SchulmanagerConnectionError(SchulmanagerError):
    """Raised when the bridge or page loading fails."""


@dataclass(slots=True)
class LoginInfo:
    """Minimal account information used during setup."""

    unique_id: str
    title: str
    account: dict[str, Any]


class SchulmanagerClient:
    """Client that talks to a local bridge service."""

    def __init__(self, username: str, password: str, bridge_url: str, bridge_secret: str | None = None) -> None:
        self._username = username
        self._password = password
        self._bridge_url = bridge_url.rstrip("/")
        self._bridge_secret = (bridge_secret or "").strip()

    async def validate_login(self, session: ClientSession) -> LoginInfo:
        """Validate credentials against the bridge."""
        _LOGGER.debug("Validating Schulmanager login against bridge %s", self._bridge_url)
        payload = await self._post_json(
            session,
            "/validate",
            {
                "username": self._username,
                "password": self._password,
            },
        )
        account = payload.get("account", {})
        full_name = account.get("full_name") or self._username
        unique_id = payload.get("unique_id") or self._username.lower()
        _LOGGER.info("Schulmanager login validation succeeded for %s", unique_id)
        return LoginInfo(
            unique_id=unique_id,
            title=f"Schulmanager ({full_name})",
            account=account,
        )

    async def fetch_data(self, session: ClientSession, modules: list[str]) -> dict[str, Any]:
        """Fetch all selected modules through the bridge."""
        _LOGGER.debug("Fetching Schulmanager modules via bridge: %s", ", ".join(modules))
        payload = await self._post_json(
            session,
            "/fetch",
            {
                "username": self._username,
                "password": self._password,
                "modules": modules,
            },
        )
        data = payload.get("data", {})
        _LOGGER.debug("Bridge returned Schulmanager data keys: %s", ", ".join(sorted(data.keys())))
        return data

    async def _post_json(
        self,
        session: ClientSession,
        path: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        url = f"{self._bridge_url}{path}"
        try:
            headers = {"X-Schulmanager-Secret": self._bridge_secret} if self._bridge_secret else None
            async with session.post(url, json=payload, headers=headers, timeout=180) as response:
                if response.status == 401:
                    _LOGGER.warning("Bridge rejected Schulmanager credentials for %s", url)
                    raise SchulmanagerAuthError("Authentication failed.")
                if response.status >= 400:
                    detail = await response.text()
                    _LOGGER.error(
                        "Bridge request to %s failed with status %s: %s",
                        url,
                        response.status,
                        detail,
                    )
                    raise SchulmanagerConnectionError(
                        f"Bridge request failed with status {response.status}: {detail}"
                    )
                return await response.json()
        except SchulmanagerAuthError:
            raise
        except ClientResponseError as err:
            _LOGGER.error("Bridge response error for %s: %s", url, err)
            raise SchulmanagerConnectionError(str(err)) from err
        except ClientError as err:
            _LOGGER.error("Bridge could not be reached at %s: %s", url, err)
            raise SchulmanagerConnectionError(
                f"Bridge could not be reached: {err}"
            ) from err
        except TimeoutError as err:
            _LOGGER.error("Bridge request to %s timed out", url)
            raise SchulmanagerConnectionError("Bridge request timed out.") from err
