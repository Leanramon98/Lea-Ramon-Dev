import argon2 from 'argon2';
import Database from 'better-sqlite3';
import { createHash, randomBytes } from 'node:crypto';
import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

const databasePath = process.env.PORTAL_DATABASE_PATH ?? './data/portal.db';
mkdirSync(dirname(databasePath), { recursive: true });

const db = new Database(databasePath);
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at INTEGER NOT NULL
  );
  CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at INTEGER NOT NULL,
    created_at INTEGER NOT NULL
  );
  CREATE INDEX IF NOT EXISTS sessions_expires_at_idx ON sessions(expires_at);
`);

export type AdminUser = { id: number; username: string };
const sessionLifetimeMs = 1000 * 60 * 60 * 8;

function tokenHash(token: string) {
  return createHash('sha256').update(token).digest('hex');
}

export async function bootstrapInitialAdmin() {
  const username = process.env.PORTAL_INITIAL_ADMIN_USERNAME;
  const password = process.env.PORTAL_INITIAL_ADMIN_PASSWORD;

  if (!username && !password) return;
  if (!username || !password) {
    throw new Error('Both initial admin environment variables must be set together.');
  }

  const existingUser = db.prepare('SELECT id FROM users WHERE username = ?').get(username);
  if (existingUser) return;

  const passwordHash = await argon2.hash(password, {
    type: argon2.argon2id,
    memoryCost: 19_456,
    timeCost: 2,
    parallelism: 1,
  });
  db.prepare('INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)')
    .run(username, passwordHash, Date.now());
}

let bootstrapPromise: Promise<void> | undefined;
export function ensureInitialAdmin() {
  bootstrapPromise ??= bootstrapInitialAdmin();
  return bootstrapPromise;
}

export async function authenticate(username: string, password: string): Promise<AdminUser | null> {
  await ensureInitialAdmin();
  const row = db.prepare('SELECT id, username, password_hash FROM users WHERE username = ?').get(username) as
    | { id: number; username: string; password_hash: string }
    | undefined;
  if (!row || !(await argon2.verify(row.password_hash, password))) return null;
  return { id: row.id, username: row.username };
}

export function createSession(userId: number) {
  const token = randomBytes(32).toString('base64url');
  const now = Date.now();
  db.prepare('DELETE FROM sessions WHERE expires_at <= ?').run(now);
  db.prepare('INSERT INTO sessions (token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)')
    .run(tokenHash(token), userId, now + sessionLifetimeMs, now);
  return { token, expiresAt: new Date(now + sessionLifetimeMs) };
}

export function getSessionUser(token: string | undefined): AdminUser | null {
  if (!token) return null;
  const now = Date.now();
  db.prepare('DELETE FROM sessions WHERE expires_at <= ?').run(now);
  return (db.prepare(`
    SELECT users.id, users.username
    FROM sessions JOIN users ON users.id = sessions.user_id
    WHERE sessions.token_hash = ? AND sessions.expires_at > ?
  `).get(tokenHash(token), now) as AdminUser | undefined) ?? null;
}

export function deleteSession(token: string | undefined) {
  if (token) db.prepare('DELETE FROM sessions WHERE token_hash = ?').run(tokenHash(token));
}
