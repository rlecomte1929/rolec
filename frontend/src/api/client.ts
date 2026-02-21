import axios from 'axios';
import { getAuthItem, clearAuthItems } from '../utils/demo';
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

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = getAuthItem('relopass_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Global 401 handler: clear session and redirect to auth (skip for login/register)
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const status = err?.response?.status;
    const url = err?.config?.url ?? '';
    const isAuthEndpoint = /\/api\/auth\/(login|register)$/.test(url);
    if (status === 401 && !isAuthEndpoint) {
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
  saveCompanyProfile: async (payload: { name: string; country?: string; size_band?: string; address?: string; phone?: string; hr_contact?: string }): Promise<any> => {
    const response = await api.post('/api/hr/company-profile', payload);
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
    decision: 'HR_APPROVED' | 'CHANGES_REQUESTED',
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
};

export const employeeAPI = {
  getCurrentAssignment: async (): Promise<{ assignment: any }> => {
    const response = await api.get('/api/employee/assignments/current');
    return response.data;
  },
  listMessages: async (): Promise<{ messages: any[] }> => {
    const response = await api.get('/api/employee/messages');
    return response.data;
  },
  claimAssignment: async (assignmentId: string, email: string): Promise<any> => {
    const response = await api.post(`/api/employee/assignments/${assignmentId}/claim`, { email });
    return response.data;
  },
  getNextQuestion: async (assignmentId: string): Promise<EmployeeJourneyResponse> => {
    const response = await api.get('/api/employee/journey/next-question', { params: { assignmentId } });
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

export async function apiGet<T>(path: string, opts?: { headers?: Record<string, string> }): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders(),
        ...(opts?.headers || {}),
      },
    });
  } catch {
    throw new Error('Unable to reach the server. Please check your connection and try again.');
  }
  if (!response.ok) {
    const text = await response.text();
    throw buildApiError(response, text);
  }
  return response.json() as Promise<T>;
}

export async function apiPost<T>(
  path: string,
  body?: any,
  opts?: { headers?: Record<string, string> }
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders(),
        ...(opts?.headers || {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error('Unable to reach the server. Please check your connection and try again.');
  }
  if (!response.ok) {
    const text = await response.text();
    throw buildApiError(response, text);
  }
  return response.json() as Promise<T>;
}

export async function apiPatch<T>(
  path: string,
  body?: any,
  opts?: { headers?: Record<string, string> }
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders(),
        ...(opts?.headers || {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error('Unable to reach the server. Please check your connection and try again.');
  }
  if (!response.ok) {
    const text = await response.text();
    throw buildApiError(response, text);
  }
  return response.json() as Promise<T>;
}
