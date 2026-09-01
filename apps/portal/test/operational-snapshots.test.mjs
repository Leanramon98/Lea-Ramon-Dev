import assert from 'node:assert/strict';
import test from 'node:test';
import { parseSnapshot, snapshotPath } from '../src/lib/operational-snapshots.mjs';

test('parses a current versioned observation snapshot', () => {
  const snapshot = parseSnapshot('observation', JSON.stringify({
    schema: 'lea-ramon/observation/v1', generated_at: '2026-09-01T00:00:00Z', status: 'success', apps: [], host: {}, logs: [],
  }), Date.parse('2026-09-01T00:01:00Z'));
  assert.equal(snapshot.status, 'success');
  assert.equal(snapshot.stale, false);
});

test('rejects an unexpected schema and marks old snapshots stale', () => {
  assert.equal(parseSnapshot('backup', '{"schema":"other","generated_at":"2026-09-01T00:00:00Z"}').status, 'not_configured');
  const stale = parseSnapshot('alert', '{"schema":"lea-ramon/alert/v1","generated_at":"2026-09-01T00:00:00Z"}', Date.parse('2026-09-01T00:06:00Z'));
  assert.equal(stale.stale, true);
});

test('allows only fixed snapshot names, not request-controlled paths', () => {
  assert.match(snapshotPath('/observations', 'observation'), /platform-observation\.json$/);
  assert.throws(() => snapshotPath('/observations', '../../etc/passwd'), /Unknown snapshot kind/);
});
