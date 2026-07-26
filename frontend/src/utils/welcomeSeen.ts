/**
 * First-login welcome dismissal, per user id (global, one-time).
 *
 * Mirrors the localStorage helper pattern in utils/employeeCaseProgress.ts —
 * try/catch wrapped, failures swallowed. When storage is blocked (private mode,
 * quota) hasSeenWelcome returns true so we never trap the user on the welcome
 * page with no way to persist the dismissal.
 *
 * Keyed on relopass_user_id (see utils/demo.ts / hooks/useAuth.ts). Distinct from
 * the per-assignment welcome CARD in EmployeeJourney (rp_welcome_dismissed:*),
 * which is suppressed once this global flag is set.
 */
const key = (userId: string) => `relopass_welcome_seen_${userId}`;

export function hasSeenWelcome(userId: string): boolean {
  try {
    return localStorage.getItem(key(userId)) === '1';
  } catch {
    return true; // storage blocked → don't force the page on them
  }
}

export function markWelcomeSeen(userId: string): void {
  try {
    localStorage.setItem(key(userId), '1');
  } catch {
    // ignore — see module doc
  }
}

/**
 * AIQ-1701 — mirror the server's `profiles.welcome_seen_at` into this browser at login.
 *
 * The dismissal is owned server-side so it survives a change of browser or device, but
 * the redirect check (useWelcomeRedirect) must stay SYNCHRONOUS or the role home could
 * flash the welcome page while an async answer is in flight. Seeding the cache at login
 * — where the profile row is already loaded — gives durability without that risk.
 *
 * Only ever SETS the flag, never clears it. A server that reports false (or a legacy
 * account with no profiles row) must leave an already-onboarded browser alone: that is
 * the pre-AIQ-1701 behaviour, and clearing here would re-onboard people on the very
 * login that was supposed to stop doing that.
 */
export function seedWelcomeSeenFromLogin(
  userId: string,
  welcomeSeen: boolean | null | undefined,
): void {
  if (userId && welcomeSeen) markWelcomeSeen(userId);
}
