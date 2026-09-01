import type { APIRoute } from 'astro';
import { getSessionUser } from '../../../lib/db';
import { readPlatformSnapshots } from '../../../lib/operational-snapshots.mjs';
import { sessionCookieName } from '../../../lib/security';

export const GET: APIRoute = async ({ cookies }) => {
  if (!getSessionUser(cookies.get(sessionCookieName)?.value)) {
    return new Response('Unauthorized.', { status: 401 });
  }
  return Response.json(await readPlatformSnapshots(), {
    headers: { 'Cache-Control': 'no-store' },
  });
};
