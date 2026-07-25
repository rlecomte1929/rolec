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
 * True when the case's roadmap may be shown. Fails CLOSED (false → paywall) when there's
 * no caseId or the status call errors.
 *
 * AIQ-1691/roadmap-paywall: this used to fail OPEN (true). But the paywall is a revenue
 * gate and the roadmap render gates on THIS boolean, not on the roadmap-data 402. A direct
 * URL load carries the assignment_id (the checkout success_url uses it), so
 * getPaymentStatus(assignmentId) 404'd → the old `catch { return true }` unlocked the full
 * €800 roadmap for an unpaid case. A false lock is recoverable (the user retries / the
 * server now resolves the assignment_id → correct status); a free roadmap is lost revenue.
 * Err toward the paywall on any ambiguity.
 */
export async function fetchRoadmapUnlocked(caseId: string): Promise<boolean> {
  if (!caseId) return false;
  try {
    const status = await getPaymentStatus(caseId);
    return status.roadmap_unlocked;
  } catch {
    return false;
  }
}
