import axios from 'axios';
import { getAuthItem, clearAuthItems } from '../utils/demo';
import { signOutSupabase } from './supabaseAuth';
import { getCurrentInteractionId, recordRequestPerf } from '../perf/perf';
import type {
  LoginRequest,
  LoginResponse,
  PolicyServiceComparisonResponse,
  RegisterRequest,
  NextQuestionResponse,
  AnswerRequest,
  RelocationProfile,
  DashboardResponse,
  HousingRecommendation,
  SchoolRecommendation,
  MoverRecommendation,
  AssignmentSummary,
  AssignmentsListResponse,
  AssignmentDetail,
  AssignCaseResponse,
  EmployeeJourneyResponse,
  PolicyResponse,
  ComplianceCaseReport,
  AdminContextResponse,
  AdminCompany,
  AdminProfile,
  AdminEmployee,
  AdminHrUser,
  HrCompanyEmployee,
  AdminRelocationCase,
  AdminAssignment,
  AdminCompanyDetailAssignment,
  AdminCompanyDetailPolicy,
  AdminCompanyDetailCounts,
  AdminCompanyDetailOrphanDiagnostics,
  AdminAssignmentDetail,
  AdminPolicyCompany,
  AdminPoliciesByCompany,
  AdminPolicyDetail,
  AdminPolicyVersion,
  AdminPolicyTemplatesResponse,
  AdminSupportCase,
  AdminSupportNote,
  CompanyProfilePayload,
  DossierQuestionsResponse,
  DossierSearchSuggestionsResponse,
} from '../types';

// VITE_API_URL must be set for every environment:
//   - Development:  http://localhost:8000         (via frontend/.env.development)
//   - Production:   https://api.relopass.com      (via frontend/.env.production)
// Fallback keeps local dev working if .env.development is missing.
const API_BASE_URL: string =
  import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://localhost:8000' : '');

export { API_BASE_URL };


// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  /** Avoid hanging UI for minutes when the API/proxy is wedged; large uploads can override per-request. */
  timeout: 90_000,
  headers: {
    'Content-Type': 'application/json',
  },
});

type CacheEntry<T> = {
  ts: number;
  data?: T;
  promise?: Promise<T>;
};

const apiCache = new Map<string, CacheEntry<any>>();

/** Clear a cached value so the next request fetches fresh. Use after 401 or when user retries. */
export function invalidateApiCache(key: string): void {
  apiCache.delete(key);
}

/** Drop all cache entries whose key starts with `prefix` (e.g. `admin:companies:`). */
export function invalidateApiCachePrefix(prefix: string): void {
  for (const k of [...apiCache.keys()]) {
    if (k.startsWith(prefix)) {
      apiCache.delete(k);
    }
  }
}

const cachedRequest = <T>(key: string, ttlMs: number, fetcher: () => Promise<T>): Promise<T> => {
  const now = Date.now();
  const existing = apiCache.get(key);
  if (existing?.data && now - existing.ts < ttlMs) {
    return Promise.resolve(existing.data as T);
  }
  if (existing?.promise) {
    return existing.promise as Promise<T>;
  }
  const promise = fetcher()
    .then((data) => {
      apiCache.set(key, { ts: Date.now(), data });
      return data;
    })
    .finally(() => {
      const current = apiCache.get(key);
      if (current?.promise) {
        apiCache.set(key, { ts: current.ts, data: current.data });
      }
    });
  apiCache.set(key, { ts: now, promise });
  return promise;
};

// Add auth token + request/perf metadata to requests
api.interceptors.request.use((config) => {
  const token = getAuthItem('relopass_token');
  if (!config.headers) (config as { headers?: Record<string, string> }).headers = {};
  // FormData: must NOT set Content-Type so browser sets multipart/form-data with boundary
  if (config.data instanceof FormData) {
    delete (config.headers as Record<string, unknown>)['Content-Type'];
  }
  if (token) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (config.headers as any).Authorization = `Bearer ${token}`;
  }

  // Attach / propagate X-Request-ID for correlation with backend.
  const existingId =
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ((config.headers as any)['X-Request-ID'] as string | undefined) || getCurrentInteractionId();
  const requestId =
    existingId ||
    (typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (config.headers as any)['X-Request-ID'] = requestId;

  // Stash perf metadata on the config (type-cast to avoid axios type extension).
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (config as any)._perfMeta = {
    requestId,
    tStart: typeof performance !== 'undefined' ? performance.now() : Date.now(),
  };

  return config;
});

// Global 401 handler + perf logging
api.interceptors.response.use(
  (res) => {
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const meta = (res.config as any)._perfMeta as { requestId: string; tStart: number } | undefined;
      if (meta) {
        const tEnd = typeof performance !== 'undefined' ? performance.now() : Date.now();
        const duration = tEnd - meta.tStart;
        // With axios we don't get a separate "headers" vs "body" hook; treat both as full duration.
        const path = (res.config.url || '').split('?')[0] || '/';
        const method = (res.config.method || 'GET').toUpperCase();
        recordRequestPerf({
          requestId: meta.requestId,
          method,
          path,
          status: res.status,
          ok: res.status >= 200 && res.status < 300,
          durationHeadersMs: duration,
          durationBodyMs: duration,
          startedAt: meta.tStart,
        });
      }
    } catch {
      // do not block response on perf logging failures
    }
    return res;
  },
  (err) => {
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const cfg = (err?.config || {}) as any;
      const meta = cfg._perfMeta as { requestId: string; tStart: number } | undefined;
      const status = err?.response?.status ?? 0;
      if (meta) {
        const tEnd = typeof performance !== 'undefined' ? performance.now() : Date.now();
        const duration = tEnd - meta.tStart;
        const path = (cfg.url || '').split('?')[0] || '/';
        const method = (cfg.method || 'GET').toUpperCase();
        recordRequestPerf({
          requestId: meta.requestId,
          method,
          path,
          status,
          ok: false,
          durationHeadersMs: duration,
          durationBodyMs: duration,
          startedAt: meta.tStart,
        });
      }
    } catch {
      // ignore
    }
    const status = err?.response?.status;
    const url = err?.config?.url ?? '';
    const isAuthEndpoint = /\/api\/auth\/(login|register)$/.test(url);
    const isDebugEndpoint = /\/api\/debug\//.test(url);
    if (status === 401 && !isAuthEndpoint && !isDebugEndpoint) {
      try {
        const d = typeof err?.response?.data?.detail === 'string'
          ? err.response.data.detail
          : JSON.stringify(err?.response?.data || 'Unknown');
        localStorage.setItem('debug_last_auth_error', d);
      } catch {
        localStorage.setItem('debug_last_auth_error', '401 Unauthorized');
      }
      invalidateApiCache('employee:current-assignment');
      clearAuthItems();
      const path = window.location.pathname || '';
      if (!path.startsWith('/auth') && path !== '/' && path !== '') {
        window.location.href = '/auth?mode=login';
      }
    }
    return Promise.reject(err);
  }
);

// Auth API
export const authAPI = {
  login: async (data: LoginRequest): Promise<LoginResponse> => {
    const response = await api.post('/api/auth/login', data);
    return response.data;
  },
  register: async (data: RegisterRequest): Promise<LoginResponse> => {
    const response = await api.post('/api/auth/register', data);
    return response.data;
  },
  logout: async (): Promise<void> => {
    const token = getAuthItem('relopass_token');
    try {
      await api.post(
        '/api/auth/logout',
        null,
        token ? { headers: { Authorization: `Bearer ${token}` } } : undefined
      );
    } catch {
      // Ignore — client will clear session anyway
    }
    await signOutSupabase();
    clearAuthItems();
  },
};

// Profile API
export const profileAPI = {
  getCurrent: async (): Promise<RelocationProfile> => {
    const response = await api.get('/api/profile/current');
    return response.data;
  },

  getNextQuestion: async (): Promise<NextQuestionResponse> => {
    const response = await api.get('/api/profile/next-question');
    return response.data;
  },

  submitAnswer: async (data: AnswerRequest): Promise<any> => {
    const response = await api.post('/api/profile/answer', data);
    return response.data;
  },

  complete: async (): Promise<any> => {
    const response = await api.post('/api/profile/complete');
    return response.data;
  },
};

// Recommendations API
export const recommendationsAPI = {
  getHousing: async (): Promise<HousingRecommendation[]> => {
    const response = await api.get('/api/recommendations/housing');
    return response.data;
  },

  getSchools: async (): Promise<SchoolRecommendation[]> => {
    const response = await api.get('/api/recommendations/schools');
    return response.data;
  },

  getMovers: async (): Promise<MoverRecommendation[]> => {
    const response = await api.get('/api/recommendations/movers');
    return response.data;
  },
};

// Dashboard API
export const dashboardAPI = {
  get: async (): Promise<DashboardResponse> => {
    const response = await api.get('/api/dashboard');
    return response.data;
  },
};

export const hrAPI = {
  createCase: async (): Promise<{ caseId: string }> => {
    const response = await api.post('/api/hr/cases');
    return response.data;
  },
  assignCase: async (
    caseId: string,
    employeeIdentifier: string,
    options?: { firstName?: string; lastName?: string }
  ): Promise<AssignCaseResponse> => {
    const response = await api.post(`/api/hr/cases/${caseId}/assign`, {
      employeeIdentifier,
      employeeFirstName: options?.firstName?.trim() || undefined,
      employeeLastName: options?.lastName?.trim() || undefined,
    });
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
    const response = await api.get('/api/hr/assignments', {
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
  getAssignment: async (assignmentId: string, opts?: { signal?: AbortSignal }): Promise<AssignmentDetail> => {
    const response = await api.get(`/api/hr/assignments/${assignmentId}`, { signal: opts?.signal });
    return response.data;
  },
  getReadinessSummary: async (
    assignmentId: string,
    opts?: { signal?: AbortSignal }
  ): Promise<Record<string, unknown>> => {
    const response = await api.get(`/api/hr/assignments/${encodeURIComponent(assignmentId)}/readiness/summary`, {
      signal: opts?.signal,
    });
    return response.data;
  },
  getReadinessDetail: async (
    assignmentId: string,
    opts?: { signal?: AbortSignal }
  ): Promise<Record<string, unknown>> => {
    const response = await api.get(`/api/hr/assignments/${encodeURIComponent(assignmentId)}/readiness/detail`, {
      signal: opts?.signal,
    });
    return response.data;
  },
  patchReadinessChecklistItem: async (
    assignmentId: string,
    itemId: string,
    payload: { status: string; notes?: string }
  ): Promise<{ success: boolean }> => {
    const response = await api.patch(
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
    const response = await api.patch(
      `/api/hr/assignments/${encodeURIComponent(assignmentId)}/readiness/milestones/${encodeURIComponent(milestoneId)}`,
      payload
    );
    return response.data;
  },
  getResolvedPolicy: async (assignmentId: string): Promise<{
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
  }> => {
    const response = await api.get(`/api/hr/assignments/${assignmentId}/resolved-policy`);
    return response.data;
  },
  recomputeResolvedPolicy: async (assignmentId: string): Promise<{
    resolved: unknown | null;
    policy_version?: Record<string, unknown>;
    message?: string;
  }> => {
    const response = await api.post(`/api/hr/assignments/${assignmentId}/resolved-policy/recompute`);
    return response.data;
  },
  /** Compare selected services vs resolved policy (with diagnostics) */
  getPolicyServiceComparison: async (assignmentId: string): Promise<PolicyServiceComparisonResponse> => {
    const response = await api.get(`/api/hr/assignments/${assignmentId}/policy-service-comparison`);
    return response.data;
  },
  getPolicy: async (caseId: string): Promise<PolicyResponse> => {
    const response = await api.get('/api/hr/policy', { params: { caseId } });
    return response.data;
  },
  requestPolicyException: async (
    caseId: string,
    payload: { category: string; reason?: string; amount?: number }
  ): Promise<any> => {
    const response = await api.post(`/api/hr/cases/${caseId}/policy/exceptions`, payload);
    return response.data;
  },
  getCompanyProfile: async (): Promise<{ company: any | null }> => {
    return cachedRequest('hr:company-profile', 60_000, async () => {
      const response = await api.get('/api/hr/company-profile');
      return response.data;
    });
  },
  /** Company-scoped employees for HR */
  listCompanyEmployees: async (): Promise<{
    employees: HrCompanyEmployee[];
    has_company?: boolean;
  }> => {
    const response = await api.get('/api/hr/employees');
    return response.data;
  },
  getEmployee: async (employeeId: string): Promise<{ employee: HrCompanyEmployee }> => {
    const response = await api.get(`/api/hr/employees/${employeeId}`);
    return response.data;
  },
  updateEmployee: async (
    employeeId: string,
    payload: { band?: string; assignment_type?: string; status?: string }
  ): Promise<{ employee: HrCompanyEmployee }> => {
    const response = await api.patch(`/api/hr/employees/${employeeId}`, payload);
    return response.data;
  },
  saveCompanyProfile: async (payload: CompanyProfilePayload): Promise<any> => {
    const response = await api.post('/api/hr/company-profile', payload);
    invalidateApiCache('hr:company-profile');
    invalidateApiCache('company:get');
    return response.data;
  },
  uploadCompanyLogo: async (file: File): Promise<{ ok: boolean; logo_url: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/api/hr/company-profile/logo', formData);
    invalidateApiCache('hr:company-profile');
    invalidateApiCache('company:get');
    return response.data;
  },
  removeCompanyLogo: async (): Promise<{ ok: boolean }> => {
    const response = await api.post('/api/hr/company-profile/remove-logo');
    invalidateApiCache('hr:company-profile');
    invalidateApiCache('company:get');
    return response.data;
  },
  listMessages: async (): Promise<{ messages: any[] }> => {
    const response = await api.get('/api/hr/messages');
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
  }): Promise<{ conversations: any[]; has_more?: boolean }> => {
    const { signal, ...query } = params ?? {};
    const response = await api.get('/api/hr/messages/conversations', {
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
  ): Promise<{ assignment_id: string; messages: any[] }> => {
    const response = await api.get(
      `/api/hr/messages/threads/${encodeURIComponent(assignmentId)}`,
      { signal: opts?.signal }
    );
    return response.data;
  },
  archiveMessageConversations: async (payload: {
    assignment_ids: string[];
    archived: boolean;
  }): Promise<{ ok: boolean; updated: number }> => {
    const response = await api.post('/api/hr/messages/conversations/archive', payload);
    return response.data;
  },
  deleteHrMessage: async (messageId: string): Promise<{ ok: boolean }> => {
    const response = await api.delete(
      `/api/hr/messages/${encodeURIComponent(messageId)}`
    );
    return response.data;
  },
  getCaseCompliance: async (caseId: string): Promise<ComplianceCaseReport> => {
    const response = await api.get(`/api/hr/cases/${caseId}/compliance`);
    return response.data;
  },
  runCaseCompliance: async (caseId: string): Promise<ComplianceCaseReport> => {
    const response = await api.post(`/api/hr/cases/${caseId}/compliance/run`);
    return response.data;
  },
  recordComplianceAction: async (
    caseId: string,
    payload: { actionType: string; checkId: string; notes?: string; payload?: any }
  ): Promise<any> => {
    const response = await api.post(`/api/hr/cases/${caseId}/compliance/actions`, payload);
    return response.data;
  },
  runCompliance: async (assignmentId: string): Promise<any> => {
    const response = await api.post(`/api/hr/assignments/${assignmentId}/run-compliance`);
    return response.data;
  },
  decide: async (
    assignmentId: string,
    decision: 'approved' | 'rejected',
    opts?: { notes?: string; requestedSections?: string[] }
  ): Promise<any> => {
    const response = await api.post(`/api/hr/assignments/${assignmentId}/decision`, {
      decision,
      notes: opts?.notes,
      requestedSections: opts?.requestedSections,
    });
    return response.data;
  },
  updateIdentifier: async (assignmentId: string, employeeIdentifier: string): Promise<any> => {
    const response = await api.post(`/api/hr/assignments/${assignmentId}/identifier`, { employeeIdentifier });
    return response.data;
  },
  deleteAssignment: async (assignmentId: string): Promise<any> => {
    const response = await api.delete(`/api/hr/assignments/${assignmentId}`);
    return response.data;
  },
  postFeedback: async (assignmentId: string, message: string): Promise<{ ok: boolean; id: string; created_at: string }> => {
    const response = await api.post(`/api/hr/assignments/${assignmentId}/feedback`, { message });
    return response.data;
  },
  getFeedback: async (assignmentId: string): Promise<Array<{ id: string; assignment_id: string; hr_user_id: string; employee_user_id: string | null; message: string; created_at: string }>> => {
    const response = await api.get(`/api/hr/assignments/${assignmentId}/feedback`);
    return response.data;
  },
  // Command Center
  getCommandCenterKPIs: async (): Promise<{
    activeCases: number;
    atRiskCount: number;
    attentionNeededCount: number;
    overdueTasksCount: number;
    avgVisaDurationDays?: number;
    budgetOverrunsCount: number;
    actionRequiredCount: number;
    departingSoonCount: number;
    completedCount: number;
  }> => {
    const response = await api.get('/api/hr/command-center/kpis');
    return response.data;
  },
  listCommandCenterCases: async (params?: { page?: number; limit?: number; risk_filter?: string }): Promise<Array<{ id: string; employeeIdentifier: string; destCountry?: string; status: string; riskStatus: string; tasksDonePercent: number; budgetLimit?: number; budgetEstimated?: number; nextDeadline?: string }>> => {
    const response = await api.get('/api/hr/command-center/cases', { params });
    return response.data;
  },
  getCommandCenterCaseDetail: async (assignmentId: string): Promise<{ id: string; employeeIdentifier: string; destCountry?: string; status: string; riskStatus: string; budgetLimit?: number; budgetEstimated?: number; expectedStartDate?: string; tasksTotal: number; tasksDone: number; tasksOverdue: number; phases: Array<{ phase: string; tasks: Array<{ title: string; status: string; due_date?: string }> }>; events: Array<{ event_type: string; description?: string; created_at: string }> }> => {
    const response = await api.get(`/api/hr/command-center/cases/${assignmentId}`);
    return response.data;
  },
};

// Company API (for header branding: HR and Employee)
export const companyAPI = {
  get: async (): Promise<{ company: { id?: string; name: string; logo_url?: string | null; [key: string]: unknown } | null }> => {
    return cachedRequest('company:get', 60_000, async () => {
      const response = await api.get('/api/company');
      return response.data;
    });
  },
};

// Admin API
export const adminAPI = {
  getContext: async (): Promise<AdminContextResponse> => {
    return cachedRequest('admin:context', 20_000, async () => {
      const response = await api.get('/api/admin/context');
      return response.data;
    });
  },
  startImpersonation: async (payload: { targetUserId: string; mode: 'hr' | 'employee'; reason?: string }) => {
    const response = await api.post('/api/admin/impersonate/start', payload);
    invalidateApiCache('admin:context');
    return response.data;
  },
  stopImpersonation: async (): Promise<{ ok: boolean }> => {
    const response = await api.post('/api/admin/impersonate/stop');
    invalidateApiCache('admin:context');
    return response.data;
  },
  listCompanies: async (q?: string): Promise<{ companies: AdminCompany[] }> => {
    const key = `admin:companies:${q ?? ''}`;
    return cachedRequest(key, 60_000, async () => {
      const response = await api.get('/api/admin/companies', { params: { q } });
      return response.data;
    });
  },
  getCompanyDetail: async (companyId: string): Promise<{
    company: AdminCompany | null;
    summary?: { hr_users_count: number; employee_count: number; assignments_count: number; policies_count: number };
    counts_summary?: AdminCompanyDetailCounts;
    hr_users: AdminHrUser[];
    employees: AdminEmployee[];
    assignments: AdminCompanyDetailAssignment[];
    policies: AdminCompanyDetailPolicy[];
    orphan_diagnostics?: AdminCompanyDetailOrphanDiagnostics;
  }> => {
    const response = await api.get(`/api/admin/companies/${companyId}`);
    return response.data;
  },
  createCompany: async (payload: {
    name: string;
    country?: string;
    size_band?: string;
    status?: string;
    plan_tier?: string;
    hr_seat_limit?: number;
    employee_seat_limit?: number;
    address?: string;
    phone?: string;
    hr_contact?: string;
    support_email?: string;
  }): Promise<{ company: AdminCompany }> => {
    const response = await api.post('/api/admin/companies', payload);
    invalidateApiCachePrefix('admin:companies:');
    return response.data;
  },
  updateCompany: async (
    companyId: string,
    payload: Partial<{
      name: string;
      country: string;
      size_band: string;
      status: string;
      plan_tier: string;
      hr_seat_limit: number;
      employee_seat_limit: number;
      address: string;
      phone: string;
      hr_contact: string;
      support_email: string;
    }>
  ): Promise<{ company: AdminCompany }> => {
    const response = await api.patch(`/api/admin/companies/${companyId}`, payload);
    invalidateApiCachePrefix('admin:companies:');
    return response.data;
  },
  deactivateCompany: async (companyId: string): Promise<{ company: AdminCompany; message?: string }> => {
    const response = await api.post(`/api/admin/companies/${companyId}/deactivate`);
    invalidateApiCachePrefix('admin:companies:');
    return response.data;
  },
  runReconciliationBackfillTestCompany: async (): Promise<{ ok: boolean; summary?: { test_company_id: string; profiles_linked: number; hr_users_linked: number; relocation_cases_linked: number }; error?: string }> => {
    const response = await api.post('/api/admin/reconciliation/backfill-test-company');
    return response.data;
  },
  rebuildTestCompanyGraph: async (): Promise<{
    ok: boolean;
    summary: {
      test_company_id: string;
      profiles_linked: number;
      hr_users_linked: number;
      employees_linked: number;
      relocation_cases_linked: number;
      case_assignments_repaired: number;
      policies_linked: number;
    };
    before: Record<string, number>;
    after: Record<string, number>;
  }> => {
    const response = await api.post('/api/admin/reconciliation/rebuild-test-company-graph');
    return response.data;
  },
  listProfiles: async (params?: { q?: string; company_id?: string; role?: string }): Promise<{ profiles: AdminProfile[]; summary?: { count: number; orphans_without_company?: number } }> => {
    const response = await api.get('/api/admin/users', { params: params || {} });
    return response.data;
  },
  listPeople: async (params?: { company_id?: string; role?: string; q?: string }): Promise<{ people: AdminProfile[]; summary?: { count: number; orphans_without_company?: number } }> => {
    const response = await api.get('/api/admin/people', { params: params || {} });
    return response.data;
  },
  createPerson: async (payload: { email: string; full_name?: string; role?: string; company_id?: string }): Promise<{ person: AdminProfile }> => {
    const response = await api.post('/api/admin/people', payload);
    return response.data;
  },
  updatePerson: async (personId: string, payload: Partial<{ full_name: string; role: string; company_id: string; status: string }>): Promise<{ person: AdminProfile }> => {
    const response = await api.patch(`/api/admin/people/${personId}`, payload);
    return response.data;
  },
  assignPersonCompany: async (personId: string, companyId: string): Promise<{ person: AdminProfile }> => {
    const response = await api.post(`/api/admin/people/${personId}/assign-company`, { company_id: companyId });
    return response.data;
  },
  setPersonRole: async (personId: string, role: string): Promise<{ person: AdminProfile }> => {
    const response = await api.post(`/api/admin/people/${personId}/set-role`, { role });
    return response.data;
  },
  deactivatePerson: async (personId: string): Promise<{ person: AdminProfile }> => {
    const response = await api.post(`/api/admin/people/${personId}/deactivate`);
    return response.data;
  },
  listEmployees: async (companyId?: string): Promise<{ employees: AdminEmployee[] }> => {
    const response = await api.get('/api/admin/employees', { params: { company_id: companyId } });
    return response.data;
  },
  listHrUsers: async (companyId?: string): Promise<{ hr_users: AdminHrUser[] }> => {
    const response = await api.get('/api/admin/hr-users', { params: { company_id: companyId } });
    return response.data;
  },
  listRelocations: async (params?: { company_id?: string; status?: string }): Promise<{ relocations: AdminRelocationCase[] }> => {
    const response = await api.get('/api/admin/relocations', { params });
    return response.data;
  },
  listAssignments: async (params?: {
    company_id?: string;
    employee_user_id?: string;
    employee_search?: string;
    status?: string;
    destination_country?: string;
  }): Promise<{ assignments: AdminAssignment[] }> => {
    const response = await api.get('/api/admin/assignments', { params });
    return response.data;
  },
  getAssignmentDetail: async (assignmentId: string): Promise<{ assignment: AdminAssignmentDetail }> => {
    const response = await api.get(`/api/admin/assignments/${assignmentId}`);
    return response.data;
  },
  reassignEmployeeCompany: async (assignmentId: string, payload: { reason: string; company_id: string }) => {
    const response = await api.patch(`/api/admin/assignments/${assignmentId}/reassign-employee-company`, payload);
    return response.data;
  },
  reassignHrOwner: async (assignmentId: string, payload: { reason: string; hr_user_id: string }) => {
    const response = await api.patch(`/api/admin/assignments/${assignmentId}/reassign-hr-owner`, payload);
    return response.data;
  },
  fixAssignmentCompanyLinkage: async (assignmentId: string, payload: { reason: string; company_id: string }) => {
    const response = await api.patch(`/api/admin/assignments/${assignmentId}/fix-company-linkage`, payload);
    return response.data;
  },
  updateAssignmentStatus: async (assignmentId: string, payload: { status: string }) => {
    const response = await api.patch(`/api/admin/assignments/${assignmentId}/status`, payload);
    return response.data;
  },
  createAssignment: async (payload: {
    company_id: string;
    hr_user_id: string;
    employee_user_id?: string;
    employee_identifier?: string;
    destination_country?: string;
  }): Promise<{ ok: boolean; assignment_id: string; case_id: string }> => {
    const response = await api.post('/api/admin/assignments', payload);
    return response.data;
  },
  listPolicyOverview: async (params?: { company_id?: string }): Promise<{ companies: AdminPolicyCompany[] }> => {
    const response = await api.get('/api/admin/policies/overview', { params });
    return response.data;
  },
  listAdminPolicies: async (companyId: string): Promise<AdminPoliciesByCompany> => {
    const response = await api.get('/api/admin/policies', { params: { company_id: companyId } });
    return response.data;
  },
  getAdminPolicyDetail: async (policyId: string): Promise<AdminPolicyDetail> => {
    const response = await api.get(`/api/admin/policies/${policyId}`);
    return response.data;
  },
  getAdminPolicyVersions: async (policyId: string): Promise<{ policy_id: string; versions: AdminPolicyVersion[] }> => {
    const response = await api.get(`/api/admin/policies/${policyId}/versions`);
    return response.data;
  },
  patchAdminPolicy: async (
    policyId: string,
    payload: { title?: string; version?: string; effective_date?: string; publish_version_id?: string; unpublish?: boolean }
  ): Promise<AdminPolicyDetail> => {
    const response = await api.patch(`/api/admin/policies/${policyId}`, payload);
    return response.data;
  },
  listAdminPolicyTemplates: async (): Promise<AdminPolicyTemplatesResponse> => {
    const response = await api.get('/api/admin/policies/templates');
    return response.data;
  },
  applyDefaultTemplateToCompany: async (
    companyId: string,
    opts?: { template_id?: string; overwrite_existing?: boolean }
  ): Promise<{ ok: boolean; policy_id?: string; version_id?: string; error?: string }> => {
    const response = await api.post('/api/admin/policies/apply-default-template', {
      company_id: companyId,
      template_id: opts?.template_id,
      overwrite_existing: opts?.overwrite_existing ?? false,
    });
    return response.data;
  },
  listSupportCases: async (params?: { status?: string; severity?: string; company_id?: string; priority?: string }): Promise<{ support_cases: AdminSupportCase[] }> => {
    const response = await api.get('/api/admin/support-cases', { params });
    return response.data;
  },
  patchSupportCase: async (
    caseId: string,
    payload: { priority?: string; status?: string; assignee_id?: string | null; category?: string }
  ): Promise<AdminSupportCase> => {
    const response = await api.patch(`/api/admin/support-cases/${caseId}`, payload);
    return response.data;
  },
  listMessageThreads: async (params?: {
    company_id?: string;
    user_id?: string;
    thread_type?: 'hr_employee' | 'collaboration';
    limit?: number;
    offset?: number;
  }) => {
    const response = await api.get('/api/admin/messages/threads', { params });
    return response.data;
  },
  getHrThreadDetail: async (assignmentId: string) => {
    const response = await api.get(`/api/admin/messages/threads/hr-employee/${assignmentId}`);
    return response.data;
  },
  listSupportNotes: async (caseId: string): Promise<{ notes: AdminSupportNote[] }> => {
    const response = await api.get(`/api/admin/support-cases/${caseId}/notes`);
    return response.data;
  },
  addSupportNote: async (caseId: string, payload: { note: string; reason: string }) => {
    const response = await api.post(`/api/admin/support-cases/${caseId}/notes`, payload);
    return response.data;
  },
  adminAction: async (action: string, payload: { reason: string; breakGlass?: boolean; payload?: any }) => {
    const response = await api.post(`/api/admin/actions/${action}`, payload);
    return response.data;
  },
  getReconciliationReport: async () => {
    const response = await api.get('/api/admin/reconciliation/report');
    return response.data;
  },
  reconciliationLinkPersonCompany: async (profileId: string, companyId: string) => {
    const response = await api.post('/api/admin/reconciliation/link-person-company', { profile_id: profileId, company_id: companyId });
    return response.data;
  },
  reconciliationLinkAssignmentCompany: async (assignmentId: string, companyId: string, reason: string) => {
    const response = await api.post('/api/admin/reconciliation/link-assignment-company', {
      assignment_id: assignmentId,
      company_id: companyId,
      reason,
    });
    return response.data;
  },
  reconciliationLinkAssignmentPerson: async (assignmentId: string, profileId: string) => {
    const response = await api.post('/api/admin/reconciliation/link-assignment-person', {
      assignment_id: assignmentId,
      profile_id: profileId,
    });
    return response.data;
  },
  reconciliationLinkPolicyCompany: async (policyId: string, companyId: string) => {
    const response = await api.post('/api/admin/reconciliation/link-policy-company', {
      policy_id: policyId,
      company_id: companyId,
    });
    return response.data;
  },
  listResearchCandidates: async (params?: { destination_country?: string; status?: string }) => {
    const response = await api.get('/api/admin/research/candidates', { params });
    return response.data;
  },
  researchHealth: async (params: { destination: string }) => {
    const response = await api.get('/api/admin/research/health', { params });
    return response.data;
  },
  approveResearchCandidate: async (candidateId: string, payload: { domain_area: string }) => {
    const response = await api.post(`/api/admin/research/candidates/${candidateId}/approve`, payload);
    return response.data;
  },
  ingestUrl: async (payload: { url: string; destination_country: string; domain_area: string }) => {
    const response = await api.post('/api/admin/ingest/url', payload);
    return response.data;
  },
  ingestBatch: async (payload: { urls: Array<string | { url: string; domain_area?: string }>; destination_country: string; domain_area?: string }) => {
    const response = await api.post('/api/admin/ingest/batch', payload);
    return response.data;
  },
  listIngestJobs: async (params?: { status?: string }) => {
    const response = await api.get('/api/admin/ingest/jobs', { params });
    return response.data;
  },
  listKnowledgeDocs: async (params: { destination_country: string }) => {
    const response = await api.get('/api/admin/knowledge/docs', { params });
    return response.data;
  },
  listRequirementEntities: async (params: { destination: string; status?: string }) => {
    const response = await api.get('/api/admin/requirements/entities', { params });
    return response.data;
  },
  listRequirementFacts: async (entityId: string, params?: { status?: string }) => {
    const response = await api.get(`/api/admin/requirements/entities/${entityId}/facts`, { params });
    return response.data;
  },
  listRequirementCriteria: async (params: { destination: string; status?: string }) => {
    const response = await api.get('/api/admin/requirements/criteria', { params });
    return response.data;
  },
  approveRequirementFacts: async (payload: { fact_ids: string[] }) => {
    const response = await api.post('/api/admin/requirements/facts/approve', payload);
    return response.data;
  },
  rejectRequirementFacts: async (payload: { fact_ids: string[] }) => {
    const response = await api.post('/api/admin/requirements/facts/reject', payload);
    return response.data;
  },
  /** Mobility graph: case context + audit logs (admin JWT). */
  inspectMobilityCase: async (
    caseId: string
  ): Promise<{
    context: Record<string, unknown>;
    audit_logs: Array<Record<string, unknown>>;
  }> => {
    const response = await api.get(`/api/admin/mobility/cases/${encodeURIComponent(caseId)}/inspect`);
    return response.data;
  },
};

// Supplier Registry API (admin)
export const suppliersAPI = {
  list: async (params?: {
    status?: string;
    service_category?: string;
    country_code?: string;
    city_name?: string;
    limit?: number;
    offset?: number;
  }) => {
    const response = await api.get('/api/suppliers', { params: params || {} });
    return response.data;
  },
  get: async (supplierId: string) => {
    const response = await api.get(`/api/suppliers/${supplierId}`);
    return response.data;
  },
  search: async (params: {
    service_category: string;
    destination_country?: string;
    destination_city?: string;
    limit?: number;
  }) => {
    const response = await api.get('/api/suppliers/search', { params });
    return response.data;
  },
  getCategories: async () => {
    const response = await api.get('/api/suppliers/categories');
    return response.data;
  },
  getCountries: async () => {
    const response = await api.get('/api/suppliers/countries');
    return response.data;
  },
  create: async (payload: Record<string, unknown>) => {
    const response = await api.post('/api/suppliers', payload);
    return response.data;
  },
  update: async (supplierId: string, payload: Record<string, unknown>) => {
    const response = await api.patch(`/api/suppliers/${supplierId}`, payload);
    return response.data;
  },
  setStatus: async (supplierId: string, status: 'active' | 'inactive' | 'draft') => {
    const response = await api.patch(`/api/suppliers/${supplierId}/status`, { status });
    return response.data;
  },
  addCapability: async (supplierId: string, payload: Record<string, unknown>) => {
    const response = await api.post(`/api/suppliers/${supplierId}/capabilities`, payload);
    return response.data;
  },
  updateCapability: async (
    supplierId: string,
    capabilityId: string,
    payload: Record<string, unknown>
  ) => {
    const response = await api.patch(
      `/api/suppliers/${supplierId}/capabilities/${capabilityId}`,
      payload
    );
    return response.data;
  },
  removeCapability: async (supplierId: string, capabilityId: string) => {
    const response = await api.delete(
      `/api/suppliers/${supplierId}/capabilities/${capabilityId}`
    );
    return response.data;
  },
  updateScoring: async (supplierId: string, payload: Record<string, unknown>) => {
    const response = await api.patch(`/api/suppliers/${supplierId}/scoring`, payload);
    return response.data;
  },
  getRankingDebug: async (
    supplierId: string,
    params?: { service_category?: string; destination_country?: string; destination_city?: string }
  ) => {
    const response = await api.get(`/api/suppliers/${supplierId}/ranking-debug`, { params });
    return response.data;
  },
};

// Admin recommendations debug (admin only)
export const adminRecommendationsAPI = {
  getDebug: async (assignmentId: string, serviceCategory: string) => {
    const response = await api.get('/api/admin/recommendations/debug', {
      params: { assignment_id: assignmentId, service_category: serviceCategory },
    });
    return response.data;
  },
};

// Admin Resources CMS API
export const adminResourcesAPI = {
  getCounts: async () => api.get('/api/admin/resources/counts').then((r) => r.data),
  listResources: async (params?: {
    country_code?: string;
    city?: string;
    category_id?: string;
    status?: string;
    audience?: string;
    featured?: boolean;
    family_friendly?: boolean;
    search?: string;
    limit?: number;
    offset?: number;
  }) => api.get('/api/admin/resources', { params }).then((r) => r.data),
  getResource: async (id: string) => api.get(`/api/admin/resources/${id}`).then((r) => r.data),
  createResource: async (payload: Record<string, unknown>) =>
    api.post('/api/admin/resources', payload).then((r) => r.data),
  updateResource: async (id: string, payload: Record<string, unknown>) =>
    api.put(`/api/admin/resources/${id}`, payload).then((r) => r.data),
  submitForReview: async (id: string) =>
    api.post(`/api/admin/resources/${id}/submit-for-review`).then((r) => r.data),
  approveResource: async (id: string, notes?: string) =>
    api.post(`/api/admin/resources/${id}/approve`, { notes }).then((r) => r.data),
  publishResource: async (id: string) =>
    api.post(`/api/admin/resources/${id}/publish`).then((r) => r.data),
  unpublishResource: async (id: string) =>
    api.post(`/api/admin/resources/${id}/unpublish`).then((r) => r.data),
  archiveResource: async (id: string) =>
    api.post(`/api/admin/resources/${id}/archive`).then((r) => r.data),
  restoreResource: async (id: string) =>
    api.post(`/api/admin/resources/${id}/restore`).then((r) => r.data),
  getResourceAudit: async (id: string, limit?: number) =>
    api.get(`/api/admin/resources/${id}/audit`, { params: { limit } }).then((r) => r.data),
  getGlobalAuditLog: async (params?: { entity_type?: string; limit?: number; offset?: number }) =>
    api.get('/api/admin/resources/audit-log', { params }).then((r) => r.data),
  listEvents: async (params?: {
    country_code?: string;
    city?: string;
    event_type?: string;
    status?: string;
    family_friendly?: boolean;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }) => api.get('/api/admin/resources/events', { params }).then((r) => r.data),
  getEvent: async (id: string) => api.get(`/api/admin/resources/events/${id}`).then((r) => r.data),
  createEvent: async (payload: Record<string, unknown>) =>
    api.post('/api/admin/resources/events', payload).then((r) => r.data),
  updateEvent: async (id: string, payload: Record<string, unknown>) =>
    api.put(`/api/admin/resources/events/${id}`, payload).then((r) => r.data),
  publishEvent: async (id: string) =>
    api.post(`/api/admin/resources/events/${id}/publish`).then((r) => r.data),
  archiveEvent: async (id: string) =>
    api.post(`/api/admin/resources/events/${id}/archive`).then((r) => r.data),
  submitEventForReview: async (id: string) =>
    api.post(`/api/admin/resources/events/${id}/submit-for-review`).then((r) => r.data),
  approveEvent: async (id: string, notes?: string) =>
    api.post(`/api/admin/resources/events/${id}/approve`, { notes }).then((r) => r.data),
  unpublishEvent: async (id: string) =>
    api.post(`/api/admin/resources/events/${id}/unpublish`).then((r) => r.data),
  restoreEvent: async (id: string) =>
    api.post(`/api/admin/resources/events/${id}/restore`).then((r) => r.data),
  getEventAudit: async (id: string, limit?: number) =>
    api.get(`/api/admin/resources/events/${id}/audit`, { params: { limit } }).then((r) => r.data),
  listCategories: async () => api.get('/api/admin/resources/taxonomy/categories').then((r) => r.data),
  createCategory: async (payload: Record<string, unknown>) =>
    api.post('/api/admin/resources/taxonomy/categories', payload).then((r) => r.data),
  updateCategory: async (id: string, payload: Record<string, unknown>) =>
    api.put(`/api/admin/resources/taxonomy/categories/${id}`, payload).then((r) => r.data),
  deactivateCategory: async (id: string) =>
    api.delete(`/api/admin/resources/taxonomy/categories/${id}`).then((r) => r.data),
  listTags: async (tag_group?: string) =>
    api.get('/api/admin/resources/taxonomy/tags', { params: { tag_group } }).then((r) => r.data),
  createTag: async (payload: Record<string, unknown>) =>
    api.post('/api/admin/resources/taxonomy/tags', payload).then((r) => r.data),
  updateTag: async (id: string, payload: Record<string, unknown>) =>
    api.put(`/api/admin/resources/taxonomy/tags/${id}`, payload).then((r) => r.data),
  listSources: async () => api.get('/api/admin/resources/taxonomy/sources').then((r) => r.data),
  createSource: async (payload: Record<string, unknown>) =>
    api.post('/api/admin/resources/taxonomy/sources', payload).then((r) => r.data),
  updateSource: async (id: string, payload: Record<string, unknown>) =>
    api.put(`/api/admin/resources/taxonomy/sources/${id}`, payload).then((r) => r.data),
};

// Admin Staging Review API (admin-only)
export const adminStagingAPI = {
  getDashboard: () => api.get('/api/admin/staging/dashboard').then((r) => r.data),
  listResourceCandidates: (params?: {
    status?: string;
    country_code?: string;
    city_name?: string;
    category_key?: string;
    resource_type?: string;
    trust_tier?: string;
    search?: string;
    limit?: number;
    offset?: number;
  }) => api.get('/api/admin/staging/resources', { params }).then((r) => r.data),
  getResourceCandidate: (id: string) =>
    api.get(`/api/admin/staging/resources/${id}`).then((r) => r.data),
  getResourceCandidateMatches: (id: string) =>
    api.get(`/api/admin/staging/resources/${id}/matches`).then((r) => r.data),
  approveResourceAsNew: (id: string, reason?: string) =>
    api.post(`/api/admin/staging/resources/${id}/approve-new`, { reason }).then((r) => r.data),
  mergeResource: (
    id: string,
    payload: {
      target_resource_id: string;
      merge_mode?: string;
      fields_to_merge?: string[];
      reason?: string;
    }
  ) => api.post(`/api/admin/staging/resources/${id}/merge`, payload).then((r) => r.data),
  rejectResource: (id: string, reason?: string) =>
    api.post(`/api/admin/staging/resources/${id}/reject`, { reason }).then((r) => r.data),
  markResourceDuplicate: (
    id: string,
    payload: {
      duplicate_of_candidate_id?: string;
      duplicate_of_live_resource_id?: string;
      reason?: string;
    }
  ) => api.post(`/api/admin/staging/resources/${id}/mark-duplicate`, payload).then((r) => r.data),
  ignoreResource: (id: string, reason?: string) =>
    api.post(`/api/admin/staging/resources/${id}/ignore`, { reason }).then((r) => r.data),
  restoreResourceToReview: (id: string) =>
    api.post(`/api/admin/staging/resources/${id}/restore-review`).then((r) => r.data),
  listEventCandidates: (params?: {
    status?: string;
    country_code?: string;
    city_name?: string;
    event_type?: string;
    trust_tier?: string;
    search?: string;
    limit?: number;
    offset?: number;
  }) => api.get('/api/admin/staging/events', { params }).then((r) => r.data),
  getEventCandidate: (id: string) =>
    api.get(`/api/admin/staging/events/${id}`).then((r) => r.data),
  getEventCandidateMatches: (id: string) =>
    api.get(`/api/admin/staging/events/${id}/matches`).then((r) => r.data),
  approveEventAsNew: (id: string, reason?: string) =>
    api.post(`/api/admin/staging/events/${id}/approve-new`, { reason }).then((r) => r.data),
  mergeEvent: (
    id: string,
    payload: {
      target_event_id: string;
      merge_mode?: string;
      fields_to_merge?: string[];
      reason?: string;
    }
  ) => api.post(`/api/admin/staging/events/${id}/merge`, payload).then((r) => r.data),
  rejectEvent: (id: string, reason?: string) =>
    api.post(`/api/admin/staging/events/${id}/reject`, { reason }).then((r) => r.data),
  markEventDuplicate: (
    id: string,
    payload: {
      duplicate_of_candidate_id?: string;
      duplicate_of_live_event_id?: string;
      reason?: string;
    }
  ) => api.post(`/api/admin/staging/events/${id}/mark-duplicate`, payload).then((r) => r.data),
  ignoreEvent: (id: string, reason?: string) =>
    api.post(`/api/admin/staging/events/${id}/ignore`, { reason }).then((r) => r.data),
  restoreEventToReview: (id: string) =>
    api.post(`/api/admin/staging/events/${id}/restore-review`).then((r) => r.data),
};

// Admin Freshness & Crawl API (admin-only)
export const adminFreshnessAPI = {
  getOverview: () => api.get('/api/admin/freshness/overview').then((r) => r.data),
  getCountries: () => api.get('/api/admin/freshness/countries').then((r) => r.data),
  getCities: (params?: { country_code?: string }) =>
    api.get('/api/admin/freshness/cities', { params }).then((r) => r.data),
  getSources: () => api.get('/api/admin/freshness/sources').then((r) => r.data),
  refreshFreshness: () => api.post('/api/admin/freshness/refresh').then((r) => r.data),
  listSchedules: (params?: { is_active?: boolean; limit?: number }) =>
    api.get('/api/admin/crawl/schedules', { params }).then((r) => r.data),
  getDueSchedules: () => api.get('/api/admin/crawl/schedules/due').then((r) => r.data),
  getSchedule: (id: string) => api.get(`/api/admin/crawl/schedules/${id}`).then((r) => r.data),
  createSchedule: (payload: Record<string, unknown>) =>
    api.post('/api/admin/crawl/schedules', payload).then((r) => r.data),
  updateSchedule: (id: string, payload: Record<string, unknown>) =>
    api.put(`/api/admin/crawl/schedules/${id}`, payload).then((r) => r.data),
  pauseSchedule: (id: string) => api.post(`/api/admin/crawl/schedules/${id}/pause`).then((r) => r.data),
  resumeSchedule: (id: string) => api.post(`/api/admin/crawl/schedules/${id}/resume`).then((r) => r.data),
  triggerSchedule: (id: string) => api.post(`/api/admin/crawl/schedules/${id}/trigger`).then((r) => r.data),
  processDueSchedules: () => api.post('/api/admin/crawl/process-due').then((r) => r.data),
  triggerCrawl: (payload: { source_name?: string; country_code?: string; city_name?: string; content_domain?: string }) =>
    api.post('/api/admin/crawl/trigger', payload).then((r) => r.data),
  listJobRuns: (params?: { schedule_id?: string; status?: string; limit?: number; offset?: number }) =>
    api.get('/api/admin/crawl/job-runs', { params }).then((r) => r.data),
  getJobRun: (id: string) => api.get(`/api/admin/crawl/job-runs/${id}`).then((r) => r.data),
  listDocumentChanges: (params?: {
    job_run_id?: string;
    source_name?: string;
    change_type?: string;
    since?: string;
    limit?: number;
    offset?: number;
  }) => api.get('/api/admin/changes/documents', { params }).then((r) => r.data),
  getDocumentChange: (id: string) => api.get(`/api/admin/changes/documents/${id}`).then((r) => r.data),
  getStaleResources: (params?: { country_code?: string; city_name?: string; limit?: number }) =>
    api.get('/api/admin/changes/live-stale-resources', { params }).then((r) => r.data),
  getStaleEvents: (params?: { country_code?: string; city_name?: string; limit?: number }) =>
    api.get('/api/admin/changes/live-stale-events', { params }).then((r) => r.data),
};

// Admin Review Queue API (admin-only)
export const adminReviewQueueAPI = {
  list: (params?: {
    status?: string;
    priority_band?: string;
    assignee_id?: string;
    country_code?: string;
    city_name?: string;
    queue_item_type?: string;
    overdue_only?: boolean;
    unassigned_only?: boolean;
    search?: string;
    limit?: number;
    offset?: number;
    sort?: 'priority' | 'created' | 'due' | 'age';
  }) => api.get('/api/admin/review-queue', { params }).then((r) => r.data),
  getStats: () => api.get('/api/admin/review-queue/stats').then((r) => r.data),
  getAssignees: (limit?: number) =>
    api.get('/api/admin/review-queue/assignees', { params: { limit } }).then((r) => r.data),
  getItem: (id: string) => api.get(`/api/admin/review-queue/${id}`).then((r) => r.data),
  getActivity: (id: string, limit?: number) =>
    api.get(`/api/admin/review-queue/${id}/activity`, { params: { limit } }).then((r) => r.data),
  assign: (id: string, assigneeUserId: string) =>
    api.post(`/api/admin/review-queue/${id}/assign`, { assignee_user_id: assigneeUserId }).then((r) => r.data),
  claim: (id: string) => api.post(`/api/admin/review-queue/${id}/claim`).then((r) => r.data),
  unassign: (id: string) => api.post(`/api/admin/review-queue/${id}/unassign`).then((r) => r.data),
  setStatus: (id: string, status: string, note?: string) =>
    api.post(`/api/admin/review-queue/${id}/status`, { status, note }).then((r) => r.data),
  defer: (id: string, dueAt?: string, note?: string) =>
    api.post(`/api/admin/review-queue/${id}/defer`, { due_at: dueAt, note }).then((r) => r.data),
  resolve: (id: string, resolutionSummary?: string) =>
    api.post(`/api/admin/review-queue/${id}/resolve`, { resolution_summary: resolutionSummary }).then((r) => r.data),
  reopen: (id: string, note?: string) =>
    api.post(`/api/admin/review-queue/${id}/reopen`, { note }).then((r) => r.data),
  updateNotes: (id: string, notes: string) =>
    api.patch(`/api/admin/review-queue/${id}/notes`, { notes }).then((r) => r.data),
  bulkAssign: (itemIds: string[], assigneeUserId: string) =>
    api.post('/api/admin/review-queue/bulk-assign', { item_ids: itemIds, assignee_user_id: assigneeUserId }).then((r) => r.data),
  bulkStatus: (itemIds: string[], status: string, note?: string) =>
    api.post('/api/admin/review-queue/bulk-status', { item_ids: itemIds, status, note }).then((r) => r.data),
  backfill: () => api.post('/api/admin/review-queue/backfill').then((r) => r.data),
};

// Admin Ops Notifications API (admin-only)
export const adminNotificationsAPI = {
  list: (params?: {
    status?: string;
    severity?: string;
    notification_type?: string;
    country_code?: string;
    escalation_only?: boolean;
    open_only?: boolean;
    limit?: number;
    offset?: number;
  }) => api.get('/api/admin/notifications', { params }).then((r) => r.data),
  getStats: () => api.get('/api/admin/notifications/stats').then((r) => r.data),
  getFeed: (params?: { limit?: number; critical_first?: boolean }) =>
    api.get('/api/admin/notifications/feed', { params }).then((r) => r.data),
  getOne: (id: string) => api.get(`/api/admin/notifications/${id}`).then((r) => r.data),
  getEvents: (id: string, limit?: number) =>
    api.get(`/api/admin/notifications/${id}/events`, { params: { limit } }).then((r) => r.data),
  acknowledge: (id: string) => api.post(`/api/admin/notifications/${id}/acknowledge`).then((r) => r.data),
  resolve: (id: string, reason?: string) =>
    api.post(`/api/admin/notifications/${id}/resolve`, null, { params: { reason } }).then((r) => r.data),
  suppress: (id: string, until?: string) =>
    api.post(`/api/admin/notifications/${id}/suppress`, null, { params: { until } }).then((r) => r.data),
  reopen: (id: string, reason?: string) =>
    api.post(`/api/admin/notifications/${id}/reopen`, null, { params: { reason } }).then((r) => r.data),
  recompute: () => api.post('/api/admin/notifications/recompute').then((r) => r.data),
  sync: () => api.post('/api/admin/notifications/sync').then((r) => r.data),
};

// Admin Ops Analytics API (admin-only)
export const adminOpsAnalyticsAPI = {
  getSlaOverview: (params?: { country_code?: string; days?: number }) =>
    api.get('/api/admin/ops/sla/overview', { params }).then((r) => r.data),
  getQueueBacklog: (params?: { country_code?: string }) =>
    api.get('/api/admin/ops/queue/backlog', { params }).then((r) => r.data),
  getQueueBreaches: (params?: { country_code?: string; limit?: number }) =>
    api.get('/api/admin/ops/queue/breaches', { params }).then((r) => r.data),
  getReviewerWorkload: () => api.get('/api/admin/ops/reviewers/workload').then((r) => r.data),
  getDestinations: () => api.get('/api/admin/ops/destinations').then((r) => r.data),
  getNotificationMetrics: (params?: { days?: number }) =>
    api.get('/api/admin/ops/notifications', { params }).then((r) => r.data),
  getBottlenecks: () => api.get('/api/admin/ops/bottlenecks').then((r) => r.data),
};

// Admin Collaboration API (admin-only, internal threads)
export const adminCollaborationAPI = {
  getThread: (targetType: string, targetId: string) =>
    api.get('/api/admin/collaboration/threads/by-target', { params: { target_type: targetType, target_id: targetId } }).then((r) => r.data),
  getOrCreateThread: (targetType: string, targetId: string, title?: string) =>
    api.post('/api/admin/collaboration/threads/by-target', null, {
      params: { target_type: targetType, target_id: targetId, title: title || undefined },
    }).then((r) => r.data),
  getSummary: (targetType: string, targetId: string) =>
    api.get('/api/admin/collaboration/threads/summary', { params: { target_type: targetType, target_id: targetId } }).then((r) => r.data),
  getSummariesBatch: (targets: { target_type: string; target_id: string }[]) =>
    api.post('/api/admin/collaboration/threads/summaries', { targets }).then((r) => r.data),
  getThreadById: (threadId: string) =>
    api.get(`/api/admin/collaboration/threads/${threadId}`).then((r) => r.data),
  getComments: (threadId: string) =>
    api.get(`/api/admin/collaboration/threads/${threadId}/comments`).then((r) => r.data),
  createComment: (threadId: string, body: string, parentCommentId?: string) =>
    api.post(`/api/admin/collaboration/threads/${threadId}/comments`, { body, parent_comment_id: parentCommentId }).then((r) => r.data),
  editComment: (commentId: string, body: string) =>
    api.patch(`/api/admin/collaboration/comments/${commentId}`, { body }).then((r) => r.data),
  deleteComment: (commentId: string) =>
    api.delete(`/api/admin/collaboration/comments/${commentId}`).then((r) => r.data),
  resolveThread: (threadId: string, note?: string) =>
    api.post(`/api/admin/collaboration/threads/${threadId}/resolve`, null, { params: { note } }).then((r) => r.data),
  reopenThread: (threadId: string) =>
    api.post(`/api/admin/collaboration/threads/${threadId}/reopen`).then((r) => r.data),
  closeThread: (threadId: string) =>
    api.post(`/api/admin/collaboration/threads/${threadId}/close`).then((r) => r.data),
  markRead: (threadId: string, lastCommentId?: string) =>
    api.post(`/api/admin/collaboration/threads/${threadId}/read`, null, { params: { last_comment_id: lastCommentId } }).then((r) => r.data),
  getUnreadCount: () =>
    api.get('/api/admin/collaboration/notifications/unread-count').then((r) => r.data),
};

export const requirementsAPI = {
  getSufficiency: async (caseId: string): Promise<any> => {
    const response = await api.get('/api/requirements/sufficiency', { params: { case_id: caseId } });
    return response.data;
  },
};

export const employeeAPI = {
  getCurrentAssignment: async (): Promise<{ assignment: any }> => {
    return cachedRequest('employee:current-assignment', 30_000, async () => {
      const response = await api.get('/api/employee/assignments/current');
      return response.data;
    });
  },
  listMessages: async (): Promise<{ messages: any[] }> => {
    const response = await api.get('/api/employee/messages');
    return response.data;
  },
  claimAssignment: async (assignmentId: string, email: string): Promise<{ success: boolean; assignmentId?: string }> => {
    const response = await api.post(`/api/employee/assignments/${assignmentId}/claim`, { email });
    return response.data;
  },
  getNextQuestion: async (assignmentId: string): Promise<EmployeeJourneyResponse> => {
    const response = await api.get('/api/employee/journey/next-question', { params: { assignmentId } });
    return response.data;
  },
  getFeedback: async (assignmentId: string): Promise<Array<{ id: string; assignment_id: string; message: string; created_at: string }>> => {
    const response = await api.get('/api/employee/assignment-feedback', { params: { assignment_id: assignmentId } });
    return response.data;
  },
  submitAnswer: async (assignmentId: string, questionId: string, answer: any): Promise<EmployeeJourneyResponse> => {
    const response = await api.post('/api/employee/journey/answer', { assignmentId, questionId, answer });
    return response.data;
  },
  submitAssignment: async (assignmentId: string): Promise<any> => {
    const response = await api.post(`/api/employee/assignments/${assignmentId}/submit`);
    return response.data;
  },
  updateProfilePhoto: async (assignmentId: string, photoUrl: string): Promise<any> => {
    const response = await api.post(`/api/employee/assignments/${assignmentId}/photo`, {
      assignmentId,
      photoUrl,
    });
    return response.data;
  },
  getRecommendations: async (): Promise<{ housing: any[]; schools: any[]; movers: any[] }> => {
    const response = await api.get('/api/employee/recommendations');
    return response.data;
  },
  getPolicyCaps: async (): Promise<{
    housing_monthly_usd: number;
    movers_usd: number;
    schools_usd: number;
    immigration_usd: number;
  }> => {
    const response = await api.get('/api/employee/policy/caps');
    return response.data;
  },
  getAssignmentServices: async (assignmentId: string): Promise<{
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
  }> => {
    const response = await api.get(`/api/employee/assignments/${assignmentId}/services`);
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
  ): Promise<{ ok: boolean; services: any[] }> => {
    const response = await api.post(`/api/employee/assignments/${assignmentId}/services`, { services });
    return response.data;
  },
  getPolicyBudget: async (assignmentId: string): Promise<{
    currency: string;
    caps: Record<string, number>;
    total_cap?: number | null;
  }> => {
    const response = await api.get(`/api/employee/assignments/${assignmentId}/policy-budget`);
    return response.data;
  },
  getApplicablePolicy: async (assignmentId?: string): Promise<{
    policy: Record<string, unknown> | null;
    allowedBenefits: Array<Record<string, unknown>>;
    wizardCriteria: Record<string, unknown>;
    employeeBand?: string;
    assignmentType?: string;
  }> => {
    const params = assignmentId ? { assignmentId } : {};
    const response = await api.get('/api/employee/policy/applicable', { params });
    return response.data;
  },
  /** Resolved policy from published company policy (preferred when assignmentId available) */
  getResolvedPolicy: async (assignmentId: string): Promise<{
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
  }> => {
    const response = await api.get(`/api/employee/assignments/${assignmentId}/policy`);
    return response.data;
  },
  /**
   * Single round-trip for Assignment Package & Limits (employee HR Policy page).
   * Avoids chaining current-assignment + policy calls on the critical path.
   */
  getMyAssignmentPackagePolicy: async (): Promise<{
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
  }> => {
    const response = await api.get('/api/employee/me/assignment-package-policy');
    return response.data;
  },
  /** Policy envelope (envelope cards ready) for comparison/budget logic */
  getPolicyEnvelope: async (assignmentId: string): Promise<{
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
  }> => {
    const response = await api.get(`/api/employee/assignments/${assignmentId}/policy-envelope`);
    return response.data;
  },
  /** Compare selected services vs resolved policy (read-only, explanatory) */
  getPolicyServiceComparison: async (assignmentId: string): Promise<PolicyServiceComparisonResponse> => {
    const response = await api.get(`/api/employee/assignments/${assignmentId}/policy-service-comparison`);
    return response.data;
  },
};

export const servicesAPI = {
  /** Combined load: assignment, case context, services, answers, questions in one request. Use instead of 4 separate calls. */
  getServicesContext: async (
    assignmentId: string,
    fallbackServices?: string[]
  ): Promise<{
    assignment_id: string;
    case_id: string;
    case_context: { destCity?: string; destCountry?: string; originCity?: string; originCountry?: string };
    services: Array<{ service_key: string; selected: boolean | number; [k: string]: any }>;
    answers: Array<{ service_key: string; answers: Record<string, any> }>;
    questions: any[];
    selected_services: string[];
  }> => {
    const params: Record<string, string> = { assignment_id: assignmentId };
    if (fallbackServices?.length) {
      params.fallback_services = fallbackServices.join(',');
    }
    const response = await api.get('/api/services/context', { params });
    return response.data;
  },
  getServiceAnswers: async (params: { caseId?: string; assignmentId?: string }): Promise<{ case_id: string; answers: any[] }> => {
    const p = params.caseId ? { case_id: params.caseId } : { assignment_id: params.assignmentId };
    const response = await api.get('/api/services/answers', { params: p });
    return response.data;
  },
  getServiceQuestions: async (
    assignmentId: string,
    fallbackServices?: string[]
  ): Promise<{ questions: any[]; selected_services: string[] }> => {
    const params: Record<string, string> = { assignment_id: assignmentId };
    if (fallbackServices?.length) {
      params.fallback_services = fallbackServices.join(',');
    }
    const response = await api.get('/api/services/questions', { params });
    return response.data;
  },
  saveServiceAnswers: async (
    caseId: string,
    items: Array<{ service_key: string; answers: Record<string, any> }>,
    options?: { signal?: AbortSignal }
  ): Promise<{ ok: boolean }> => {
    const config = options?.signal ? { signal: options.signal } : {};
    const response = await api.post('/api/services/answers', { case_id: caseId, items }, config);
    return response.data;
  },
  createRfq: async (
    caseId: string,
    items: Array<{ service_key: string; requirements: Record<string, any> }>,
    supplierIds: string[]
  ): Promise<{ ok: boolean; rfq: { id: string; rfq_ref: string } }> => {
    const response = await api.post('/api/rfqs', { case_id: caseId, items, supplier_ids: supplierIds });
    return response.data;
  },
};

export const rfqAPI = {
  listByAssignment: async (assignmentId: string): Promise<{ rfqs: RfqSummary[] }> => {
    const response = await api.get(`/api/employee/assignments/${assignmentId}/rfqs`);
    return response.data;
  },
  get: async (rfqId: string): Promise<RfqDetail> => {
    const response = await api.get(`/api/rfqs/${rfqId}`);
    return response.data;
  },
  listQuotes: async (
    rfqId: string,
    options?: { comparison?: boolean }
  ): Promise<{ rfq_id: string; quotes: QuoteDetail[] }> => {
    const params = options?.comparison ? { comparison: '1' } : {};
    const response = await api.get(`/api/rfqs/${rfqId}/quotes`, { params });
    return response.data;
  },
  acceptQuote: async (rfqId: string, quoteId: string): Promise<{ ok: boolean; quote: QuoteDetail }> => {
    const response = await api.patch(`/api/rfqs/${rfqId}/quotes/${quoteId}/accept`);
    return response.data;
  },
};

export const vendorAPI = {
  listRfqs: async (): Promise<{ rfqs: RfqSummary[] }> => {
    const response = await api.get('/api/vendor/rfqs');
    return response.data;
  },
  getRfq: async (rfqId: string): Promise<RfqDetail> => {
    const response = await api.get(`/api/vendor/rfqs/${rfqId}`);
    return response.data;
  },
  submitQuote: async (
    rfqId: string,
    payload: QuoteCreatePayload
  ): Promise<{ ok: boolean; quote: QuoteDetail }> => {
    const response = await api.post(`/api/vendor/rfqs/${rfqId}/quotes`, payload);
    return response.data;
  },
};

export interface RfqSummary {
  id: string;
  rfq_ref: string;
  case_id: string;
  status: string;
  created_at: string;
  items?: Array<{ service_key: string; requirements: Record<string, unknown> }>;
  recipients?: Array<{ vendor_id: string; status: string }>;
}

export interface RfqDetail extends RfqSummary {
  items: Array<{ service_key: string; requirements: Record<string, unknown> }>;
  recipients: Array<{ vendor_id: string; status: string }>;
}

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

export interface QuoteCreatePayload {
  total_amount: number;
  currency: string;
  valid_until?: string;
  quote_lines: Array<{ label: string; amount: number }>;
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

export const timelineAPI = {
  getByAssignment: async (
    assignmentId: string,
    options?: { ensureDefaults?: boolean; includeLinks?: boolean }
  ): Promise<TimelineResponse> => {
    const params: Record<string, string> = {};
    if (options?.ensureDefaults) params.ensure_defaults = '1';
    if (options?.includeLinks === false) params.include_links = 'false';
    const response = await api.get(`/api/assignments/${assignmentId}/timeline`, { params });
    return response.data;
  },
  getByCase: async (
    caseId: string,
    options?: { ensureDefaults?: boolean; includeLinks?: boolean }
  ): Promise<TimelineResponse> => {
    const params: Record<string, string> = {};
    if (options?.ensureDefaults) params.ensure_defaults = '1';
    if (options?.includeLinks === false) params.include_links = 'false';
    const response = await api.get(`/api/cases/${caseId}/timeline`, { params });
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
    const response = await api.patch(`/api/cases/${caseId}/timeline/milestones/${milestoneId}`, patch);
    return response.data;
  },
};

export type TaskOwner = 'hr' | 'employee' | 'provider' | 'joint';

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

export const hrPreferredSuppliersAPI = {
  list: async (serviceCategory?: string): Promise<{ preferred: Array<Record<string, unknown>> }> => {
    const params = serviceCategory ? { service_category: serviceCategory } : {};
    const response = await api.get('/api/hr/preferred-suppliers', { params });
    return response.data;
  },
  add: async (payload: {
    supplier_id: string;
    service_category?: string;
    priority_rank?: number;
    notes?: string;
  }) => {
    const response = await api.post('/api/hr/preferred-suppliers', payload);
    return response.data;
  },
  remove: async (supplierId: string, serviceCategory?: string) => {
    const params = serviceCategory ? { service_category: serviceCategory } : {};
    const response = await api.delete(`/api/hr/preferred-suppliers/${supplierId}`, { params });
    return response.data;
  },
};

export const hrPolicyAPI = {
  list: async (params?: { status?: string; companyEntity?: string }): Promise<{ policies: any[] }> => {
    const response = await api.get('/api/hr/policies', { params: params || {} });
    return response.data;
  },
  get: async (policyId: string): Promise<any> => {
    const response = await api.get(`/api/hr/policies/${policyId}`);
    return response.data;
  },
  create: async (policy: Record<string, unknown>): Promise<{ policyId: string; policy: any }> => {
    const response = await api.post('/api/hr/policies', policy);
    return response.data;
  },
  update: async (policyId: string, policy: Record<string, unknown>): Promise<any> => {
    const response = await api.put(`/api/hr/policies/${policyId}`, policy);
    return response.data;
  },
  upload: async (file: File): Promise<{ policyId: string; policy: any }> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/api/hr/policies/upload', formData);
    return response.data;
  },
  delete: async (policyId: string): Promise<void> => {
    await api.delete(`/api/hr/policies/${policyId}`);
  },
};

export const companyPolicyAPI = {
  list: async (params?: { company_id?: string }): Promise<{ policies: any[] }> => {
    const response = await api.get('/api/company-policies', { params });
    return response.data;
  },
  getLatest: async (): Promise<{ policy: any; benefits: any[]; company_name?: string }> => {
    const response = await api.get('/api/company-policies/latest');
    return response.data;
  },
  getById: async (policyId: string): Promise<{ policy: any; benefits: any[] }> => {
    const response = await api.get(`/api/company-policies/${policyId}`);
    return response.data;
  },
  getDownloadUrl: async (policyId: string): Promise<{ ok?: boolean; url?: string }> => {
    const response = await api.get(`/api/company-policies/${policyId}/download-url`);
    return response.data;
  },
  upload: async (file: File, meta: { title: string; version?: string; effective_date?: string }): Promise<{ policy: any }> => {
    const form = new FormData();
    form.append('file', file);
    form.append('title', meta.title);
    if (meta.version) form.append('version', meta.version);
    if (meta.effective_date) form.append('effective_date', meta.effective_date);
    const response = await api.post('/api/company-policies/upload', form);
    return response.data;
  },
  extract: async (policyId: string): Promise<{ policy: any; benefits: any[] }> => {
    const response = await api.post(`/api/policies/${policyId}/extract`);
    return response.data;
  },
  saveBenefits: async (policyId: string, benefits: any[]): Promise<{ policy: any; benefits: any[] }> => {
    const response = await api.put(`/api/company-policies/${policyId}/benefits`, { benefits });
    return response.data;
  },
  getNormalized: async (policyId: string): Promise<{
    policy: any;
    version: any;
    benefit_rules: any[];
    exclusions: any[];
    evidence_requirements: any[];
    conditions: any[];
    assignment_applicability: any[];
    family_applicability: any[];
    source_links: any[];
  }> => {
    const response = await api.get(`/api/company-policies/${policyId}/normalized`);
    return response.data;
  },
  patchBenefitRule: async (
    policyId: string,
    benefitRuleId: string,
    body: {
      amount_value?: number;
      amount_unit?: string;
      currency?: string;
      frequency?: string;
      description?: string;
      review_status?: string;
      benefit_key?: string;
      metadata_json?: Record<string, any>;
    }
  ): Promise<{ benefit_rule: any }> => {
    const response = await api.patch(`/api/company-policies/${policyId}/benefits/${benefitRuleId}`, body);
    return response.data;
  },
  patchVersionStatus: async (
    policyId: string,
    versionId: string,
    body: { status: string }
  ): Promise<{ version: any }> => {
    const response = await api.patch(`/api/company-policies/${policyId}/versions/${versionId}/status`, body);
    return response.data;
  },
  /** Update latest version status - avoids version_id mismatch 404s */
  patchLatestVersionStatus: async (policyId: string, body: { status: string }): Promise<{ version: any }> => {
    const response = await api.patch(`/api/company-policies/${policyId}/versions/latest/status`, body);
    return response.data;
  },
  publishVersion: async (policyId: string, versionId: string): Promise<{ version: any }> => {
    const response = await api.post(`/api/company-policies/${policyId}/versions/${versionId}/publish`);
    return response.data;
  },
  /** Publish latest version - avoids version_id mismatch 404s */
  publishLatestVersion: async (policyId: string): Promise<{ version: any }> => {
    const response = await api.post(`/api/company-policies/${policyId}/versions/latest/publish`);
    return response.data;
  },
  patchExclusion: async (
    policyId: string,
    exclId: string,
    body: { description?: string; review_status?: string }
  ): Promise<{ exclusion: any }> => {
    const response = await api.patch(`/api/company-policies/${policyId}/exclusions/${exclId}`, body);
    return response.data;
  },
  patchCondition: async (
    policyId: string,
    condId: string,
    body: { condition_value_json?: Record<string, any>; review_status?: string }
  ): Promise<{ condition: any }> => {
    const response = await api.patch(`/api/company-policies/${policyId}/conditions/${condId}`, body);
    return response.data;
  },
};

/** Policy document intake: upload PDF/DOCX, classify before extraction */
export const policyDocumentsAPI = {
  health: async (): Promise<{
    supabase_url_present: boolean;
    service_role_present: boolean;
    bucket_name: string;
    bucket_access_ok: boolean;
    policy_documents_table_ok: boolean;
    policy_document_clauses_table_ok: boolean;
    policy_versions_table_ok: boolean;
    resolved_assignment_policies_table_ok: boolean;
  }> => {
    const response = await api.get('/api/hr/policy-documents/health');
    return response.data;
  },
  list: async (params?: { company_id?: string }): Promise<{ documents: any[] }> => {
    const response = await api.get('/api/hr/policy-documents', { params });
    return response.data;
  },
  get: async (docId: string): Promise<{ document: any }> => {
    const response = await api.get(`/api/hr/policy-documents/${docId}`);
    return response.data;
  },
  upload: async (file: File, companyId?: string | null): Promise<{ ok: boolean; document: any; error_code?: string; message?: string; request_id?: string }> => {
    // Backend expects field name "file". When admin is viewing a company's policy workspace, pass company_id so the doc is stored for that company.
    const form = new FormData();
    form.append('file', file);
    const params = companyId && companyId.trim() ? { company_id: companyId.trim() } : undefined;
    if (import.meta.env.DEV) {
      console.info('policy upload selected file', {
        name: file?.name,
        size: file?.size,
        type: file?.type,
        isFile: file instanceof File,
        companyId: companyId ?? undefined,
      });
      console.info('policy upload form keys', [...form.keys()]);
    }
    const response = await api.post('/api/hr/policy-documents/upload', form, { params });
    return response.data;
  },
  reprocess: async (docId: string): Promise<{ document: any }> => {
    const response = await api.post(`/api/hr/policy-documents/${docId}/reprocess`);
    return response.data;
  },
  listClauses: async (docId: string, clauseType?: string): Promise<{ clauses: any[] }> => {
    const params = clauseType ? { clause_type: clauseType } : {};
    const response = await api.get(`/api/hr/policy-documents/${docId}/clauses`, { params });
    return response.data;
  },
  getClause: async (docId: string, clauseId: string): Promise<{ clause: any }> => {
    const response = await api.get(`/api/hr/policy-documents/${docId}/clauses/${clauseId}`);
    return response.data;
  },
  patchClause: async (
    docId: string,
    clauseId: string,
    body: { clause_type?: string; title?: string; hr_override_notes?: string }
  ): Promise<{ clause: any }> => {
    const response = await api.patch(
      `/api/hr/policy-documents/${docId}/clauses/${clauseId}`,
      body
    );
    return response.data;
  },
  normalize: async (docId: string): Promise<{ policy_id: string; policy_version_id: string; summary: any }> => {
    const response = await api.post(`/api/hr/policy-documents/${docId}/normalize`);
    return response.data;
  },
  bulkDelete: async (documentIds: string[]): Promise<{ ok: boolean; deleted: number; skipped?: Array<{ id: string; reason: string }> }> => {
    const response = await api.post('/api/hr/policy-documents/bulk-delete', { document_ids: documentIds });
    return response.data;
  },
};

export const resourcesAPI = {
  /** Legacy: uses /api/resources/country (rkg_resources). Kept for backward compatibility. */
  getCountryResources: async (
    assignmentId: string,
    filters?: Record<string, string | number | boolean | null>
  ): Promise<{
    profile: Record<string, any>;
    context?: Record<string, any>;
    hints: { priorities: string[]; recommendations: string[] };
    sections: Array<{ key: string; title: string; content: any }>;
    events?: any[];
    recommended?: any[];
    filters_applied: Record<string, any>;
  }> => {
    const params: Record<string, string> = { assignment_id: assignmentId };
    if (filters && Object.keys(filters).length) {
      params.filters = JSON.stringify(filters);
    }
    const response = await api.get('/api/resources/country', { params });
    return response.data;
  },

  /** New: composite page data from published views. Use assignmentId or caseId (backend resolves both). */
  getPage: async (
    assignmentOrCaseId: string,
    filters?: Record<string, string | number | boolean | null>
  ): Promise<import('../types').ResourcesPagePayload> => {
    const params: Record<string, string> = { assignment_id: assignmentOrCaseId };
    if (filters && Object.keys(filters).length) {
      params.filters = JSON.stringify(filters);
    }
    const response = await api.get('/api/resources/page', { params });
    return response.data;
  },

  getContext: async (assignmentOrCaseId: string): Promise<import('../types').ResourceContext> => {
    const response = await api.get('/api/resources/context', {
      params: { assignment_id: assignmentOrCaseId },
    });
    return response.data;
  },

  getResources: async (
    assignmentOrCaseId: string,
    filters?: Record<string, string | number | boolean | null>,
    page = 1,
    limit = 50
  ): Promise<{ resources: Record<string, unknown>[] }> => {
    const params: Record<string, string | number> = {
      assignment_id: assignmentOrCaseId,
      page,
      limit,
    };
    if (filters && Object.keys(filters).length) {
      params.filters = JSON.stringify(filters);
    }
    const response = await api.get('/api/resources', { params });
    return response.data;
  },

  getEvents: async (
    assignmentOrCaseId: string,
    filters?: Record<string, string | number | boolean | null>,
    page = 1,
    limit = 50
  ): Promise<{ events: import('../types').PublicEvent[] }> => {
    const params: Record<string, string | number> = {
      assignment_id: assignmentOrCaseId,
      page,
      limit,
    };
    if (filters && Object.keys(filters).length) {
      params.filters = JSON.stringify(filters);
    }
    const response = await api.get('/api/resources/events', { params });
    return response.data;
  },

  getRecommended: async (
    assignmentOrCaseId: string,
    limit = 10
  ): Promise<import('../types').RecommendationGroup> => {
    const response = await api.get('/api/resources/recommended', {
      params: { assignment_id: assignmentOrCaseId, limit },
    });
    return response.data;
  },
};

export const dossierAPI = {
  getQuestions: async (caseId: string): Promise<DossierQuestionsResponse> => {
    const response = await api.get('/api/dossier/questions', { params: { case_id: caseId } });
    return response.data;
  },
  saveAnswers: async (payload: { case_id: string; answers: Array<{ question_id?: string | null; case_question_id?: string | null; answer: any }> }): Promise<{ ok: boolean }> => {
    const response = await api.post('/api/dossier/answers', payload);
    return response.data;
  },
  searchSuggestions: async (caseId: string): Promise<DossierSearchSuggestionsResponse> => {
    const response = await api.post('/api/dossier/search-suggestions', { case_id: caseId });
    return response.data;
  },
  addCaseQuestion: async (payload: { case_id: string; question_text: string; answer_type: string; options?: string[] | null; is_mandatory?: boolean; sources?: Array<{ title?: string; url: string }> }): Promise<any> => {
    const response = await api.post('/api/dossier/case-questions', payload);
    return response.data;
  },
};

export const guidanceAPI = {
  generate: async (caseId: string, mode?: 'demo' | 'strict'): Promise<{
    guidance_pack_id: string;
    guidance_mode?: 'demo' | 'strict';
    pack_hash?: string;
    rule_set?: any[];
    plan: any;
    checklist: any;
    markdown: string;
    sources: Array<{ doc_id: string; title?: string; url: string; publisher?: string }>;
    not_covered: string[];
    coverage?: any;
  }> => {
    const response = await api.post('/api/guidance/generate', { case_id: caseId, mode });
    return response.data;
  },
  getLatest: async (caseId: string): Promise<any> => {
    const response = await api.get('/api/guidance/latest', { params: { case_id: caseId } });
    return response.data;
  },
  explain: async (caseId: string): Promise<any> => {
    const response = await api.get('/api/guidance/explain', { params: { case_id: caseId } });
    return response.data;
  },
};

export default api;

function buildApiError(response: Response, bodyText: string) {
  let detail: any = bodyText;
  let message = bodyText || `${response.status} ${response.statusText}`;

  try {
    const parsed = JSON.parse(bodyText);
    detail = parsed?.detail ?? parsed;
    if (typeof detail === 'string') {
      message = detail;
    } else if (detail && typeof detail === 'object') {
      message = detail.message || JSON.stringify(detail);
    }
  } catch {
    // bodyText wasn't JSON
  }

  const err: any = new Error(message);
  err.status = response.status;
  err.detail = detail;
  return err;
}

function authHeaders(): Record<string, string> {
  const token = getAuthItem('relopass_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function apiGet<T>(path: string, opts?: { headers?: Record<string, string>; requestId?: string }): Promise<T> {
  let response: Response;
  const tStart = typeof performance !== 'undefined' ? performance.now() : Date.now();
  const requestId =
    opts?.requestId ||
    (typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`);
  const pathOnly = path.split('?')[0] || '/';
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders(),
        ...(opts?.headers || {}),
        'X-Request-ID': requestId,
      },
    });
  } catch {
    throw new Error('Unable to reach the server. Please check your connection and try again.');
  }
  if (!response.ok) {
    const text = await response.text();
    const tBody = typeof performance !== 'undefined' ? performance.now() : Date.now();
    recordRequestPerf({
      requestId,
      method: 'GET',
      path: pathOnly,
      status: response.status,
      ok: false,
      durationHeadersMs: tBody - tStart,
      durationBodyMs: tBody - tStart,
      startedAt: tStart,
    });
    throw buildApiError(response, text);
  }
  const jsonStart = typeof performance !== 'undefined' ? performance.now() : Date.now();
  const data = (await response.json()) as T;
  const tEnd = typeof performance !== 'undefined' ? performance.now() : Date.now();
  recordRequestPerf({
    requestId,
    method: 'GET',
    path: pathOnly,
    status: response.status,
    ok: true,
    durationHeadersMs: jsonStart - tStart,
    durationBodyMs: tEnd - tStart,
    startedAt: tStart,
  });
  return data;
}

export async function apiPost<T>(
  path: string,
  body?: any,
  opts?: { headers?: Record<string, string>; requestId?: string }
): Promise<T> {
  let response: Response;
  const tStart = typeof performance !== 'undefined' ? performance.now() : Date.now();
  const requestId =
    opts?.requestId ||
    (typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`);
  const pathOnly = path.split('?')[0] || '/';
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders(),
        ...(opts?.headers || {}),
        'X-Request-ID': requestId,
      },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error('Unable to reach the server. Please check your connection and try again.');
  }
  if (!response.ok) {
    const text = await response.text();
    const tBody = typeof performance !== 'undefined' ? performance.now() : Date.now();
    recordRequestPerf({
      requestId,
      method: 'POST',
      path: pathOnly,
      status: response.status,
      ok: false,
      durationHeadersMs: tBody - tStart,
      durationBodyMs: tBody - tStart,
      startedAt: tStart,
    });
    throw buildApiError(response, text);
  }
  const jsonStart = typeof performance !== 'undefined' ? performance.now() : Date.now();
  const data = (await response.json()) as T;
  const tEnd = typeof performance !== 'undefined' ? performance.now() : Date.now();
  recordRequestPerf({
    requestId,
    method: 'POST',
    path: pathOnly,
    status: response.status,
    ok: true,
    durationHeadersMs: jsonStart - tStart,
    durationBodyMs: tEnd - tStart,
    startedAt: tStart,
  });
  return data;
}

export async function apiPatch<T>(
  path: string,
  body?: any,
  opts?: { headers?: Record<string, string>; requestId?: string }
): Promise<T> {
  let response: Response;
  const tStart = typeof performance !== 'undefined' ? performance.now() : Date.now();
  const requestId =
    opts?.requestId ||
    (typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`);
  const pathOnly = path.split('?')[0] || '/';
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders(),
        ...(opts?.headers || {}),
        'X-Request-ID': requestId,
      },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error('Unable to reach the server. Please check your connection and try again.');
  }
  if (!response.ok) {
    const text = await response.text();
    const tBody = typeof performance !== 'undefined' ? performance.now() : Date.now();
    recordRequestPerf({
      requestId,
      method: 'PATCH',
      path: pathOnly,
      status: response.status,
      ok: false,
      durationHeadersMs: tBody - tStart,
      durationBodyMs: tBody - tStart,
      startedAt: tStart,
    });
    throw buildApiError(response, text);
  }
  const jsonStart = typeof performance !== 'undefined' ? performance.now() : Date.now();
  const data = (await response.json()) as T;
  const tEnd = typeof performance !== 'undefined' ? performance.now() : Date.now();
  recordRequestPerf({
    requestId,
    method: 'PATCH',
    path: pathOnly,
    status: response.status,
    ok: true,
    durationHeadersMs: jsonStart - tStart,
    durationBodyMs: tEnd - tStart,
    startedAt: tStart,
  });
  return data;
}
