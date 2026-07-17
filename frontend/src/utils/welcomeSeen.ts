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
