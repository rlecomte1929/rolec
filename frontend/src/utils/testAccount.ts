/**
 * Is this a synthetic (test-drive / E2E) account?
 *
 * AIQ-1571: the test-drive HR needs a different landing emphasis from a real customer —
 * "create a case" is the whole point of the campaign, whereas a real HR genuinely does
 * want to configure their company first. The two must not be conflated, so this asks one
 * narrow question and nothing more.
 *
 * SOURCE OF TRUTH IS THE BACKEND. `backend/db/test_data_filter.py::looks_like_test_email`
 * owns this list and is what stamps `profiles.is_test` at registration; this mirrors it
 * because the client has no endpoint to ask. Keep the two in step — if a domain is added
 * there, add it here. The blast radius of drift is cosmetic (a test HR would see the
 * real-customer welcome), never a permission.
 *
 * Chosen over reading the test-drive's own localStorage stash: that is absent in a cold
 * browser or a private window, so a tester who signs in fresh would silently get the
 * wrong landing. The email travels with the session.
 */
const TEST_EMAIL_DOMAINS = ['@testco.com', '@probe.test'] as const;

export function looksLikeTestEmail(email: string | null | undefined): boolean {
  const e = (email || '').trim().toLowerCase();
  return TEST_EMAIL_DOMAINS.some((d) => e.endsWith(d));
}
