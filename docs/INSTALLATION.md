# Installation

This project consists of two parts:

- the **Home Assistant custom integration**
- the **Schulmanager Bridge** add-on

Both parts are required.

## 1. Install the custom integration with HACS

In HACS:

- **HACS → Integrations**
- open the menu with the three dots
- choose **Custom repositories**
- repository: `https://github.com/misc-de/HA-Schulmanager`
- category: **Integration**
- add it, then install **Schulmanager**

Restart Home Assistant afterwards.

## 2. Install the bridge add-on repository

The bridge add-on is not installed through HACS. Add the same GitHub repository
to the Home Assistant add-on store:

- **Settings → Add-ons → Add-on Store**
- open the menu with the three dots
- choose **Repositories**
- add `https://github.com/misc-de/HA-Schulmanager`

Then install **Schulmanager Bridge** from the add-on store.

## Alternative: manual installation

### Copy the add-on

Copy the folder:

- `addons/schulmanager_bridge`

into your Home Assistant local add-on directory, usually:

- `/addons/local/schulmanager_bridge/`

Restart Home Assistant afterwards.

### Copy the custom integration

Copy the folder:

- `custom_components/schulmanager`

into your Home Assistant configuration directory:

- `/config/custom_components/schulmanager/`

Restart Home Assistant again.

## 3. Install and start the add-on

Open Home Assistant:

- **Settings → Add-ons → Schulmanager Bridge**

Install and start the add-on.

Optional add-on configuration:

```yaml
bridge_secret: "your-shared-secret"
```

## 4. Add the integration

Open:

- **Settings → Devices & Services**
- **Add Integration**
- select **Schulmanager**

Enter:

- email / username
- password
- bridge URL
- enabled modules

The integration proposes the Home Assistant host IP with port `8099` as the default bridge URL.

Example:

```text
http://192.168.0.23:8099
```

If you configured a shared secret in the add-on, enter the same value in the integration options.

## 5. Verify

You should see:

- sensors for the enabled Schulmanager modules
- binary sensors for stale data and module errors
- the `schulmanager.refresh` service

You can also test the bridge directly:

- `http://YOUR_HA_IP:8099/`
- `http://YOUR_HA_IP:8099/health`
- `http://YOUR_HA_IP:8099/diagnostics`

## Notes

- Do not expose port `8099` to the public internet.
- Keep the bridge inside your local network.
- The bridge uses browser automation and may need parser updates if the Schulmanager layout changes.
