import type { APIRoute } from 'astro';
import { authenticate, createSession } from '../../../lib/db';
import { rejectUnsafeRequest, sessionCookieName, sessionCookieOptions } from '../../../lib/security';

export const POST: APIRoute = async (context) => {
  const rejection = rejectUnsafeRequest(context);
  if (rejection) return rejection;

  const form = await context.request.formData();
  const username = String(form.get('username') ?? '').trim();
  const password = String(form.get('password') ?? '');
  const user = await authenticate(username, password);
  if (!user) return context.redirect('/admin/login?error=invalid', 303);

  const session = createSession(user.id);
  context.cookies.set(sessionCookieName, session.token, sessionCookieOptions(session.expiresAt));
  return context.redirect('/admin', 303);
};
