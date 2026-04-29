from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

import logging
import os
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
import uvicorn

from scraper_client import (
    LoginInfo,
    SchulmanagerAuthError,
    SchulmanagerClient,
    SchulmanagerConnectionError,
)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
BRIDGE_SHARED_SECRET = os.getenv("BRIDGE_SHARED_SECRET", "").strip()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
_LOGGER = logging.getLogger("schulmanager_bridge")


class AuthRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class FetchRequest(AuthRequest):
    modules: list[str] = Field(default_factory=list)
    debug: bool = False


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    _LOGGER.info("Starting Schulmanager Bridge 0.3.34")
    _LOGGER.info("Chromium available: %s", Path("/usr/bin/chromium").exists() or Path("/usr/bin/chromium-browser").exists())
    _LOGGER.info("Chromedriver available: %s", Path("/usr/bin/chromedriver").exists() or Path("/usr/lib/chromium/chromedriver").exists())
    yield


app = FastAPI(title="Schulmanager Bridge", version="0.3.34", lifespan=lifespan)
_START_TIME = time.time()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    if BRIDGE_SHARED_SECRET:
        incoming_secret = request.headers.get("X-Schulmanager-Secret", "")
        if incoming_secret != BRIDGE_SHARED_SECRET:
            raise HTTPException(status_code=401, detail="Invalid or missing bridge secret.")
    request_id = uuid.uuid4().hex[:8]
    started = time.perf_counter()
    _LOGGER.info("[%s] %s %s", request_id, request.method, request.url.path)
    try:
        response = await call_next(request)
    except Exception:
        _LOGGER.exception("[%s] Unhandled request error", request_id)
        raise
    duration = (time.perf_counter() - started) * 1000
    _LOGGER.info(
        "[%s] %s -> %s in %.1f ms",
        request_id,
        request.url.path,
        response.status_code,
        duration,
    )
    return response


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "name": "Schulmanager Bridge",
        "version": "0.3.34",
        "endpoints": ["/health", "/diagnostics", "/validate", "/fetch"],
        "debug_hint": "POST /fetch with {\"debug\": true} to include page diagnostics for schedules/meal/homework/calendar",
        "secret_enabled": bool(BRIDGE_SHARED_SECRET),
    }


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": "0.3.34",
        "uptime_seconds": round(time.time() - _START_TIME, 1),
    }


@app.get("/diagnostics")
def diagnostics() -> dict[str, Any]:
    return {
        "version": "0.3.34",
        "log_level": LOG_LEVEL,
        "secret_enabled": bool(BRIDGE_SHARED_SECRET),
        "chromium_found": Path("/usr/bin/chromium").exists() or Path("/usr/bin/chromium-browser").exists() or Path("/usr/bin/google-chrome").exists(),
        "chromedriver_found": Path("/usr/bin/chromedriver").exists() or Path("/usr/lib/chromium/chromedriver").exists(),
    }


@app.post("/validate")
def validate_login(payload: AuthRequest) -> dict[str, Any]:
    _LOGGER.info("Validating Schulmanager login for %s", payload.username)
    client = SchulmanagerClient(payload.username, payload.password)
    try:
        info: LoginInfo = client.validate_login()
    except SchulmanagerAuthError as err:
        _LOGGER.warning("Authentication failed for %s", payload.username)
        raise HTTPException(status_code=401, detail=str(err)) from err
    except SchulmanagerConnectionError as err:
        _LOGGER.error("Connection error during validation: %s", err)
        raise HTTPException(status_code=502, detail=str(err)) from err
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception("Unexpected validation error")
        raise HTTPException(status_code=500, detail=f"{type(err).__name__}: {err}") from err

    _LOGGER.info("Validation succeeded for %s", info.unique_id)
    return {
        "unique_id": info.unique_id,
        "title": info.title,
        "account": info.account,
    }


@app.post("/fetch")
def fetch_data(payload: FetchRequest) -> dict[str, Any]:
    _LOGGER.info("Fetching modules for %s: %s (debug=%s)", payload.username, ", ".join(payload.modules), payload.debug)
    client = SchulmanagerClient(payload.username, payload.password)
    try:
        data = client.fetch_data(payload.modules, debug=payload.debug)
    except SchulmanagerAuthError as err:
        _LOGGER.warning("Authentication failed while fetching data for %s", payload.username)
        raise HTTPException(status_code=401, detail=str(err)) from err
    except SchulmanagerConnectionError as err:
        _LOGGER.error("Connection error while fetching data: %s", err)
        raise HTTPException(status_code=502, detail=str(err)) from err
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception("Unexpected fetch error")
        raise HTTPException(status_code=500, detail=f"{type(err).__name__}: {err}") from err

    _LOGGER.info("Fetch succeeded for %s with keys: %s", payload.username, ", ".join(sorted(data.keys())))
    return {"data": data}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8099, log_level=LOG_LEVEL.lower())
