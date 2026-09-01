import type { APIContext } from 'astro';

export const sessionCookieName = 'portal_session';

export function isProduction() {
  return process.env.NODE_ENV === 'production';
}

export function sessionCookieOptions(expires: Date) {
  return {
    httpOnly: true,
    sameSite: 'lax' as const,
    secure: isProduction(),
    path: '/',
    expires,
  };
}

export function assertSameOrigin(request: Request) {
  const origin = request.headers.get('origin');
  if (!origin) return false;

  const requestUrl = new URL(request.url);
  const forwardedProto = request.headers.get('x-forwarded-proto')?.split(',')[0]?.trim();
  const forwardedHost = request.headers.get('x-forwarded-host')?.split(',')[0]?.trim();
  const protocol = forwardedProto === 'https' || forwardedProto === 'http'
    ? forwardedProto
    : requestUrl.protocol.slice(0, -1);
  const host = forwardedHost || requestUrl.host;
  return origin === `${protocol}://${host}`;
}

export function rejectUnsafeRequest(context: APIContext) {
  if (!assertSameOrigin(context.request)) {
    return new Response('Invalid request origin.', { status: 403 });
  }
  return null;
}
