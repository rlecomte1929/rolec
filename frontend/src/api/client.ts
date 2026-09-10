import axios, { type AxiosError } from 'axios';
import type {
  ApiErrorBody,
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
} from '../types';
import { signOutSupabase } from './supabaseAuth';

// VITE_API_URL:
//   - Development: leave unset so axios hits same-origin `/api` (Vite proxy → :8000)
//   - Production:   https://api.relopass.com      (via frontend/.env.production)
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

export type { PromptVersion, WinRate } from './suppliersApi';
export { suppliersAPI, promptsAPI } from './suppliersApi';

export type {
  ProspectSeedItem,
  ProspectRow,
  LeadRow,
  LeadStats,
  FormTemplate,
  FormTemplateCreate,
  FormTemplateUpdate,
  WorkflowFunnelStage,
  WorkflowFunnelResponse,
  AssistantTopicRow,
  AssistantTopicsResponse,
  MarketingFunnel,
} from './adminMiscApi';
export { adminProspectsAPI, adminLeadsAPI, leadCaptureAPI, adminResourcesAPI, adminFormTemplatesAPI, adminStagingAPI, adminFreshnessAPI, sourceChangeReviewAPI, adminReviewQueueAPI, adminNotificationsAPI, adminOpsAnalyticsAPI, adminMarketingAnalyticsAPI, adminCollaborationAPI } from './adminMiscApi';

export type {
  RequirementsComputeStatus,
  SupportingRequirement,
  RequirementsSufficiency,
} from './requirementsApi';
export { requirementsAPI } from './requirementsApi';

export type {
  OverrideReasonCategory,
  PayerView,
  QuoteCreatePayload,
  QuoteDetail,
  RfqCreateResult,
  RfqDetail,
  RfqRecommendation,
  RfqSummary,
  TimelineMilestone,
  TimelineResponse,
  TimelineTaskSummary,
} from './servicesApi';
export { servicesAPI, rfqAPI, vendorAPI, timelineAPI } from './servicesApi';

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

export { policyConfigMatrixAPI, companyPolicyAPI, hrPolicyReviewAPI, policyDocumentsAPI } from './policyApi';

export type { SpecialistReviewSubmitItem } from './miscApi';
export { resourcesAPI, dossierAPI, guidanceAPI, specialistReviewAPI } from './miscApi';

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
