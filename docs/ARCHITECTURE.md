# Architecture

The project is split into two layers.

## 1. Home Assistant integration

Path:

- `custom_components/schulmanager`

Responsibilities:

- setup via config flow
- module selection
- entity creation
- scheduled updates
- dashboard-friendly sensors
- stale/error handling
- optional bridge secret support

The integration talks to the bridge over HTTP.

## 2. Schulmanager Bridge add-on

Path:

- `addons/schulmanager_bridge`

Responsibilities:

- authenticate against Schulmanager Online and cache the session token
- request the selected modules from the JSON API in a single batch
- normalize the responses into the payload Home Assistant expects
- isolate per-module failures so one broken module cannot fail the fetch

Since 0.3.41 the bridge talks to the same JSON API the web front end uses
(`/api/get-salt` → `/api/login` → `/api/calls`); it no longer renders pages in a
browser. Keeping it as a separate add-on means the login — whose key derivation
is deliberately expensive — and the cached token live outside the Home Assistant
process.

## Data flow

1. Home Assistant calls the bridge
2. The bridge reuses its cached token, or logs in when it has expired
3. All selected modules are requested in one batched API call
4. Normalized data is returned as JSON
5. The integration updates entities in Home Assistant

A token stays valid for roughly an hour, so most fetches skip step 2 entirely
and complete in a fraction of a second.

## Caching behavior

The integration keeps the last known good data when possible.

This prevents entities from becoming empty immediately if a fetch temporarily fails or returns incomplete data.

Related metadata:

- `data_stale`
- `last_successful_update`
- `last_attempted_update`

## Security model

Recommended setup:

- keep the bridge inside the local network only
- do not publish port `8099` externally
- optionally configure a shared secret between integration and bridge

If a bridge secret is configured, requests must include the matching `X-Schulmanager-Secret` header.

## Limitations

- the JSON API is not officially documented and may change without notice —
  though such a change surfaces as an explicit HTTP status rather than as
  silently empty data
- schools enable different modules; a module that is not enabled returns an
  empty list
- the meal plan has no API mapping yet and always returns an empty list, with
  the reason recorded in `meta.module_errors`

## Failure semantics

- Schulmanager refusing the credentials → HTTP 401 → Home Assistant asks for a
  re-login
- a wrong shared secret → HTTP 401 carrying `X-Schulmanager-Error: bridge_secret`
  → treated as a configuration problem, not as wrong credentials
- anything else (network, timeout, unexpected response) → HTTP 502 → the next
  scheduled update simply tries again
