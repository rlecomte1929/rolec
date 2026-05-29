/**
 * Auth helpers — reuse the SAME JWT mechanism as the main relopass.com
 * frontend so an HR user logged into either surface can move between them
 * without a second login.
 *
 * Storage key + Authorization header pattern come straight from
 * frontend/src/api/client.ts (see request interceptor at lines 124–134 and
 * the buildAuthHeaders helper near line 3453).
 *
 * Do NOT introduce a second auth layer here. If the login flow needs to be
 * changed, change it in the main frontend first and mirror only the read
 * side here.
 */

const TOKEN_STORAGE_KEY = 'relopass_token';

export function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    // localStorage can throw in private/sandboxed contexts — treat as logged out
    return null;
  }
}

export function isAuthenticated(): boolean {
  return Boolean(getAuthToken());
}

export function clearAuthToken(): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    // no-op
  }
}

/** Build the Authorization header pair if we have a token. */
export function buildAuthHeaders(): Record<string, string> {
  const token = getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
