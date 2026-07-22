/**
 * Client-side roadmap payment status helper — TEST PHASE ONLY.
 *
 * The flag is set when the employee lands on
 *   /employee/dashboard?payment=success&session_id=…
 * after Stripe checkout, and persists in localStorage so the roadmap page
 * lets them through on subsequent visits without re-paying.
 *
 * ⚠️  Replace with a real API call once the platform has a payment-status
 *     endpoint (e.g. GET /api/payment/status/:assignmentId that reads from
 *     the backend `case_access` table written by the Stripe webhook).
 *
 * Key: `rp_roadmap_unlocked_{userId}` → '1' | absent
 */

const payKey = (userId: string) => `rp_roadmap_unlocked_${userId}`;

/**
 * Returns true when the current user's roadmap is unlocked (paid or test-unlocked).
 * Falls back to `false` on localStorage errors so the gate shows rather than hides.
 */
export function isRoadmapUnlocked(userId: string): boolean {
  if (!userId) return false;
  try {
    return localStorage.getItem(payKey(userId)) === '1';
  } catch {
    return false;
  }
}

/**
 * Marks the roadmap as unlocked for this user.
 * Called from EmployeeJourney when ?payment=success lands.
 */
export function markRoadmapUnlocked(userId: string): void {
  if (!userId) return;
  try {
    localStorage.setItem(payKey(userId), '1');
  } catch {
    // ignore quota / private-browsing restrictions
  }
}
