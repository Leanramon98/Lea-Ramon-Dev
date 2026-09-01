# Operate the platform foundation

This runbook enables host-side observation, optional encrypted R2 backups, and transition-only alerts without granting the portal host control.

## Quick path

1. Install the versioned registry, scripts, and systemd units from this checkout.
2. Create `/srv/platform/data/observations` as root-owned, numeric-group `10001`, mode `0750`; mount it read-only into the portal through Compose.
3. Enable the observer timer, verify the authenticated dashboard, then make explicit backup and alert decisions before enabling their timers.

## Security boundaries

| Boundary | Decision |
| --- | --- |
| Portal | Reads only three fixed snapshot filenames from `/observations`; numeric group `10001` grants directory traversal and file reads, never writes. No host paths, shell commands, Docker socket, or journal access. |
| Snapshots | Writers atomically replace root-owned, group-`10001`, `0640` files. The host directory is root-owned, group-`10001`, `0750`; no host login user is created. |
| Observer | Reads only `managed-apps.v1.json`, a fixed loopback URL, and the fixed `host-system-log` source; output is redacted and capped at 100 lines. |
| Backup | Backs up only `/srv/platform/data/portal` with restic encryption; it does nothing when required environment values are absent. |
| Alerts | Posts only changed states when `ALERT_WEBHOOK_URL` is present; evidence is capped at 20 transitions. |

## Enable observation

Install the units as root, then enable only the observer timer:

```bash
sudo install -d -o root -g 10001 -m 0750 /srv/platform/data/observations
sudo install -d -o root -g root -m 0750 /srv/platform/data/alerts
sudo install -o root -g root -m 0644 /srv/platform/src/lea-ramon-dev/infra/systemd/lea-ramon-observer.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lea-ramon-observer.timer
sudo systemctl start lea-ramon-observer.service
```

Verify `platform-observation.json` is root-owned, group `10001`, mode `0640`, then log in to `/admin`. Confirm that Portal health is observed and Balne shows `not_configured`. Do not expose the observation directory through Nginx.

## Configure R2 backups

Cloudflare R2 requires an account, a private bucket, and an S3 API token. Create a token restricted to **Object Read & Write** for only the selected backup bucket; record its Access Key ID and Secret Access Key once, because the secret cannot be retrieved later. Do not enable the `r2.dev` public URL or attach a public custom domain to the backup bucket.

Choose and document these decisions before activation: bucket name/account endpoint, retention duration, lifecycle behavior, bucket lock policy, operator who holds the restic password, and restore-verification cadence. Use lifecycle rules for expiry and bucket lock where retention must resist early deletion; test their effect against the selected policy.

Install `restic` through the operating system's managed package channel. Copy `config/platform/backup-r2.env.example` to `/srv/platform/secrets/backup-r2.env` (mode `0600`), fill in the selected endpoint and credentials, and create the referenced restic password file as root-owned `0600`. `RESTIC_REPOSITORY` must identify the approved S3-compatible R2 repository. Initialize it explicitly once with the same environment, then enable the timer:

```bash
sudo install -o root -g root -m 0644 /srv/platform/src/lea-ramon-dev/infra/systemd/lea-ramon-backup.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lea-ramon-backup.timer
sudo systemctl start lea-ramon-backup.service
```

Restic encrypts repository contents with its repository password. Protect that password separately from R2 credentials and test a restore to an isolated temporary directory at least once before relying on the backup:

```bash
restic snapshots
restic restore latest --target /var/tmp/lea-ramon-restore-check
```

Compare the restored portal data with the source using an operator-approved method, then securely remove the temporary restore. The portal does not receive R2 credentials.

## Configure alerts

Copy `config/platform/alerts.env.example` to `/srv/platform/secrets/alerts.env` (mode `0600`) and set an explicitly approved webhook destination. Install and enable the alert timer only after testing that destination:

```bash
sudo install -o root -g root -m 0644 /srv/platform/src/lea-ramon-dev/infra/systemd/lea-ramon-alert-dispatcher.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lea-ramon-alert-dispatcher.timer
sudo systemctl start lea-ramon-alert-dispatcher.service
```

The first state evaluation establishes a baseline without notification. Repeated identical states do not notify. Empty configuration produces an `unconfigured` local snapshot and never sends a request.

## Deployment, verification, and rollback

Deploy the portal using the existing [portal deployment runbook](deploy-portal.md); the Compose mount requires `/srv/platform/data/observations` to exist before the portal starts. Verify `docker compose config`, `systemctl status` for enabled jobs, and authenticated `/admin` plus `/admin/api/platform-snapshot` (authenticated only). Check the public site remains free of operational data.

To roll back, disable and stop only `lea-ramon-observer.timer`, `lea-ramon-backup.timer`, and/or `lea-ramon-alert-dispatcher.timer`; remove their units if required. The dashboard will render not-configured state. Preserve snapshots and backup repositories until an operator has confirmed retention and recovery requirements. Do not change Balne or unrelated host services.

## Limitations

- The fixed initial log source is `/var/log/syslog`; distributions without it report unavailable rather than falling back to journald.
- Redaction is defense in depth, not authorization to include secrets in logs; keep host logging hygiene in place.
- No Balne probe, logs, data, backup, or alerting is enabled until runtime facts are verified.
