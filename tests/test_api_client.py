"""Unit tests for SchulmanagerClient (api.py) - mocked aiohttp session."""

from __future__ import annotations

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock


def _api():
    return sys.modules["custom_components.schulmanager.api"]


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_response(status: int = 200, json_data: dict | None = None, text: str = "error"):
    """Return an async-context-manager mock that yields a response with given status."""
    response = AsyncMock()
    response.status = status
    response.json = AsyncMock(return_value=json_data or {})
    response.text = AsyncMock(return_value=text)

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=response)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _make_session(status: int = 200, json_data: dict | None = None, text: str = "error"):
    session = MagicMock()
    session.post = MagicMock(return_value=_make_response(status, json_data, text))
    return session


# ── validate_login ────────────────────────────────────────────────────────────

def test_validate_login_returns_login_info_on_success() -> None:
    async def _run():
        api = _api()
        client = api.SchulmanagerClient("user@test.de", "secret", "http://bridge:8099")
        session = _make_session(200, {
            "unique_id": "user@test.de",
            "account": {"full_name": "Max Mustermann"},
        })
        result = await client.validate_login(session)
        assert result.unique_id == "user@test.de"
        assert "Max Mustermann" in result.title
        assert result.account["full_name"] == "Max Mustermann"

    asyncio.run(_run())


def test_validate_login_uses_username_as_unique_id_fallback() -> None:
    async def _run():
        api = _api()
        client = api.SchulmanagerClient("HANS@SCHULE.DE", "pw", "http://bridge:8099")
        session = _make_session(200, {"account": {}})
        result = await client.validate_login(session)
        assert result.unique_id == "hans@schule.de"

    asyncio.run(_run())


def test_validate_login_raises_auth_error_on_401() -> None:
    async def _run():
        api = _api()
        client = api.SchulmanagerClient("user", "wrong", "http://bridge:8099")
        session = _make_session(401)
        try:
            await client.validate_login(session)
            assert False, "Expected SchulmanagerAuthError"
        except api.SchulmanagerAuthError:
            pass

    asyncio.run(_run())


def test_validate_login_raises_connection_error_on_500() -> None:
    async def _run():
        api = _api()
        client = api.SchulmanagerClient("user", "pw", "http://bridge:8099")
        session = _make_session(500, text="Internal Server Error")
        try:
            await client.validate_login(session)
            assert False, "Expected SchulmanagerConnectionError"
        except api.SchulmanagerConnectionError as exc:
            assert "500" in str(exc)

    asyncio.run(_run())


def test_validate_login_raises_connection_error_on_client_error() -> None:
    async def _run():
        api = _api()
        client = api.SchulmanagerClient("user", "pw", "http://bridge:8099")
        import aiohttp
        ClientError = sys.modules["aiohttp"].ClientError

        session = MagicMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(side_effect=ClientError("connection refused"))
        cm.__aexit__ = AsyncMock(return_value=None)
        session.post = MagicMock(return_value=cm)

        try:
            await client.validate_login(session)
            assert False, "Expected SchulmanagerConnectionError"
        except api.SchulmanagerConnectionError:
            pass

    asyncio.run(_run())


# ── fetch_data ────────────────────────────────────────────────────────────────

def test_fetch_data_returns_data_dict() -> None:
    async def _run():
        api = _api()
        client = api.SchulmanagerClient("user", "pw", "http://bridge:8099")
        session = _make_session(200, {
            "data": {
                "account": {"full_name": "Test"},
                "schedules": {"today": []},
            }
        })
        result = await client.fetch_data(session, ["account", "schedules"])
        assert "account" in result
        assert "schedules" in result

    asyncio.run(_run())


def test_fetch_data_returns_empty_dict_when_no_data_key() -> None:
    async def _run():
        api = _api()
        client = api.SchulmanagerClient("user", "pw", "http://bridge:8099")
        session = _make_session(200, {})  # no "data" key
        result = await client.fetch_data(session, ["account"])
        assert result == {}

    asyncio.run(_run())


# ── secret header ─────────────────────────────────────────────────────────────

def test_post_json_sends_secret_header_when_configured() -> None:
    async def _run():
        api = _api()
        client = api.SchulmanagerClient("user", "pw", "http://bridge:8099", bridge_secret="mysecret")
        response_cm = _make_response(200, {})
        session = MagicMock()
        session.post = MagicMock(return_value=response_cm)

        await client._post_json(session, "/validate", {"username": "user", "password": "pw"})

        call_kwargs = session.post.call_args
        headers = call_kwargs.kwargs.get("headers") or (call_kwargs.args[1] if len(call_kwargs.args) > 1 else {})
        # headers may be passed as kwarg
        headers = call_kwargs.kwargs.get("headers", {})
        assert headers.get("X-Schulmanager-Secret") == "mysecret"

    asyncio.run(_run())


def test_post_json_sends_no_auth_header_without_secret() -> None:
    async def _run():
        api = _api()
        client = api.SchulmanagerClient("user", "pw", "http://bridge:8099")
        response_cm = _make_response(200, {})
        session = MagicMock()
        session.post = MagicMock(return_value=response_cm)

        await client._post_json(session, "/validate", {})

        call_kwargs = session.post.call_args
        headers = call_kwargs.kwargs.get("headers")
        assert headers is None

    asyncio.run(_run())


def test_post_json_constructs_correct_url() -> None:
    async def _run():
        api = _api()
        client = api.SchulmanagerClient("user", "pw", "http://bridge:8099/")  # trailing slash
        response_cm = _make_response(200, {})
        session = MagicMock()
        session.post = MagicMock(return_value=response_cm)

        await client._post_json(session, "/fetch", {})

        url = session.post.call_args.args[0]
        assert url == "http://bridge:8099/fetch"  # no double slash

    asyncio.run(_run())
