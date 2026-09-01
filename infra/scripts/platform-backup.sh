#!/usr/bin/env bash
set -Eeuo pipefail

output=/srv/platform/data/observations/backup-snapshot.json
mkdir -p -m 0750 "$(dirname "$output")"

write_snapshot() {
  local status="$1" evidence="$2"
  SNAPSHOT_STATUS="$status" SNAPSHOT_EVIDENCE="$evidence" SNAPSHOT_OUTPUT="$output" python3 - <<'PY'
import json, os, tempfile
from datetime import datetime, timezone
from pathlib import Path
path = Path(os.environ["SNAPSHOT_OUTPUT"])
payload = {"schema": "lea-ramon/backup/v1", "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "status": os.environ["SNAPSHOT_STATUS"], "evidence": [os.environ["SNAPSHOT_EVIDENCE"][:500]]}
with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as f:
    json.dump(payload, f, separators=(",", ":")); f.write("\n"); name = f.name
os.chmod(name, 0o640); os.replace(name, path)
PY
}

required=(AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_ENDPOINT RESTIC_REPOSITORY RESTIC_PASSWORD_FILE)
for variable in "${required[@]}"; do
  if [[ -z "${!variable:-}" ]]; then
    write_snapshot unconfigured "Backup is not configured."
    exit 0
  fi
done
if [[ ! -r "$RESTIC_PASSWORD_FILE" ]] || ! command -v restic >/dev/null 2>&1; then
  write_snapshot unconfigured "Backup prerequisites are not available."
  exit 0
fi

if restic backup --json /srv/platform/data/portal >/dev/null 2>&1; then
  write_snapshot success "Encrypted backup completed."
else
  write_snapshot failure "Backup failed; inspect host-side service logs."
  exit 1
fi
