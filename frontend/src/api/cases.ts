import { apiGet, apiPatch, apiPost } from './client';

export interface HrTeamMember {
  profile_id: string;
  name: string | null;
  email: string | null;
}

/**
 * List HR users in the caller's company — the reassignment target list
 * (AIQ-1136). GET /api/hr/team, tenant-scoped server-side.
 */
export async function listCompanyHrTeam(): Promise<HrTeamMember[]> {
  const res = await apiGet<{ members: HrTeamMember[] }>(`/api/hr/team`);
  return res.members ?? [];
}

/**
 * Reassign a case's HR owner to another HR in the same company (AIQ-1136).
 * PATCH /api/hr/cases/{case_id}/reassign-hr-owner — HR-scoped; the backend
 * verifies both the case and the target HR belong to the caller's company.
 */
export async function reassignCaseHrOwner(
  caseId: string,
  payload: { hr_user_id: string; reason: string },
): Promise<{ ok: boolean }> {
  return apiPatch<{ ok: boolean }>(
    `/api/hr/cases/${encodeURIComponent(caseId)}/reassign-hr-owner`,
    payload,
  );
}
import type { CaseDTO, CaseDraftDTO, CaseRequirementsDTO, CaseExceptionsResponse, ExceptionFlag } from '../types';

export async function getCase(caseId: string): Promise<CaseDTO> {
  return apiGet(`/api/cases/${caseId}`);
}

export async function patchCase(caseId: string, patch: Partial<CaseDraftDTO>): Promise<CaseDTO> {
  return apiPatch(`/api/cases/${caseId}`, patch);
}

export async function startResearch(caseId: string): Promise<{ jobId: string }> {
  return apiPost(`/api/cases/${caseId}/research/start`);
}

export async function validateRoadmap(caseId: string): Promise<{
  roadmap_validated: boolean;
  roadmap_validated_at?: string | null;
  roadmap_validated_by?: string | null;
}> {
  return apiPost(`/api/cases/${caseId}/roadmap/validate`);
}

export async function getRequirements(caseId: string): Promise<CaseRequirementsDTO> {
  return apiGet(`/api/cases/${caseId}/requirements`);
}

export async function createCase(caseId: string): Promise<{ createdCaseId: string; requirementsSnapshotId: string }> {
  return apiPost(`/api/cases/${caseId}/create`);
}

/**
 * Fetch exception flags for a case from the ExceptionRequestService.
 * Returns blockers and warnings detected during timeline generation.
 * Returns null on network/auth error so callers can fail silently.
 */
export async function fetchCaseExceptions(caseId: string): Promise<CaseExceptionsResponse | null> {
  if (!caseId) return null;
  try {
    return await apiGet<CaseExceptionsResponse>(`/api/cases/${caseId}/exceptions`);
  } catch {
    return null;
  }
}

export type ExceptionResolutionStatus = 'approved' | 'denied' | 'escalated' | 'withdrawn';

export interface UpdateExceptionPayload {
  status: ExceptionResolutionStatus;
  resolution_notes?: string;
}

/**
 * Approve, deny, escalate, or withdraw an exception flag.
 * HR-only — throws on auth failure or if the flag is not found.
 */
export async function updateCaseException(
  caseId: string,
  exceptionId: string,
  payload: UpdateExceptionPayload,
): Promise<ExceptionFlag> {
  return apiPatch<ExceptionFlag>(
    `/api/cases/${caseId}/exceptions/${exceptionId}`,
    payload,
  );
}

export type EscalationKind = 'specialist' | 'legal' | 'other';

export interface EscalateCasePayload {
  reason: string;
  kind: EscalationKind;
  assignee?: string;
  sla_due_at?: string;
}

/**
 * Escalate a case to a specialist / legal (NAV-HR-2). Composes the existing
 * HR endpoint POST /api/hr/cases/{case_id}/escalate (backend
 * hr_case_escalation.py) — tenant-scoped server-side by the HR user's company.
 * HR/Admin only; throws on auth failure or missing company association.
 */
export async function escalateCase(
  caseId: string,
  payload: EscalateCasePayload,
): Promise<{ id?: string; status?: string }> {
  return apiPost<{ id?: string; status?: string }>(
    `/api/hr/cases/${encodeURIComponent(caseId)}/escalate`,
    payload,
  );
}

// ── Case overview (AIQ-1751) ─────────────────────────────────────────────────

/**
 * Whether the case's target start date leaves room for its corridor to run.
 *
 * Null when the backend has no opinion — an unresolvable corridor, a corridor
 * with no declared arrival anchor, or a case with no target start date. Absent
 * must render as nothing, never as reassurance.
 */
export interface CaseFeasibility {
  verdict: 'critical' | 'tight' | 'ok';
  /** Days of corridor steps that must complete before the employee can arrive. */
  required_days: number;
  /** Days between today and the target start date. Negative if already past. */
  available_days: number;
  /** Server-rendered explanation. Never recompute this client-side. */
  derivation: string;
}

export interface CaseOverview {
  case_id: string;
  employee: {
    employee_id: string;
    display_name: string;
    primary_email?: string | null;
    nationality?: string | null;
  };
  origin_country_code?: string | null;
  dest_country_code?: string | null;
  corridor?: string | null;
  status: string;
  stage?: string | null;
  target_start_date?: string | null;
  actual_start_date?: string | null;
  target_close_date?: string | null;
  family_members: Array<{
    family_member_id: string;
    relationship: string;
    display_name: string;
    date_of_birth?: string | null;
    is_dependent?: boolean | null;
  }>;
  feasibility?: CaseFeasibility | null;
}

/**
 * GET /api/hr/cases/{caseId}/overview — HR/Admin, tenant-scoped server-side.
 *
 * ⚠️ `caseId` must be the **relocation_cases** UUID — `detail.caseId` on the
 * command-center detail response, which backend/main.py annotates as
 * "use this for /api/hr/cases/{id} navigation". NOT an assignment id: the
 * backend resolves with `SELECT * FROM relocation_cases WHERE id = :id`, so an
 * assignment id 404s.
 *
 * Returns null on any error so callers can fail silently — matching
 * fetchCaseExceptions above.
 */
export async function fetchCaseOverview(caseId: string): Promise<CaseOverview | null> {
  if (!caseId) return null;
  try {
    const res = await apiGet<{ overview: CaseOverview }>(
      `/api/hr/cases/${encodeURIComponent(caseId)}/overview`,
    );
    return res.overview ?? null;
  } catch {
    return null;
  }
}
