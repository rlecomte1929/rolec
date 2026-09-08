import { apiPost } from './client';

/**
 * First-login welcome dismissal (AIQ-1701).
 *
 * The dismissal is written to localStorage first (that is what the synchronous
 * `useWelcomeRedirect` check reads), then persisted here so it survives a change of
 * browser or device. Takes no arguments — the backend reads the user id from the
 * token, so one account can never dismiss another's welcome.
 *
 * Best-effort: a failure leaves the dismissal browser-local, which is exactly the
 * pre-AIQ-1701 behaviour, so callers should not surface an error for it.
 */
export async function persistWelcomeSeen(): Promise<void> {
  await apiPost<{ welcome_seen: boolean; persisted: boolean }>('/api/auth/welcome-seen', {});
}
