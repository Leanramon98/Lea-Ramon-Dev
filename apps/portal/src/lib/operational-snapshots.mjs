import { readFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';

const files = {
  observation: 'platform-observation.json',
  backup: 'backup-snapshot.json',
  alert: 'alert-snapshot.json',
};
const schemas = {
  observation: 'lea-ramon/observation/v1',
  backup: 'lea-ramon/backup/v1',
  alert: 'lea-ramon/alert/v1',
};
const maxSnapshotAgeMs = 5 * 60 * 1000;

function unavailable(reason) {
  return { status: 'not_configured', reason };
}

export function snapshotPath(directory, kind) {
  if (!(kind in files)) throw new Error('Unknown snapshot kind.');
  const base = resolve(directory);
  const candidate = resolve(join(base, files[kind]));
  if (!candidate.startsWith(`${base}/`)) throw new Error('Snapshot path escaped its directory.');
  return candidate;
}

export function parseSnapshot(kind, value, currentTime = Date.now()) {
  try {
    const snapshot = JSON.parse(value);
    if (snapshot?.schema !== schemas[kind] || typeof snapshot.generated_at !== 'string') return unavailable('Snapshot is unavailable.');
    const generatedAt = Date.parse(snapshot.generated_at);
    if (Number.isNaN(generatedAt)) return unavailable('Snapshot has an invalid timestamp.');
    return { ...snapshot, stale: currentTime - generatedAt > maxSnapshotAgeMs };
  } catch {
    return unavailable('Snapshot is unavailable.');
  }
}

export async function readPlatformSnapshots(directory = process.env.OBSERVATIONS_DIR || '/observations', currentTime = Date.now()) {
  const entries = await Promise.all(Object.keys(files).map(async (kind) => {
    try {
      return [kind, parseSnapshot(kind, await readFile(snapshotPath(directory, kind), 'utf8'), currentTime)];
    } catch {
      return [kind, unavailable('Snapshot is not configured.')];
    }
  }));
  return Object.fromEntries(entries);
}
