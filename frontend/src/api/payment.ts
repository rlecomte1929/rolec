/**
 * Payment / roadmap-entitlement API — GET /api/payment/status/{caseId}.
 *
 * The server is the source of truth for whether a roadmap is unlocked (Phase 4a,
 * `roadmap_entitlement.py`). This replaces the old client-trusted localStorage flag:
 * `roadmap_unlocked` already accounts for the backend paywall flag + the case's
 * access_tier, so the frontend just consults it.
 */
import api from './client';

export interface PaymentStatus {
  case_id: string;
  access_tier: 'free' | 'roadmap' | 'essentials';
  payment_status: string;
  /** The single boolean the UI gates on. True when the paywall is off, when the case
   *  has paid, or when the server can't resolve the tier (fail-open). */
  roadmap_unlocked: boolean;
}

export async function getPaymentStatus(caseId: string): Promise<PaymentStatus> {
  const r = await api.get<PaymentStatus>(`/api/payment/status/${caseId}`);
  return r.data;
}
