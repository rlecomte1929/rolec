import { apiGet, apiPost } from './client';

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

/** [AIQ-1137] Optional server-side filters for the audit trail. */
export interface CaseAuditFilters {
  action_type?: 'insert' | 'update' | 'delete';
  event?: string;
  date_from?: string; // ISO timestamp
  date_to?: string; // ISO timestamp
}

/** Chronological (newest-first) HR-action trail for a case, aggregated across all
 *  of the case's bridged ids (AIQ-1137). Tenant-scoped + 404 on cross-tenant
 *  access server-side. Optional filters narrow by action type, semantic verb, or
 *  date range. */
export const getCaseAuditTrail = (
  caseId: string,
  filters?: CaseAuditFilters,
): Promise<CaseAuditEvent[]> => {
  const qs = new URLSearchParams();
  if (filters?.action_type) qs.set('action_type', filters.action_type);
  if (filters?.event) qs.set('event', filters.event);
  if (filters?.date_from) qs.set('date_from', filters.date_from);
  if (filters?.date_to) qs.set('date_to', filters.date_to);
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return apiGet(`/api/hr/cases/${encodeURIComponent(caseId)}/audit-trail${suffix}`);
};

/** [AIQ-1137] Append an amendment (correction note) linked to an audit entry.
 *  Append-only: the original row is never mutated. */
export const amendCaseAuditEvent = (
  caseId: string,
  auditId: string,
  reason: string,
): Promise<{ ok: boolean; id: string; amends: string }> =>
  apiPost(
    `/api/hr/cases/${encodeURIComponent(caseId)}/audit-trail/${encodeURIComponent(auditId)}/amend`,
    { reason },
  );

/** [AIQ-1137] Append a reversal linked to an audit entry (reversible state only). */
export const reverseCaseAuditEvent = (
  caseId: string,
  auditId: string,
  reason: string,
): Promise<{ ok: boolean; id: string; reverses: string }> =>
  apiPost(
    `/api/hr/cases/${encodeURIComponent(caseId)}/audit-trail/${encodeURIComponent(auditId)}/reverse`,
    { reason },
  );
