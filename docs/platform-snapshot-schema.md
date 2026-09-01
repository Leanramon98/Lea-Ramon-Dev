# Platform snapshot contracts

The portal reads three fixed JSON files from its read-only observations mount. They are produced atomically by host-side jobs; the browser cannot select files, commands, paths, or probes.

## Contracts

| File | Schema | Producer | Purpose |
| --- | --- | --- | --- |
| `platform-observation.json` | `lea-ramon/observation/v1` | observer | Managed-app, host, and redacted-log state |
| `backup-snapshot.json` | `lea-ramon/backup/v1` | backup runner | Latest configured, successful, failed, or unconfigured backup result |
| `alert-snapshot.json` | `lea-ramon/alert/v1` | alert dispatcher | Dispatcher status and bounded transition evidence |

## Shared envelope

Every snapshot includes `schema`, `generated_at` (UTC ISO-8601), and `status`. Producers replace a completed temporary file with `rename(2)` semantics. Readers must reject an unknown schema or malformed JSON and render a not-configured/unavailable state instead.

## Observation v1

`apps` contains registry-derived `id`, `display_name`, `enabled`, `configuration_status`, `public_url`, optional `release` (`version` and/or `commit`), and a health result. An app with a fixed allowlisted systemd runtime may include `systemd_state` (`active`, `activating`, `inactive`, `deactivating`, `failed`, or `unavailable`) and a current repository `release.commit`; neither exposes a service unit name, repository path, command, or raw output. Disabled apps use `health.status: "not_configured"`; entries with `configuration_status: "pending_configuration"` are inactive placeholders and emit no guessed endpoint. `host` reports aggregate CPU load, RAM, and filesystem usage when available. `logs` is retained as an empty array for v1 compatibility; the observer does not read journals or raw logs.

## Backup and alert v1

Backup snapshots use `status` values `unconfigured`, `success`, or `failure`; they may include a bounded redacted `evidence` array. Alert snapshots use `unconfigured`, `healthy`, or `failure`, plus at most 20 transition records. Neither contract includes credentials, destination URLs, host paths, shell commands, or raw provider output.

## Compatibility rule

Additive fields are permitted. Changing a schema identifier or the meaning of an existing field requires a new `vN` contract and a portal-reader update.
