#!/usr/bin/env python3
"""Bump the version across all project files in one step.

Usage:
    python scripts/bump_version.py 0.3.28

After running this script:
    git add -A
    git commit -m "Release v0.3.28"
    git tag v0.3.28
    git push && git push --tags
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

FILES = [
    # (path, regex-pattern, replacement-template)
    (
        ROOT / "custom_components/schulmanager/manifest.json",
        None,  # handled via JSON
        None,
    ),
    (
        ROOT / "custom_components/schulmanager/__init__.py",
        r'INTEGRATION_BUILD = "[^"]+"',
        'INTEGRATION_BUILD = "{version}"',
    ),
    (
        ROOT / "addons/schulmanager_bridge/config.yaml",
        r'^version: "[^"]+"',
        'version: "{version}"',
    ),
    (
        ROOT / "addons/schulmanager_bridge/bridge_server.py",
        r'"Schulmanager Bridge", version="[^"]+"',
        '"Schulmanager Bridge", version="{version}"',
    ),
    (
        ROOT / "addons/schulmanager_bridge/bridge_server.py",
        r'Starting Schulmanager Bridge [0-9]+\.[0-9]+\.[0-9]+',
        'Starting Schulmanager Bridge {version}',
    ),
    (
        ROOT / "addons/schulmanager_bridge/bridge_server.py",
        r'"version": "[0-9]+\.[0-9]+\.[0-9]+"',
        '"version": "{version}"',
    ),
    (
        ROOT / "addons/schulmanager_bridge/scraper_client.py",
        r'HomeAssistant-Schulmanager-Bridge/[0-9]+\.[0-9]+\.[0-9]+',
        'HomeAssistant-Schulmanager-Bridge/{version}',
    ),
    (
        ROOT / "custom_components/schulmanager/www/schulmanager-timetable-card.js",
        r'const CARD_VERSION = "[0-9]+\.[0-9]+\.[0-9]+"',
        'const CARD_VERSION = "{version}"',
    ),
]


def bump(version: str) -> None:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        sys.exit(f"ERROR: version must be in format X.Y.Z, got: {version!r}")

    changed: list[str] = []

    for path, pattern, template in FILES:
        if not path.exists():
            print(f"  SKIP (not found): {path.relative_to(ROOT)}")
            continue

        # manifest.json is handled via JSON to keep formatting intact
        if pattern is None:
            data = json.loads(path.read_text())
            if data.get("version") == version:
                print(f"  already {version}: {path.relative_to(ROOT)}")
                continue
            data["version"] = version
            path.write_text(json.dumps(data, indent=2) + "\n")
            changed.append(str(path.relative_to(ROOT)))
            continue

        content = path.read_text()
        replacement = template.format(version=version)
        new_content, n = re.subn(pattern, replacement, content, flags=re.MULTILINE)
        if n == 0:
            print(f"  WARNING: pattern not found in {path.relative_to(ROOT)}: {pattern!r}")
            continue
        if new_content == content:
            print(f"  already {version}: {path.relative_to(ROOT)}")
            continue
        path.write_text(new_content)
        changed.append(str(path.relative_to(ROOT)))

    if not changed:
        print("Nothing changed — already at that version?")
        return

    print(f"\nBumped to v{version} in:")
    for f in sorted(set(changed)):
        print(f"  {f}")
    print(f"""
Next steps:
  git add -A
  git commit -m "Release v{version}"
  git tag v{version}
  git push && git push --tags
""")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python scripts/bump_version.py <version>  (e.g. 0.3.28)")
    bump(sys.argv[1].lstrip("v"))
