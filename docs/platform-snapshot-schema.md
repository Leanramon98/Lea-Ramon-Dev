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

`apps` contains registry-derived `id`, `display_name`, `enabled`, `public_url`, optional `release` (`version` and/or `commit`), and a health result. Disabled apps use `health.status: "not_configured"`; no guessed endpoint is emitted. `host` reports aggregate CPU load, RAM, and filesystem usage when available. `logs` contains at most 100 redacted lines per fixed allowlisted source and never includes source paths or commands.

## Backup and alert v1

Backup snapshots use `status` values `unconfigured`, `success`, or `failure`; they may include a bounded redacted `evidence` array. Alert snapshots use `unconfigured`, `healthy`, or `failure`, plus at most 20 transition records. Neither contract includes credentials, destination URLs, host paths, shell commands, or raw provider output.

## Compatibility rule

Additive fields are permitted. Changing a schema identifier or the meaning of an existing field requires a new `vN` contract and a portal-reader update.
