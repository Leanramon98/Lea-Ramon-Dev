#!/usr/bin/env python3
"""Collect fixed, allowlisted operational observations for the read-only portal."""
import json
import os
import re
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REGISTRY = Path("/srv/platform/src/lea-ramon-dev/config/platform/managed-apps.v1.json")
OUTPUT = Path("/srv/platform/data/observations/platform-observation.json")
PORTAL_GID = 10001
MAX_LOG_LINES = 100
LOG_SOURCES = {"host-system-log": Path("/var/log/syslog")}
SECRET_PATTERNS = [
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/-]+=*"),
    re.compile(r"(?i)(authorization|token|secret|password|api[_-]?key)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
]


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def redact(value):
    value = value.replace("\x00", "")[:2000]
    for pattern in SECRET_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value


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


def collect_logs(apps):
    requested = {source for app in apps if app.get("enabled") for source in app.get("log_sources", [])}
    logs = []
    for source in sorted(requested & LOG_SOURCES.keys()):
        try:
            lines = LOG_SOURCES[source].read_text(errors="replace").splitlines()[-MAX_LOG_LINES:]
            logs.append({"source": source, "status": "available", "lines": [redact(line) for line in lines]})
        except OSError:
            logs.append({"source": source, "status": "unavailable", "lines": []})
    return logs


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
        enabled = app.get("enabled") is True
        apps.append({
            "id": app["id"], "display_name": app["display_name"], "enabled": enabled,
            "public_url": app.get("public_url"), "release": app.get("release"),
            "health": health_check(app.get("health_check")) if enabled else {"status": "not_configured"},
        })
    atomic_write(OUTPUT, {"schema": "lea-ramon/observation/v1", "generated_at": now(), "status": "success", "apps": apps, "host": host_health(), "logs": collect_logs(registry["apps"])})


if __name__ == "__main__":
    main()
