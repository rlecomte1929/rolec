import axios, { type AxiosError } from 'axios';
import type {
  ApiErrorBody,
  CompanyPolicyResult,
  ServiceContextResult,
  CountryResourcesResult,
  GuidanceGenerateResult,
  ThreadSummariesResult,
  PolicyDocumentsHealth,
  PolicyNormalizeResult,
} from './types';
import type { NormalizedPolicyResponse, PolicyDocument, PolicyDocumentClause, CompanyPolicySummary } from '../features/policy/types';
import { logger } from '../lib/logger';
import { getAuthItem, clearAuthItems } from '../utils/demo';
import { recordFailedRequest } from './requestLog';
import { env } from '../config/env';
import type { IntakeData } from '../features/platform-v2/intake/EmployeeIntakePage';
import { getCurrentInteractionId, recordRequestPerf } from '../perf/perf';
import { swallow } from '../lib/errorTracking';
import { queryClient } from '../lib/queryClient';
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
  InferredOnboardingConfig,
  DossierQuestionsResponse,
  DossierSearchSuggestionsResponse,
  DossierSource,
} from '../types';
import type { EmployeePolicyAssistantQueryResponse, HrPolicyAssistantQueryResponse } from '../types/policyAssistant';
import type { AiStep } from '../features/admin/specialist-review/RoadmapStepDiff';
import type { ReasonCode, ReviewDecision } from '../features/admin/specialist-review/reasonCodes';
import { ragResponseToEmployeeResponse, ragResponseToHrResponse, type RagQueryResponse } from './policyAssistantRagAdapter';
import {
  intakeEnvelopeSchema,
  assignmentsOverviewSchema,
  currentAssignmentSchema,
} from './schemas/employee';
import { parseResponse } from './schemas/parseResponse';
import { signOutSupabase } from './supabaseAuth';

// VITE_API_URL must be set for every environment:
//   - Development:  http://localhost:8000         (via frontend/.env.development)
//   - Production:   https://api.relopass.com      (via frontend/.env.production)
// Fallback keeps local dev working if .env.development is missing.
const API_BASE_URL: string = env.apiUrl;

export { API_BASE_URL };


// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  /**
   * B13 fix: default timeout lowered from 60s → 12s so a blocked/unavailable
   * API surfaces an error within the 10s window the E2E test checks.
   * All genuinely long-running calls (file uploads, policy extraction, AI
   * inference) already override per-request with `{ timeout: 120_000 }`.
   * Query and mutation endpoints should respond well within 12s; if they don't
   * that's a backend performance bug (see B3), not a valid reason to hide the
   * error from the user.
   */
  timeout: 12_000,
  headers: {
    'Content-Type': 'application/json',
  },
});

type CacheEntry<T> = {
  ts: number;
  data?: T;
  promise?: Promise<T>;
};

const apiCache = new Map<string, CacheEntry<unknown>>();

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

// Perf metadata we stash on the axios config object (all props optional so the
// cast from InternalAxiosRequestConfig is structurally valid — no `any` needed).
type PerfMeta = { requestId: string; tStart: number };
type PerfConfig = { url?: string; method?: string; _perfMeta?: PerfMeta };

// Add auth token + request/perf metadata to requests
api.interceptors.request.use((config) => {
  const token = getAuthItem('relopass_token');
  if (!config.headers) (config as { headers?: Record<string, string> }).headers = {};
  // FormData: must NOT set Content-Type so browser sets multipart/form-data with boundary
  if (config.data instanceof FormData) {
    delete (config.headers as Record<string, unknown>)['Content-Type'];
  }
  if (token) {
    (config.headers as Record<string, unknown>).Authorization = `Bearer ${token}`;
  }

  // Attach / propagate X-Request-ID for correlation with backend.
  const existingId =
    ((config.headers as Record<string, unknown>)['X-Request-ID'] as string | undefined) || getCurrentInteractionId();
  const requestId =
    existingId ||
    (typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`);

  (config.headers as Record<string, unknown>)['X-Request-ID'] = requestId;

  // Stash perf metadata on the config (type-cast to avoid axios type extension).
  (config as PerfConfig)._perfMeta = {
    requestId,
    tStart: typeof performance !== 'undefined' ? performance.now() : Date.now(),
  };

  return config;
});

/** Parse `Server-Timing: app;dur=12.3, db;dur=4.2` → the `app` duration, or undefined. */
function parseServerTiming(header: string | null | undefined): number | undefined {
  if (!header) return undefined;
  for (const part of header.split(',')) {
    const trimmed = part.trim();
    if (!trimmed.toLowerCase().startsWith('app')) continue;
    const match = /dur\s*=\s*([\d.]+)/i.exec(trimmed);
    if (match) {
      const n = Number(match[1]);
      return Number.isFinite(n) ? n : undefined;
    }
  }
  return undefined;
}

// Global 401 handler + perf logging
api.interceptors.response.use(
  (res) => {
    try {
      const meta = (res.config as PerfConfig)._perfMeta;
      if (meta) {
        const tEnd = typeof performance !== 'undefined' ? performance.now() : Date.now();
        const duration = tEnd - meta.tStart;
        // With axios we don't get a separate "headers" vs "body" hook; treat both as full duration.
        const path = (res.config.url || '').split('?')[0] || '/';
        const method = (res.config.method || 'GET').toUpperCase();
        const serverTiming =
          (res.headers && (res.headers['server-timing'] || res.headers['Server-Timing'])) as
            | string
            | undefined;
        recordRequestPerf({
          requestId: meta.requestId,
          method,
          path,
          status: res.status,
          ok: res.status >= 200 && res.status < 300,
          durationHeadersMs: duration,
          durationBodyMs: duration,
          serverMs: parseServerTiming(serverTiming),
          startedAt: meta.tStart,
        });
      }
    } catch {
      // do not block response on perf logging failures
    }
    return res;
  },
  (err: AxiosError<ApiErrorBody>) => {
    try {
      const cfg = (err?.config || {}) as PerfConfig;
      const meta = cfg._perfMeta;
      const status = err?.response?.status ?? 0;
      if (meta) {
        const tEnd = typeof performance !== 'undefined' ? performance.now() : Date.now();
        const duration = tEnd - meta.tStart;
        const path = (cfg.url || '').split('?')[0] || '/';
        const method = (cfg.method || 'GET').toUpperCase();
        const resHeaders = err?.response?.headers;
        const serverTiming =
          (resHeaders && (resHeaders['server-timing'] || resHeaders['Server-Timing'])) as
            | string
            | undefined;
        recordRequestPerf({
          requestId: meta.requestId,
          method,
          path,
          status,
          ok: false,
          durationHeadersMs: duration,
          durationBodyMs: duration,
          serverMs: parseServerTiming(serverTiming),
          startedAt: meta.tStart,
        });
        recordFailedRequest(
          method,
          path,
          status,
          ((resHeaders?.['x-request-id'] as string | undefined) ?? meta.requestId) || null,
        );
      }
    } catch (e) {
      swallow(e, 'client: request-perf emit');
    }
    const status = err?.response?.status;
    const url = err?.config?.url ?? '';
    const isAuthEndpoint = /\/api\/auth\/(login|register)$/.test(url);
    const isDebugEndpoint = /\/api\/debug\//.test(url);

    // B13 fix: when the API is completely unreachable (network error, DNS failure,
    // or timeout), fire a window event so any mounted banner can surface the error.
    // We skip this for AbortError (user-initiated cancellation, e.g. AbortController
    // used for 5-second widget timeouts) and for 401s which already redirect to login.
    const isAbort = err?.name === 'AbortError' || err?.code === 'ERR_CANCELED';
    if (!isAbort && (!err?.response || err?.code === 'ECONNABORTED')) {
      try {
        window.dispatchEvent(new CustomEvent('api_unavailable'));
      } catch (e) {
        swallow(e, 'client: dispatch api_unavailable (SSR/test lacks window)');
      }
    }

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
      invalidateApiCache('employee:assignments-overview');
      clearAuthItems();
      const path = window.location.pathname || '';
      if (!path.startsWith('/auth') && path !== '/' && path !== '') {
        window.location.href = '/auth?mode=login&reason=session_expired';
      }
    }
    return Promise.reject(err);
  }
);

// Auth API
// `/api/auth/login` and `/api/auth/register` may be the first request after
// the Render backend has scaled to zero, so the cold-start spin-up can blow
// past the 15s default. Bump these two specifically — every other call rides
// behind a successful login and finds the worker already warm.
const AUTH_ENTRYPOINT_TIMEOUT = 45_000;

export const authAPI = {
  login: async (data: LoginRequest): Promise<LoginResponse> => {
    const response = await api.post<LoginResponse>('/api/auth/login', data, { timeout: AUTH_ENTRYPOINT_TIMEOUT });
    return response.data;
  },
  register: async (data: RegisterRequest): Promise<LoginResponse> => {
    const response = await api.post<LoginResponse>('/api/auth/register', data, { timeout: AUTH_ENTRYPOINT_TIMEOUT });
    return response.data;
  },
  // AIQ-1355/1357: set the active role for a multi-role user to one they hold.
  switchRole: async (role: string): Promise<{ roles: string[]; primary_role: string }> => {
    const response = await api.post<{ roles: string[]; primary_role: string }>('/api/auth/switch-role', { role });
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
      // Ignore: client will clear session anyway
    }
    await signOutSupabase();
    clearAuthItems();
  },
};

// Profile API
export const profileAPI = {
  getCurrent: async (): Promise<RelocationProfile> => {
    const response = await api.get<RelocationProfile>('/api/profile/current');
    return response.data;
  },

  getNextQuestion: async (): Promise<NextQuestionResponse> => {
    const response = await api.get<NextQuestionResponse>('/api/profile/next-question');
    return response.data;
  },

  submitAnswer: async (data: AnswerRequest): Promise<unknown> => {
    const response = await api.post<unknown>('/api/profile/answer', data);
    return response.data;
  },

  complete: async (): Promise<unknown> => {
    const response = await api.post<unknown>('/api/profile/complete');
    return response.data;
  },
};

// Recommendations API
export const recommendationsAPI = {
  getHousing: async (): Promise<HousingRecommendation[]> => {
    const response = await api.get<HousingRecommendation[]>('/api/recommendations/housing');
    return response.data;
  },

  getSchools: async (): Promise<SchoolRecommendation[]> => {
    const response = await api.get<SchoolRecommendation[]>('/api/recommendations/schools');
    return response.data;
  },

  getMovers: async (): Promise<MoverRecommendation[]> => {
    const response = await api.get<MoverRecommendation[]>('/api/recommendations/movers');
    return response.data;
  },
};

// Dashboard API
export const dashboardAPI = {
  get: async (): Promise<DashboardResponse> => {
    const response = await api.get<DashboardResponse>('/api/dashboard');
    return response.data;
  },
};

// HR case creation + assignment run a ~15-step DB chain (contact resolve,
// invite tokens, mobility/case-person/passport sync, message draft). The 15s
// default axios timeout was too tight when Supabase pooler RTT spiked,
// surfacing as "timeout of 15000ms exceeded" in the HR dashboard. Backend
// now dispatches the non-essential side effects to a background pool, but
// keep a 45s ceiling here as a safety net for the synchronous portion.
const HR_CASE_TIMEOUT = 45_000;

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

export interface HrQuoteRequest {
  id: string;
  case_id: string;
  employee_id: string;
  company_id: string;
  service_categories: string[];
  notes: string | null;
  budget_range: string | null;
  status: string;
  created_at: string;
  updated_at: string;
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

export interface HrRfqRequestsResponse {
  rfqs: Array<{
    id: string;
    case_id: string;
    vendor_id: string;
    vendor_name: string;
    vendor_email: string;
    service_category: string;
    move_date: string | null;
    budget_range: string | null;
    special_requirements: string | null;
    hr_email: string;
    hr_name: string;
    status: string;
    created_at: string;
  }>;
  total: number;
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
  saveCompanyProfile: async (payload: CompanyProfilePayload): Promise<unknown> => {
    const response = await api.post<unknown>('/api/hr/company-profile', payload);
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
  getCommandCenterCaseDetail: async (assignmentId: string): Promise<{ id: string; employeeIdentifier: string; destCountry?: string; destCity?: string; status: string; riskStatus: string; budgetLimit?: number; budgetEstimated?: number; expectedStartDate?: string; tasksTotal: number; tasksDone: number; tasksOverdue: number; phases: Array<{ phase: string; tasks: Array<{ title: string; status: string; due_date?: string }> }>; events: Array<{ event_type: string; description?: string; created_at: string }> }> => {
    const response = await api.get<{ id: string; employeeIdentifier: string; destCountry?: string; destCity?: string; status: string; riskStatus: string; budgetLimit?: number; budgetEstimated?: number; expectedStartDate?: string; tasksTotal: number; tasksDone: number; tasksOverdue: number; phases: Array<{ phase: string; tasks: Array<{ title: string; status: string; due_date?: string }> }>; events: Array<{ event_type: string; description?: string; created_at: string }> }>(`/api/hr/command-center/cases/${assignmentId}`);
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

  getQuoteRequests: async (params?: {
    status?: string;
    case_id?: string;
  }): Promise<{ quote_requests: HrQuoteRequest[] }> => {
    const response = await api.get<{ quote_requests: HrQuoteRequest[] } | HrQuoteRequest[]>('/api/hr/quote-requests', { params });
    // backend returns a list directly; normalise to named key
    const data = response.data;
    return { quote_requests: Array.isArray(data) ? data : (data.quote_requests ?? []) };
  },

  updateQuoteRequestStatus: async (
    requestId: string,
    status: 'acknowledged' | 'fulfilled'
  ): Promise<{ id: string; status: string }> => {
    const response = await api.patch<{ id: string; status: string }>(`/api/hr/quote-requests/${requestId}`, { status });
    return response.data;
  },

  // ── NAV-SP-2: Vendor performance dashboard ───────────────────────────────

  /** GET /api/hr/vendor-performance?range=30d|90d|12mo — NAV-SP-2 Vendor Performance tab. */
  getVendorPerformance: async (range: '30d' | '90d' | '12mo' = '90d'): Promise<VendorPerformanceResponse> => {
    const response = await api.get<VendorPerformanceResponse>('/api/hr/vendor-performance', { params: { range } });
    return response.data;
  },

  // ── AIQ-40-A/B: Vendor directory ─────────────────────────────────────────

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

  // ── AIQ-40-C: RFQ flow ────────────────────────────────────────────────────

  /** POST /api/hr/rfq-requests */
  createRfqRequest: async (payload: {
    case_id: string;
    vendor_id: string;
    service_category: string;
    move_date?: string;
    budget_range?: string;
    special_requirements?: string;
    // IMM-15: optional immigration case context (immigration-originated RFQs)
    visa_type?: string;
    corridor_from?: string;
    corridor_to?: string;
    employee_nationality?: string;
    has_dependents?: boolean;
    risk_flags?: string[];
  }): Promise<{ ok: boolean; rfq_id: string; vendor_name: string; status: string; message: string }> => {
    const response = await api.post<{ ok: boolean; rfq_id: string; vendor_name: string; status: string; message: string }>('/api/hr/rfq-requests', payload);
    return response.data;
  },

  /** GET /api/hr/rfq-requests?case_id=X */
  getRfqRequests: async (params?: { case_id?: string }): Promise<HrRfqRequestsResponse> => {
    const response = await api.get<HrRfqRequestsResponse>('/api/hr/rfq-requests', { params });
    return response.data;
  },

  /** PATCH /api/hr/rfq-requests/{id} */
  updateRfqStatus: async (
    rfqId: string,
    status: 'quote_received' | 'accepted' | 'cancelled',
    quoteDetails?: {
      quote_amount?: number;
      quote_currency?: string;
      quote_deadline?: string;
      quote_deliverable?: string;
    }
  ): Promise<{ ok: boolean; rfq_id: string; status: string }> => {
    const response = await api.patch<{ ok: boolean; rfq_id: string; status: string }>(`/api/hr/rfq-requests/${rfqId}`, { status, ...quoteDetails });
    return response.data;
  },

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

// Company API (for header branding: HR and Employee)
export const companyAPI = {
  get: async (): Promise<{ company: { id?: string; name: string; logo_url?: string | null; [key: string]: unknown } | null }> => {
    return cachedRequest('company:get', 60_000, async () => {
      const response = await api.get<{ company: { id?: string; name: string; logo_url?: string | null; [key: string]: unknown } | null }>('/api/company');
      return response.data;
    });
  },
};

/** Compact readiness + evaluation snapshot from GET .../mobility/cases/{id}/inspect */
export type AdminMobilityOperationalInspect = {
  assignment_id: string | null;
  mobility_case_id: string;
  bridge_status: 'linked' | 'missing';
  readiness_flags: {
    has_mobility_link: boolean;
    has_employee_person: boolean;
    has_passport_document: boolean;
    has_evaluations: boolean;
  };
  employee_snapshot: {
    full_name: string | null;
    email: string | null;
    nationality: string | null;
    residence_country: string | null;
    passport_country: string | null;
  };
  passport_document_snapshot: {
    document_key: string | null;
    document_status: string | null;
    source_evidence_id: string | null;
    submitted_at: string | null;
  };
  latest_evaluation_summary: {
    evaluated_at: string | null;
    counts_by_status: Record<string, number>;
  };
  latest_results: Array<{
    requirement_code?: string | null;
    evaluation_status?: string | null;
    source_rule_code?: string | null;
    evaluated_at?: string | null;
  }>;
  next_actions_preview: {
    actions: Array<{
      action_title?: string | null;
      priority?: number | null;
      related_requirement_code?: string | null;
    }>;
  };
};

// Admin API
export interface AdminCompanyDetailResponse {
  company: AdminCompany | null;
  summary?: { hr_users_count: number; employee_count: number; assignments_count: number; policies_count: number };
  counts_summary?: AdminCompanyDetailCounts;
  hr_users: AdminHrUser[];
  employees: AdminEmployee[];
  assignments: AdminCompanyDetailAssignment[];
  policies: AdminCompanyDetailPolicy[];
  orphan_diagnostics?: AdminCompanyDetailOrphanDiagnostics;
}

export interface AdminRebuildTestCompanyGraphResponse {
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
}

export interface AdminMobilityCaseInspectResponse {
  context: Record<string, unknown>;
  audit_logs: Array<Record<string, unknown>>;
  operational?: AdminMobilityOperationalInspect;
}

export const adminAPI = {
  getContext: async (): Promise<AdminContextResponse> => {
    return cachedRequest('admin:context', 20_000, async () => {
      const response = await api.get<AdminContextResponse>('/api/admin/context');
      return response.data;
    });
  },
  startImpersonation: async (payload: { targetUserId: string; mode: 'hr' | 'employee'; reason?: string }): Promise<{ ok: boolean; impersonation: { targetUserId: string; mode: 'hr' | 'employee' } }> => {
    const response = await api.post<{ ok: boolean; impersonation: { targetUserId: string; mode: 'hr' | 'employee' } }>('/api/admin/impersonate/start', payload);
    invalidateApiCache('admin:context');
    return response.data;
  },
  stopImpersonation: async (): Promise<{ ok: boolean }> => {
    const response = await api.post<{ ok: boolean }>('/api/admin/impersonate/stop');
    invalidateApiCache('admin:context');
    return response.data;
  },
  listCompanies: async (q?: string): Promise<{ companies: AdminCompany[] }> => {
    const key = `admin:companies:${q ?? ''}`;
    return cachedRequest(key, 60_000, async () => {
      const response = await api.get<{ companies: AdminCompany[] }>('/api/admin/companies', { params: { q } });
      return response.data;
    });
  },
  getCompanyDetail: async (companyId: string): Promise<AdminCompanyDetailResponse> => {
    const response = await api.get<AdminCompanyDetailResponse>(`/api/admin/companies/${companyId}`);
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
    const response = await api.post<{ company: AdminCompany }>('/api/admin/companies', payload);
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
    const response = await api.patch<{ company: AdminCompany }>(`/api/admin/companies/${companyId}`, payload);
    invalidateApiCachePrefix('admin:companies:');
    return response.data;
  },
  deactivateCompany: async (companyId: string): Promise<{ company: AdminCompany; message?: string }> => {
    const response = await api.post<{ company: AdminCompany; message?: string }>(`/api/admin/companies/${companyId}/deactivate`);
    invalidateApiCachePrefix('admin:companies:');
    return response.data;
  },
  /** Soft delete: sets status='archived' so the company is hidden from active lists. Reversible. */
  archiveCompany: async (companyId: string): Promise<{ company: AdminCompany; message?: string }> => {
    const response = await api.post<{ company: AdminCompany; message?: string }>(`/api/admin/companies/${companyId}/archive`);
    invalidateApiCachePrefix('admin:companies:');
    return response.data;
  },
  /** Hard delete: removes the company row. Irreversible — orphans references in employees/hr_users/profiles/etc. */
  deleteCompany: async (companyId: string): Promise<{ deleted: string; message?: string }> => {
    const response = await api.delete<{ deleted: string; message?: string }>(`/api/admin/companies/${companyId}`);
    invalidateApiCachePrefix('admin:companies:');
    return response.data;
  },
  runReconciliationBackfillTestCompany: async (): Promise<{ ok: boolean; summary?: { test_company_id: string; profiles_linked: number; hr_users_linked: number; relocation_cases_linked: number }; error?: string }> => {
    const response = await api.post<{ ok: boolean; summary?: { test_company_id: string; profiles_linked: number; hr_users_linked: number; relocation_cases_linked: number }; error?: string }>('/api/admin/reconciliation/backfill-test-company');
    return response.data;
  },
  rebuildTestCompanyGraph: async (): Promise<AdminRebuildTestCompanyGraphResponse> => {
    const response = await api.post<AdminRebuildTestCompanyGraphResponse>('/api/admin/reconciliation/rebuild-test-company-graph');
    return response.data;
  },
  listProfiles: async (params?: { q?: string; company_id?: string; role?: string }): Promise<{ profiles: AdminProfile[]; summary?: { count: number; orphans_without_company?: number } }> => {
    const response = await api.get<{ profiles: AdminProfile[]; summary?: { count: number; orphans_without_company?: number } }>('/api/admin/users', { params: params || {} });
    return response.data;
  },
  listPeople: async (params?: { company_id?: string; role?: string; q?: string }): Promise<{ people: AdminProfile[]; summary?: { count: number; orphans_without_company?: number } }> => {
    const response = await api.get<{ people: AdminProfile[]; summary?: { count: number; orphans_without_company?: number } }>('/api/admin/people', { params: params || {} });
    return response.data;
  },
  createPerson: async (payload: { email: string; full_name?: string; role?: string; company_id?: string; password?: string }): Promise<{ person: AdminProfile; invite_sent?: boolean; invite_error?: string; login_ready?: boolean }> => {
    const response = await api.post<{ person: AdminProfile; invite_sent?: boolean; invite_error?: string; login_ready?: boolean }>('/api/admin/people', payload);
    return response.data;
  },
  updatePerson: async (personId: string, payload: Partial<{ full_name: string; role: string; company_id: string; status: string }>): Promise<{ person: AdminProfile }> => {
    const response = await api.patch<{ person: AdminProfile }>(`/api/admin/people/${personId}`, payload);
    return response.data;
  },
  assignPersonCompany: async (personId: string, companyId: string): Promise<{ person: AdminProfile }> => {
    const response = await api.post<{ person: AdminProfile }>(`/api/admin/people/${personId}/assign-company`, { company_id: companyId });
    return response.data;
  },
  setPersonRole: async (personId: string, role: string): Promise<{ person: AdminProfile }> => {
    const response = await api.post<{ person: AdminProfile }>(`/api/admin/people/${personId}/set-role`, { role });
    return response.data;
  },
  deactivatePerson: async (personId: string): Promise<{ person: AdminProfile }> => {
    const response = await api.post<{ person: AdminProfile }>(`/api/admin/people/${personId}/deactivate`);
    return response.data;
  },
  listEmployees: async (companyId?: string): Promise<{ employees: AdminEmployee[] }> => {
    const response = await api.get<{ employees: AdminEmployee[] }>('/api/admin/employees', { params: { company_id: companyId } });
    return response.data;
  },
  listHrUsers: async (companyId?: string): Promise<{ hr_users: AdminHrUser[] }> => {
    const response = await api.get<{ hr_users: AdminHrUser[] }>('/api/admin/hr-users', { params: { company_id: companyId } });
    return response.data;
  },
  listRelocations: async (params?: { company_id?: string; status?: string }): Promise<{ relocations: AdminRelocationCase[] }> => {
    const response = await api.get<{ relocations: AdminRelocationCase[] }>('/api/admin/relocations', { params });
    return response.data;
  },
  listAssignments: async (params?: {
    company_id?: string;
    employee_user_id?: string;
    employee_search?: string;
    status?: string;
    destination_country?: string;
  }): Promise<{ assignments: AdminAssignment[] }> => {
    const response = await api.get<{ assignments: AdminAssignment[] }>('/api/admin/assignments', { params });
    return response.data;
  },
  getAssignmentDetail: async (assignmentId: string): Promise<{ assignment: AdminAssignmentDetail }> => {
    const response = await api.get<{ assignment: AdminAssignmentDetail }>(`/api/admin/assignments/${assignmentId}`);
    return response.data;
  },
  reassignEmployeeCompany: async (assignmentId: string, payload: { reason: string; company_id: string }): Promise<{ ok: boolean }> => {
    const response = await api.patch<{ ok: boolean }>(`/api/admin/assignments/${assignmentId}/reassign-employee-company`, payload);
    return response.data;
  },
  reassignHrOwner: async (assignmentId: string, payload: { reason: string; hr_user_id: string }): Promise<{ ok: boolean }> => {
    const response = await api.patch<{ ok: boolean }>(`/api/admin/assignments/${assignmentId}/reassign-hr-owner`, payload);
    return response.data;
  },
  fixAssignmentCompanyLinkage: async (assignmentId: string, payload: { reason: string; company_id: string }): Promise<{ ok: boolean }> => {
    const response = await api.patch<{ ok: boolean }>(`/api/admin/assignments/${assignmentId}/fix-company-linkage`, payload);
    return response.data;
  },
  updateAssignmentStatus: async (assignmentId: string, payload: { status: string }): Promise<{ ok: boolean; status: string }> => {
    const response = await api.patch<{ ok: boolean; status: string }>(`/api/admin/assignments/${assignmentId}/status`, payload);
    return response.data;
  },
  // Force an eligibility decision for one requirement category on an assignment
  // (POST /api/admin/actions/override-eligibility — reason required, audit-logged).
  overrideEligibility: async (payload: {
    assignment_id: string;
    category: string;
    allowed: boolean;
    reason: string;
    note?: string;
  }): Promise<{ ok: boolean }> => {
    const response = await api.post<{ ok: boolean }>('/api/admin/actions/override-eligibility', {
      reason: payload.reason,
      payload: {
        assignment_id: payload.assignment_id,
        category: payload.category,
        allowed: payload.allowed,
        note: payload.note,
      },
    });
    return response.data;
  },
  // Reactivate a stuck relocation case (status-only; never null-overwrites other fields).
  // `unlocked` reports whether a case actually matched the id.
  unlockCase: async (payload: { case_id: string; reason: string }): Promise<{ ok: boolean; unlocked: boolean }> => {
    const response = await api.post<{ ok: boolean; unlocked: boolean }>('/api/admin/actions/unlock-case', {
      reason: payload.reason,
      payload: { case_id: payload.case_id },
    });
    return response.data;
  },
  createAssignment: async (payload: {
    company_id: string;
    hr_user_id: string;
    employee_user_id?: string;
    employee_identifier?: string;
    destination_country?: string;
  }): Promise<{ ok: boolean; assignment_id: string; case_id: string }> => {
    const response = await api.post<{ ok: boolean; assignment_id: string; case_id: string }>('/api/admin/assignments', payload);
    return response.data;
  },
  listPolicyOverview: async (params?: { company_id?: string }): Promise<{ companies: AdminPolicyCompany[] }> => {
    try {
      const response = await api.get<{ companies: AdminPolicyCompany[] }>('/api/admin/policies/overview', { params });
      return response.data;
    } catch {
      return { companies: [] };
    }
  },
  listAdminPolicies: async (companyId: string): Promise<AdminPoliciesByCompany> => {
    const response = await api.get<AdminPoliciesByCompany>('/api/admin/policies', { params: { company_id: companyId } });
    return response.data;
  },
  getAdminPolicyDetail: async (policyId: string): Promise<AdminPolicyDetail> => {
    const response = await api.get<AdminPolicyDetail>(`/api/admin/policies/${policyId}`);
    return response.data;
  },
  getAdminPolicyVersions: async (policyId: string): Promise<{ policy_id: string; versions: AdminPolicyVersion[] }> => {
    const response = await api.get<{ policy_id: string; versions: AdminPolicyVersion[] }>(`/api/admin/policies/${policyId}/versions`);
    return response.data;
  },
  patchAdminPolicy: async (
    policyId: string,
    payload: { title?: string; version?: string; effective_date?: string; publish_version_id?: string; unpublish?: boolean }
  ): Promise<AdminPolicyDetail> => {
    const response = await api.patch<AdminPolicyDetail>(`/api/admin/policies/${policyId}`, payload);
    return response.data;
  },
  /** Legacy / optional. Never throws — callers must not tie page load to this result. */
  listAdminPolicyTemplates: async (): Promise<AdminPolicyTemplatesResponse> => {
    try {
      const response = await api.get<AdminPolicyTemplatesResponse>('/api/admin/policies/templates');
      return response.data ?? { templates: [] };
    } catch (e) {
      logger.warn('[adminAPI] listAdminPolicyTemplates failed (non-blocking)', e);
      return { templates: [] };
    }
  },
  applyDefaultTemplateToCompany: async (
    companyId: string,
    opts?: { template_id?: string; overwrite_existing?: boolean }
  ): Promise<{ ok: boolean; policy_id?: string; version_id?: string; error?: string }> => {
    const response = await api.post<{ ok: boolean; policy_id?: string; version_id?: string; error?: string }>('/api/admin/policies/apply-default-template', {
      company_id: companyId,
      template_id: opts?.template_id,
      overwrite_existing: opts?.overwrite_existing ?? false,
    });
    return response.data;
  },
  getPolicyAssistantCompanyHistory: async (companyId: string): Promise<Record<string, unknown>> => {
    const response = await api.get<Record<string, unknown>>(`/api/admin/policies/company/${companyId}/history`);
    return response.data;
  },
  getPolicyAssistantSnapshotDiff: async (
    companyId: string,
    olderSnapshotId: string,
    newerSnapshotId: string
  ): Promise<Record<string, unknown>> => {
    const response = await api.get<Record<string, unknown>>(`/api/admin/policies/company/${companyId}/diff`, {
      params: { older_snapshot_id: olderSnapshotId, newer_snapshot_id: newerSnapshotId },
    });
    return response.data;
  },
  listPolicyAssistantAnswerAudits: async (params: {
    company_id: string;
    case_id?: string;
    snapshot_id?: string;
    evidence_status?: string;
    created_after?: string;
    created_before?: string;
    limit?: number;
  }): Promise<{ audits: Record<string, unknown>[] }> => {
    const response = await api.get<{ audits: Record<string, unknown>[] }>('/api/admin/policies/answers/audits', { params });
    return response.data;
  },
  listSupportCases: async (params?: { status?: string; severity?: string; company_id?: string; priority?: string }): Promise<{ support_cases: AdminSupportCase[] }> => {
    const response = await api.get<{ support_cases: AdminSupportCase[] }>('/api/admin/support-cases', { params });
    return response.data;
  },
  patchSupportCase: async (
    caseId: string,
    payload: { priority?: string; status?: string; assignee_id?: string | null; category?: string }
  ): Promise<AdminSupportCase> => {
    const response = await api.patch<AdminSupportCase>(`/api/admin/support-cases/${caseId}`, payload);
    return response.data;
  },
  listMessageThreads: async (params?: {
    company_id?: string;
    user_id?: string;
    thread_type?: 'hr_employee' | 'collaboration';
    limit?: number;
    offset?: number;
  }): Promise<unknown> => {
    const response = await api.get<unknown>('/api/admin/messages/threads', { params });
    return response.data;
  },
  getHrThreadDetail: async (assignmentId: string): Promise<unknown> => {
    const response = await api.get<unknown>(`/api/admin/messages/threads/hr-employee/${assignmentId}`);
    return response.data;
  },
  listSupportNotes: async (caseId: string): Promise<{ notes: AdminSupportNote[] }> => {
    const response = await api.get<{ notes: AdminSupportNote[] }>(`/api/admin/support-cases/${caseId}/notes`);
    return response.data;
  },
  addSupportNote: async (caseId: string, payload: { note: string; reason: string }): Promise<unknown> => {
    const response = await api.post<unknown>(`/api/admin/support-cases/${caseId}/notes`, payload);
    return response.data;
  },
  adminAction: async (action: string, payload: { reason: string; breakGlass?: boolean; payload?: unknown }): Promise<unknown> => {
    const response = await api.post<unknown>(`/api/admin/actions/${action}`, payload);
    return response.data;
  },
  getReconciliationReport: async (): Promise<unknown> => {
    const response = await api.get<unknown>('/api/admin/reconciliation/report');
    return response.data;
  },
  reconciliationLinkPersonCompany: async (profileId: string, companyId: string): Promise<unknown> => {
    const response = await api.post<unknown>('/api/admin/reconciliation/link-person-company', { profile_id: profileId, company_id: companyId });
    return response.data;
  },
  reconciliationLinkAssignmentCompany: async (assignmentId: string, companyId: string, reason: string): Promise<unknown> => {
    const response = await api.post<unknown>('/api/admin/reconciliation/link-assignment-company', {
      assignment_id: assignmentId,
      company_id: companyId,
      reason,
    });
    return response.data;
  },
  reconciliationLinkAssignmentPerson: async (assignmentId: string, profileId: string): Promise<unknown> => {
    const response = await api.post<unknown>('/api/admin/reconciliation/link-assignment-person', {
      assignment_id: assignmentId,
      profile_id: profileId,
    });
    return response.data;
  },
  reconciliationLinkPolicyCompany: async (policyId: string, companyId: string): Promise<unknown> => {
    const response = await api.post<unknown>('/api/admin/reconciliation/link-policy-company', {
      policy_id: policyId,
      company_id: companyId,
    });
    return response.data;
  },
  listResearchCandidates: async (params?: { destination_country?: string; status?: string }): Promise<unknown> => {
    const response = await api.get<unknown>('/api/admin/research/candidates', { params });
    return response.data;
  },
  researchHealth: async (params: { destination: string }): Promise<unknown> => {
    const response = await api.get<unknown>('/api/admin/research/health', { params });
    return response.data;
  },
  approveResearchCandidate: async (candidateId: string, payload: { domain_area: string }): Promise<unknown> => {
    const response = await api.post<unknown>(`/api/admin/research/candidates/${candidateId}/approve`, payload);
    return response.data;
  },
  ingestUrl: async (payload: { url: string; destination_country: string; domain_area: string }): Promise<unknown> => {
    const response = await api.post<unknown>('/api/admin/ingest/url', payload);
    return response.data;
  },
  ingestBatch: async (payload: { urls: Array<string | { url: string; domain_area?: string }>; destination_country: string; domain_area?: string }): Promise<unknown> => {
    const response = await api.post<unknown>('/api/admin/ingest/batch', payload);
    return response.data;
  },
  listIngestJobs: async (params?: { status?: string }): Promise<unknown> => {
    const response = await api.get<unknown>('/api/admin/ingest/jobs', { params });
    return response.data;
  },
  listKnowledgeDocs: async (params: { destination_country: string }): Promise<unknown> => {
    const response = await api.get<unknown>('/api/admin/knowledge/docs', { params });
    return response.data;
  },
  listRequirementEntities: async (params: { destination: string; status?: string }): Promise<unknown> => {
    const response = await api.get<unknown>('/api/admin/requirements/entities', { params });
    return response.data;
  },
  listRequirementFacts: async (entityId: string, params?: { status?: string }): Promise<unknown> => {
    const response = await api.get<unknown>(`/api/admin/requirements/entities/${entityId}/facts`, { params });
    return response.data;
  },
  listRequirementCriteria: async (params: { destination: string; status?: string }): Promise<unknown> => {
    const response = await api.get<unknown>('/api/admin/requirements/criteria', { params });
    return response.data;
  },
  approveRequirementFacts: async (payload: { fact_ids: string[] }): Promise<unknown> => {
    const response = await api.post<unknown>('/api/admin/requirements/facts/approve', payload);
    return response.data;
  },
  rejectRequirementFacts: async (payload: { fact_ids: string[] }): Promise<unknown> => {
    const response = await api.post<unknown>('/api/admin/requirements/facts/reject', payload);
    return response.data;
  },
  /** Mobility graph: case context + audit logs (admin JWT). */
  inspectMobilityCase: async (
    caseId: string
  ): Promise<AdminMobilityCaseInspectResponse> => {
    const response = await api.get<AdminMobilityCaseInspectResponse>(`/api/admin/mobility/cases/${encodeURIComponent(caseId)}/inspect`);
    return response.data;
  },
  /** Run requirement evaluation for the assignment linked to a mobility case (admin JWT). */
  evaluateMobilityAssignmentRequirements: async (assignmentId: string): Promise<unknown> => {
    const response = await api.post<unknown>(
      `/api/admin/mobility/assignments/${encodeURIComponent(assignmentId)}/evaluate-requirements`
    );
    return response.data;
  },
  /** AIQ-1219: Upload a policy PDF/DOCX and get a workflow summary. */
  analyzePolicy: async (file: File): Promise<PolicyAnalysisResult> => {
    const form = new FormData();
    form.append('file', file);
    const response = await api.post<PolicyAnalysisResult>('/api/admin/policy-analysis', form, { timeout: 120_000 });
    return response.data;
  },
};

export interface PolicyWorkflowSummary {
  policy_title: string | null;
  effective_date: string | null;
  tiers: Array<{ name: string; bands: string[]; benefits_count: number }>;
  tasks: Array<{ category: string; task: string; owner: string; benefit_key: string; confidence: number }>;
  timeline: Array<{ phase: string; duration: string; tasks: string[] }>;
  cost_summary: {
    total_range: { min: number; max: number; currency: string } | null;
    by_category: Array<{ category: string; estimated_range: { min: number; max: number; currency: string } }>;
    note: string;
  };
  benefits_count: number;
}

export interface PolicyAnalysisResult {
  workflow_summary: PolicyWorkflowSummary;
  extraction: {
    llm_used: boolean;
    llm_unavailable_reason: string | null;
    model: string | null;
    truncated: boolean;
    benefits_count: number;
  };
  elapsed_ms: number;
}

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
    const response = await api.get<{ suppliers: unknown[]; total?: number }>('/api/suppliers', { params: params || {} });
    return response.data;
  },
  get: async (supplierId: string) => {
    const response = await api.get<unknown>(`/api/suppliers/${supplierId}`);
    return response.data;
  },
  listPendingCapabilities: async () => {
    const response = await api.get<{ capabilities: unknown[]; total?: number }>(
      '/api/suppliers/capabilities/pending'
    );
    return response.data;
  },
  search: async (params: {
    service_category: string;
    destination_country?: string;
    destination_city?: string;
    limit?: number;
  }) => {
    const response = await api.get<{ suppliers: unknown[]; total?: number }>('/api/suppliers/search', { params });
    return response.data;
  },
  getCategories: async () => {
    const response = await api.get<{ categories: unknown[] }>('/api/suppliers/categories');
    return response.data;
  },
  getCountries: async () => {
    const response = await api.get<{ countries: unknown[] }>('/api/suppliers/countries');
    return response.data;
  },
  create: async (payload: Record<string, unknown>) => {
    const response = await api.post<unknown>('/api/suppliers', payload);
    return response.data;
  },
  update: async (supplierId: string, payload: Record<string, unknown>) => {
    const response = await api.patch<unknown>(`/api/suppliers/${supplierId}`, payload);
    return response.data;
  },
  setStatus: async (supplierId: string, status: 'active' | 'inactive' | 'draft') => {
    const response = await api.patch<unknown>(`/api/suppliers/${supplierId}/status`, { status });
    return response.data;
  },
  addCapability: async (supplierId: string, payload: Record<string, unknown>) => {
    const response = await api.post<unknown>(`/api/suppliers/${supplierId}/capabilities`, payload);
    return response.data;
  },
  updateCapability: async (
    supplierId: string,
    capabilityId: string,
    payload: Record<string, unknown>
  ) => {
    const response = await api.patch<unknown>(
      `/api/suppliers/${supplierId}/capabilities/${capabilityId}`,
      payload
    );
    return response.data;
  },
  removeCapability: async (supplierId: string, capabilityId: string) => {
    const response = await api.delete<unknown>(
      `/api/suppliers/${supplierId}/capabilities/${capabilityId}`
    );
    return response.data;
  },
  approveCapability: async (supplierId: string, capabilityId: string, notes?: string) => {
    const response = await api.post<unknown>(
      `/api/suppliers/${supplierId}/capabilities/${capabilityId}/approve`,
      { notes }
    );
    return response.data;
  },
  rejectCapability: async (supplierId: string, capabilityId: string, notes: string) => {
    const response = await api.post<unknown>(
      `/api/suppliers/${supplierId}/capabilities/${capabilityId}/reject`,
      { notes }
    );
    return response.data;
  },
  updateScoring: async (supplierId: string, payload: Record<string, unknown>) => {
    const response = await api.patch<unknown>(`/api/suppliers/${supplierId}/scoring`, payload);
    return response.data;
  },
  getRankingDebug: async (
    supplierId: string,
    params?: { service_category?: string; destination_country?: string; destination_city?: string }
  ) => {
    const response = await api.get<unknown>(`/api/suppliers/${supplierId}/ranking-debug`, { params });
    return response.data;
  },
};

// Admin Prompt Registry API (admin only) — Parker Step D
export type PromptVersion = {
  id: string;
  task_key: string;
  version: number;
  system_prompt: string;
  user_template: string | null;
  model_name: string;
  temperature: number;
  max_tokens: number;
  status: string;
  created_at?: string;
  notes?: string | null;
};

export const promptsAPI = {
  list: async (): Promise<PromptVersion[]> => {
    const response = await api.get<PromptVersion[]>('/api/admin/prompts');
    return response.data;
  },
  listForTask: async (taskKey: string): Promise<PromptVersion[]> => {
    const response = await api.get<PromptVersion[]>(`/api/admin/prompts/${encodeURIComponent(taskKey)}`);
    return response.data;
  },
  create: async (payload: {
    task_key: string;
    system_prompt: string;
    model_name: string;
    user_template?: string | null;
    temperature?: number;
    max_tokens?: number;
    status?: string;
    notes?: string | null;
  }) => {
    const response = await api.post<unknown>('/api/admin/prompts', payload);
    return response.data;
  },
  promote: async (versionId: string, targetStatus: string) => {
    const response = await api.post<unknown>(`/api/admin/prompts/${encodeURIComponent(versionId)}/promote`, {
      target_status: targetStatus,
    });
    return response.data;
  },
  setCanaryShare: async (taskKey: string, canaryShare: number) => {
    const response = await api.post<unknown>(`/api/admin/prompts/${encodeURIComponent(taskKey)}/canary-share`, {
      canary_share: canaryShare,
    });
    return response.data;
  },
  // Parker Step E — per-version win rates (approvals / verdicts) with Wilson CI.
  winRates: async (taskKey: string): Promise<Record<string, WinRate>> => {
    const response = await api.get<Record<string, WinRate>>(`/api/admin/prompts/${encodeURIComponent(taskKey)}/win-rates`);
    return response.data;
  },
};

// Parker Step E — per-version human-feedback win rate, keyed by prompt_version_id.
export type WinRate = {
  version_id: string;
  approvals: number;
  total: number;
  win_rate: number;
  ci_low: number;
  ci_high: number;
};

// Admin HR Prospect Pipeline API (admin only)
export type ProspectSeedItem = {
  company_name: string;
  company_domain?: string;
  company_linkedin_url?: string;
  notes?: string;
};

export type ProspectRow = {
  id: string;
  company_name: string;
  company_domain: string | null;
  company_linkedin_url: string | null;
  icp_score: number | null;
  qualification_band: string | null;
  suggested_contact_title: string | null;
  suggested_hook: string | null;
  status: string;
  web_search_used: boolean;
  batch_id: string | null;
  enrichment_error: string | null;
  enriched?: Record<string, unknown> | null;
  raw_input?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  enriched_at: string | null;
  reviewed_at: string | null;
  reviewed_by: string | null;
};

export const adminProspectsAPI = {
  list: async (params?: {
    status?: string;
    band?: string;
    batch_id?: string;
    min_score?: number;
    limit?: number;
    offset?: number;
  }) =>
    api
      .get('/api/admin/prospects', { params: params || {} })
      .then((r) => r.data as { total: number; limit: number; offset: number; prospects: ProspectRow[] }),
  get: async (prospectId: string) =>
    api.get(`/api/admin/prospects/${prospectId}`).then((r) => r.data as ProspectRow),
  ingestBatch: async (payload: { prospects: ProspectSeedItem[]; enable_web_search: boolean }) =>
    api
      .post('/api/admin/prospects/batch', payload)
      .then(
        (r) =>
          r.data as {
            batch_id: string;
            queued: number;
            skipped_duplicates: number;
            duplicate_domains: string[];
            enable_web_search: boolean;
            estimated_web_search_cost_usd: number;
          },
      ),
  remove: async (prospectId: string) =>
    api.delete(`/api/admin/prospects/${prospectId}`).then((r) => r.data as { deleted: string }),
  triage: async (prospectId: string, decision: 'approved' | 'maybe' | 'rejected') =>
    api
      .post(`/api/admin/prospects/${prospectId}/triage`, { decision })
      .then((r) => r.data as ProspectRow),
  // Track B: convert an approved prospect into a live tenant (company + HR seat + welcome).
  onboard: async (
    prospectId: string,
    payload: { hr_email: string; hr_name?: string; reason?: string; send_welcome?: boolean },
  ): Promise<{ ok: boolean; company_id?: string; company_name?: string; hr_email?: string; invite_sent?: boolean; already_onboarded?: boolean }> =>
    api
      .post<{ ok: boolean; company_id?: string; company_name?: string; hr_email?: string; invite_sent?: boolean; already_onboarded?: boolean }>(
        `/api/admin/prospects/${prospectId}/onboard`, payload,
      )
      .then((r) => r.data),
  reenrich: async (prospectId: string, enableWebSearch: boolean) =>
    api
      .post(`/api/admin/prospects/${prospectId}/reenrich`, { enable_web_search: enableWebSearch })
      .then((r) => r.data as ProspectRow),
  reenrichFailed: async (enableWebSearch: boolean) =>
    api
      .post('/api/admin/prospects/reenrich-failed', { enable_web_search: enableWebSearch })
      .then(
        (r) =>
          r.data as {
            reenriched: number;
            enable_web_search: boolean;
            estimated_web_search_cost_usd: number;
          },
      ),
  costEstimate: async (prospectCount: number) =>
    api
      .get('/api/admin/prospects/cost-estimate', { params: { prospect_count: prospectCount } })
      .then(
        (r) =>
          r.data as {
            prospect_count: number;
            tavily_cost_per_query_usd: number;
            estimated_web_search_cost_usd: number;
            notes: string;
          },
      ),
  exportCsvUrl: (status: string = 'approved') =>
    `${API_BASE_URL}/api/admin/prospects/export.csv?status=${encodeURIComponent(status)}`,
};

// Admin Leads API (admin only) — audos-P1
export interface LeadRow {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  company_domain: string | null;
  source: string;
  status: string;
  tags: string[];
  message: string | null;
  utm_source: string | null;
  utm_campaign: string | null;
  created_at: string;
  updated_at: string;
  matched_prospect: boolean;
}

export interface LeadStats {
  total: number;
  new_this_week: number;
  by_status: Record<string, number>;
}

export const adminLeadsAPI = {
  list: async (params?: { status?: string; search?: string; limit?: number }) =>
    api
      .get('/api/admin/leads', { params: params || {} })
      .then((r) => r.data as { total: number; leads: LeadRow[] }),
  get: async (id: string) =>
    api.get(`/api/admin/leads/${id}`).then((r) => r.data as LeadRow),
  patch: async (id: string, patch: { status?: string; tags?: string[] }) =>
    api.patch(`/api/admin/leads/${id}`, patch).then((r) => r.data as LeadRow),
  stats: async () => api.get('/api/admin/leads/stats').then((r) => r.data as LeadStats),
};

export const leadCaptureAPI = {
  submit: async (payload: {
    email: string; first_name?: string; last_name?: string;
    company_domain?: string; message?: string; source: string;
    utm_source?: string; utm_campaign?: string;
  }) =>
    api.post('/api/public/lead-capture', payload).then((r) => r.data as { id: string; matched_prospect: boolean }),
};

// Admin recommendations debug (admin only)
export const adminRecommendationsAPI = {
  getDebug: async (assignmentId: string, serviceCategory: string) => {
    const response = await api.get<unknown>('/api/admin/recommendations/debug', {
      params: { assignment_id: assignmentId, service_category: serviceCategory },
    });
    return response.data;
  },
};

// Admin Resources CMS API
export const adminResourcesAPI = {
  getCounts: async (): Promise<Record<string, number>> => api.get<Record<string, number>>('/api/admin/resources/counts').then((r) => r.data),
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
  }): Promise<{ items: unknown[]; total: number }> => api.get<{ items: unknown[]; total: number }>('/api/admin/resources', { params }).then((r) => r.data),
  getResource: async (id: string) => api.get<unknown>(`/api/admin/resources/${id}`).then((r) => r.data),
  createResource: async (payload: Record<string, unknown>) =>
    api.post<unknown>('/api/admin/resources', payload).then((r) => r.data),
  updateResource: async (id: string, payload: Record<string, unknown>) =>
    api.put<unknown>(`/api/admin/resources/${id}`, payload).then((r) => r.data),
  submitForReview: async (id: string) =>
    api.post<unknown>(`/api/admin/resources/${id}/submit-for-review`).then((r) => r.data),
  approveResource: async (id: string, notes?: string) =>
    api.post<unknown>(`/api/admin/resources/${id}/approve`, { notes }).then((r) => r.data),
  publishResource: async (id: string) =>
    api.post<unknown>(`/api/admin/resources/${id}/publish`).then((r) => r.data),
  unpublishResource: async (id: string) =>
    api.post<unknown>(`/api/admin/resources/${id}/unpublish`).then((r) => r.data),
  archiveResource: async (id: string) =>
    api.post<unknown>(`/api/admin/resources/${id}/archive`).then((r) => r.data),
  restoreResource: async (id: string) =>
    api.post<unknown>(`/api/admin/resources/${id}/restore`).then((r) => r.data),
  // [AIQ-1333] Soft-delete a draft/archived resource (server enforces the status guard).
  deleteResource: async (id: string) =>
    api.delete<{ ok: boolean; id: string }>(`/api/admin/resources/${id}`).then((r) => r.data),
  getResourceAudit: async (id: string, limit?: number) =>
    api.get<unknown>(`/api/admin/resources/${id}/audit`, { params: { limit } }).then((r) => r.data),
  getGlobalAuditLog: async (params?: { entity_type?: string; limit?: number; offset?: number }) =>
    api.get<unknown>('/api/admin/resources/audit-log', { params }).then((r) => r.data),
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
  }): Promise<{ items: unknown[]; total: number }> => api.get<{ items: unknown[]; total: number }>('/api/admin/resources/events', { params }).then((r) => r.data),
  getEvent: async (id: string) => api.get<unknown>(`/api/admin/resources/events/${id}`).then((r) => r.data),
  createEvent: async (payload: Record<string, unknown>) =>
    api.post<unknown>('/api/admin/resources/events', payload).then((r) => r.data),
  updateEvent: async (id: string, payload: Record<string, unknown>) =>
    api.put<unknown>(`/api/admin/resources/events/${id}`, payload).then((r) => r.data),
  publishEvent: async (id: string) =>
    api.post<unknown>(`/api/admin/resources/events/${id}/publish`).then((r) => r.data),
  archiveEvent: async (id: string) =>
    api.post<unknown>(`/api/admin/resources/events/${id}/archive`).then((r) => r.data),
  submitEventForReview: async (id: string) =>
    api.post<unknown>(`/api/admin/resources/events/${id}/submit-for-review`).then((r) => r.data),
  approveEvent: async (id: string, notes?: string) =>
    api.post<unknown>(`/api/admin/resources/events/${id}/approve`, { notes }).then((r) => r.data),
  unpublishEvent: async (id: string) =>
    api.post<unknown>(`/api/admin/resources/events/${id}/unpublish`).then((r) => r.data),
  restoreEvent: async (id: string) =>
    api.post<unknown>(`/api/admin/resources/events/${id}/restore`).then((r) => r.data),
  getEventAudit: async (id: string, limit?: number) =>
    api.get<unknown>(`/api/admin/resources/events/${id}/audit`, { params: { limit } }).then((r) => r.data),
  listCategories: async (): Promise<{ categories: unknown[] }> => api.get<{ categories: unknown[] }>('/api/admin/resources/taxonomy/categories').then((r) => r.data),
  createCategory: async (payload: Record<string, unknown>) =>
    api.post<unknown>('/api/admin/resources/taxonomy/categories', payload).then((r) => r.data),
  updateCategory: async (id: string, payload: Record<string, unknown>) =>
    api.put<unknown>(`/api/admin/resources/taxonomy/categories/${id}`, payload).then((r) => r.data),
  deactivateCategory: async (id: string) =>
    api.delete<unknown>(`/api/admin/resources/taxonomy/categories/${id}`).then((r) => r.data),
  listTags: async (tag_group?: string): Promise<{ tags: unknown[] }> =>
    api.get<{ tags: unknown[] }>('/api/admin/resources/taxonomy/tags', { params: { tag_group } }).then((r) => r.data),
  createTag: async (payload: Record<string, unknown>) =>
    api.post<unknown>('/api/admin/resources/taxonomy/tags', payload).then((r) => r.data),
  updateTag: async (id: string, payload: Record<string, unknown>) =>
    api.put<unknown>(`/api/admin/resources/taxonomy/tags/${id}`, payload).then((r) => r.data),
  listSources: async (): Promise<{ sources: unknown[] }> => api.get<{ sources: unknown[] }>('/api/admin/resources/taxonomy/sources').then((r) => r.data),
  createSource: async (payload: Record<string, unknown>) =>
    api.post<unknown>('/api/admin/resources/taxonomy/sources', payload).then((r) => r.data),
  updateSource: async (id: string, payload: Record<string, unknown>) =>
    api.put<unknown>(`/api/admin/resources/taxonomy/sources/${id}`, payload).then((r) => r.data),
};

// [P1-2] Admin Form Templates API — catalog of official government forms.
// Backend: backend/app/routers/admin_form_templates.py
export interface FormTemplate {
  id: string;
  code: string;
  name: string;
  country: string;
  authority_code: string | null;
  authority_name: string | null;
  category: string | null;
  original_pdf_url: string | null;
  version: string;
  fields: Array<Record<string, unknown>>;
  trigger_rules: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export type FormTemplateCreate = Omit<FormTemplate, 'id' | 'created_at' | 'updated_at'> & {
  // All optional except code/name/country — backend supplies defaults.
  authority_code?: string | null;
  authority_name?: string | null;
  category?: string | null;
  original_pdf_url?: string | null;
  version?: string;
  fields?: Array<Record<string, unknown>>;
  trigger_rules?: Record<string, unknown>;
};

export type FormTemplateUpdate = Partial<Omit<FormTemplate, 'id' | 'created_at' | 'updated_at'>>;

export const adminFormTemplatesAPI = {
  list: async (params?: {
    country?: string;
    category?: string;
    code?: string;
    limit?: number;
    offset?: number;
  }): Promise<FormTemplate[]> =>
    api.get<FormTemplate[]>('/api/admin/form-templates', { params }).then((r) => r.data),

  get: async (id: string): Promise<FormTemplate> =>
    api.get<FormTemplate>(`/api/admin/form-templates/${id}`).then((r) => r.data),

  create: async (payload: FormTemplateCreate): Promise<FormTemplate> =>
    api.post<FormTemplate>('/api/admin/form-templates', payload).then((r) => r.data),

  /**
   * PATCH — two modes:
   *  - In-place: omit `version` (or pass the current value) → row is mutated.
   *  - Version bump: pass a NEW `version` → a new row is inserted carrying the
   *    merged values; the old row is preserved so historical case_forms keep
   *    pointing at it. The returned row is the new one.
   */
  update: async (id: string, payload: FormTemplateUpdate): Promise<FormTemplate> =>
    api.patch<FormTemplate>(`/api/admin/form-templates/${id}`, payload).then((r) => r.data),
};

// Admin Staging Review API (admin-only)
export const adminStagingAPI = {
  getDashboard: () => api.get<unknown>('/api/admin/staging/dashboard').then((r) => r.data),
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
  }): Promise<{ items: unknown[]; total: number }> => api.get<{ items: unknown[]; total: number }>('/api/admin/staging/resources', { params }).then((r) => r.data),
  getResourceCandidate: (id: string) =>
    api.get<unknown>(`/api/admin/staging/resources/${id}`).then((r) => r.data),
  getResourceCandidateMatches: (id: string) =>
    api.get<unknown>(`/api/admin/staging/resources/${id}/matches`).then((r) => r.data),
  approveResourceAsNew: (id: string, reason?: string) =>
    api.post<unknown>(`/api/admin/staging/resources/${id}/approve-new`, { reason }).then((r) => r.data),
  mergeResource: (
    id: string,
    payload: {
      target_resource_id: string;
      merge_mode?: string;
      fields_to_merge?: string[];
      reason?: string;
    }
  ) => api.post<unknown>(`/api/admin/staging/resources/${id}/merge`, payload).then((r) => r.data),
  rejectResource: (id: string, reason?: string) =>
    api.post<unknown>(`/api/admin/staging/resources/${id}/reject`, { reason }).then((r) => r.data),
  markResourceDuplicate: (
    id: string,
    payload: {
      duplicate_of_candidate_id?: string;
      duplicate_of_live_resource_id?: string;
      reason?: string;
    }
  ) => api.post<unknown>(`/api/admin/staging/resources/${id}/mark-duplicate`, payload).then((r) => r.data),
  ignoreResource: (id: string, reason?: string) =>
    api.post<unknown>(`/api/admin/staging/resources/${id}/ignore`, { reason }).then((r) => r.data),
  restoreResourceToReview: (id: string) =>
    api.post<unknown>(`/api/admin/staging/resources/${id}/restore-review`).then((r) => r.data),
  listEventCandidates: (params?: {
    status?: string;
    country_code?: string;
    city_name?: string;
    event_type?: string;
    trust_tier?: string;
    search?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ items: unknown[]; total: number }> => api.get<{ items: unknown[]; total: number }>('/api/admin/staging/events', { params }).then((r) => r.data),
  getEventCandidate: (id: string) =>
    api.get<unknown>(`/api/admin/staging/events/${id}`).then((r) => r.data),
  getEventCandidateMatches: (id: string) =>
    api.get<unknown>(`/api/admin/staging/events/${id}/matches`).then((r) => r.data),
  approveEventAsNew: (id: string, reason?: string) =>
    api.post<unknown>(`/api/admin/staging/events/${id}/approve-new`, { reason }).then((r) => r.data),
  mergeEvent: (
    id: string,
    payload: {
      target_event_id: string;
      merge_mode?: string;
      fields_to_merge?: string[];
      reason?: string;
    }
  ) => api.post<unknown>(`/api/admin/staging/events/${id}/merge`, payload).then((r) => r.data),
  rejectEvent: (id: string, reason?: string) =>
    api.post<unknown>(`/api/admin/staging/events/${id}/reject`, { reason }).then((r) => r.data),
  markEventDuplicate: (
    id: string,
    payload: {
      duplicate_of_candidate_id?: string;
      duplicate_of_live_event_id?: string;
      reason?: string;
    }
  ) => api.post<unknown>(`/api/admin/staging/events/${id}/mark-duplicate`, payload).then((r) => r.data),
  ignoreEvent: (id: string, reason?: string) =>
    api.post<unknown>(`/api/admin/staging/events/${id}/ignore`, { reason }).then((r) => r.data),
  restoreEventToReview: (id: string) =>
    api.post<unknown>(`/api/admin/staging/events/${id}/restore-review`).then((r) => r.data),
};

// Admin Freshness & Crawl API (admin-only)
export const adminFreshnessAPI = {
  getOverview: () => api.get<unknown>('/api/admin/freshness/overview').then((r) => r.data),
  getCountries: () => api.get<{ items: Record<string, unknown>[]; total?: number }>('/api/admin/freshness/countries').then((r) => r.data),
  getCities: (params?: { country_code?: string }) =>
    api.get<{ items: Record<string, unknown>[]; total?: number }>('/api/admin/freshness/cities', { params }).then((r) => r.data),
  getSources: () => api.get<{ items: Record<string, unknown>[]; total?: number }>('/api/admin/freshness/sources').then((r) => r.data),
  getSourcePages: () => api.get<{ items: Record<string, unknown>[]; total?: number }>('/api/admin/freshness/source-pages').then((r) => r.data),
  refreshFreshness: () => api.post<unknown>('/api/admin/freshness/refresh').then((r) => r.data),
  listSchedules: (params?: { is_active?: boolean; limit?: number }) =>
    api.get<{ items: Record<string, unknown>[]; total?: number }>('/api/admin/crawl/schedules', { params }).then((r) => r.data),
  getDueSchedules: () => api.get<unknown>('/api/admin/crawl/schedules/due').then((r) => r.data),
  getSchedule: (id: string) => api.get<unknown>(`/api/admin/crawl/schedules/${id}`).then((r) => r.data),
  createSchedule: (payload: Record<string, unknown>) =>
    api.post<unknown>('/api/admin/crawl/schedules', payload).then((r) => r.data),
  updateSchedule: (id: string, payload: Record<string, unknown>) =>
    api.put<unknown>(`/api/admin/crawl/schedules/${id}`, payload).then((r) => r.data),
  pauseSchedule: (id: string) => api.post<unknown>(`/api/admin/crawl/schedules/${id}/pause`).then((r) => r.data),
  resumeSchedule: (id: string) => api.post<unknown>(`/api/admin/crawl/schedules/${id}/resume`).then((r) => r.data),
  triggerSchedule: (id: string) => api.post<unknown>(`/api/admin/crawl/schedules/${id}/trigger`).then((r) => r.data),
  processDueSchedules: () => api.post<unknown>('/api/admin/crawl/process-due').then((r) => r.data),
  triggerCrawl: (payload: { source_name?: string; country_code?: string; city_name?: string; content_domain?: string }) =>
    api.post<unknown>('/api/admin/crawl/trigger', payload).then((r) => r.data),
  listJobRuns: (params?: { schedule_id?: string; status?: string; limit?: number; offset?: number }) =>
    api.get<{ items: Record<string, unknown>[]; total?: number }>('/api/admin/crawl/job-runs', { params }).then((r) => r.data),
  getJobRun: (id: string) => api.get<unknown>(`/api/admin/crawl/job-runs/${id}`).then((r) => r.data),
  listDocumentChanges: (params?: {
    job_run_id?: string;
    source_name?: string;
    change_type?: string;
    since?: string;
    limit?: number;
    offset?: number;
  }) => api.get<{ items: Record<string, unknown>[]; total?: number }>('/api/admin/changes/documents', { params }).then((r) => r.data),
  getDocumentChange: (id: string) => api.get<unknown>(`/api/admin/changes/documents/${id}`).then((r) => r.data),
  getStaleResources: (params?: { country_code?: string; city_name?: string; limit?: number }) =>
    api.get<{ items: Record<string, unknown>[]; total?: number }>('/api/admin/changes/live-stale-resources', { params }).then((r) => r.data),
  getStaleEvents: (params?: { country_code?: string; city_name?: string; limit?: number }) =>
    api.get<{ items: Record<string, unknown>[]; total?: number }>('/api/admin/changes/live-stale-events', { params }).then((r) => r.data),
};

// P2-02d — admin material-change review queue (approve before users are notified).
export const sourceChangeReviewAPI = {
  listPending: (params?: { limit?: number; offset?: number }) =>
    api.get<{ items: unknown[]; total?: number }>('/api/admin/source-change-reviews', { params }).then((r) => r.data),
  approve: (id: string) =>
    api.post<unknown>(`/api/admin/source-change-reviews/${id}/approve`).then((r) => r.data),
  reject: (id: string, note?: string) =>
    api.post<unknown>(`/api/admin/source-change-reviews/${id}/reject`, { note }).then((r) => r.data),
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
  }) => api.get<{ items: unknown[]; total?: number }>('/api/admin/review-queue', { params }).then((r) => r.data),
  getStats: () => api.get<unknown>('/api/admin/review-queue/stats').then((r) => r.data),
  getAssignees: (limit?: number) =>
    api.get<unknown>('/api/admin/review-queue/assignees', { params: { limit } }).then((r) => r.data),
  getItem: (id: string) => api.get<unknown>(`/api/admin/review-queue/${id}`).then((r) => r.data),
  getActivity: (id: string, limit?: number) =>
    api.get<unknown>(`/api/admin/review-queue/${id}/activity`, { params: { limit } }).then((r) => r.data),
  assign: (id: string, assigneeUserId: string) =>
    api.post<unknown>(`/api/admin/review-queue/${id}/assign`, { assignee_user_id: assigneeUserId }).then((r) => r.data),
  claim: (id: string) => api.post<unknown>(`/api/admin/review-queue/${id}/claim`).then((r) => r.data),
  unassign: (id: string) => api.post<unknown>(`/api/admin/review-queue/${id}/unassign`).then((r) => r.data),
  setStatus: (id: string, status: string, note?: string) =>
    api.post<unknown>(`/api/admin/review-queue/${id}/status`, { status, note }).then((r) => r.data),
  defer: (id: string, dueAt?: string, note?: string) =>
    api.post<unknown>(`/api/admin/review-queue/${id}/defer`, { due_at: dueAt, note }).then((r) => r.data),
  resolve: (id: string, resolutionSummary?: string) =>
    api.post<unknown>(`/api/admin/review-queue/${id}/resolve`, { resolution_summary: resolutionSummary }).then((r) => r.data),
  reopen: (id: string, note?: string) =>
    api.post<unknown>(`/api/admin/review-queue/${id}/reopen`, { note }).then((r) => r.data),
  updateNotes: (id: string, notes: string) =>
    api.patch<unknown>(`/api/admin/review-queue/${id}/notes`, { notes }).then((r) => r.data),
  bulkAssign: (itemIds: string[], assigneeUserId: string) =>
    api.post<unknown>('/api/admin/review-queue/bulk-assign', { item_ids: itemIds, assignee_user_id: assigneeUserId }).then((r) => r.data),
  bulkStatus: (itemIds: string[], status: string, note?: string) =>
    api.post<unknown>('/api/admin/review-queue/bulk-status', { item_ids: itemIds, status, note }).then((r) => r.data),
  backfill: () => api.post<unknown>('/api/admin/review-queue/backfill').then((r) => r.data),
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
  }) => api.get<{ items: unknown[]; total?: number }>('/api/admin/notifications', { params }).then((r) => r.data),
  getStats: () => api.get<unknown>('/api/admin/notifications/stats').then((r) => r.data),
  getFeed: (params?: { limit?: number; critical_first?: boolean }) =>
    api.get<unknown>('/api/admin/notifications/feed', { params }).then((r) => r.data),
  getOne: (id: string) => api.get<unknown>(`/api/admin/notifications/${id}`).then((r) => r.data),
  getEvents: (id: string, limit?: number) =>
    api.get<unknown>(`/api/admin/notifications/${id}/events`, { params: { limit } }).then((r) => r.data),
  acknowledge: (id: string) => api.post<unknown>(`/api/admin/notifications/${id}/acknowledge`).then((r) => r.data),
  resolve: (id: string, reason?: string) =>
    api.post<unknown>(`/api/admin/notifications/${id}/resolve`, null, { params: { reason } }).then((r) => r.data),
  suppress: (id: string, until?: string) =>
    api.post<unknown>(`/api/admin/notifications/${id}/suppress`, null, { params: { until } }).then((r) => r.data),
  reopen: (id: string, reason?: string) =>
    api.post<unknown>(`/api/admin/notifications/${id}/reopen`, null, { params: { reason } }).then((r) => r.data),
  recompute: () => api.post<unknown>('/api/admin/notifications/recompute').then((r) => r.data),
  sync: () => api.post<unknown>('/api/admin/notifications/sync').then((r) => r.data),
};

// Admin Ops Analytics API (admin-only)
export const adminOpsAnalyticsAPI = {
  getSlaOverview: (params?: { country_code?: string; days?: number }) =>
    api.get<unknown>('/api/admin/ops/sla/overview', { params }).then((r) => r.data),
  getWorkflowOverview: (params?: { country_code?: string; days?: number }) =>
    // The aggregate event counts are nested under `events` (alongside period_days/rates).
    api.get<{ events?: { case_created?: number; rfq_created?: number; recommendations_generated?: number; quote_received?: number } }>(
      '/api/admin/workflow/overview',
      { params },
    ).then((r) => r.data),
  getQueueBacklog: (params?: { country_code?: string }) =>
    api.get<unknown>('/api/admin/ops/queue/backlog', { params }).then((r) => r.data),
  getQueueBreaches: (params?: { country_code?: string; limit?: number }) =>
    api.get<unknown>('/api/admin/ops/queue/breaches', { params }).then((r) => r.data),
  getReviewerWorkload: () => api.get<unknown>('/api/admin/ops/reviewers/workload').then((r) => r.data),
  getDestinations: () => api.get<unknown>('/api/admin/ops/destinations').then((r) => r.data),
  /** Top destinations selected by users across all relocation cases (request-driven, not ops backlog). */
  getTopDestinationsByRequest: (params?: { limit?: number }) =>
    api.get<unknown>('/api/admin/ops/destinations/requests', { params }).then((r) => r.data),
  getNotificationMetrics: (params?: { days?: number }) =>
    api.get<unknown>('/api/admin/ops/notifications', { params }).then((r) => r.data),
  getBottlenecks: () => api.get<unknown>('/api/admin/ops/bottlenecks').then((r) => r.data),
};

// Admin Marketing Analytics API (admin-only, pre-signup acquisition funnel)
export interface MarketingFunnel {
  period_days: number;
  events: { landing_page_view: number; landing_cta_click: number; lead_captured: number };
  rates: { cta_rate_pct: number; capture_rate_pct: number };
  daily: { date: string; landing_page_view: number; landing_cta_click: number; lead_captured: number }[];
}

export const adminMarketingAnalyticsAPI = {
  funnel: async (days = 30) =>
    api.get('/api/admin/marketing-analytics/funnel', { params: { days } }).then((r) => r.data as MarketingFunnel),
};

// Admin Collaboration API (admin-only, internal threads)
export const adminCollaborationAPI = {
  getThread: (targetType: string, targetId: string) =>
    api.get<unknown>('/api/admin/collaboration/threads/by-target', { params: { target_type: targetType, target_id: targetId } }).then((r) => r.data),
  getOrCreateThread: (targetType: string, targetId: string, title?: string) =>
    api.post<unknown>('/api/admin/collaboration/threads/by-target', null, {
      params: { target_type: targetType, target_id: targetId, title: title || undefined },
    }).then((r) => r.data),
  getSummary: (targetType: string, targetId: string) =>
    api.get<ThreadSummariesResult>('/api/admin/collaboration/threads/summary', { params: { target_type: targetType, target_id: targetId } }).then((r) => r.data),
  getSummariesBatch: (targets: { target_type: string; target_id: string }[]) =>
    api.post<ThreadSummariesResult>('/api/admin/collaboration/threads/summaries', { targets }).then((r) => r.data),
  getThreadById: (threadId: string) =>
    api.get<unknown>(`/api/admin/collaboration/threads/${threadId}`).then((r) => r.data),
  getComments: (threadId: string) =>
    api.get<unknown>(`/api/admin/collaboration/threads/${threadId}/comments`).then((r) => r.data),
  createComment: (threadId: string, body: string, parentCommentId?: string) =>
    api.post<unknown>(`/api/admin/collaboration/threads/${threadId}/comments`, { body, parent_comment_id: parentCommentId }).then((r) => r.data),
  editComment: (commentId: string, body: string) =>
    api.patch<unknown>(`/api/admin/collaboration/comments/${commentId}`, { body }).then((r) => r.data),
  deleteComment: (commentId: string) =>
    api.delete<unknown>(`/api/admin/collaboration/comments/${commentId}`).then((r) => r.data),
  resolveThread: (threadId: string, note?: string) =>
    api.post<unknown>(`/api/admin/collaboration/threads/${threadId}/resolve`, null, { params: { note } }).then((r) => r.data),
  reopenThread: (threadId: string) =>
    api.post<unknown>(`/api/admin/collaboration/threads/${threadId}/reopen`).then((r) => r.data),
  closeThread: (threadId: string) =>
    api.post<unknown>(`/api/admin/collaboration/threads/${threadId}/close`).then((r) => r.data),
  markRead: (threadId: string, lastCommentId?: string) =>
    api.post<unknown>(`/api/admin/collaboration/threads/${threadId}/read`, null, { params: { last_comment_id: lastCommentId } }).then((r) => r.data),
  getUnreadCount: () =>
    api.get<unknown>('/api/admin/collaboration/notifications/unread-count').then((r) => r.data),
};

export const requirementsAPI = {
  getSufficiency: async (caseId: string): Promise<{ missing_fields?: string[]; compute_status?: string; message?: string }> => {
    const response = await api.get<{ missing_fields?: string[]; compute_status?: string; message?: string }>('/api/requirements/sufficiency', { params: { case_id: caseId } });
    return response.data;
  },
};

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

interface CreateQuoteRequestResponse {
  id: string;
  case_id: string;
  status: string;
  created_at: string;
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
  getAssignmentsOverview: async (): Promise<{ linked: unknown[]; pending: unknown[] }> => {
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

  createQuoteRequest: async (payload: {
    case_id: string;
    service_categories: string[];
    notes?: string;
    budget_range?: string;
  }): Promise<CreateQuoteRequestResponse> => {
    const response = await api.post<CreateQuoteRequestResponse>('/api/employee/quote-requests', payload);
    return response.data;
  },

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
  createRfq: async (
    caseId: string,
    items: Array<{ service_key: string; requirements: Record<string, unknown> }>,
    supplierIds: string[]
  ): Promise<{ ok: boolean; rfq: { id: string; rfq_ref: string } }> => {
    const response = await api.post<{ ok: boolean; rfq: { id: string; rfq_ref: string } }>('/api/rfqs', { case_id: caseId, items, supplier_ids: supplierIds });
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
  acceptQuote: async (rfqId: string, quoteId: string): Promise<{ ok: boolean; quote: QuoteDetail }> => {
    const response = await api.patch<{ ok: boolean; quote: QuoteDetail }>(`/api/rfqs/${rfqId}/quotes/${quoteId}/accept`);
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

// ── Provider Status Grid types (AIQ-14) ───────────────────────────────────────

export type GridCellStatus = 'on-track' | 'at-risk' | 'blocked' | 'complete' | 'not-assigned';

export type CoordinationStatus = 'not-started' | 'in-progress' | 'at-risk' | 'complete';

export interface ProviderGridCells {
  housing: GridCellStatus;
  immigration: GridCellStatus;
  shipping: GridCellStatus;
  other: GridCellStatus;
}

export interface ProviderGridRow {
  case_id: string;
  employee_name: string;
  employee_identifier: string;
  dest_country: string | null;
  move_date: string | null;
  coordination_status: CoordinationStatus;
  cells: ProviderGridCells;
}

export interface ProviderGridResponse {
  rows: ProviderGridRow[];
  total: number;
}

export interface CommandCenterCaseRow {
  id: string;
  caseId?: string | null;
  employeeIdentifier: string;
  employeeRole?: string | null;
  originCountry?: string | null;
  destCountry?: string | null;
  status: string;
  riskStatus: 'green' | 'yellow' | 'red' | string;
  tasksDonePercent: number;
  budgetLimit?: number | null;
  budgetEstimated?: number | null;
  nextDeadline?: string | null;
  targetMoveDate?: string | null;
  ownerName?: string | null;
  updatedAt?: string | null;
  /** Best-available visa surrogate (wizard.move_type → contract_type →
   *  assignment_type). Null when none of those are set. */
  visaLabel?: string | null;
  /** Derived household composition string: "Solo" / "Partner" / "N kids" /
   *  "Partner + N kids". Null when wizard family fields weren't answered. */
  household?: string | null;
  hasSpouse?: boolean | null;
  childCount?: number | null;
  /** W2-2 timeline SLA: on_track | at_risk | overdue | null. */
  slaStatus?: 'on_track' | 'at_risk' | 'overdue' | string | null;
  /** Signed days to the target move date (negative = past). */
  daysUntilMove?: number | null;
}

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
    const response = await api.get<{ preferred: Array<Record<string, unknown>> }>('/api/hr/preferred-suppliers', { params });
    return response.data;
  },
  add: async (payload: {
    supplier_id: string;
    service_category?: string;
    priority_rank?: number;
    notes?: string;
  }) => {
    const response = await api.post<unknown>('/api/hr/preferred-suppliers', payload);
    return response.data;
  },
  remove: async (supplierId: string, serviceCategory?: string) => {
    const params = serviceCategory ? { service_category: serviceCategory } : {};
    const response = await api.delete<unknown>(`/api/hr/preferred-suppliers/${supplierId}`, { params });
    return response.data;
  },
};

export const hrPolicyAPI = {
  list: async (params?: { status?: string; companyEntity?: string }): Promise<{ policies: unknown[] }> => {
    const response = await api.get<{ policies: unknown[] }>('/api/hr/policies', { params: params || {} });
    return response.data;
  },
  get: async (policyId: string): Promise<unknown> => {
    const response = await api.get<unknown>(`/api/hr/policies/${policyId}`);
    return response.data;
  },
  create: async (policy: Record<string, unknown>): Promise<{ policyId: string; policy: unknown }> => {
    const response = await api.post<{ policyId: string; policy: unknown }>('/api/hr/policies', policy);
    return response.data;
  },
  update: async (policyId: string, policy: Record<string, unknown>): Promise<unknown> => {
    const response = await api.put<unknown>(`/api/hr/policies/${policyId}`, policy);
    return response.data;
  },
  upload: async (file: File): Promise<{ policyId: string; policy: unknown }> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post<{ policyId: string; policy: unknown }>('/api/hr/policies/upload', formData, { timeout: 120_000 });
    return response.data;
  },
  delete: async (policyId: string): Promise<void> => {
    await api.delete<unknown>(`/api/hr/policies/${policyId}`);
  },
};

/** Structured Compensation & Allowance matrix (policy_configs / versions / benefits). */
export const policyConfigMatrixAPI = {
  hrGet: async (companyId?: string): Promise<Record<string, unknown>> => {
    const response = await api.get<Record<string, unknown>>('/api/hr/policy-config', {
      params: companyId ? { companyId } : {},
    });
    return response.data;
  },
  hrPostDraft: async (companyId?: string): Promise<Record<string, unknown>> => {
    const response = await api.post<Record<string, unknown>>('/api/hr/policy-config/draft', {}, {
      params: companyId ? { companyId } : {},
      // Seeding/cloning a draft writes the full benefit matrix (~90 rows for a
      // multi-tier policy) — override the 12s default per the B13 convention.
      timeout: 120_000,
    });
    return response.data;
  },
  hrPutDraft: async (body: Record<string, unknown>, companyId?: string): Promise<Record<string, unknown>> => {
    const response = await api.put<Record<string, unknown>>('/api/hr/policy-config/draft', body, {
      params: companyId ? { companyId } : {},
      // Destructive replace of the whole matrix (~90 rows + audit rows) can
      // exceed the 12s default; override per the B13 convention.
      timeout: 120_000,
    });
    return response.data;
  },
  /**
   * AIQ-1415 — Natural-Language Policy Builder. Read-only: turns a free-text
   * policy description into a CANDIDATE config-matrix `categories` body for
   * confirm-before-save. Never persists — saving goes through hrPutDraft after
   * the HR user approves the preview. An LLM call can exceed the 12s default.
   */
  hrGenerate: async (text: string, companyId?: string): Promise<Record<string, unknown>> => {
    const response = await api.post<Record<string, unknown>>('/api/hr/policy-config/generate', { text }, {
      params: companyId ? { companyId } : {},
      timeout: 120_000,
    });
    return response.data;
  },
  hrPublish: async (body: Record<string, unknown> | undefined, companyId?: string): Promise<Record<string, unknown>> => {
    const response = await api.post<Record<string, unknown>>('/api/hr/policy-config/publish', body ?? {}, {
      params: companyId ? { companyId } : {},
      // Publish also rebuilds the RAG index (OpenAI embeddings over all chunks),
      // which can take well over 12s; override per the B13 convention.
      timeout: 120_000,
    });
    return response.data;
  },
  hrHistory: async (companyId?: string): Promise<{ versions: unknown[] }> => {
    const response = await api.get<{ versions: unknown[] }>('/api/hr/policy-config/history', {
      params: companyId ? { companyId } : {},
    });
    return response.data;
  },
  hrPublished: async (companyId?: string): Promise<Record<string, unknown>> => {
    const response = await api.get<Record<string, unknown>>('/api/hr/policy-config/published', {
      params: companyId ? { companyId } : {},
    });
    return response.data;
  },
  hrGetVersion: async (versionId: string, companyId?: string): Promise<Record<string, unknown>> => {
    const response = await api.get<Record<string, unknown>>(`/api/hr/policy-config/versions/${encodeURIComponent(versionId)}`, {
      params: companyId ? { companyId } : {},
    });
    return response.data;
  },
  /**
   * List admin-curated starter templates. Metadata only
   * — { templates: [{ key, label, description }] }.
   */
  hrListTemplates: async (): Promise<{ templates: Array<{ key: string; label: string; description: string }> }> => {
    const response = await api.get<{ templates: Array<{ key: string; label: string; description: string }> }>('/api/hr/policy-config/templates');
    return response.data;
  },
  /**
   * Apply a starter template to the company's draft. Body:
   *   { template_key, replace_existing_draft? }
   * On success returns the fresh working payload. On 409
   * ("draft_has_rows") the UI should offer to retry with
   * replace_existing_draft=true.
   */
  hrApplyTemplate: async (
    body: { template_key: string; replace_existing_draft?: boolean },
    companyId?: string
  ): Promise<Record<string, unknown>> => {
    const response = await api.post<Record<string, unknown>>('/api/hr/policy-config/draft/apply-template', body, {
      params: companyId ? { companyId } : {},
    });
    return response.data;
  },
  /**
   * Draft-vs-Live snapshot for the HR Policy "Draft vs Live" section.
   * Returns {live, draft, diff: {added, removed, changed, unchanged_count, summary}}.
   */
  hrDiff: async (companyId?: string): Promise<Record<string, unknown>> => {
    const response = await api.get<Record<string, unknown>>('/api/hr/policy-config/diff', {
      params: companyId ? { companyId } : {},
    });
    return response.data;
  },
  /**
   * Revert one benefit row of the current draft back to the live version.
   * Body: { benefit_key, targeting_signature }. Returns the refreshed diff.
   */
  hrRevertRow: async (
    body: { benefit_key: string; targeting_signature: string },
    companyId?: string
  ): Promise<Record<string, unknown>> => {
    const response = await api.post<Record<string, unknown>>('/api/hr/policy-config/draft/revert-row', body, {
      params: companyId ? { companyId } : {},
    });
    return response.data;
  },

  /**
   * Import an uploaded policy document's LLM-extracted benefits into the
   * company's config-matrix draft as `extracted_llm` rows (AIQ-873 bridge).
   * Body: { policy_id } — the policy_documents id returned by the upload flow.
   * Existing manual/template/extracted rows are never clobbered. Returns the
   * imported matrix keys, keys skipped as already-present, and extraction keys
   * that had no canonical mapping (for manual entry).
   */
  hrImportExtraction: async (
    body: { policy_id: string },
    companyId?: string
  ): Promise<{ imported: string[]; skipped_existing: string[]; unmapped: string[]; version_id: string }> => {
    const response = await api.post<{ imported: string[]; skipped_existing: string[]; unmapped: string[]; version_id: string }>(
      '/api/hr/policy-config/draft/import-extraction',
      body,
      {
        params: companyId ? { companyId } : {},
        // Merging the extracted matrix rewrites the draft row set; override the
        // 12s default per the B13 convention (same as hrPutDraft/hrPublish).
        timeout: 120_000,
      },
    );
    return response.data;
  },

  adminGet: async (companyId: string): Promise<Record<string, unknown>> => {
    const response = await api.get<Record<string, unknown>>('/api/admin/policy-config', { params: { companyId } });
    return response.data;
  },
  /**
   * POST /api/admin/policy-config/draft — ensures a company draft (idempotent if draft exists).
   * Backend clones from latest published when present, otherwise seeds canonical rows.
   * (Product names like “clone published” / “create empty” map to this single route today.)
   */
  adminPostDraft: async (companyId: string): Promise<Record<string, unknown>> => {
    const response = await api.post<Record<string, unknown>>('/api/admin/policy-config/draft', {}, { params: { companyId } });
    return response.data;
  },
  adminPutDraft: async (companyId: string, body: Record<string, unknown>): Promise<Record<string, unknown>> => {
    const response = await api.put<Record<string, unknown>>('/api/admin/policy-config/draft', body, { params: { companyId } });
    return response.data;
  },
  adminPublish: async (companyId: string, body?: Record<string, unknown>): Promise<Record<string, unknown>> => {
    const response = await api.post<Record<string, unknown>>('/api/admin/policy-config/publish', body ?? {}, { params: { companyId } });
    return response.data;
  },
  adminHistory: async (companyId: string): Promise<{ versions: unknown[] }> => {
    const response = await api.get<{ versions: unknown[] }>('/api/admin/policy-config/history', { params: { companyId } });
    return response.data;
  },
  adminPublished: async (companyId: string): Promise<Record<string, unknown>> => {
    const response = await api.get<Record<string, unknown>>('/api/admin/policy-config/published', { params: { companyId } });
    return response.data;
  },
  adminGetVersion: async (companyId: string, versionId: string): Promise<Record<string, unknown>> => {
    const response = await api.get<Record<string, unknown>>(`/api/admin/policy-config/versions/${encodeURIComponent(versionId)}`, {
      params: { companyId },
    });
    return response.data;
  },

  employeeGet: async (params?: {
    assignmentId?: string;
    caseId?: string;
    assignmentType?: string;
    familyStatus?: string;
  }): Promise<Record<string, unknown>> => {
    const response = await api.get<Record<string, unknown>>('/api/employee/policy-config', {
      params: {
        assignmentId: params?.assignmentId,
        caseId: params?.caseId,
        assignmentType: params?.assignmentType,
        familyStatus: params?.familyStatus,
      },
    });
    return response.data;
  },

  /** HR / Admin: compare provider monetary estimates to published normalized caps. */
  hrCompareProviderEstimates: async (
    body: {
      assignment_type?: string;
      family_status?: string;
      estimates: Array<{ benefit_key: string; amount: number; currency: string }>;
    },
    companyId?: string
  ): Promise<{ metadata?: Record<string, unknown>; results: unknown[] }> => {
    const response = await api.post<{ metadata?: Record<string, unknown>; results: unknown[] }>('/api/hr/policy-config/caps/compare', body, {
      params: companyId ? { companyId } : {},
    });
    return response.data;
  },
};

export const companyPolicyAPI = {
  list: async (params?: { company_id?: string }): Promise<{ policies: CompanyPolicySummary[] }> => {
    const response = await api.get<{ policies: CompanyPolicySummary[] }>('/api/company-policies', { params });
    return response.data;
  },
  getLatest: async (): Promise<CompanyPolicyResult> => {
    const response = await api.get<CompanyPolicyResult>('/api/company-policies/latest');
    return response.data;
  },
  getById: async (policyId: string): Promise<CompanyPolicyResult> => {
    const response = await api.get<CompanyPolicyResult>(`/api/company-policies/${policyId}`);
    return response.data;
  },
  getDownloadUrl: async (policyId: string): Promise<{ ok?: boolean; url?: string }> => {
    const response = await api.get<{ ok?: boolean; url?: string }>(`/api/company-policies/${policyId}/download-url`);
    return response.data;
  },
  upload: async (file: File, meta: { title: string; version?: string; effective_date?: string }): Promise<{ policy: unknown }> => {
    const form = new FormData();
    form.append('file', file);
    form.append('title', meta.title);
    if (meta.version) form.append('version', meta.version);
    if (meta.effective_date) form.append('effective_date', meta.effective_date);
    const response = await api.post<{ policy: unknown }>('/api/company-policies/upload', form, { timeout: 120_000 });
    return response.data;
  },
  extract: async (policyId: string): Promise<CompanyPolicyResult> => {
    const response = await api.post<CompanyPolicyResult>(`/api/policies/${policyId}/extract`, undefined, { timeout: 120_000 });
    return response.data;
  },
  saveBenefits: async (policyId: string, benefits: unknown[]): Promise<CompanyPolicyResult> => {
    const response = await api.put<CompanyPolicyResult>(`/api/company-policies/${policyId}/benefits`, { benefits });
    return response.data;
  },
  getNormalized: async (
    policyId: string,
    opts?: { detail?: 'full' | 'summary'; includeReadiness?: boolean }
  ): Promise<NormalizedPolicyResponse> => {
    const params: Record<string, string | boolean> = {};
    if (opts?.detail === 'summary') params.detail = 'summary';
    if (opts?.includeReadiness === false) params.include_readiness = 'false';
    const response = await api.get<NormalizedPolicyResponse>(`/api/company-policies/${policyId}/normalized`, {
      params: Object.keys(params).length ? params : undefined,
    });
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
      metadata_json?: Record<string, unknown>;
    }
  ): Promise<{ benefit_rule: unknown }> => {
    const response = await api.patch<{ benefit_rule: unknown }>(`/api/company-policies/${policyId}/benefits/${benefitRuleId}`, body);
    return response.data;
  },
  /** HR override layer — does not change extracted Layer-2 rows; adjusts effective entitlements. */
  patchHrBenefitOverride: async (
    policyId: string,
    versionId: string,
    benefitRuleId: string,
    body: {
      service_visibility?: 'force_included' | 'force_excluded' | null;
      amount_value_override?: number | null;
      amount_unit_override?: string | null;
      currency_override?: string | null;
      duration_quantity_json?: { quantity?: number; unit?: string } | null;
      approval_required_override?: boolean | null;
      hr_notes?: string | null;
    }
  ): Promise<{ hr_override: unknown }> => {
    const response = await api.patch<{ hr_override: unknown }>(
      `/api/company-policies/${policyId}/versions/${versionId}/benefits/${benefitRuleId}/hr-override`,
      body
    );
    return response.data;
  },
  deleteHrBenefitOverride: async (
    policyId: string,
    versionId: string,
    benefitRuleId: string
  ): Promise<{ ok?: boolean }> => {
    const response = await api.delete<{ ok?: boolean }>(
      `/api/company-policies/${policyId}/versions/${versionId}/benefits/${benefitRuleId}/hr-override`
    );
    return response.data;
  },
  patchVersionStatus: async (
    policyId: string,
    versionId: string,
    body: { status: string }
  ): Promise<{ version: unknown }> => {
    const response = await api.patch<{ version: unknown }>(`/api/company-policies/${policyId}/versions/${versionId}/status`, body);
    return response.data;
  },
  /** Update latest version status - avoids version_id mismatch 404s */
  patchLatestVersionStatus: async (policyId: string, body: { status: string }): Promise<{ version: unknown }> => {
    const response = await api.patch<{ version: unknown }>(`/api/company-policies/${policyId}/versions/latest/status`, body);
    return response.data;
  },
  publishVersion: async (policyId: string, versionId: string): Promise<{ version: unknown }> => {
    const response = await api.post<{ version: unknown }>(`/api/company-policies/${policyId}/versions/${versionId}/publish`);
    return response.data;
  },
  /**
   * Archive a live (published) version. Employees stop seeing its benefits
   * immediately; the row stays queryable for audit history. HR can then
   * import a new document or start from a template, review, and publish
   * a fresh version.
   * Returns `{ version, already }`. When `already` is a non-null string
   * the version was not in "published" status — the call was a no-op.
   */
  unpublishVersion: async (
    policyId: string,
    versionId: string
  ): Promise<{ version: unknown; already: string | null }> => {
    const response = await api.post<{ version: unknown; already: string | null }>(`/api/company-policies/${policyId}/versions/${versionId}/unpublish`);
    return response.data;
  },
  /**
   * Canonical (document-normalized) policy diff for a company — sibling
   * of policyConfigMatrixAPI.hrDiff which covers the compensation
   * matrix. Auto-resolves the primary policy_id server-side; returns
   * has_policy=false when the company hasn't uploaded a canonical
   * policy yet (frontend renders a neutral empty state in that case).
   */
  hrCanonicalDiffForCompany: async (
    companyId?: string
  ): Promise<Record<string, unknown>> => {
    const response = await api.get<Record<string, unknown>>('/api/hr/canonical-policy/diff', {
      params: companyId ? { companyId } : {},
    });
    return response.data;
  },
  /** Publish latest version - avoids version_id mismatch 404s */
  publishLatestVersion: async (policyId: string): Promise<{ version: unknown }> => {
    const response = await api.post<{ version: unknown }>(`/api/company-policies/${policyId}/versions/latest/publish`);
    return response.data;
  },
  patchExclusion: async (
    policyId: string,
    exclId: string,
    body: { description?: string; review_status?: string }
  ): Promise<{ exclusion: unknown }> => {
    const response = await api.patch<{ exclusion: unknown }>(`/api/company-policies/${policyId}/exclusions/${exclId}`, body);
    return response.data;
  },
  patchCondition: async (
    policyId: string,
    condId: string,
    body: { condition_value_json?: Record<string, unknown>; review_status?: string }
  ): Promise<{ condition: unknown }> => {
    const response = await api.patch<{ condition: unknown }>(`/api/company-policies/${policyId}/conditions/${condId}`, body);
    return response.data;
  },
  /** Platform starter baseline (only when company has no policy yet). */
  initializeFromTemplate: async (body: {
    template_key: string;
    comparison_ready_structure?: boolean;
  }): Promise<{
    ok?: boolean;
    policy_id?: string;
    policy_version_id?: string;
    version_status?: string;
    benefit_rules_created?: number;
    message?: string;
  }> => {
    const response = await api.post<{ ok?: boolean; policy_id?: string; policy_version_id?: string; version_status?: string; benefit_rules_created?: number; message?: string }>('/api/hr/company-policy/initialize-from-template', body);
    return response.data;
  },
};

/** HR aggregate review payload (document + policy + draft + readiness). */
export const hrPolicyReviewAPI = {
  get: async (params: { document_id?: string; policy_id?: string }): Promise<Record<string, unknown>> => {
    const response = await api.get<Record<string, unknown>>('/api/hr/policy-review', { params });
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
    const response = await api.get<PolicyDocumentsHealth>('/api/hr/policy-documents/health');
    return response.data;
  },
  list: async (params?: { company_id?: string }): Promise<{ documents: PolicyDocument[] }> => {
    const response = await api.get<{ documents: PolicyDocument[] }>('/api/hr/policy-documents', { params });
    return response.data;
  },
  get: async (docId: string): Promise<{ document: PolicyDocument }> => {
    const response = await api.get<{ document: PolicyDocument }>(`/api/hr/policy-documents/${docId}`);
    return response.data;
  },
  upload: async (file: File, companyId?: string | null): Promise<{ ok: boolean; document: PolicyDocument; error_code?: string; message?: string; request_id?: string; processing_queued?: boolean }> => {
    // Backend expects field name "file". When admin is viewing a company's policy workspace, pass company_id so the doc is stored for that company.
    const form = new FormData();
    form.append('file', file);
    const params = companyId && companyId.trim() ? { company_id: companyId.trim() } : undefined;
    if (import.meta.env.DEV) {
      logger.info('policy upload selected file', {
        name: file?.name,
        size: file?.size,
        type: file?.type,
        isFile: file instanceof File,
        companyId: companyId ?? undefined,
      });
      logger.info('policy upload form keys', [...form.keys()]);
    }
    const response = await api.post<{ ok: boolean; document: PolicyDocument; error_code?: string; message?: string; request_id?: string; processing_queued?: boolean }>('/api/hr/policy-documents/upload', form, { params, timeout: 120_000 });
    return response.data;
  },
  reprocess: async (docId: string): Promise<{ document: PolicyDocument }> => {
    const response = await api.post<{ document: PolicyDocument }>(`/api/hr/policy-documents/${docId}/reprocess`, undefined, { timeout: 120_000 });
    return response.data;
  },
  listClauses: async (docId: string, clauseType?: string): Promise<{ clauses: PolicyDocumentClause[] }> => {
    const params = clauseType ? { clause_type: clauseType } : {};
    const response = await api.get<{ clauses: PolicyDocumentClause[] }>(`/api/hr/policy-documents/${docId}/clauses`, { params });
    return response.data;
  },
  getClause: async (docId: string, clauseId: string): Promise<{ clause: PolicyDocumentClause }> => {
    const response = await api.get<{ clause: PolicyDocumentClause }>(`/api/hr/policy-documents/${docId}/clauses/${clauseId}`);
    return response.data;
  },
  patchClause: async (
    docId: string,
    clauseId: string,
    body: { clause_type?: string; title?: string; hr_override_notes?: string }
  ): Promise<{ clause: PolicyDocumentClause }> => {
    const response = await api.patch<{ clause: PolicyDocumentClause }>(
      `/api/hr/policy-documents/${docId}/clauses/${clauseId}`,
      body
    );
    return response.data;
  },
  normalize: async (
    docId: string
  ): Promise<{
    ok?: boolean;
    normalized?: boolean;
    publishable?: boolean;
    published?: boolean;
    outcome?: string;
    /** Stable semantic code for success path (draft-only, published, publish blocked). */
    normalization_result_code?: string;
    readiness_status?: string;
    readiness_issues?: Array<Record<string, unknown>>;
    publish_block_code?: string;
    publish_block_detail?: string;
    comparison_readiness_code?: string;
    rule_candidates_summary?: {
      benefit_rules?: number;
      exclusions?: number;
      evidence_requirements?: number;
      conditions?: number;
      draft_rule_candidates?: number;
    };
    policy_id: string;
    policy_version_id: string;
    summary: unknown;
    version?: Record<string, unknown>;
    input_repairs?: Array<Record<string, string>>;
    policy_readiness?: {
      normalization_readiness?: { status?: string; issues?: Array<Record<string, unknown>> };
      publish_readiness?: { status?: string; issues?: Array<Record<string, unknown>> };
      comparison_readiness?: { status?: string; issues?: Array<Record<string, unknown>> };
    };
    normalization_draft?: Record<string, unknown> | null;
  }> => {
    const response = await api.post<PolicyNormalizeResult>(`/api/hr/policy-documents/${docId}/normalize`, undefined, { timeout: 120_000 });
    return response.data;
  },
  bulkDelete: async (documentIds: string[]): Promise<{ ok: boolean; deleted: number; skipped?: Array<{ id: string; reason: string }> }> => {
    const response = await api.post<{ ok: boolean; deleted: number; skipped?: Array<{ id: string; reason: string }> }>('/api/hr/policy-documents/bulk-delete', { document_ids: documentIds });
    return response.data;
  },
};

export const resourcesAPI = {
  /** Legacy: uses /api/resources/country (rkg_resources). Kept for backward compatibility. */
  getCountryResources: async (
    assignmentId: string,
    filters?: Record<string, string | number | boolean | null>
  ): Promise<{
    profile: Record<string, unknown>;
    context?: Record<string, unknown>;
    hints: { priorities: string[]; recommendations: string[] };
    sections: Array<{ key: string; title: string; content: unknown }>;
    events?: unknown[];
    recommended?: unknown[];
    filters_applied: Record<string, unknown>;
  }> => {
    const params: Record<string, string> = { assignment_id: assignmentId };
    if (filters && Object.keys(filters).length) {
      params.filters = JSON.stringify(filters);
    }
    const response = await api.get<CountryResourcesResult>('/api/resources/country', { params });
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
    const response = await api.get<import('../types').ResourcesPagePayload>('/api/resources/page', { params });
    return response.data;
  },

  getContext: async (assignmentOrCaseId: string): Promise<import('../types').ResourceContext> => {
    const response = await api.get<import('../types').ResourceContext>('/api/resources/context', {
      params: { assignment_id: assignmentOrCaseId },
    });
    return response.data;
  },

  /**
   * Returns the catalog destination allowlist — every (city, country) pair the
   * platform supports for AI scraping. Used by HrResourcesPreview to build a
   * live dropdown instead of a hardcoded 12-country list (B14 fix).
   */
  getDestinations: async (): Promise<Array<{ city: string; country: string }>> => {
    const response = await api.get<Array<{ city: string; country: string }>>('/api/hr/resources/destinations');
    return Array.isArray(response.data) ? response.data : [];
  },

  /** HR-only preview: same payload shape as getPage, but driven by an explicit
   *  destination + persona instead of a real assignment. */
  getHrPreviewPage: async (
    params: {
      countryCode: string;
      countryName?: string | null;
      city?: string | null;
      familyType?: 'single' | 'couple' | 'family';
      relocationType?: 'short_term' | 'long_term' | 'permanent';
      hasChildren?: boolean | null;
    },
    filters?: Record<string, string | number | boolean | null>
  ): Promise<import('../types').ResourcesPagePayload> => {
    const q: Record<string, string> = { country_code: params.countryCode };
    if (params.countryName) q.country_name = params.countryName;
    if (params.city) q.city = params.city;
    if (params.familyType) q.family_type = params.familyType;
    if (params.relocationType) q.relocation_type = params.relocationType;
    if (params.hasChildren != null) q.has_children = String(params.hasChildren);
    if (filters && Object.keys(filters).length) q.filters = JSON.stringify(filters);
    const response = await api.get<import('../types').ResourcesPagePayload>('/api/hr/resources/page', { params: q });
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
    const response = await api.get<{ resources: Record<string, unknown>[] }>('/api/resources', { params });
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
    const response = await api.get<{ events: import('../types').PublicEvent[] }>('/api/resources/events', { params });
    return response.data;
  },

  getRecommended: async (
    assignmentOrCaseId: string,
    limit = 10
  ): Promise<import('../types').RecommendationGroup> => {
    const response = await api.get<import('../types').RecommendationGroup>('/api/resources/recommended', {
      params: { assignment_id: assignmentOrCaseId, limit },
    });
    return response.data;
  },
};

export const dossierAPI = {
  getQuestions: async (caseId: string): Promise<DossierQuestionsResponse> => {
    const response = await api.get<DossierQuestionsResponse>('/api/dossier/questions', { params: { case_id: caseId } });
    return response.data;
  },
  saveAnswers: async (payload: { case_id: string; answers: Array<{ question_id?: string | null; case_question_id?: string | null; answer: unknown }> }): Promise<{ ok: boolean }> => {
    const response = await api.post<{ ok: boolean }>('/api/dossier/answers', payload);
    return response.data;
  },
  searchSuggestions: async (caseId: string): Promise<DossierSearchSuggestionsResponse> => {
    const response = await api.post<DossierSearchSuggestionsResponse>('/api/dossier/search-suggestions', { case_id: caseId });
    return response.data;
  },
  addCaseQuestion: async (payload: { case_id: string; question_text: string; answer_type: string; options?: string[] | null; is_mandatory?: boolean; sources?: DossierSource[] }): Promise<unknown> => {
    const response = await api.post<unknown>('/api/dossier/case-questions', payload);
    return response.data;
  },
};

export const guidanceAPI = {
  generate: async (caseId: string, mode?: 'demo' | 'strict'): Promise<{
    guidance_pack_id: string;
    guidance_mode?: 'demo' | 'strict';
    pack_hash?: string;
    rule_set?: unknown[];
    plan: unknown;
    checklist: unknown;
    markdown: string;
    sources: Array<{ doc_id: string; title?: string; url: string; publisher?: string }>;
    not_covered: string[];
    coverage?: unknown;
  }> => {
    const response = await api.post<GuidanceGenerateResult>('/api/guidance/generate', { case_id: caseId, mode });
    return response.data;
  },
  getLatest: async (caseId: string): Promise<unknown> => {
    const response = await api.get<unknown>('/api/guidance/latest', { params: { case_id: caseId } });
    return response.data;
  },
  explain: async (caseId: string): Promise<unknown> => {
    const response = await api.get<unknown>('/api/guidance/explain', { params: { case_id: caseId } });
    return response.data;
  },
};

// ── Policy Builder API ────────────────────────────────────────────────────────
export interface PolicyTemplateCategoryOut {
  category_id: string;
  code: string;
  display_name: string;
  cap_value: number;
  cap_unit: string;
  cap_currency: string;
  benchmark_source: string;
}

export interface PolicyTemplateTierOut {
  tier: string;
  tier_order: number;
  categories: PolicyTemplateCategoryOut[];
}

export interface PolicyTemplatesResponse {
  ok: boolean;
  tiers: PolicyTemplateTierOut[];
}

export const policyBuilderAPI = {
  getTemplates: (): Promise<PolicyTemplatesResponse> =>
    api.get<PolicyTemplatesResponse>('/api/policy/templates').then((r) => r.data),
};

export default api;

/**
 * [B20] Shared 401 redirect for the native-fetch API helpers (apiGet/apiPost/
 * apiPatch/apiPut/apiDelete). These bypass the Axios interceptor, so they each
 * need to call this when they receive a 401. Mirrors the behaviour in the Axios
 * response interceptor above: clear all relopass_* auth keys and hard-navigate
 * to the login page with a session-expired reason parameter.
 */
function handle401Redirect(response: Response): void {
  if (response.status !== 401) return;
  try {
    clearAuthItems();
  } catch {
    // ignore — localStorage may be unavailable
  }
  const path = window.location.pathname || '';
  if (!path.startsWith('/auth') && path !== '/' && path !== '') {
    window.location.href = '/auth?mode=login&reason=session_expired';
  }
}

function buildApiError(response: Response, bodyText: string) {
  let detail: unknown = bodyText;
  let message = bodyText || `${response.status} ${response.statusText}`;

  try {
    const parsed: unknown = JSON.parse(bodyText);
    const parsedDetail =
      parsed && typeof parsed === 'object' && 'detail' in parsed
        ? (parsed as Record<string, unknown>).detail
        : undefined;
    detail = parsedDetail ?? parsed;
    if (typeof detail === 'string') {
      message = detail;
    } else if (detail && typeof detail === 'object') {
      message = (detail as { message?: string }).message || JSON.stringify(detail);
    }
  } catch {
    // bodyText wasn't JSON
  }

  const err = new Error(message) as Error & { status?: number; detail?: unknown };
  err.status = response.status;
  err.detail = detail;
  return err;
}

function authHeaders(): Record<string, string> {
  const token = getAuthItem('relopass_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// Failed requests are recorded into ./requestLog (a lightweight module) so the feedback
// diagnostics snapshot can read them without importing this heavy client (which pulls
// api/supabase and breaks the jsdom test env). This file only writes via recordFailedRequest.

export async function apiGet<T>(path: string, opts?: { headers?: Record<string, string>; requestId?: string; signal?: AbortSignal }): Promise<T> {
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
      signal: opts?.signal,
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders(),
        ...(opts?.headers || {}),
        'X-Request-ID': requestId,
      },
    });
  } catch {
    recordFailedRequest('GET', pathOnly, 0, requestId);
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
    recordFailedRequest('GET', pathOnly, response.status, response.headers.get('X-Request-ID') ?? requestId);
    handle401Redirect(response); // [B20]
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
  body?: unknown,
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
    recordFailedRequest('POST', pathOnly, 0, requestId);
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
    recordFailedRequest('POST', pathOnly, response.status, response.headers.get('X-Request-ID') ?? requestId);
    handle401Redirect(response); // [B20]
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
  body?: unknown,
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
    recordFailedRequest('PATCH', pathOnly, 0, requestId);
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
    recordFailedRequest('PATCH', pathOnly, response.status, response.headers.get('X-Request-ID') ?? requestId);
    handle401Redirect(response); // [B20]
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

export async function apiPut<T>(
  path: string,
  body?: unknown,
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
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders(),
        ...(opts?.headers || {}),
        'X-Request-ID': requestId,
      },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    recordFailedRequest('PUT', pathOnly, 0, requestId);
    throw new Error('Unable to reach the server. Please check your connection and try again.');
  }
  if (!response.ok) {
    const text = await response.text();
    const tBody = typeof performance !== 'undefined' ? performance.now() : Date.now();
    recordRequestPerf({
      requestId,
      method: 'PUT',
      path: pathOnly,
      status: response.status,
      ok: false,
      durationHeadersMs: tBody - tStart,
      durationBodyMs: tBody - tStart,
      startedAt: tStart,
    });
    recordFailedRequest('PUT', pathOnly, response.status, response.headers.get('X-Request-ID') ?? requestId);
    handle401Redirect(response); // [B20]
    throw buildApiError(response, text);
  }
  const jsonStart = typeof performance !== 'undefined' ? performance.now() : Date.now();
  const data = (await response.json()) as T;
  const tEnd = typeof performance !== 'undefined' ? performance.now() : Date.now();
  recordRequestPerf({
    requestId,
    method: 'PUT',
    path: pathOnly,
    status: response.status,
    ok: true,
    durationHeadersMs: jsonStart - tStart,
    durationBodyMs: tEnd - tStart,
    startedAt: tStart,
  });
  return data;
}

export async function apiDelete<T>(
  path: string,
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
      method: 'DELETE',
      headers: {
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
      method: 'DELETE',
      path: pathOnly,
      status: response.status,
      ok: false,
      durationHeadersMs: tBody - tStart,
      durationBodyMs: tBody - tStart,
      startedAt: tStart,
    });
    handle401Redirect(response); // [B20]
    throw buildApiError(response, text);
  }
  const jsonStart = typeof performance !== 'undefined' ? performance.now() : Date.now();
  const text = await response.text();
  const data = (text ? JSON.parse(text) : null) as T;
  const tEnd = typeof performance !== 'undefined' ? performance.now() : Date.now();
  recordRequestPerf({
    requestId,
    method: 'DELETE',
    path: pathOnly,
    status: response.status,
    ok: true,
    durationHeadersMs: jsonStart - tStart,
    durationBodyMs: tEnd - tStart,
    startedAt: tStart,
  });
  return data;
}

// ── Specialist review API (AIQ-633) ───────────────────────────────────────────

export interface SpecialistReviewSubmitItem {
  step_id: string;
  decision: ReviewDecision;
  reason_code?: ReasonCode;
  original_step: AiStep;
  edited_step?: AiStep;
}

export const specialistReviewAPI = {
  getRoadmap: async (caseId: string): Promise<{ case_id: string; steps: AiStep[] }> => {
    const res = await api.get<{ case_id: string; steps: AiStep[] }>(`/api/internal/specialist-review/${caseId}`);
    return res.data;
  },
  submit: async (
    caseId: string,
    body: { decision: 'approved' | 'rejected'; notes?: string; items: SpecialistReviewSubmitItem[] },
  ): Promise<{ released_to_user: boolean; regeneration_requested: boolean }> => {
    const res = await api.post<{ released_to_user: boolean; regeneration_requested: boolean }>(`/api/internal/specialist-review/submit`, { case_id: caseId, ...body });
    return res.data;
  },
};
