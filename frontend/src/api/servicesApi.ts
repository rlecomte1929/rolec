import { api } from './client';
import type { EmployeeTask, EmployeeTaskListResponse } from './employeeApi';
import type { ServiceContextResult } from './types';

/** What POST /api/rfqs actually did.
 *
 *  [AIQ-1521] `contacted` is the list of suppliers whose inbox the request reached. It is EMPTY
 *  when supplier dispatch is turned off — in which case nobody outside ReloPass has seen the
 *  request, and the UI must say so. `not_contacted` gives the honest reason per supplier
 *  (typically: we hold no email address for them). */
export interface RfqCreateResult {
  ok: boolean;
  rfq: { id: string; rfq_ref: string };
  /** Shortlisted items that resolved to no supplier at all (AIQ-1520). */
  unreachable: string[];
  contacted?: string[];
  not_contacted?: Array<{ supplier: string; reason: string }>;
}

/** [AIQ-1516] The 5 categories HR must pick from when overriding the recommendation. */
export type OverrideReasonCategory =
  | 'employee_preference'
  | 'preferred_supplier'
  | 'negotiated_terms'
  | 'policy_exception'
  | 'other';

export interface QuoteDetail {
  id: string;
  rfq_id: string;
  vendor_id: string;
  currency: string;
  total_amount: number;
  valid_until?: string;
  status: string;
  quote_lines?: Array<{ label: string; amount: number }>;
}

/** [AIQ-1516] Best-value recommendation. `confidence: 'REFUSED'` (with `refused_reason`) means
 *  ranking would mislead — render the reason, not a pick. Never a bare score. */
export interface RfqRecommendation {
  recommended_quote_id: string | null;
  confidence: 'HIGH' | 'MEDIUM' | 'LOW' | 'REFUSED';
  headline: string;
  reasons: string[];
  trade_offs: string[];
  refused_reason?: string;
}

export interface PayerView {
  rfq_id: string;
  quotes: QuoteDetail[];
  recommendation: RfqRecommendation;
}

export interface RfqSummary {
  id: string;
  rfq_ref: string;
  case_id: string;
  /** Populated by GET /api/rfqs/{id} when the case is linked to an assignment */
  assignment_id?: string;
  status: string;
  created_at: string;
  items?: Array<{ service_key: string; requirements: Record<string, unknown> }>;
  recipients?: Array<{ vendor_id: string; status: string }>;
}

export interface RfqDetail extends RfqSummary {
  items: Array<{ service_key: string; requirements: Record<string, unknown> }>;
  recipients: Array<{ vendor_id: string; status: string }>;
  /** AIQ-1524: the offer the EMPLOYEE proposed. A proposal — it commits no spend. */
  preferred_quote_id?: string | null;
  /** AIQ-1524: the offer HR (the payer) validated. This is the spend approval. */
  validated_quote_id?: string | null;
  /** AIQ-1524: why HR validated this offer — surfaced to the employee, and it matters most
   *  when HR validated something other than what the employee proposed. */
  validation_reason?: string | null;
}

export interface QuoteCreatePayload {
  total_amount: number;
  currency: string;
  valid_until?: string;
  quote_lines: Array<{ label: string; amount: number }>;
}

export interface TimelineMilestone {
  id: string;
  case_id: string;
  milestone_type: string;
  title: string;
  description?: string;
  target_date?: string;
  actual_date?: string;
  status: string;
  sort_order: number;
  owner?: string;
  criticality?: string;
  notes?: string | null;
  created_at?: string;
  updated_at?: string;
  links?: Array<{ id: string; linked_entity_type: string; linked_entity_id: string }>;
}

export interface TimelineTaskSummary {
  total: number;
  completed: number;
  overdue: number;
  due_this_week: number;
  blocked: number;
  in_progress: number;
}

export interface TimelineResponse {
  case_id: string;
  assignment_id?: string;
  milestones: TimelineMilestone[];
  summary: TimelineTaskSummary;
}

export const servicesAPI = {
  /** Combined load: assignment, case context, services, answers, questions in one request. Use instead of 4 separate calls. */
  getServicesContext: async (
    assignmentId: string,
    fallbackServices?: string[]
  ): Promise<{
    assignment_id: string;
    case_id: string;
    case_context: { destCity?: string; destCountry?: string; originCity?: string; originCountry?: string };
    /** AIQ-1249d: canonical move date for the services context banner. */
    target_start_date?: string | null;
    services: Array<{ service_key: string; selected: boolean | number; [k: string]: unknown }>;
    answers: Array<{ service_key: string; answers: Record<string, unknown> }>;
    questions: unknown[];
    selected_services: string[];
  }> => {
    const params: Record<string, string> = { assignment_id: assignmentId };
    if (fallbackServices?.length) {
      params.fallback_services = fallbackServices.join(',');
    }
    const response = await api.get<ServiceContextResult>('/api/services/context', { params });
    return response.data;
  },
  getServiceAnswers: async (params: { caseId?: string; assignmentId?: string }): Promise<{ case_id: string; answers: unknown[] }> => {
    const p = params.caseId ? { case_id: params.caseId } : { assignment_id: params.assignmentId };
    const response = await api.get<{ case_id: string; answers: unknown[] }>('/api/services/answers', { params: p });
    return response.data;
  },
  getServiceQuestions: async (
    assignmentId: string,
    fallbackServices?: string[]
  ): Promise<{ questions: unknown[]; selected_services: string[] }> => {
    const params: Record<string, string> = { assignment_id: assignmentId };
    if (fallbackServices?.length) {
      params.fallback_services = fallbackServices.join(',');
    }
    const response = await api.get<{ questions: unknown[]; selected_services: string[] }>('/api/services/questions', { params });
    return response.data;
  },
  saveServiceAnswers: async (
    caseId: string,
    items: Array<{ service_key: string; answers: Record<string, unknown> }>,
    options?: { signal?: AbortSignal }
  ): Promise<{ ok: boolean }> => {
    const config = options?.signal ? { signal: options.signal } : {};
    const response = await api.post<{ ok: boolean }>('/api/services/answers', { case_id: caseId, items }, config);
    return response.data;
  },
  /** Create a real RFQ: one `rfqs` row + one `rfq_recipients` row per supplier.
   *
   *  `unreachable` (AIQ-1520) names the suppliers we could NOT reach — a catalog item with no
   *  supplier on record. The RFQ still goes to everyone who DID resolve; the caller must tell
   *  the employee who was left out rather than quietly send to fewer suppliers than they chose.
   *
   *  `contacted` / `not_contacted` (AIQ-1521) say what actually reached a supplier's inbox. The
   *  UI copy MUST be driven off these, not assumed: when supplier dispatch is off, `contacted` is
   *  empty and nobody was emailed — claiming otherwise would be the same lie AIQ-1515 removed. */
  createRfq: async (
    caseId: string,
    items: Array<{ service_key: string; requirements: Record<string, unknown> }>,
    supplierIds: string[]
  ): Promise<RfqCreateResult> => {
    const response = await api.post<RfqCreateResult>(
      '/api/rfqs',
      { case_id: caseId, items, supplier_ids: supplierIds },
    );
    return response.data;
  },

  // ---- Task Portal (AIQ-34-B) ----

  /** List all tasks for the current employee (auto-resolves case from linked assignment). */
  getTasks: async (caseId?: string): Promise<EmployeeTaskListResponse> => {
    const params: Record<string, string> = {};
    if (caseId) params.case_id = caseId;
    const response = await api.get<EmployeeTaskListResponse>('/api/employee/tasks', { params });
    return response.data;
  },

  /** Get a single task by ID. */
  getTask: async (taskId: string): Promise<EmployeeTask> => {
    const response = await api.get<EmployeeTask>(`/api/employee/tasks/${taskId}`);
    return response.data;
  },

  /** Submit a task with optional form data and/or file URL. */
  submitTask: async (
    taskId: string,
    payload: { submission_data?: Record<string, unknown>; file_url?: string }
  ): Promise<EmployeeTask> => {
    const response = await api.patch<EmployeeTask>(`/api/employee/tasks/${taskId}`, payload);
    return response.data;
  },
};

export const rfqAPI = {
  listByAssignment: async (assignmentId: string): Promise<{ rfqs: RfqSummary[] }> => {
    const response = await api.get<{ rfqs: RfqSummary[] }>(`/api/employee/assignments/${assignmentId}/rfqs`);
    return response.data;
  },
  get: async (rfqId: string): Promise<RfqDetail> => {
    const response = await api.get<RfqDetail>(`/api/rfqs/${rfqId}`);
    return response.data;
  },
  listQuotes: async (
    rfqId: string,
    options?: { comparison?: boolean }
  ): Promise<{ rfq_id: string; quotes: QuoteDetail[] }> => {
    const params = options?.comparison ? { comparison: '1' } : {};
    const response = await api.get<{ rfq_id: string; quotes: QuoteDetail[] }>(`/api/rfqs/${rfqId}/quotes`, { params });
    return response.data;
  },
  /** [AIQ-1516] The best-value recommendation for an RFQ's offers. Read-only; grounded only in
   *  signals that exist (price vs market, quality when reviews suffice) and REFUSES to rank when
   *  that would mislead (currency mismatch, a single offer). HR still validates via acceptQuote. */
  getPayerView: async (rfqId: string): Promise<PayerView> => {
    const response = await api.get<PayerView>(`/api/rfqs/${rfqId}/payer-view`);
    return response.data;
  },
  /** AIQ-1524: HR (the payer) validates the offer the company will pay for. HR-only — an
   *  employee calling this gets a 403. `reason` is recorded and shown back to the employee,
   *  and matters most when HR validates something other than what the employee proposed.
   *  [AIQ-1516] `overrideReasonCategory` is required by the server (422) when HR validates an
   *  offer other than the recommendation. */
  acceptQuote: async (
    rfqId: string,
    quoteId: string,
    reason?: string,
    overrideReasonCategory?: OverrideReasonCategory,
  ): Promise<{ ok: boolean; quote: QuoteDetail }> => {
    const body: Record<string, string> = {};
    if (reason) body.reason = reason;
    if (overrideReasonCategory) body.override_reason_category = overrideReasonCategory;
    const response = await api.patch<{ ok: boolean; quote: QuoteDetail }>(
      `/api/rfqs/${rfqId}/quotes/${quoteId}/accept`,
      body,
    );
    return response.data;
  },
  /** AIQ-1524: the EMPLOYEE proposes the offer they want. Commits no spend — HR validates. */
  proposeQuote: async (rfqId: string, quoteId: string): Promise<{ ok: boolean }> => {
    const response = await api.patch<{ ok: boolean }>(`/api/rfqs/${rfqId}/quotes/${quoteId}/propose`);
    return response.data;
  },
};

export const vendorAPI = {
  listRfqs: async (): Promise<{ rfqs: RfqSummary[] }> => {
    const response = await api.get<{ rfqs: RfqSummary[] }>('/api/vendor/rfqs');
    return response.data;
  },
  getRfq: async (rfqId: string): Promise<RfqDetail> => {
    const response = await api.get<RfqDetail>(`/api/vendor/rfqs/${rfqId}`);
    return response.data;
  },
  submitQuote: async (
    rfqId: string,
    payload: QuoteCreatePayload
  ): Promise<{ ok: boolean; quote: QuoteDetail }> => {
    const response = await api.post<{ ok: boolean; quote: QuoteDetail }>(`/api/vendor/rfqs/${rfqId}/quotes`, payload);
    return response.data;
  },
};

export const timelineAPI = {
  getByAssignment: async (
    assignmentId: string,
    options?: { ensureDefaults?: boolean; includeLinks?: boolean }
  ): Promise<TimelineResponse> => {
    const params: Record<string, string> = {};
    if (options?.ensureDefaults) params.ensure_defaults = '1';
    if (options?.includeLinks === false) params.include_links = 'false';
    const response = await api.get<TimelineResponse>(`/api/assignments/${assignmentId}/timeline`, { params });
    return response.data;
  },
  getByCase: async (
    caseId: string,
    options?: { ensureDefaults?: boolean; includeLinks?: boolean }
  ): Promise<TimelineResponse> => {
    const params: Record<string, string> = {};
    if (options?.ensureDefaults) params.ensure_defaults = '1';
    if (options?.includeLinks === false) params.include_links = 'false';
    const response = await api.get<TimelineResponse>(`/api/cases/${caseId}/timeline`, { params });
    return response.data;
  },
  updateMilestone: async (
    caseId: string,
    milestoneId: string,
    patch: Partial<{
      title: string;
      description: string;
      target_date: string;
      actual_date: string;
      status: string;
      sort_order: number;
      owner: string;
      criticality: string;
      notes: string | null;
    }>
  ): Promise<TimelineMilestone> => {
    const response = await api.patch<TimelineMilestone>(`/api/cases/${caseId}/timeline/milestones/${milestoneId}`, patch);
    return response.data;
  },
};
