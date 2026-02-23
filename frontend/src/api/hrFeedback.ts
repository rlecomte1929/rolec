/**
 * HR Feedback on Employee case
 * Uses hr_feedback table + post_hr_feedback RPC (Supabase)
 */

import { supabase } from './supabase';

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL;
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY;
const FALLBACK_ACCESS_TOKEN = import.meta.env.VITE_SUPABASE_ACCESS_TOKEN;

const isJwt = (v?: string | null) => typeof v === 'string' && v.split('.').length === 3;

async function getAccessToken(): Promise<string | null> {
  const session = await supabase.auth.getSession();
  const token = session.data?.session?.access_token || FALLBACK_ACCESS_TOKEN;
  return token && isJwt(token) ? token : null;
}

async function fetchWithAuth(path: string, opts?: RequestInit) {
  const token = await getAccessToken();
  if (!token) {
    throw new Error('Supabase access token missing. Set VITE_SUPABASE_ACCESS_TOKEN for local tests.');
  }
  return fetch(`${SUPABASE_URL}${path}`, {
    ...opts,
    headers: {
      apikey: SUPABASE_ANON_KEY!,
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...opts?.headers,
    },
  });
}

export interface HrFeedbackRow {
  id: string;
  assignment_id: string;
  hr_user_id: string;
  employee_user_id: string | null;
  message: string;
  created_at: string;
}

/** List feedback for an assignment, newest first */
export async function getHrFeedback(
  assignmentId: string
): Promise<{ data: HrFeedbackRow[] | null; error: string | null }> {
  try {
    const path = `/rest/v1/hr_feedback?assignment_id=eq.${encodeURIComponent(assignmentId)}&order=created_at.desc`;
    const res = await fetchWithAuth(path);
    if (!res.ok) {
      const text = await res.text();
      let msg = text;
      try {
        const j = JSON.parse(text);
        msg = j.message || j.error || j.details || text;
      } catch {
        // keep text
      }
      return { data: null, error: msg };
    }
    const data = (await res.json()) as HrFeedbackRow[];
    return { data, error: null };
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Failed to load feedback';
    return { data: null, error: msg };
  }
}

/** Post feedback (HR only) - uses RPC so hr_user_id/employee_user_id are resolved server-side */
export async function postHrFeedback(
  assignmentId: string,
  message: string
): Promise<{ data: { id: string; created_at: string } | null; error: string | null }> {
  try {
    const token = await getAccessToken();
    if (!token) {
      return { data: null, error: 'Not authenticated' };
    }
    const res = await fetchWithAuth('/rest/v1/rpc/post_hr_feedback', {
      method: 'POST',
      body: JSON.stringify({
        p_assignment_id: assignmentId,
        p_message: message.trim(),
      }),
    });
    const json = (await res.json()) as { ok?: boolean; error?: string; id?: string; created_at?: string };
    if (!res.ok) {
      return { data: null, error: json?.error || `HTTP ${res.status}` };
    }
    if (json?.ok === false) {
      return { data: null, error: json?.error || 'Failed to post feedback' };
    }
    if (json?.ok === true && json?.id) {
      return {
        data: { id: json.id, created_at: json.created_at || new Date().toISOString() },
        error: null,
      };
    }
    return { data: null, error: 'Unexpected response from server' };
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Failed to send feedback';
    return { data: null, error: msg };
  }
}
