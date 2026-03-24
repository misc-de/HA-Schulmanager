#!/usr/bin/env bash
set -eu

echo "[schulmanager_bridge] starting"
echo "[schulmanager_bridge] python=$(python --version 2>&1)"
if command -v chromium >/dev/null 2>&1; then
  echo "[schulmanager_bridge] chromium=$(command -v chromium)"
elif command -v chromium-browser >/dev/null 2>&1; then
  echo "[schulmanager_bridge] chromium=$(command -v chromium-browser)"
else
  echo "[schulmanager_bridge] chromium not found"
fi
if command -v chromedriver >/dev/null 2>&1; then
  echo "[schulmanager_bridge] chromedriver=$(command -v chromedriver)"
else
  echo "[schulmanager_bridge] chromedriver not found"
fi
echo "[schulmanager_bridge] log_level=${LOG_LEVEL:-INFO}"
BRIDGE_SHARED_SECRET="$(python - <<'PY'
import json, pathlib
p = pathlib.Path('/data/options.json')
if p.exists():
    try:
        data = json.loads(p.read_text())
        print(data.get('bridge_secret', ''))
    except Exception:
        print("")
else:
    print("")
PY
)"
export BRIDGE_SHARED_SECRET
echo "[schulmanager_bridge] secret_enabled=$([ -n "$BRIDGE_SHARED_SECRET" ] && echo true || echo false)"
exec python /app/bridge_server.py
