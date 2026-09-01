import type { APIRoute } from 'astro';
import { deleteSession } from '../../lib/db';
import { rejectUnsafeRequest, sessionCookieName, sessionCookieOptions } from '../../lib/security';

export const POST: APIRoute = (context) => {
  const rejection = rejectUnsafeRequest(context);
  if (rejection) return rejection;

  deleteSession(context.cookies.get(sessionCookieName)?.value);
  context.cookies.delete(sessionCookieName, sessionCookieOptions(new Date(0)));
  return context.redirect('/admin/login', 303);
};
