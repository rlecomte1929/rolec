/** Shared 401 → login decision. Used by the Axios interceptor and native-fetch helpers. */

export const SESSION_EXPIRED_HREF = '/auth?mode=login&reason=session_expired';

export function isSessionExpiredSearch(search: string): boolean {
  return new URLSearchParams(search.startsWith('?') ? search.slice(1) : search).get('reason') === 'session_expired';
}

/**
 * Only a real missing/invalid token is session expiry. 403 (wrong role) stays
 * on the current page. Auth and debug endpoints handle their own 401s.
 */
export function shouldRedirectOnUnauthorized(opts: {
  status: number;
  requestUrl?: string;
  currentPath: string;
}): boolean {
  if (opts.status !== 401) return false;
  const url = opts.requestUrl ?? '';
  if (/\/api\/auth\/(login|register)$/.test(url)) return false;
  if (/\/api\/debug\//.test(url)) return false;
  const path = opts.currentPath || '';
  if (path.startsWith('/auth') || path === '/' || path === '') return false;
  return true;
}
