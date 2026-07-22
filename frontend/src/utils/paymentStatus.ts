/**
 * Roadmap payment-status helper — SERVER-backed.
 *
 * Replaces the earlier client-trusted localStorage unlock: the roadmap gate is now
 * enforced server-side (`assert_roadmap_access`, Phase 4a), and this reads the same
 * source of truth via GET /api/payment/status/:caseId. Setting a localStorage flag or
 * visiting `?payment=success` no longer unlocks anything — only a real paid tier does.
 */
import { getPaymentStatus } from '../api/payment';

/**
 * True when the case's roadmap may be shown. Fails OPEN (true) when there's no caseId or
 * the status call errors — a transient network failure must never wrongly paywall a user
 * (and the server still enforces the gate on the roadmap fetch itself as the backstop).
 */
export async function fetchRoadmapUnlocked(caseId: string): Promise<boolean> {
  if (!caseId) return true;
  try {
    const status = await getPaymentStatus(caseId);
    return status.roadmap_unlocked;
  } catch {
    return true;
  }
}
