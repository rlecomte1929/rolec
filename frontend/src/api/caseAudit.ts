import { apiGet } from './client';

/**
 * [NAV-HR-3 / AIQ-1122] One row of a case's HR-action audit trail, from the
 * canonical public.audit_logs (consolidated by AUDIT-1/2/3). `event` carries the
 * original semantic verb (e.g. REASSIGN_HR_OWNER) while `action_type` is the
 * insert/update/delete bucket.
 */
export interface CaseAuditEvent {
  id: string;
  entity_type: string;
  entity_id: string;
  action_type: string;
  actor_type?: string | null;
  actor_id?: string | null;
  actor_name?: string | null;
  event?: string | null;
  old_value?: Record<string, unknown> | null;
  new_value?: Record<string, unknown> | null;
  created_at?: string | null;
}

/** Chronological (newest-first) HR-action trail for a case. Tenant-scoped + 404
 *  on cross-tenant access server-side. */
export const getCaseAuditTrail = (caseId: string): Promise<CaseAuditEvent[]> =>
  apiGet(`/api/hr/cases/${encodeURIComponent(caseId)}/audit-trail`);
