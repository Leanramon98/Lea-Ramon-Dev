#!/usr/bin/env python3
"""Collect fixed, allowlisted operational observations for the read-only portal."""
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from types import MappingProxyType
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REGISTRY = Path("/srv/platform/src/lea-ramon-dev/config/platform/managed-apps.v1.json")
OUTPUT = Path("/srv/platform/data/observations/platform-observation.json")
PORTAL_GID = 10001
RUNTIME_SOURCES = MappingProxyType({
    "balne": MappingProxyType({
        "systemd_unit": "balne-landing.service",
        "repository": Path("/srv/balne-landing"),
        "health_check": MappingProxyType({
            "url": "http://127.0.0.1:3000/",
            "timeout_seconds": 5,
            "expected_status": 200,
        }),
    }),
})
SYSTEMCTL = "/usr/bin/systemctl"
GIT = "/usr/bin/git"
SYSTEMD_STATES = {"active", "activating", "inactive", "deactivating", "failed"}


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def health_check(config):
    if not config:
        return {"status": "not_configured"}
    try:
        request = Request(config["url"], method="GET", headers={"User-Agent": "lea-ramon-observer/1"})
        with urlopen(request, timeout=min(max(int(config.get("timeout_seconds", 5)), 1), 10)) as response:
            code = response.status
        return {"status": "healthy" if code == config.get("expected_status", 200) else "unhealthy", "http_status": code}
    except HTTPError as error:
        return {"status": "unhealthy", "http_status": error.code}
    except (URLError, OSError, ValueError):
        return {"status": "unavailable"}


def systemd_state(unit):
    try:
        result = subprocess.run(
            [SYSTEMCTL, "show", "--property=ActiveState", "--value", unit],
            check=False, capture_output=True, text=True, timeout=5,
        )
        state = result.stdout.strip()
        return state if state in SYSTEMD_STATES else "unavailable"
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"


def repository_revision(repository):
    try:
        result = subprocess.run(
            [GIT, "-C", str(repository), "rev-parse", "--verify", "HEAD"],
            check=False, capture_output=True, text=True, timeout=5,
        )
        revision = result.stdout.strip()
        return revision if re.fullmatch(r"[0-9a-f]{40}", revision) else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def host_health():
    result = {"status": "available"}
    try:
        result["cpu_load_1m"] = round(os.getloadavg()[0], 2)
    except OSError:
        pass
    try:
        memory = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines() if ":" in line)
        total = int(memory["MemTotal"].split()[0]) * 1024
        available = int(memory["MemAvailable"].split()[0]) * 1024
        result["memory"] = {"total_bytes": total, "available_bytes": available, "used_percent": round((total - available) * 100 / total, 1)}
    except (OSError, KeyError, ValueError):
        result["memory"] = {"status": "unavailable"}
    try:
        usage = shutil.disk_usage("/")
        result["disk"] = {"total_bytes": usage.total, "free_bytes": usage.free, "used_percent": round(usage.used * 100 / usage.total, 1)}
    except OSError:
        result["disk"] = {"status": "unavailable"}
    return result


def app_observation(app):
    enabled = app.get("enabled") is True
    runtime = RUNTIME_SOURCES.get(app["id"]) if enabled else None
    observation = {
        "id": app["id"], "display_name": app["display_name"], "enabled": enabled,
        "configuration_status": app.get("configuration_status", "configured" if enabled else "not_configured"),
        "public_url": app.get("public_url"), "release": app.get("release"),
        "health": health_check(runtime["health_check"]) if runtime else health_check(app.get("health_check")) if enabled else {"status": "not_configured"},
    }
    if runtime:
        observation["systemd_state"] = systemd_state(runtime["systemd_unit"])
        revision = repository_revision(runtime["repository"])
        if revision:
            observation["release"] = {**(observation["release"] or {}), "commit": revision}
    return observation


def atomic_write(path, payload):
    path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    os.chown(path.parent, 0, PORTAL_GID)
    os.chmod(path.parent, 0o750)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, separators=(",", ":"), sort_keys=True)
        handle.write("\n")
        temp_name = handle.name
    os.chown(temp_name, 0, PORTAL_GID)
    os.chmod(temp_name, 0o640)
    os.replace(temp_name, path)


def main():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if registry.get("schema") != "lea-ramon/managed-app-registry/v1":
        raise ValueError("unsupported managed-app registry schema")
    apps = []
    for app in registry.get("apps", []):
        apps.append(app_observation(app))
    atomic_write(OUTPUT, {"schema": "lea-ramon/observation/v1", "generated_at": now(), "status": "success", "apps": apps, "host": host_health(), "logs": []})


if __name__ == "__main__":
    main()
