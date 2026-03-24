# Schulmanager for Home Assistant

A custom Home Assistant integration for **Schulmanager Online** with a local bridge add-on.

⚠️ **AI-assisted project**  
⚠️ **Work in progress**  
This project is under active development. Features may change and instability is possible.

This project contains two parts:

- a **Home Assistant custom integration**
- a **local bridge add-on** that logs into Schulmanager Online and fetches data

The bridge is required because Schulmanager access is based on browser automation.

## Features

- UI-based setup in Home Assistant
- selectable Schulmanager modules
- sensors for:
  - account
  - schedule (today / week)
  - homework
  - meal plan
  - calendar
  - exams
  - activities
- manual refresh service
- stale/error binary sensors
- optional shared secret between integration and bridge
- dashboard markdown examples included

## Repository structure

- `custom_components/schulmanager` – Home Assistant custom integration
- `addons/schulmanager_bridge` – local Home Assistant add-on
- `markdown-examples` – ready-to-use dashboard markdown cards

## Quick installation

### 1. Install the add-on files

Copy the folder:

- `addons/schulmanager_bridge`

to your Home Assistant local add-on directory, usually:

- `/addons/local/schulmanager_bridge/`

Then restart Home Assistant.

### 2. Install the custom integration files

Copy the folder:

- `custom_components/schulmanager`

to your Home Assistant config directory:

- `/config/custom_components/schulmanager/`

Then restart Home Assistant again.

### 3. Start the bridge add-on

Open Home Assistant:

- **Settings → Add-ons → Schulmanager Bridge**

Install and start the add-on.

If needed, configure an optional shared secret:

```yaml
bridge_secret: "your-shared-secret"
```

### 4. Add the integration

Open:

- **Settings → Devices & Services**
- **Add Integration**
- choose **Schulmanager**

Enter:

- username / email
- password
- bridge URL
- modules to enable

The integration suggests the Home Assistant host IP with port `8099` as default bridge URL.

Example:

```text
http://192.168.0.1:8099
```

If you use a shared secret in the add-on, enter the same value in the integration options.

## Updating sensors manually

You can force an update with the built-in service:

```yaml
action: schulmanager.refresh
target: {}
data: {}
```

Or only for one config entry:

```yaml
action: schulmanager.refresh
target: {}
data:
  entry_id: "YOUR_CONFIG_ENTRY_ID"
```

## Security notes

- Do **not** expose port `8099` to the public internet.
- Keep the bridge inside your local network only.
- Use the optional shared secret if you want to protect bridge access further.
- Avoid leaving verbose debug logging enabled permanently.

## Dashboard examples

Ready-made markdown examples are included in:

- `markdown-examples/`

Examples are available for:

- schedule week
- schedule today
- meal plan today
- homework
- debug status
- manual refresh
- security setup

## Notes

- The bridge depends on browser automation and may need parser adjustments if the Schulmanager layout changes.
- Some schools use slightly different page structures.
- If data is temporarily empty, the integration keeps the last known good values when possible.

## Upstream reference

This project is based on the public Schulmanager scraping approach from:

- https://github.com/SchmueI/Schulmanager-API
