#!/usr/bin/env python3
"""Dispatch only state transitions; never expose webhook details in snapshots."""
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

OBSERVATIONS = Path("/srv/platform/data/observations")
STATE = Path("/srv/platform/data/alerts/dispatch-state.json")
OUTPUT = OBSERVATIONS / "alert-snapshot.json"

def now(): return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
def load(path):
    try: return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError): return None
def write(path, payload):
    path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as f:
        json.dump(payload, f, separators=(",", ":")); f.write("\n"); name = f.name
    os.chmod(name, 0o640); os.replace(name, path)
def current_states():
    observation, backup = load(OBSERVATIONS / "platform-observation.json"), load(OBSERVATIONS / "backup-snapshot.json")
    states = {}
    if observation:
        states.update({f"app:{a['id']}": a.get("health", {}).get("status", "unavailable") for a in observation.get("apps", []) if a.get("enabled")})
    if backup: states["backup"] = backup.get("status", "unavailable")
    return states
def transitions(previous, current, has_prior):
    if not has_prior:
        return []
    return [{"at": now(), "subject": key, "from": previous.get(key), "to": value} for key, value in current.items() if previous.get(key) != value]
def main():
    webhook, states = os.environ.get("ALERT_WEBHOOK_URL"), current_states()
    stored = load(STATE)
    prior = stored or {"states": {}, "evidence": []}
    changes = transitions(prior["states"], states, stored is not None)
    evidence = (prior.get("evidence", []) + changes)[-20:]
    if not webhook:
        write(OUTPUT, {"schema": "lea-ramon/alert/v1", "generated_at": now(), "status": "unconfigured", "evidence": evidence})
        write(STATE, {"states": states, "evidence": evidence})
        return
    try:
        if changes:
            body = json.dumps({"source": "lea-ramon-platform", "transitions": changes}).encode()
            with urlopen(Request(webhook, data=body, method="POST", headers={"Content-Type": "application/json"}), timeout=5): pass
        write(OUTPUT, {"schema": "lea-ramon/alert/v1", "generated_at": now(), "status": "healthy", "evidence": evidence})
        write(STATE, {"states": states, "evidence": evidence})
    except Exception:
        write(OUTPUT, {"schema": "lea-ramon/alert/v1", "generated_at": now(), "status": "failure", "evidence": evidence[-20:]})
        raise
if __name__ == "__main__": main()
