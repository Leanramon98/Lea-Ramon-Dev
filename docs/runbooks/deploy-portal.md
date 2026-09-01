# Deploy the Lea Ramon Portal

This runbook deploys only the isolated `balne.online` portal. It does not modify `balne.com.ar`, the existing Balne repository, or any unrelated service.

## Prerequisites to verify

Before making changes, the operator must verify all of the following:

- `balne.online` DNS resolves to the intended VPS and both IPv4/IPv6 records match the Nginx listeners.
- The existing Nginx include layout and the correct enabled-vhost directory; do not alter the `balne.com.ar` vhost.
- VPS operating system, service account convention, and whether a `platform` user exists and can access Docker without root.
- Docker Engine and the Docker Compose plugin are installed; confirm the executable path used by the systemd unit (`/usr/bin/docker`).
- The host firewall permits HTTP (80) and HTTPS (443), and no existing service owns port 3100.

## 1. Prepare server directories and secrets

Run as the deployment operator after choosing the confirmed source checkout location:

```bash
if ! id platform >/dev/null 2>&1; then
  sudo useradd --system --user-group --no-create-home \
    --home-dir /nonexistent --shell /usr/sbin/nologin platform
fi
sudo usermod --append --groups docker platform
sudo -u platform /usr/bin/docker version

sudo install -d -o platform -g platform -m 0750 /srv/platform
sudo install -d -o platform -g platform -m 0750 /srv/platform/secrets
sudo install -d -o platform -g platform -m 0755 /srv/platform/src
sudo install -d -o root -g root -m 0755 /srv/platform/data
sudo install -d -o 10001 -g 10001 -m 0750 /srv/platform/data/portal
sudo install -d -o root -g root -m 0750 /srv/platform/data/observations
sudo -u platform git clone <REPOSITORY_URL> /srv/platform/src/lea-ramon-dev
sudo install -o platform -g platform -m 0600 /dev/null /srv/platform/secrets/portal.env
sudoedit /srv/platform/secrets/portal.env
```

The `platform` user needs Docker-group membership because the systemd unit runs Docker as that user. Treat this access as privileged. The SQLite directory is owned by the container's non-root UID/GID `10001`; do not change it to `platform`.

Populate the secret file using `config/apps/portal.env.example` as a shape only. Set a unique, long initial password and keep `PORTAL_DATABASE_PATH=/data/portal.db`. The secret file is outside Git, must remain mode `0600`, and must never be pasted into logs or tickets.

The initial admin is created only if that username does not already exist. Do not rotate the bootstrap password by editing this file after first start; use a future explicit credential-management procedure. The password is never logged by the application.

## 2. Build and start the portal

```bash
sudo -u platform /usr/bin/docker compose \
  --project-name lea-ramon-portal \
  --env-file /srv/platform/secrets/portal.env \
  -f /srv/platform/src/lea-ramon-dev/infra/compose/portal.compose.yml \
  up --detach --build
curl --fail http://127.0.0.1:3100/
```

Confirm the host exposes only the loopback mapping: `127.0.0.1:3100`. The SQLite database persists at `/srv/platform/data/portal/portal.db` through the container bind mount.

## 3. Install and enable systemd

```bash
sudo install -o root -g root -m 0644 \
  /srv/platform/src/lea-ramon-dev/infra/systemd/lea-ramon-portal.service \
  /etc/systemd/system/lea-ramon-portal.service
sudo systemctl daemon-reload
sudo systemctl enable --now lea-ramon-portal.service
sudo systemctl status lea-ramon-portal.service
```

If the verified service account or Docker path differs, edit the unit deliberately before installation; do not use shell wrappers or add secrets to the unit.

## 4. Enable the HTTP vhost

Install the new vhost in the operator-verified Nginx site directory. Debian-style example:

```bash
sudo install -o root -g root -m 0644 \
  /srv/platform/src/lea-ramon-dev/infra/nginx/balne.online.http.conf \
  /etc/nginx/sites-available/balne.online.conf
sudo ln -s /etc/nginx/sites-available/balne.online.conf /etc/nginx/sites-enabled/balne.online.conf
sudo nginx -t
sudo systemctl reload nginx
curl --fail -H 'Host: balne.online' http://127.0.0.1/
```

Do not replace, rename, or edit the existing `balne.com.ar` configuration.

## 5. Add TLS and validate authentication

After confirming public DNS and HTTP reachability, use the operator-approved Certbot command for the installed Nginx layout. Typical Debian Nginx plugin invocation:

```bash
sudo certbot --nginx -d balne.online
curl --fail --location https://balne.online/
```

Open `https://balne.online/admin`, sign in with the runtime-created admin credentials, confirm that unconfigured operational snapshots are clearly labelled, then use **Log out** and confirm `/admin` redirects to `/admin/login`. Follow the [operations runbook](operate-platform.md) before enabling host-side observation, backups, or alerts.

## Rollback

1. Remove the `balne.online` enabled-vhost symlink or its equivalent, run `sudo nginx -t`, then reload Nginx.
2. Stop and disable only this service: `sudo systemctl disable --now lea-ramon-portal.service`.
3. If necessary, remove the portal Compose project with the same explicit compose command and `down`.
4. Preserve `/srv/platform/data/portal` unless the operator intentionally wants to destroy all portal users and sessions. Do not touch any Balne files or services.

## Scope boundary

The portal cannot administer Docker, read the host journal, or execute host commands. The optional operational foundation is limited to fixed host-side probes and read-only JSON snapshots; see [the operations runbook](operate-platform.md). Balne remains untouched until its runtime facts are verified.
