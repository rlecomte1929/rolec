import { describe, expect, it } from 'vitest';
import {
  isSessionExpiredSearch,
  shouldRedirectOnUnauthorized,
  SESSION_EXPIRED_HREF,
} from './sessionExpired';

describe('shouldRedirectOnUnauthorized', () => {
  it('redirects a 401 on an in-app page', () => {
    expect(
      shouldRedirectOnUnauthorized({
        status: 401,
        requestUrl: '/api/employee/assignments/overview',
        currentPath: '/employee/dashboard',
      }),
    ).toBe(true);
  });

  it('does not redirect 403 (wrong role is not expiry)', () => {
    expect(
      shouldRedirectOnUnauthorized({
        status: 403,
        requestUrl: '/api/employee/assignments/overview',
        currentPath: '/employee/dashboard',
      }),
    ).toBe(false);
  });

  it('does not redirect login 401s or when already on /auth', () => {
    expect(
      shouldRedirectOnUnauthorized({
        status: 401,
        requestUrl: '/api/auth/login',
        currentPath: '/employee/dashboard',
      }),
    ).toBe(false);
    expect(
      shouldRedirectOnUnauthorized({
        status: 401,
        requestUrl: '/api/employee/assignments/overview',
        currentPath: '/auth',
      }),
    ).toBe(false);
  });
});

describe('isSessionExpiredSearch', () => {
  it('detects the interceptor query', () => {
    expect(isSessionExpiredSearch('?mode=login&reason=session_expired')).toBe(true);
    expect(isSessionExpiredSearch('mode=login')).toBe(false);
    expect(SESSION_EXPIRED_HREF).toContain('reason=session_expired');
  });
});
