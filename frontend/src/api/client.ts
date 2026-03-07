import axios from 'axios';
import { getAuthItem, clearAuthItems } from '../utils/demo';
import { signOutSupabase } from './supabaseAuth';
import { getCurrentInteractionId, recordRequestPerf } from '../perf/perf';
import type {
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  NextQuestionResponse,
  AnswerRequest,
  RelocationProfile,
  DashboardResponse,
  HousingRecommendation,
  SchoolRecommendation,
  MoverRecommendation,
  AssignmentSummary,
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
  AdminRelocationCase,
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
  assignCase: async (caseId: string, employeeIdentifier: string): Promise<AssignCaseResponse> => {
    const response = await api.post(`/api/hr/cases/${caseId}/assign`, { employeeIdentifier });
    return response.data;
  },
  listAssignments: async (): Promise<AssignmentSummary[]> => {
    const response = await api.get('/api/hr/assignments');
    return response.data;
  },
  getAssignment: async (assignmentId: string): Promise<AssignmentDetail> => {
    const response = await api.get(`/api/hr/assignments/${assignmentId}`);
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
    const response = await api.get('/api/hr/company-profile');
    return response.data;
  },
  saveCompanyProfile: async (payload: CompanyProfilePayload): Promise<any> => {
    const response = await api.post('/api/hr/company-profile', payload);
    return response.data;
  },
  uploadCompanyLogo: async (file: File): Promise<{ ok: boolean; logo_url: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/api/hr/company-profile/logo', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },
  removeCompanyLogo: async (): Promise<{ ok: boolean }> => {
    const response = await api.post('/api/hr/company-profile/remove-logo');
    return response.data;
  },
  listMessages: async (): Promise<{ messages: any[] }> => {
    const response = await api.get('/api/hr/messages');
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
    const response = await api.get('/api/admin/context');
    return response.data;
  },
  startImpersonation: async (payload: { targetUserId: string; mode: 'hr' | 'employee'; reason?: string }) => {
    const response = await api.post('/api/admin/impersonate/start', payload);
    return response.data;
  },
  stopImpersonation: async (): Promise<{ ok: boolean }> => {
    const response = await api.post('/api/admin/impersonate/stop');
    return response.data;
  },
  listCompanies: async (q?: string): Promise<{ companies: AdminCompany[] }> => {
    const response = await api.get('/api/admin/companies', { params: { q } });
    return response.data;
  },
  getCompanyDetail: async (companyId: string): Promise<{ company: AdminCompany | null; hr_users: AdminHrUser[]; employees: AdminEmployee[]; policies: any[] }> => {
    const response = await api.get(`/api/admin/companies/${companyId}`);
    return response.data;
  },
  listProfiles: async (q?: string): Promise<{ profiles: AdminProfile[] }> => {
    const response = await api.get('/api/admin/users', { params: { q } });
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
  listSupportCases: async (params?: { status?: string; severity?: string; company_id?: string }): Promise<{ support_cases: AdminSupportCase[] }> => {
    const response = await api.get('/api/admin/support-cases', { params });
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
};

export const servicesAPI = {
  getServiceAnswers: async (caseId: string): Promise<{ case_id: string; answers: any[] }> => {
    const response = await api.get('/api/services/answers', { params: { case_id: caseId } });
    return response.data;
  },
  saveServiceAnswers: async (
    caseId: string,
    items: Array<{ service_key: string; answers: Record<string, any> }>
  ): Promise<{ ok: boolean }> => {
    const response = await api.post('/api/services/answers', { case_id: caseId, items });
    return response.data;
  },
  createRfq: async (
    caseId: string,
    items: Array<{ service_key: string; requirements: Record<string, any> }>,
    vendorIds: string[]
  ): Promise<{ ok: boolean; rfq: { id: string; rfq_ref: string } }> => {
    const response = await api.post('/api/rfqs', { case_id: caseId, items, vendor_ids: vendorIds });
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
    const response = await api.post('/api/hr/policies/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },
  delete: async (policyId: string): Promise<void> => {
    await api.delete(`/api/hr/policies/${policyId}`);
  },
};

export const companyPolicyAPI = {
  list: async (): Promise<{ policies: any[] }> => {
    const response = await api.get('/api/company-policies');
    return response.data;
  },
  getLatest: async (): Promise<{ policy: any; benefits: any[] }> => {
    const response = await api.get('/api/company-policies/latest');
    return response.data;
  },
  getById: async (policyId: string): Promise<{ policy: any; benefits: any[] }> => {
    const response = await api.get(`/api/company-policies/${policyId}`);
    return response.data;
  },
  getDownloadUrl: async (policyId: string): Promise<{ url: string }> => {
    const response = await api.get(`/api/company-policies/${policyId}/download-url`);
    return response.data;
  },
  upload: async (file: File, meta: { title: string; version?: string; effective_date?: string }): Promise<{ policy: any }> => {
    const form = new FormData();
    form.append('file', file);
    form.append('title', meta.title);
    if (meta.version) form.append('version', meta.version);
    if (meta.effective_date) form.append('effective_date', meta.effective_date);
    const response = await api.post('/api/company-policies/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
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
};

export const resourcesAPI = {
  getCountryResources: async (
    assignmentId: string,
    filters?: Record<string, string | number | boolean | null>
  ): Promise<{
    profile: Record<string, any>;
    hints: { priorities: string[]; recommendations: string[] };
    sections: Array<{ key: string; title: string; content: any }>;
    filters_applied: Record<string, any>;
  }> => {
    const params: Record<string, string> = { assignment_id: assignmentId };
    if (filters && Object.keys(filters).length) {
      params.filters = JSON.stringify(filters);
    }
    const response = await api.get('/api/resources/country', { params });
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
