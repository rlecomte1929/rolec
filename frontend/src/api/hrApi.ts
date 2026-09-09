import type {
  AssignCaseResponse,
  AssignmentDetail,
  AssignmentSummary,
  AssignmentsListResponse,
  CompanyProfilePayload,
  ComplianceCaseReport,
  HrCompanyEmployee,
  InferredOnboardingConfig,
  PolicyResponse,
  PolicyServiceComparisonResponse,
} from '../types';
import type { HrPolicyAssistantQueryResponse } from '../types/policyAssistant';
import { ragResponseToHrResponse, type RagQueryResponse } from './policyAssistantRagAdapter';
import {
  api,
  cachedRequest,
  invalidateApiCache,
} from './client';
import type {
  CommandCenterCaseRow,
  EmployeeTask,
  EmployeeTaskListResponse,
  ProviderGridResponse,
  TaskType,
} from './client';

// HR case creation + assignment run a ~15-step DB chain (contact resolve,
// invite tokens, mobility/case-person/passport sync, message draft). The 15s
// default axios timeout was too tight when Supabase pooler RTT spiked,
// surfacing as "timeout of 15000ms exceeded" in the HR dashboard. Backend
// now dispatches the non-essential side effects to a background pool, but
// keep a 45s ceiling here as a safety net for the synchronous portion.
const HR_CASE_TIMEOUT = 45_000;

// ── P5-7: Policy calibration alerts ─────────────────────────────────────────
export interface CalibrationAlert {
  id: string;
  organization_id: string;
  category: string;
  tier_name: string | null;
  exception_count: number;
  avg_excess_pct: number;
  alert_message: string;
  created_at: string;
}

// ── HR-side backlog: pending employee tasks across the HR's company ────────

export interface HrBacklogTask {
  id: string;
  case_id?: string | null;
  employee_id?: string | null;
  org_id?: string | null;
  type?: string | null;
  title: string;
  description?: string | null;
  due_date?: string | null;
  status: 'pending' | 'revision_requested' | string;
  required_file_upload?: boolean;
  submitted_at?: string | null;
  reviewed_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  /** Joined columns — may be missing if profiles join failed. */
  employee_name?: string | null;
  employee_email?: string | null;
}

export interface HrBacklogResponse {
  items: HrBacklogTask[];
  total: number;
  has_company: boolean;
}

/** AIQ-378d — one behind-schedule case in the HR "Case health" panel. */
export interface CaseHealthFlag {
  case_id: string;
  stage: string | null;
  /** [AIQ-2041] The milestone's own curated title. `stage` is a milestone_type key
   *  and many are opaque ('pre_departure_ai_01'), so this is what to display. */
  milestone_title: string | null;
  /** 'hr' | 'employee' | 'joint' | authority code — who the overdue step is on. */
  owner: string | null;
  days_behind: number | null;
  expected_date: string | null;
  severity: string | null;
  suggested_action: string | null;
  draft_reminder: string | null;
}

// ── hrAPI response shapes (extracted from inline literals for type-safety) ──

export interface ResolvedPolicyResponse {
  resolved: {
    id: string;
    assignment_id: string;
    benefits: unknown[];
    exclusions: unknown[];
    resolution_context?: Record<string, unknown>;
  } | null;
  policy_version?: Record<string, unknown>;
  resolution_context?: Record<string, unknown>;
  message?: string;
}

export interface RecomputedPolicyResponse {
  resolved: unknown;
  policy_version?: Record<string, unknown>;
  message?: string;
}

export interface AssignmentServicesResponse {
  assignment_id: string;
  case_id: string;
  services: Array<{
    id: string;
    assignment_id: string;
    case_id: string;
    service_key: string;
    category: string;
    selected: number | boolean;
    estimated_cost: number | null;
    currency: string | null;
  }>;
}

export interface CommandCenterKPIs {
  activeCases: number;
  atRiskCount: number;
  attentionNeededCount: number;
  overdueTasksCount: number;
  avgVisaDurationDays?: number;
  budgetOverrunsCount: number;
  actionRequiredCount: number;
  departingSoonCount: number;
  completedCount: number;
}

export interface VendorPerformanceResponse {
  summary: {
    avg_rating: number | null;
    avg_cost_eur: number | null;
    active_vendors: number;
    avg_response_sla_hours: number | null;
  };
  monthly_trend: Array<{
    month: string;
    supplier_id: string;
    category: string;
    case_count: number;
  }>;
  categories: Array<{
    category: string;
    vendor_count: number;
    avg_rating: number | null;
    avg_cost_eur: number | null;
    status: 'healthy' | 'low_coverage' | 'review' | 'critical';
    vendors: Array<{
      id: string;
      name: string;
      location: string;
      country: string | null;
      rating: number | null;
      review_count: number;
      response_sla_hours: number | null;
      cost_eur: number | null;
      cost_min_eur: number | null;
      cost_max_eur: number | null;
      recent_reviews: Array<{ score: number; comment: string; date: string }>;
    }>;
  }>;
  coverage: Array<{
    category: string;
    country: string;
    vendor_count: number;
    status: 'healthy' | 'thin' | 'gap';
  }>;
  cost_trend: Array<{ date: string; avg_cost_eur: number }>;
  rating_trend: Array<{ date: string; avg_rating: number }>;
}

export interface HrVendor {
  id: string;
  name: string;
  service_categories: string[];
  corridors: string[];
  contact_email: string;
  description?: string;
  is_approved: boolean;
}

/** A row of a case's assigned-vendor shortlist.
 *  Returned by GET /api/cases/:caseId/vendors and, identically shaped, by the
 *  POST that creates one — so an assign result can go straight into the panel's
 *  query cache. Rendered by CaseVendorsPanel. */
/** [AIQ-2025] The four states public.case_vendor_shortlist.status permits. Mirrors
 *  the table's CHECK constraint — "Removed" is deliberately absent: unassigning is
 *  a hard DELETE, not a state. */
export const CASE_VENDOR_STATUSES = ['Assigned', 'Briefed', 'In Progress', 'Complete'] as const;
export type CaseVendorStatus = (typeof CASE_VENDOR_STATUSES)[number];

export interface CaseVendorRow {
  shortlist_id: string | null;
  /** [AIQ-2024] The vendor's own id, so a caller can tell WHICH vendor a row is
   *  without matching on the display name. */
  vendor_id: string | null;
  category: string | null;
  status: string;
  contact_name: string | null;
  contact_email: string | null;
  vendor_name: string | null;
  vendor_website: string | null;
}

export interface ImmigrationRequirementsResponse {
  covered: boolean;
  coverage_reason: string | null;
  corridor: string | null;
  corridor_from: string;
  corridor_to: string;
  visa_type: string;
  document_count: number;
  estimated_timeline_days: number | null;
  requirements: Array<{
    document_type: string;
    document_name: string;
    is_required: boolean;
    freshness_days: number | null;
    requires_apostille: boolean;
    apostille_countries: string[];
    requires_translation: boolean;
    translation_languages: string[];
    typical_processing_days: number | null;
    book_early_flag: boolean;
    book_early_reason: string | null;
    form_url: string | null;
  }>;
  risk_flags: Array<{
    flag_type: string;
    severity: 'critical' | 'warning' | 'info';
    title: string;
    description: string;
    recommended_action: string;
    deadline: string | null;
  }>;
  employee_nationality?: string | null;
  has_dependents?: boolean;
  dependents_count?: number;
}

export interface ImmigrationInterviewStatus {
  has_session: boolean;
  completion_pct: number;
  is_complete: boolean;
  started_at: string | null;
  last_active_at: string | null;
  completed_at: string | null;
}

export interface ImmigrationMilestonesResponse {
  milestones: Array<{
    id: string;
    milestone_type: string;
    status: string;
    sort_order: number;
    target_date: string | null;
    completed_date: string | null;
    notes: string | null;
    evidence_url: string | null;
    book_early_alert: string | null;
    created_at: string | null;
    updated_at: string | null;
  }>;
}

export interface ErasureRequestsResponse {
  requests: Array<{
    id: string;
    case_id: string;
    employee_id: string;
    status: string;
    reason: string | null;
    requested_at: string | null;
    statutory_due_at: string | null;
    reviewed_by: string | null;
    reviewed_at: string | null;
    review_notes: string | null;
    completed_at: string | null;
  }>;
  pending_count: number;
}

export interface ProcessErasureResponse {
  request_id: string;
  status: string;
  profiles_anonymised: number;
  reviewed_by: string;
  reviewed_at: string;
}

export interface HrAnalyticsResponse {
  workspace: {
    avg_completion_days: number | null;
    compliance_incident_rate: number | null;
    total_cases_in_window: number;
    closed_cases_in_window: number;
    top_delay_causes: Array<{ cause: string; count: number }>;
    corridor_breakdown: Array<{ corridor: string; avg_days: number; case_count: number }>;
    computed_at: string | null;
  };
  industry: {
    median_completion_days: number | null;
    median_compliance_rate: number | null;
    case_count: number;
    workspace_count: number;
    is_valid: boolean;
    computed_at: string | null;
  } | null;
  trend: Array<{ month: string; avg_completion_days: number | null }>;
}

export interface HrDraftCase {
  id: string;
  status: 'draft';
  company_id: string | null;
  created_at: string | null;
  hr_user_id: string | null;
}

export interface BenefitCandidateInput {
  id: string;
  category: string;
  cost_per_employee: number;
  expected_satisfaction: number;
  variance?: number;
  mandatory?: boolean;
}
export interface OptimizeBenefitMixRequest {
  budget: number;
  candidates: BenefitCandidateInput[];
  mandatory_ids?: string[];
  category_caps?: Record<string, number>;
  lambda_risk?: number;
  min_coverage?: number;
}
export interface OptimizeBenefitMixResponse {
  feasible: boolean;
  infeasibility_reason: string | null;
  selected: string[];
  achieved_utility: number;
  total_cost: number;
  lambda_risk: number;
  shadow_prices: {
    budget_per_1000: number;
    category_caps: Record<string, number>;
    min_coverage: number;
  };
}

export const hrAPI = {
  getBacklog: async (): Promise<HrBacklogResponse> => {
    const response = await api.get<HrBacklogResponse>('/api/hr/backlog');
    return response.data;
  },
  /** [Parker-B] Run the Markowitz benefit-mix optimizer for a company. Candidates
   *  must carry expected_satisfaction (else the endpoint 422s when no prior exists). */
  optimizeBenefitMix: async (companyId: string, body: OptimizeBenefitMixRequest): Promise<OptimizeBenefitMixResponse> => {
    const response = await api.post<OptimizeBenefitMixResponse>(`/api/hr/${companyId}/optimize-benefit-mix`, body);
    return response.data;
  },
  createCase: async (): Promise<{ caseId: string }> => {
    const response = await api.post<{ caseId: string }>('/api/hr/cases', undefined, { timeout: HR_CASE_TIMEOUT });
    return response.data;
  },
  assignCase: async (
    caseId: string,
    employeeIdentifier: string,
    options?: { firstName?: string; lastName?: string; level?: string }
  ): Promise<AssignCaseResponse> => {
    const response = await api.post<AssignCaseResponse>(
      `/api/hr/cases/${caseId}/assign`,
      {
        employeeIdentifier,
        employeeFirstName: options?.firstName?.trim() || undefined,
        employeeLastName: options?.lastName?.trim() || undefined,
        // Optional seniority band → benefit comparison targets the employee's level.
        employeeLevel: options?.level?.trim() || undefined,
      },
      { timeout: HR_CASE_TIMEOUT },
    );
    return response.data;
  },
  listAssignments: async (params?: {
    signal?: AbortSignal;
    limit?: number;
    offset?: number;
    search?: string;
    status?: string;
    destination?: string;
  }): Promise<AssignmentsListResponse> => {
    const { signal, ...query } = params ?? {};
    const response = await api.get<unknown>('/api/hr/assignments', {
      signal,
      params: {
        limit: query.limit ?? 25,
        offset: query.offset ?? 0,
        ...(query.search && { search: query.search }),
        ...(query.status && { status: query.status }),
        ...(query.destination && { destination: query.destination }),
      },
    });
    const payload = response.data;
    // Defensive: proxies or older backends may return a non-array; prevents ".filter is not a function" crashes.
    const raw =
      payload && typeof payload === 'object' && 'assignments' in payload
        ? (payload as AssignmentsListResponse).assignments
        : Array.isArray(payload)
          ? (payload as AssignmentSummary[])
          : [];
    const assignments = Array.isArray(raw) ? raw : [];
    const totalRaw = payload && typeof payload === 'object' && 'total' in payload ? (payload as AssignmentsListResponse).total : undefined;
    const total = typeof totalRaw === 'number' && Number.isFinite(totalRaw) ? totalRaw : assignments.length;
    return { assignments, total };
  },
  /** AIQ-378d — behind-schedule ("case health") cases for the HR's company. */
  getCaseHealth: async (opts?: { signal?: AbortSignal }): Promise<{ cases: CaseHealthFlag[] }> => {
    const response = await api.get<{ cases: CaseHealthFlag[] }>('/api/hr/cases/behind-schedule', { signal: opts?.signal });
    const cases = Array.isArray(response.data?.cases) ? (response.data.cases) : [];
    return { cases };
  },
  getAssignment: async (assignmentId: string, opts?: { signal?: AbortSignal }): Promise<AssignmentDetail> => {
    const response = await api.get<AssignmentDetail>(`/api/hr/assignments/${assignmentId}`, { signal: opts?.signal });
    return response.data;
  },
  getReadinessSummary: async (
    assignmentId: string,
    opts?: { signal?: AbortSignal }
  ): Promise<Record<string, unknown>> => {
    const response = await api.get<Record<string, unknown>>(`/api/hr/assignments/${encodeURIComponent(assignmentId)}/readiness/summary`, {
      signal: opts?.signal,
    });
    return response.data;
  },
  getReadinessDetail: async (
    assignmentId: string,
    opts?: { signal?: AbortSignal }
  ): Promise<Record<string, unknown>> => {
    const response = await api.get<Record<string, unknown>>(`/api/hr/assignments/${encodeURIComponent(assignmentId)}/readiness/detail`, {
      signal: opts?.signal,
    });
    return response.data;
  },
  patchReadinessChecklistItem: async (
    assignmentId: string,
    itemId: string,
    payload: { status: string; notes?: string }
  ): Promise<{ success: boolean }> => {
    const response = await api.patch<{ success: boolean }>(
      `/api/hr/assignments/${encodeURIComponent(assignmentId)}/readiness/checklist-items/${encodeURIComponent(itemId)}`,
      payload
    );
    return response.data;
  },
  patchReadinessMilestone: async (
    assignmentId: string,
    milestoneId: string,
    payload: { completed: boolean; notes?: string }
  ): Promise<{ success: boolean }> => {
    const response = await api.patch<{ success: boolean }>(
      `/api/hr/assignments/${encodeURIComponent(assignmentId)}/readiness/milestones/${encodeURIComponent(milestoneId)}`,
      payload
    );
    return response.data;
  },
  getResolvedPolicy: async (assignmentId: string): Promise<ResolvedPolicyResponse> => {
    const response = await api.get<ResolvedPolicyResponse>(`/api/hr/assignments/${assignmentId}/resolved-policy`);
    return response.data;
  },
  recomputeResolvedPolicy: async (assignmentId: string): Promise<RecomputedPolicyResponse> => {
    const response = await api.post<RecomputedPolicyResponse>(`/api/hr/assignments/${assignmentId}/resolved-policy/recompute`);
    return response.data;
  },
  /** Compare selected services vs resolved policy (with diagnostics) */
  getPolicyServiceComparison: async (assignmentId: string): Promise<PolicyServiceComparisonResponse> => {
    const response = await api.get<PolicyServiceComparisonResponse>(`/api/hr/assignments/${assignmentId}/policy-service-comparison`);
    return response.data;
  },
  /** Same payload as employee route; allowed for HR via `require_hr_or_employee`. */
  getAssignmentServices: async (assignmentId: string): Promise<AssignmentServicesResponse> => {
    const response = await api.get<AssignmentServicesResponse>(`/api/employee/assignments/${encodeURIComponent(assignmentId)}/services`);
    return response.data;
  },
  getPolicy: async (caseId: string): Promise<PolicyResponse> => {
    const response = await api.get<PolicyResponse>('/api/hr/policy', { params: { caseId } });
    return response.data;
  },
  requestPolicyException: async (
    caseId: string,
    payload: { category: string; reason?: string; amount?: number }
  ): Promise<unknown> => {
    const response = await api.post<unknown>(`/api/hr/cases/${caseId}/policy/exceptions`, payload);
    return response.data;
  },
  getCompanyProfile: async (): Promise<{ company: Record<string, unknown> | null }> => {
    return cachedRequest('hr:company-profile', 60_000, async () => {
      const response = await api.get<{ company: Record<string, unknown> | null }>('/api/hr/company-profile');
      return response.data;
    });
  },
  /** AIQ-1223c — deterministic proposed workspace config for the first-run UI. */
  getInferredOnboardingConfig: async (): Promise<InferredOnboardingConfig> => {
    const response = await api.get<InferredOnboardingConfig>('/api/hr/onboarding/inferred-config');
    return response.data;
  },
  /** Company-scoped employees for HR */
  listCompanyEmployees: async (): Promise<{
    employees: HrCompanyEmployee[];
    has_company?: boolean;
  }> => {
    const response = await api.get<{ employees: HrCompanyEmployee[]; has_company?: boolean }>('/api/hr/employees');
    return response.data;
  },
  getEmployee: async (employeeId: string): Promise<{ employee: HrCompanyEmployee }> => {
    const response = await api.get<{ employee: HrCompanyEmployee }>(`/api/hr/employees/${employeeId}`);
    return response.data;
  },
  updateEmployee: async (
    employeeId: string,
    payload: { band?: string; assignment_type?: string; status?: string }
  ): Promise<{ employee: HrCompanyEmployee }> => {
    const response = await api.patch<{ employee: HrCompanyEmployee }>(`/api/hr/employees/${employeeId}`, payload);
    return response.data;
  },
  deleteEmployee: async (employeeId: string): Promise<void> => {
    await api.delete(`/api/hr/employees/${employeeId}`);
  },
  saveCompanyProfile: async (
    payload: CompanyProfilePayload,
  ): Promise<{ ok?: boolean; company_id?: string; company?: Record<string, unknown> | null }> => {
    const response = await api.post<{ ok?: boolean; company_id?: string; company?: Record<string, unknown> | null }>(
      '/api/hr/company-profile',
      payload,
    );
    invalidateApiCache('hr:company-profile');
    invalidateApiCache('company:get');
    return response.data;
  },
  uploadCompanyLogo: async (file: File): Promise<{ ok: boolean; logo_url: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post<{ ok: boolean; logo_url: string }>('/api/hr/company-profile/logo', formData, { timeout: 120_000 });
    invalidateApiCache('hr:company-profile');
    invalidateApiCache('company:get');
    return response.data;
  },
  removeCompanyLogo: async (): Promise<{ ok: boolean }> => {
    const response = await api.post<{ ok: boolean }>('/api/hr/company-profile/remove-logo');
    invalidateApiCache('hr:company-profile');
    invalidateApiCache('company:get');
    return response.data;
  },
  listMessages: async (): Promise<{ messages: Record<string, unknown>[] }> => {
    const response = await api.get<{ messages: Record<string, unknown>[] }>('/api/hr/messages');
    return response.data;
  },
  /** Send a message to the assigned employee on a case thread (tenant-scoped server-side). */
  sendMessage: async (assignmentId: string, body: string): Promise<{ ok: boolean; message: Record<string, unknown> }> => {
    const response = await api.post<{ ok: boolean; message: Record<string, unknown> }>('/api/hr/messages', {
      assignment_id: assignmentId,
      body,
    });
    return response.data;
  },
  /** One row per assignment (case thread); company-scoped. */
  listMessageConversations: async (params?: {
    q?: string;
    archive?: 'active' | 'archived' | 'all';
    unread_only?: boolean;
    limit?: number;
    offset?: number;
    signal?: AbortSignal;
  }): Promise<{ conversations: Record<string, unknown>[]; has_more?: boolean }> => {
    const { signal, ...query } = params ?? {};
    const response = await api.get<{ conversations: Record<string, unknown>[]; has_more?: boolean }>('/api/hr/messages/conversations', {
      signal,
      params: {
        ...(query.q && { q: query.q }),
        archive: query.archive ?? 'active',
        unread_only: query.unread_only ?? false,
        limit: query.limit ?? 50,
        offset: query.offset ?? 0,
      },
    });
    return response.data;
  },
  getMessageThread: async (
    assignmentId: string,
    opts?: { signal?: AbortSignal }
  ): Promise<{ assignment_id: string; messages: Record<string, unknown>[] }> => {
    const response = await api.get<{ assignment_id: string; messages: Record<string, unknown>[] }>(
      `/api/hr/messages/threads/${encodeURIComponent(assignmentId)}`,
      { signal: opts?.signal }
    );
    return response.data;
  },
  archiveMessageConversations: async (payload: {
    assignment_ids: string[];
    archived: boolean;
  }): Promise<{ ok: boolean; updated: number }> => {
    const response = await api.post<{ ok: boolean; updated: number }>('/api/hr/messages/conversations/archive', payload);
    return response.data;
  },
  deleteHrMessage: async (messageId: string): Promise<{ ok: boolean }> => {
    const response = await api.delete<{ ok: boolean }>(
      `/api/hr/messages/${encodeURIComponent(messageId)}`
    );
    return response.data;
  },
  getCaseCompliance: async (caseId: string): Promise<ComplianceCaseReport> => {
    const response = await api.get<ComplianceCaseReport>(`/api/hr/cases/${caseId}/compliance`);
    return response.data;
  },
  runCaseCompliance: async (caseId: string): Promise<ComplianceCaseReport> => {
    const response = await api.post<ComplianceCaseReport>(`/api/hr/cases/${caseId}/compliance/run`);
    return response.data;
  },
  recordComplianceAction: async (
    caseId: string,
    payload: { actionType: string; checkId: string; notes?: string; payload?: unknown }
  ): Promise<unknown> => {
    const response = await api.post<unknown>(`/api/hr/cases/${caseId}/compliance/actions`, payload);
    return response.data;
  },
  runCompliance: async (assignmentId: string): Promise<unknown> => {
    const response = await api.post<unknown>(`/api/hr/assignments/${assignmentId}/run-compliance`);
    return response.data;
  },
  decide: async (
    assignmentId: string,
    decision: 'approved' | 'rejected',
    opts?: { notes?: string; requestedSections?: string[] }
  ): Promise<unknown> => {
    const response = await api.post<unknown>(`/api/hr/assignments/${assignmentId}/decision`, {
      decision,
      notes: opts?.notes,
      requestedSections: opts?.requestedSections,
    });
    return response.data;
  },
  updateIdentifier: async (assignmentId: string, employeeIdentifier: string): Promise<unknown> => {
    const response = await api.post<unknown>(`/api/hr/assignments/${assignmentId}/identifier`, { employeeIdentifier });
    return response.data;
  },
  deleteAssignment: async (assignmentId: string): Promise<unknown> => {
    const response = await api.delete<unknown>(`/api/hr/assignments/${assignmentId}`);
    return response.data;
  },
  postFeedback: async (assignmentId: string, message: string): Promise<{ ok: boolean; id: string; created_at: string }> => {
    const response = await api.post<{ ok: boolean; id: string; created_at: string }>(`/api/hr/assignments/${assignmentId}/feedback`, { message });
    return response.data;
  },
  getFeedback: async (assignmentId: string): Promise<Array<{ id: string; assignment_id: string; hr_user_id: string; employee_user_id: string | null; message: string; created_at: string }>> => {
    const response = await api.get<Array<{ id: string; assignment_id: string; hr_user_id: string; employee_user_id: string | null; message: string; created_at: string }>>(`/api/hr/assignments/${assignmentId}/feedback`);
    return response.data;
  },
  // Command Center
  getCommandCenterKPIs: async (): Promise<CommandCenterKPIs> => {
    const response = await api.get<CommandCenterKPIs>('/api/hr/command-center/kpis');
    return response.data;
  },
  listCommandCenterCases: async (params?: { page?: number; limit?: number; risk_filter?: string }): Promise<CommandCenterCaseRow[]> => {
    const response = await api.get<CommandCenterCaseRow[]>('/api/hr/command-center/cases', { params });
    return response.data;
  },
  getCommandCenterCaseDetail: async (assignmentId: string): Promise<{ id: string; caseId?: string | null; employeeIdentifier: string; destCountry?: string; destCity?: string; status: string; riskStatus: string; budgetLimit?: number; budgetEstimated?: number; expectedStartDate?: string; tasksTotal: number; tasksDone: number; tasksOverdue: number; phases: Array<{ phase: string; tasks: Array<{ title: string; status: string; due_date?: string }> }>; events: Array<{ event_type: string; description?: string; created_at: string }> }> => {
    const response = await api.get<{ id: string; caseId?: string | null; employeeIdentifier: string; destCountry?: string; destCity?: string; status: string; riskStatus: string; budgetLimit?: number; budgetEstimated?: number; expectedStartDate?: string; tasksTotal: number; tasksDone: number; tasksOverdue: number; phases: Array<{ phase: string; tasks: Array<{ title: string; status: string; due_date?: string }> }>; events: Array<{ event_type: string; description?: string; created_at: string }> }>(`/api/hr/command-center/cases/${assignmentId}`);
    return response.data;
  },
  /** [Parker-A] Predicted remaining case duration (Cox model). 404s when the
   *  PREDICTIONS_ENABLED canary is off or no model has been trained — callers
   *  should treat 404 as "no prediction" and render nothing. */
  getCasePredictedDuration: async (caseId: string): Promise<{ median_days: number; p20_days: number; p80_days: number; model_version: string; n_training_cases: number }> => {
    const response = await api.get<{ median_days: number; p20_days: number; p80_days: number; model_version: string; n_training_cases: number }>(`/api/cases/${caseId}/predicted-duration`);
    return response.data;
  },
  /** Provider × Case status matrix for the HR grid view (AIQ-14). */
  getProviderStatusGrid: async (): Promise<ProviderGridResponse> => {
    const response = await api.get<ProviderGridResponse>('/api/hr/provider-status-grid');
    return response.data;
  },
  /** Bounded policy Q&A for the HR policy workspace (draft + published context). */
  postPolicyAssistantQuery: async (
    policyId: string,
    message: string,
    documentId?: string | null
  ): Promise<HrPolicyAssistantQueryResponse> => {
    // AIQ-833 / F2: cut over to the constrained RAG engine. Company scoping is
    // server-derived from the authenticated user — policy_id/document_id are no
    // longer sent (kept on the signature + response for shape compatibility).
    const response = await api.post<RagQueryResponse>(
      '/api/policy-assistant/rag-query',
      { question: message },
      { timeout: 120_000 }
    );
    return ragResponseToHrResponse(response.data, policyId, documentId);
  },

  // ── Quote requests (AIQ-65) ──────────────────────────────────────────────

  getServiceCategories: async (): Promise<{ service_categories: string[] }> => {
    const response = await api.get<{ service_categories: string[] }>('/api/hr/service-categories');
    return response.data;
  },

  // `getQuoteRequests` / `updateQuoteRequestStatus` (GET+PATCH /api/hr/quote-requests) are
  // gone: they read the retired `quote_requests` table, whose write path was tombstoned in
  // AIQ-1525 (newest row 2026-06-29). The HR case detail was their only caller and it now
  // reads the canonical `rfqs` via getCaseRfqs() in api/hrCoordination.ts.

  // ── NAV-SP-2: Vendor performance dashboard ───────────────────────────────

  /** GET /api/hr/vendor-performance?range=30d|90d|12mo — NAV-SP-2 Vendor Performance tab. */
  getVendorPerformance: async (range: '30d' | '90d' | '12mo' = '90d'): Promise<VendorPerformanceResponse> => {
    const response = await api.get<VendorPerformanceResponse>('/api/hr/vendor-performance', { params: { range } });
    return response.data;
  },

  // ── AIQ-40-A/B: Vendor directory ─────────────────────────────────────────

  // ── AIQ-1896: case vendor assignment ─────────────────────────────────────
  //
  // These are the write path public.case_vendor_shortlist never had. They live on
  // /api/cases (cases_write.py), not /api/hr, because the shortlist is keyed on the
  // canonical case id — the backend resolves whichever id form the caller passes.

  /** POST /api/cases/:caseId/vendors — attach a browsed vendor to a case.
   *  Idempotent: re-assigning the same vendor+service returns the existing row. */
  assignVendorToCase: async (
    caseId: string,
    payload: {
      vendor_id: string;
      service_key?: string;
      contact_name?: string;
      contact_email?: string;
    },
  ): Promise<CaseVendorRow> => {
    const response = await api.post<CaseVendorRow>(`/api/cases/${caseId}/vendors`, payload);
    return response.data;
  },

  /** GET /api/cases/:caseId/vendors — the vendors already attached to a case.
   *  [AIQ-2024] Used by VendorBrowsePanel to show real "already assigned" state on
   *  open, rather than only remembering clicks made in the current session. */
  getCaseVendors: async (caseId: string): Promise<CaseVendorRow[]> => {
    const response = await api.get<CaseVendorRow[]>(`/api/cases/${caseId}/vendors`);
    return Array.isArray(response.data) ? response.data : [];
  },

  /** PATCH /api/cases/:caseId/vendors/:shortlistId — move a vendor through its
   *  engagement lifecycle. [AIQ-2025] Only Assigned / Briefed / In Progress /
   *  Complete are accepted; the server 422s anything else rather than letting the
   *  database CHECK constraint surface as a 500. */
  updateCaseVendorStatus: async (
    caseId: string,
    shortlistId: string,
    status: CaseVendorStatus,
  ): Promise<CaseVendorRow> => {
    const response = await api.patch<CaseVendorRow>(
      `/api/cases/${caseId}/vendors/${shortlistId}`,
      { status },
    );
    return response.data;
  },

  /** DELETE /api/cases/:caseId/vendors/:shortlistId — detach a vendor from a case. */
  unassignVendorFromCase: async (caseId: string, shortlistId: string): Promise<void> => {
    await api.delete(`/api/cases/${caseId}/vendors/${shortlistId}`);
  },

  /** GET /api/hr/vendors?corridor=X&category=Y */
  getVendors: async (params?: {
    corridor?: string;
    category?: string;
  }): Promise<{ vendors: HrVendor[] }> => {
    const response = await api.get<{ vendors: HrVendor[] } | HrVendor[]>('/api/hr/vendors', { params });
    const data = response.data;
    return { vendors: Array.isArray(data) ? data : (data.vendors ?? []) };
  },

  /** GET /api/hr/vendors/corridors */
  getVendorCorridors: async (): Promise<{ corridors: string[] }> => {
    const response = await api.get<{ corridors: string[] }>('/api/hr/vendors/corridors');
    return response.data;
  },

  // ── IMM-13: Immigration status panel ─────────────────────────────────────

  /** GET /api/hr/cases/{caseId}/immigration-requirements */
  // AIQ-847 / F1: backend fails closed on uncovered corridors (AIQ-832, PR #399).
  // covered=false ⇒ no seeded checklist for this corridor × visa_type; the
  // timeline is then null and requirements/risk_flags are empty.
  getImmigrationRequirements: async (caseId: string): Promise<ImmigrationRequirementsResponse> => {
    const response = await api.get<ImmigrationRequirementsResponse>(`/api/hr/cases/${caseId}/immigration-requirements`);
    return response.data;
  },

  /** GET /api/hr/cases/{caseId}/immigration/interview-status (IMM-13) */
  getImmigrationInterviewStatus: async (caseId: string): Promise<ImmigrationInterviewStatus> => {
    const response = await api.get<ImmigrationInterviewStatus>(`/api/hr/cases/${caseId}/immigration/interview-status`);
    return response.data;
  },

  // ── IMM-14: immigration milestones ────────────────────────────────────────

  /** GET /api/hr/cases/{caseId}/immigration/milestones */
  listImmigrationMilestones: async (caseId: string): Promise<ImmigrationMilestonesResponse> => {
    const response = await api.get<ImmigrationMilestonesResponse>(`/api/hr/cases/${caseId}/immigration/milestones`);
    return response.data;
  },

  /** POST /api/hr/cases/{caseId}/immigration/milestones */
  createImmigrationMilestone: async (
    caseId: string,
    payload: {
      milestone_type: string;
      target_date?: string | null;
      sort_order?: number;
      book_early_alert?: string | null;
    },
  ): Promise<{ id: string; milestone_type: string; status: string }> => {
    const response = await api.post<{ id: string; milestone_type: string; status: string }>(`/api/hr/cases/${caseId}/immigration/milestones`, payload);
    return response.data;
  },

  /** PATCH /api/hr/cases/{caseId}/immigration/milestones/{milestoneId} */
  updateImmigrationMilestone: async (
    caseId: string,
    milestoneId: string,
    patch: {
      status?: string;
      completed_date?: string | null;
      target_date?: string | null;
      notes?: string | null;
      evidence_url?: string | null;
    },
  ): Promise<{ id: string; status: string; updated_at: string }> => {
    const response = await api.patch<{ id: string; status: string; updated_at: string }>(
      `/api/hr/cases/${caseId}/immigration/milestones/${milestoneId}`,
      patch,
    );
    return response.data;
  },

  // ── IMM-18: GDPR erasure-request review queue ────────────────────────────

  /** GET /api/hr/immigration/erasure-requests */
  listErasureRequests: async (
    statusFilter: 'pending' | 'completed' | 'rejected' | 'all' = 'pending',
  ): Promise<ErasureRequestsResponse> => {
    const response = await api.get<ErasureRequestsResponse>('/api/hr/immigration/erasure-requests', {
      params: { status_filter: statusFilter },
    });
    return response.data;
  },

  /** POST /api/hr/cases/{caseId}/immigration/process-erasure-request */
  processErasureRequest: async (
    caseId: string,
    payload: { request_id: string; decision: 'approve' | 'reject'; review_notes?: string },
  ): Promise<ProcessErasureResponse> => {
    const response = await api.post<ProcessErasureResponse>(
      `/api/hr/cases/${caseId}/immigration/process-erasure-request`,
      payload,
    );
    return response.data;
  },

  // [AIQ-1683] The HR-initiated `rfq_requests` model is fully retired — RFQs are
  // employee-led (canonical `rfqs`/`rfq_items`/`quotes` via servicesAPI.createRfq →
  // POST /api/rfqs), HR is payer/approver. The last `/api/hr/rfq-requests` reader was
  // removed and the table archived to `rfq_requests_legacy` (read-only).

  // ── AIQ-34-C: Employee task management (HR side) ──────────────────────────

  /** GET /api/hr/cases/{caseId}/tasks — full task list + completion stats */
  getCaseTasks: async (caseId: string): Promise<EmployeeTaskListResponse> => {
    const response = await api.get<EmployeeTaskListResponse>(`/api/hr/cases/${caseId}/tasks`);
    return response.data;
  },

  /** PATCH /api/hr/cases/{caseId}/tasks/{taskId} — approve or request revision */
  reviewTask: async (
    caseId: string,
    taskId: string,
    body: { action: 'approved' | 'revision_requested'; review_note?: string }
  ): Promise<EmployeeTask> => {
    const response = await api.patch<EmployeeTask>(`/api/hr/cases/${caseId}/tasks/${taskId}`, body);
    return response.data;
  },

  /** POST /api/hr/cases/{caseId}/tasks — HR creates a task for the employee */
  addCaseTask: async (
    caseId: string,
    body: {
      employee_id: string;
      task_type: TaskType;
      title: string;
      description?: string;
      due_date?: string;
      required_file_upload?: boolean;
    }
  ): Promise<EmployeeTask> => {
    const response = await api.post<EmployeeTask>(`/api/hr/cases/${caseId}/tasks`, body);
    return response.data;
  },

  /** AIQ-39-B: Workspace benchmarking stats + industry comparison. */
  getAnalytics: async (): Promise<HrAnalyticsResponse> => {
    const response = await api.get<HrAnalyticsResponse>('/api/hr/analytics');
    return response.data;
  },

  // ── B10: Draft case info (no assignment yet) ─────────────────────────────

  /** Fetch minimal info for a draft relocation case that has no assignment row yet. */
  getDraftCase: async (caseId: string): Promise<HrDraftCase> => {
    const response = await api.get<HrDraftCase>(`/api/hr/cases/${caseId}`);
    return response.data;
  },

  // ── P5-7: Policy calibration alerts ────────────────────────────────────

  /** List undismissed policy calibration alerts for the caller's organisation. */
  listCalibrationAlerts: async (): Promise<CalibrationAlert[]> => {
    const response = await api.get<CalibrationAlert[]>('/api/hr/calibration-alerts');
    return response.data;
  },

  /** Dismiss a single calibration alert by ID. */
  dismissCalibrationAlert: async (alertId: string): Promise<void> => {
    await api.patch(`/api/hr/calibration-alerts/${alertId}/dismiss`);
  },

};
