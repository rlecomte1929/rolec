/**
 * AIQ-37-B · Policy Builder API client
 * Typed wrappers for the /api/hr/policies endpoints (hr_policies.py).
 */
import type {
  RelocationPolicyJson,
  RelocationPolicyRow,
  PolicyVersionListResponse,
  ActivePolicyResponse,
  CreatePolicyVersionRequest,
} from '../types/relocationPolicy';
import { API_BASE_URL } from './client';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function authHeaders(): Record<string, string> {
  const token =
    localStorage.getItem('auth_token') ||
    sessionStorage.getItem('auth_token') ||
    '';
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

/** List all policy versions for the caller's org, newest first. */
export async function listPolicies(): Promise<PolicyVersionListResponse> {
  const res = await fetch(`${API_BASE_URL}/api/hr/policies`, {
    headers: authHeaders(),
  });
  return handleResponse<PolicyVersionListResponse>(res);
}

/** Get the currently active policy version (null if none). */
export async function getActivePolicy(): Promise<ActivePolicyResponse> {
  const res = await fetch(`${API_BASE_URL}/api/hr/policies/active`, {
    headers: authHeaders(),
  });
  return handleResponse<ActivePolicyResponse>(res);
}

/** Create a new (inactive) draft policy version. */
export async function createPolicy(
  body: CreatePolicyVersionRequest,
): Promise<{ ok: boolean; policy: RelocationPolicyRow }> {
  const res = await fetch(`${API_BASE_URL}/api/hr/policies`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  return handleResponse<{ ok: boolean; policy: RelocationPolicyRow }>(res);
}

/** Update label and/or json_schema of an existing draft version. */
export async function updatePolicy(
  policyId: string,
  body: { label?: string; json_schema?: RelocationPolicyJson },
): Promise<{ ok: boolean; policy: RelocationPolicyRow }> {
  const res = await fetch(`${API_BASE_URL}/api/hr/policies/${policyId}`, {
    method: 'PATCH',
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  return handleResponse<{ ok: boolean; policy: RelocationPolicyRow }>(res);
}

/** Atomically activate a policy version, deactivating the current active one. */
export async function activatePolicy(
  policyId: string,
): Promise<{ ok: boolean; policy: RelocationPolicyRow }> {
  const res = await fetch(
    `${API_BASE_URL}/api/hr/policies/${policyId}/activate`,
    {
      method: 'POST',
      headers: authHeaders(),
    },
  );
  return handleResponse<{ ok: boolean; policy: RelocationPolicyRow }>(res);
}
