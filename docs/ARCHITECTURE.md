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

- launch the scraping environment
- authenticate against Schulmanager Online
- load the selected pages
- parse module data
- return normalized JSON to Home Assistant

The bridge is required because the upstream Schulmanager access method is based on browser automation.

## Data flow

1. Home Assistant calls the bridge
2. The bridge logs into Schulmanager Online
3. The bridge fetches selected modules
4. Parsed data is returned as JSON
5. The integration updates entities in Home Assistant

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

- parsing depends on the current Schulmanager HTML structure
- some schools may use different layouts
- individual modules may need parser adjustments over time
