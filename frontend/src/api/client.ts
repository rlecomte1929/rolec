import axios from 'axios';
import { getAuthItem } from '../utils/demo';
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

export const employeeAPI = {
  getCurrentAssignment: async (): Promise<{ assignment: any }> => {
    const response = await api.get('/api/employee/assignments/current');
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
