import axios, { type AxiosError } from 'axios';
import type {
  ApiErrorBody,
  ServiceContextResult,
  CountryResourcesResult,
  GuidanceGenerateResult,
  ThreadSummariesResult,
} from './types';
import { getAuthItem, clearAuthItems } from '../utils/demo';
import { recordFailedRequest } from './requestLog';
import { env } from '../config/env';
import { getCurrentInteractionId, recordRequestPerf } from '../perf/perf';
import { swallow } from '../lib/errorTracking';
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
  DossierQuestionsResponse,
  DossierSearchSuggestionsResponse,
  DossierSource,
} from '../types';
import type { AiStep } from '../features/admin/specialist-review/RoadmapStepDiff';
import type { ReasonCode, ReviewDecision } from '../features/admin/specialist-review/reasonCodes';
import { signOutSupabase } from './supabaseAuth';
import type { EmployeeTask, EmployeeTaskListResponse } from './employeeApi';

// VITE_API_URL must be set for every environment:
//   - Development:  http://localhost:8000         (via frontend/.env.development)
//   - Production:   https://api.relopass.com      (via frontend/.env.production)
// Fallback keeps local dev working if .env.development is missing.
const API_BASE_URL: string = env.apiUrl;

export { API_BASE_URL };


// Create axios instance
export const api = axios.create({
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

export const cachedRequest = <T>(key: string, ttlMs: number, fetcher: () => Promise<T>): Promise<T> => {
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
  // [AIQ-1491] Exchange a verified Supabase Auth JWT (from a passkey/WebAuthn sign-in)
  // for a ReloPass session token — the merged bridge POST /api/auth/exchange-supabase-token
  // (auth.py). Never auto-provisions: 401 if no matching ReloPass user by email.
  exchangeSupabaseToken: async (accessToken: string): Promise<LoginResponse> => {
    const response = await api.post<LoginResponse>(
      '/api/auth/exchange-supabase-token',
      { access_token: accessToken },
      { timeout: AUTH_ENTRYPOINT_TIMEOUT },
    );
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


export type { TaskType, EmployeeTask, EmployeeTaskListResponse } from './employeeApi';
export { employeeAPI } from './employeeApi';

export type {
  CalibrationAlert,
  HrBacklogTask,
  HrBacklogResponse,
  CaseHealthFlag,
  ResolvedPolicyResponse,
  RecomputedPolicyResponse,
  AssignmentServicesResponse,
  CommandCenterKPIs,
  VendorPerformanceResponse,
  HrVendor,
  CaseVendorStatus,
  CaseVendorRow,
  ImmigrationRequirementsResponse,
  ImmigrationInterviewStatus,
  ImmigrationMilestonesResponse,
  ErasureRequestsResponse,
  ProcessErasureResponse,
  HrAnalyticsResponse,
  HrDraftCase,
  BenefitCandidateInput,
  OptimizeBenefitMixRequest,
  OptimizeBenefitMixResponse,
} from './hrApi';
export { CASE_VENDOR_STATUSES, hrAPI } from './hrApi';

// Company API (for header branding: HR and Employee)
export const companyAPI = {
  get: async (): Promise<{ company: { id?: string; name: string; logo_url?: string | null; [key: string]: unknown } | null }> => {
    return cachedRequest('company:get', 60_000, async () => {
      const response = await api.get<{ company: { id?: string; name: string; logo_url?: string | null; [key: string]: unknown } | null }>('/api/company');
      return response.data;
    });
  },
};


export type {
  AdminMobilityOperationalInspect,
  AdminCompanyDetailResponse,
  AdminRebuildTestCompanyGraphResponse,
  AdminMobilityCaseInspectResponse,
  PolicyWorkflowSummary,
  PolicyAnalysisResult,
} from './adminApi';
export { adminAPI } from './adminApi';


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
export interface WorkflowFunnelStage {
  stage: string;
  label: string;
  count: number;
  /** null for the first stage (no previous to convert from). */
  conversion_from_prev_pct: number | null;
  conversion_from_start_pct: number;
}
export interface WorkflowFunnelResponse {
  period_days: number;
  since: string;
  stages: WorkflowFunnelStage[];
}
export interface AssistantTopicRow {
  topic: string;
  asked: number;
  supported: number;
  unsupported: number;
  refusal: number;
  support_rate_pct: number;
  refusal_rate_pct: number;
}
export interface AssistantTopicsResponse {
  period_days: number;
  since: string;
  overall: {
    asked: number;
    supported: number;
    unsupported: number;
    refusal: number;
    support_rate_pct: number;
    refusal_rate_pct: number;
  };
  topics: AssistantTopicRow[];
}

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
  /** AIQ-1439: workflow conversion funnel (per-stage counts + conversion %). */
  getWorkflowFunnel: (params?: { days?: number }) =>
    api.get<WorkflowFunnelResponse>('/api/admin/workflow/funnel', { params }).then((r) => r.data),
  /** AIQ-1438: policy-assistant questions ranked by canonical topic. */
  getAssistantTopics: (params?: { days?: number; limit?: number }) =>
    api.get<AssistantTopicsResponse>('/api/admin/workflow/assistant-topics', { params }).then((r) => r.data),
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

export type {
  RequirementsComputeStatus,
  SupportingRequirement,
  RequirementsSufficiency,
} from './requirementsApi';
export { requirementsAPI } from './requirementsApi';

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

/** [AIQ-1516] The 5 categories HR must pick from when overriding the recommendation. */
export type OverrideReasonCategory =
  | 'employee_preference'
  | 'preferred_supplier'
  | 'negotiated_terms'
  | 'policy_exception'
  | 'other';

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

export { policyConfigMatrixAPI, companyPolicyAPI, hrPolicyReviewAPI, policyDocumentsAPI } from './policyApi';


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

  /**
   * AIQ-1581: LLM-generated "things to do" suggestions for a destination city.
   * City + country are non-personal. The backend is fail-soft (empty list on
   * generation failure), so this never throws for a missing feed.
   */
  getCityActivities: async (
    city: string,
    country: string
  ): Promise<import('../types').CityActivity[]> => {
    const response = await api.get<import('../types').CityActivitiesResponse>(
      '/api/resources/city-activities',
      { params: { city, country } }
    );
    return Array.isArray(response.data?.activities) ? response.data.activities : [];
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

export type {
  PolicyTemplateCategoryOut,
  PolicyTemplateTierOut,
  PolicyTemplatesResponse,
} from './policyBuilderApi';
export { policyBuilderAPI } from './policyBuilderApi';

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
  opts?: { headers?: Record<string, string>; requestId?: string; signal?: AbortSignal }
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
      signal: opts?.signal,
    });
  } catch (err) {
    // Re-throw AbortError so callers can handle their own timeouts with a clear message.
    if (err instanceof Error && err.name === 'AbortError') throw err;
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
