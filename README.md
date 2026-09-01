# Lea Ramon Platform Portal

An isolated Astro SSR portal for `balne.online`: a public portfolio landing page and a server-protected administration foundation.

## Quick path

1. Copy `config/apps/portal.env.example` to the server-only secret file described in the deploy runbook.
2. Build and start with the portal Compose deployment.
3. Enable the dedicated `balne.online` Nginx vhost, then add TLS with Certbot.

The public site intentionally exposes no operational details. The private dashboard is available at `/admin` after native application login.

## Layout

| Path | Purpose |
| --- | --- |
| `apps/portal` | Astro SSR application and container image |
| `infra/compose` | Isolated loopback-only Compose deployment |
| `infra/nginx` | Dedicated HTTP vhost for `balne.online` |
| `infra/systemd` | Portal, observer, backup, and alert service units/timers |
| `config/platform` | Versioned app registry and non-secret configuration templates |
| `infra/scripts` | Fixed host-side observer, backup, and alert contracts |
| `docs/runbooks` | Ordered deployment and rollback procedure |
| `config/apps` | Safe environment-file template only |

## Local development

```bash
cd apps/portal
cp ../../config/apps/portal.env.example .env
npm install
npm run dev
```

For local development, set `PORTAL_DATABASE_PATH=./data/portal.db`. Never commit `.env` or a database file.

## Operations foundation

The authenticated dashboard reads host-produced snapshots mounted read-only. The portal has no Docker socket, host journal, command execution interface, or writable observations mount. The active `portal` app is checked through its loopback health URL. `Balne` is observed only through its fixed loopback health URL, fixed `balne-landing.service` active state, and fixed repository HEAD; it has no log, host-control, or modification capability.

The observer, encrypted R2 backup runner, and alert dispatcher are opt-in systemd jobs. They remain unconfigured or disabled without their operator-managed environment files. See [the operations runbook](docs/runbooks/operate-platform.md) and [snapshot contracts](docs/platform-snapshot-schema.md).

## Remaining operator decisions

- Cloudflare R2 account, private bucket, bucket-lock compatibility, least-privilege credentials, restic password handling, and the tracked restic-native retention policy. Never apply object-level lifecycle expiration to a live restic repository.
- Alert destination and webhook secret.
- Balne data and backup ownership.

See [the deployment runbook](docs/runbooks/deploy-portal.md) for the production procedure and operator prerequisites.
