/**
 * Assignment debug - dev only
 * Verify case_assignments visibility. Uses backend (relopass_token) first to avoid JWT expiry.
 */

import api from './client';
import { getAuthItem } from '../utils/demo';
import { supabase } from './supabase';

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL;
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY;
const FALLBACK_ACCESS_TOKEN = import.meta.env.VITE_SUPABASE_ACCESS_TOKEN;

const isJwt = (v?: string | null) => typeof v === 'string' && v.split('.').length === 3;

async function getAccessToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession();
  let token = data?.session?.access_token || FALLBACK_ACCESS_TOKEN;
  if (token && isJwt(token)) return token;
  if (data?.session?.refresh_token) {
    const { data: refreshed } = await supabase.auth.refreshSession({ refresh_token: data.session.refresh_token });
    token = refreshed?.session?.access_token || null;
    if (token && isJwt(token)) return token;
  }
  return null;
}

/** Try backend (uses relopass_token). Returns null error on 401/403 to allow Supabase fallback. */
async function fetchViaBackend(assignmentId: string): Promise<{ data: GetAssignmentResult | null; error: string | null; fallback?: boolean }> {
  try {
    const res = await api.get<{ found: boolean; row?: GetAssignmentResult['row']; current_user_id?: string }>(
      `/api/debug/assignment-check?assignment_id=${encodeURIComponent(assignmentId)}`
    );
    const d = res.data;
    return { data: { found: d.found, row: d.row, current_user_id: d.current_user_id }, error: null };
  } catch (err: unknown) {
    const status = (err as { response?: { status?: number } })?.response?.status;
    if (status === 401 || status === 403) return { data: null, error: null, fallback: true };
    const msg = err instanceof Error ? err.message : 'Request failed';
    return { data: null, error: msg };
  }
}

async function fetchViaSupabase(assignmentId: string): Promise<{ data: GetAssignmentResult | null; error: string | null }> {
  try {
    const token = await getAccessToken();
    if (!token) return { data: null, error: 'Not authenticated. Sign in with Supabase.' };
    const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/get_assignment_by_id`, {
      method: 'POST',
      headers: {
        apikey: SUPABASE_ANON_KEY!,
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ p_assignment_id: assignmentId }),
    });
    const json = await res.json();
    if (!res.ok) {
      let msg = json?.message || json?.error || json?.details || `HTTP ${res.status}`;
      if (typeof msg !== 'string') msg = JSON.stringify(msg);
      if (msg.toLowerCase().includes('jwt expired') || msg.includes('PGRST301') || msg.includes('PGRST302')) {
        msg += ' Sign in with Supabase (e.g. /debug/auth) to refresh your session.';
      }
      return { data: null, error: msg };
    }
    return { data: json as GetAssignmentResult, error: null };
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Request failed';
    return { data: null, error: msg };
  }
}

export interface GetAssignmentResult {
  found: boolean;
  row?: {
    id: string;
    case_id: string;
    employee_user_id: string | null;
    hr_user_id: string;
    status: string;
    created_at: string;
    updated_at: string;
  };
  /** When from backend: current user id for match display */
  current_user_id?: string;
  error?: string;
}

export interface AssertLinksResult {
  found: boolean;
  matches_employee?: boolean;
  matches_hr?: boolean;
  employee_user_id?: string;
  hr_user_id?: string;
  error?: string;
}

export async function getAssignmentById(
  assignmentId: string
): Promise<{ data: GetAssignmentResult | null; error: string | null }> {
  if (getAuthItem('relopass_token')) {
    const backend = await fetchViaBackend(assignmentId);
    if (!backend.fallback) return { data: backend.data, error: backend.error };
  }
  return fetchViaSupabase(assignmentId);
}

export async function assertAssignmentLinks(
  assignmentId: string,
  expectedEmployeeUuid: string,
  expectedHrUuid: string
): Promise<{ data: AssertLinksResult | null; error: string | null }> {
  try {
    const token = await getAccessToken();
    if (!token) return { data: null, error: 'Not authenticated. Sign in with Supabase.' };
    const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/assert_assignment_links`, {
      method: 'POST',
      headers: {
        apikey: SUPABASE_ANON_KEY!,
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        p_assignment_id: assignmentId,
        p_expected_employee: expectedEmployeeUuid,
        p_expected_hr: expectedHrUuid,
      }),
    });
    const json = await res.json();
    if (!res.ok) {
      const msg = json?.message || json?.error || json?.details || `HTTP ${res.status}`;
      return { data: null, error: typeof msg === 'string' ? msg : JSON.stringify(msg) };
    }
    return { data: json as AssertLinksResult, error: null };
  } catch (err) {
    return { data: null, error: err instanceof Error ? err.message : 'Request failed' };
  }
}
