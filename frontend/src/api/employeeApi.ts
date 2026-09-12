import type { IntakeData } from '../features/platform-v2/intake/EmployeeIntakePage';
import { queryClient } from '../lib/queryClient';
import type { EmployeeJourneyResponse, PolicyServiceComparisonResponse } from '../types';
import type { EmployeePolicyAssistantQueryResponse } from '../types/policyAssistant';
import { api, cachedRequest, invalidateApiCache } from './client';
import { ragResponseToEmployeeResponse, type RagQueryResponse } from './policyAssistantRagAdapter';
import {
  assignmentsOverviewSchema,
  currentAssignmentSchema,
  intakeEnvelopeSchema,
} from './schemas/employee';
import { parseResponse } from './schemas/parseResponse';

// ── AIQ-34-C shared types ────────────────────────────────────────────────────
export type TaskType =
  | 'document_upload'
  | 'address_confirmation'
  | 'acknowledgment'
  | 'selection'
  | 'custom';

export interface EmployeeTask {
  id: string;
  case_id: string;
  employee_id: string;
  org_id: string;
  task_type: TaskType;
  title: string;
  description: string | null;
  status: 'pending' | 'submitted' | 'revision_requested' | 'approved';
  due_date: string | null;
  required_file_upload: boolean;
  file_url: string | null;
  submission_data: Record<string, unknown> | null;
  review_note: string | null;
  submitted_at: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface EmployeeTaskListResponse {
  case_id: string;
  tasks: EmployeeTask[];
  stats: { total: number; completed: number; pct: number };
}
// ─────────────────────────────────────────────────────────────────────────────

interface EmployeePolicyCaps {
  // AIQ-999 — caps now come from the caller's resolved per-assignment policy,
  // not a global default. When the company has not published a matching
  // policy, has_policy is false and every cap is null (no fake defaults).
  has_policy?: boolean;
  housing_monthly_usd: number | null;
  movers_usd: number | null;
  schools_usd: number | null;
  immigration_usd: number | null;
}

interface AssignmentServiceRow {
  id: string;
  assignment_id: string;
  case_id: string;
  service_key: string;
  category: string;
  selected: number | boolean;
  estimated_cost: number | null;
  currency: string | null;
}

interface EmployeeAssignmentServicesResponse {
  assignment_id: string;
  case_id: string;
  services: AssignmentServiceRow[];
}

interface ComparisonReadiness {
  comparison_ready: boolean;
  comparison_blockers: string[];
  partial_numeric_coverage?: boolean;
}

interface ServicesPolicyContextResponse {
  ok?: boolean;
  has_policy?: boolean;
  comparison_available?: boolean;
  comparison_readiness?: ComparisonReadiness;
  currency: string;
  categories: Record<
    string,
    {
      wizard_key: string;
      benefit_key: string | null;
      determination: string;
      show_policy_comparison: boolean;
      primary_label: string;
      detail?: string | null;
      approval_required?: boolean;
      cap_summary?: string | null;
    }
  >;
  /** Availability for `requiresCuration` service tiles (e.g. pets): true once HR has
   *  curated ≥1 vendor for this employee's destination. Absent = treat as locked. */
  curated_availability?: Record<string, boolean>;
  source?: string;
  policy_surface?: {
    id?: string;
    title?: string;
    version?: number;
    effective_date?: string | null;
    company_name?: string | null;
  };
  resolution_context?: {
    assignment_type?: string | null;
    family_status?: string | null;
    tier?: string | null;
    source?: string | null;
  };
}

interface EmployeePolicyBudgetResponse {
  ok?: boolean;
  has_policy?: boolean;
  comparison_available?: boolean;
  comparison_readiness?: ComparisonReadiness;
  currency: string;
  caps: Record<string, number>;
  total_cap?: number | null;
  budget?: unknown;
}

interface ApplicablePolicyResponse {
  policy: Record<string, unknown> | null;
  allowedBenefits: Array<Record<string, unknown>>;
  wizardCriteria: Record<string, unknown>;
  employeeBand?: string;
  assignmentType?: string;
}

interface EmployeeResolvedPolicyResponse {
  policy: { id: string; title: string; version: number; effective_date: string } | null;
  benefits: Array<{
    benefit_key: string;
    included: boolean;
    min_value?: number;
    standard_value?: number;
    max_value?: number;
    currency?: string;
    approval_required: boolean;
    evidence_required_json?: string[];
    condition_summary?: string;
    exclusions_json?: Array<{ domain?: string; description?: string }>;
  }>;
  exclusions: Array<{ benefit_key?: string; domain: string; description?: string }>;
  resolved_at?: string;
  resolution_context?: { assignment_type?: string; family_status?: string; tier?: string };
  message?: string;
  has_policy?: boolean;
  message_secondary?: string;
  comparison_available?: boolean;
  comparison_readiness?: ComparisonReadiness;
}

interface MyAssignmentPackagePolicyResponse {
  status: 'found' | 'no_policy_found' | 'no_assignment' | 'error';
  ok?: boolean;
  assignment_id: string | null;
  has_policy?: boolean;
  policy: Record<string, unknown> | null;
  benefits: unknown[];
  exclusions: unknown[];
  resolved_at?: string | null;
  resolution_context?: Record<string, unknown> | null;
  message?: string | null;
  message_secondary?: string | null;
  company_id_used?: string;
  comparison_available?: boolean;
  comparison_readiness?: ComparisonReadiness;
}

interface PolicyEnvelopeResponse {
  policy: Record<string, unknown> | null;
  benefits: unknown[];
  exclusions: unknown[];
  envelopes: Array<{
    key: string;
    label: string;
    included: boolean;
    capped: boolean;
    min_value?: number;
    standard_value?: number;
    max_value?: number;
    currency: string;
    approval_required: boolean;
    evidence_required: string[];
  }>;
  message?: string;
}

interface QuoteRequestListItem {
  id: string;
  case_id: string;
  service_categories: string[];
  notes: string | null;
  budget_range: string | null;
  status: string;
  created_at: string;
}

export const employeeAPI = {
  getCurrentAssignment: async (): Promise<{
    assignment: unknown;
    linked_assignments?: unknown[];
    pending_claim_assignments?: unknown[];
  }> => {
    return cachedRequest('employee:current-assignment', 30_000, async () => {
      const response = await api.get('/api/employee/assignments/current');
      return parseResponse(currentAssignmentSchema, response.data, 'getCurrentAssignment');
    });
  },
  /** Compact linked + pending summaries (no case draft hydration). */
  getAssignmentsOverview: async (): Promise<{ linked: unknown[]; pending: unknown[]; overview_degraded?: boolean }> => {
    return cachedRequest('employee:assignments-overview', 60_000, async () => {
      const response = await api.get('/api/employee/assignments/overview');
      return parseResponse(assignmentsOverviewSchema, response.data, 'getAssignmentsOverview');
    });
  },
  listMessages: async (): Promise<{
    messages: unknown[];
    quote_threads?: unknown[];
  }> => {
    const response = await api.get<{ messages: unknown[]; quote_threads?: unknown[] }>('/api/employee/messages');
    return response.data;
  },
  /** Send a message to HR on your own assignment thread (ownership enforced server-side). */
  sendMessage: async (assignmentId: string, body: string): Promise<{ ok: boolean; message: unknown }> => {
    const response = await api.post<{ ok: boolean; message: unknown }>('/api/employee/messages', {
      assignment_id: assignmentId,
      body,
    });
    return response.data;
  },
  claimAssignment: async (assignmentId: string, email: string): Promise<{ success: boolean; assignmentId?: string }> => {
    const response = await api.post<{ success: boolean; assignmentId?: string }>(`/api/employee/assignments/${assignmentId}/claim`, { email });
    invalidateApiCache('employee:current-assignment');
    invalidateApiCache('employee:assignments-overview');
    void queryClient.invalidateQueries({ queryKey: ['employee', 'assignments-overview'] });
    return response.data;
  },
  /** Magic-link token claim: employee arrived via invite URL with ?token=<uuid>. */
  claimByToken: async (token: string): Promise<{ success: boolean; assignmentId?: string }> => {
    const response = await api.post<{ success: boolean; assignmentId?: string }>('/api/employee/assignments/claim-by-token', { token });
    invalidateApiCache('employee:current-assignment');
    invalidateApiCache('employee:assignments-overview');
    void queryClient.invalidateQueries({ queryKey: ['employee', 'assignments-overview'] });
    return response.data;
  },
  /**
   * Persist the intake wizard step counter for an assignment.
   * Fire-and-forget from the wizard on every `goTo` so the hub row can show
   * "N / TOTAL steps" without refresh. Invalidates the overview cache so the
   * next bootstrap returns the new count.
   */
  updateIntakeProgress: async (
    assignmentId: string,
    step: number,
    totalSteps: number,
  ): Promise<{ assignmentId: string; intakeStep: number; intakeTotalSteps: number; intakeUpdatedAt: string | null }> => {
    const response = await api.post<{ assignmentId: string; intakeStep: number; intakeTotalSteps: number; intakeUpdatedAt: string | null }>(
      `/api/employee/assignments/${assignmentId}/intake-progress`,
      { step, total_steps: totalSteps },
    );
    invalidateApiCache('employee:assignments-overview');
    void queryClient.invalidateQueries({ queryKey: ['employee', 'assignments-overview'] });
    return response.data;
  },
  /**
   * Fetch the persisted intake state (step counter + form draft) for an
   * assignment. Called once on wizard mount to hydrate `data` and `step`
   * from the last session.
   */
  getIntake: async (
    assignmentId: string,
  ): Promise<{
    assignmentId: string;
    intakeStep: number;
    intakeTotalSteps: number;
    intakeUpdatedAt: string | null;
    intakeDraft: Record<string, unknown> | null;
  }> => {
    const response = await api.get(`/api/employee/assignments/${assignmentId}/intake`);
    return parseResponse(intakeEnvelopeSchema, response.data, 'getIntake');
  },
  /**
   * Persist the wizard form draft. Fire-and-forget from the wizard's
   * debounced autosave (~700ms after the last edit). The wizard owns
   * the draft schema; the backend treats it opaquely.
   */
  updateIntakeDraft: async (
    assignmentId: string,
    data: IntakeData,
  ): Promise<{ assignmentId: string; intakeUpdatedAt: string | null }> => {
    const response = await api.patch<{ assignmentId: string; intakeUpdatedAt: string | null }>(
      `/api/employee/assignments/${assignmentId}/intake-draft`,
      { data },
    );
    return response.data;
  },
  /** Hub pending rows only: strict eligibility (pending_claim + contact linked + company + invites). */
  linkPendingAssignment: async (
    assignmentId: string,
    email: string
  ): Promise<{ success: boolean; assignmentId?: string; alreadyLinked?: boolean }> => {
    const response = await api.post<{ success: boolean; assignmentId?: string; alreadyLinked?: boolean }>(`/api/employee/assignments/${assignmentId}/link-pending`, { email });
    invalidateApiCache('employee:current-assignment');
    invalidateApiCache('employee:assignments-overview');
    void queryClient.invalidateQueries({ queryKey: ['employee', 'assignments-overview'] });
    return response.data;
  },
  getNextQuestion: async (assignmentId: string): Promise<EmployeeJourneyResponse> => {
    const response = await api.get<EmployeeJourneyResponse>('/api/employee/journey/next-question', { params: { assignmentId } });
    return response.data;
  },
  getFeedback: async (assignmentId: string): Promise<Array<{ id: string; assignment_id: string; message: string; created_at: string }>> => {
    const response = await api.get<Array<{ id: string; assignment_id: string; message: string; created_at: string }>>('/api/employee/assignment-feedback', { params: { assignment_id: assignmentId } });
    return response.data;
  },
  submitAnswer: async (assignmentId: string, questionId: string, answer: unknown): Promise<EmployeeJourneyResponse> => {
    const response = await api.post<EmployeeJourneyResponse>('/api/employee/journey/answer', { assignmentId, questionId, answer });
    return response.data;
  },
  submitAssignment: async (assignmentId: string): Promise<unknown> => {
    const response = await api.post<unknown>(`/api/employee/assignments/${assignmentId}/submit`);
    invalidateApiCache('employee:assignments-overview');
    invalidateApiCache('employee:current-assignment');
    void queryClient.invalidateQueries({ queryKey: ['employee', 'assignments-overview'] });
    return response.data;
  },
  updateProfilePhoto: async (assignmentId: string, photoUrl: string): Promise<unknown> => {
    const response = await api.post<unknown>(`/api/employee/assignments/${assignmentId}/photo`, {
      assignmentId,
      photoUrl,
    });
    return response.data;
  },
  getRecommendations: async (): Promise<{ housing: unknown[]; schools: unknown[]; movers: unknown[] }> => {
    const response = await api.get<{ housing: unknown[]; schools: unknown[]; movers: unknown[] }>('/api/employee/recommendations');
    return response.data;
  },
  getPolicyCaps: async (): Promise<EmployeePolicyCaps> => {
    const response = await api.get<EmployeePolicyCaps>('/api/employee/policy/caps');
    return response.data;
  },
  getAssignmentServices: async (assignmentId: string): Promise<EmployeeAssignmentServicesResponse> => {
    const response = await api.get<EmployeeAssignmentServicesResponse>(`/api/employee/assignments/${assignmentId}/services`);
    return response.data;
  },
  saveAssignmentServices: async (
    assignmentId: string,
    services: Array<{
      service_key: string;
      category: string;
      selected: boolean;
      estimated_cost: number | null;
      currency?: string | null;
    }>
  ): Promise<{ ok: boolean; services: unknown[] }> => {
    const response = await api.post<{ ok: boolean; services: unknown[] }>(`/api/employee/assignments/${assignmentId}/services`, { services });
    return response.data;
  },
  /**
   * Services page: per-category policy view from resolved published policy (Layer 2) only.
   */
  getServicesPolicyContext: async (assignmentId: string): Promise<ServicesPolicyContextResponse> => {
    const response = await api.get<ServicesPolicyContextResponse>(`/api/employee/assignments/${assignmentId}/services-policy-context`);
    return response.data;
  },
  getPolicyBudget: async (assignmentId: string): Promise<EmployeePolicyBudgetResponse> => {
    const response = await api.get<EmployeePolicyBudgetResponse>(`/api/employee/assignments/${assignmentId}/policy-budget`);
    return response.data;
  },
  getApplicablePolicy: async (assignmentId?: string): Promise<ApplicablePolicyResponse> => {
    const params = assignmentId ? { assignmentId } : {};
    const response = await api.get<ApplicablePolicyResponse>('/api/employee/policy/applicable', { params });
    return response.data;
  },
  /** Resolved policy from published company policy (preferred when assignmentId available) */
  getResolvedPolicy: async (assignmentId: string): Promise<EmployeeResolvedPolicyResponse> => {
    const response = await api.get<EmployeeResolvedPolicyResponse>(`/api/employee/assignments/${assignmentId}/policy`);
    return response.data;
  },
  /**
   * Single round-trip for Assignment Package & Limits (employee HR Policy page).
   * Avoids chaining current-assignment + policy calls on the critical path.
   */
  getMyAssignmentPackagePolicy: async (): Promise<MyAssignmentPackagePolicyResponse> => {
    const response = await api.get<MyAssignmentPackagePolicyResponse>('/api/employee/me/assignment-package-policy');
    return response.data;
  },
  /** Policy envelope (envelope cards ready) for comparison/budget logic */
  getPolicyEnvelope: async (assignmentId: string): Promise<PolicyEnvelopeResponse> => {
    const response = await api.get<PolicyEnvelopeResponse>(`/api/employee/assignments/${assignmentId}/policy-envelope`);
    return response.data;
  },
  /** Compare selected services vs resolved policy (read-only, explanatory) */
  getPolicyServiceComparison: async (assignmentId: string): Promise<PolicyServiceComparisonResponse> => {
    const response = await api.get<PolicyServiceComparisonResponse>(`/api/employee/assignments/${assignmentId}/policy-service-comparison`);
    return response.data;
  },
  /** Bounded policy Q&A from published policy data for this assignment. */
  postPolicyAssistantQuery: async (
    assignmentId: string,
    message: string
  ): Promise<EmployeePolicyAssistantQueryResponse> => {
    // AIQ-833 / F2: cut over to the constrained RAG engine (company scoping is
    // server-derived). assignment_id is kept on the signature + response shape.
    const response = await api.post<RagQueryResponse>(
      '/api/policy-assistant/rag-query',
      { question: message },
      { timeout: 120_000 }
    );
    return ragResponseToEmployeeResponse(response.data, assignmentId);
  },

  // ── Quote requests (AIQ-65) ──────────────────────────────────────────────
  // [AIQ-1525] The write path (createQuoteRequest → POST /api/employee/quote-requests) is
  // retired: employees now request quotes via the canonical RFQ flow (servicesAPI.createRfq →
  // POST /api/rfqs, a vendor shortlist). The read wrapper below stays for the historical rows.

  listMyQuoteRequests: async (): Promise<QuoteRequestListItem[]> => {
    const response = await api.get<QuoteRequestListItem[]>('/api/employee/quote-requests');
    return Array.isArray(response.data) ? response.data : [];
  },

  exportPolicySessionPdf: async (
    assignmentId: string,
    turns: Array<{
      question: string;
      answer_text: string;
      evidence: Array<{ label?: string; excerpt?: string }>;
    }>
  ): Promise<Blob> => {
    const response = await api.post<Blob>(
      '/api/employee/policy-assistant/export-pdf',
      { assignment_id: assignmentId, turns },
      { responseType: 'blob' }
    );
    return response.data;
  },
};

