/**
 * Block 5: HR Review + Feedback
 * Supabase-backed feedback API (case_feedback table)
 */

import { supabase } from './supabase';

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL;
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY;
const FALLBACK_ACCESS_TOKEN = import.meta.env.VITE_SUPABASE_ACCESS_TOKEN as string | undefined;

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
  const res = await fetch(`${SUPABASE_URL}${path}`, {
    ...opts,
    headers: {
      apikey: SUPABASE_ANON_KEY,
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      Prefer: 'return=representation',
      ...opts?.headers,
    },
  });
  return res;
}

const errMessage = (err: unknown, fallback: string): string =>
  err instanceof Error ? err.message : fallback;

interface RestError {
  message?: string;
  error?: string;
  details?: string;
}

/** Extract a human message from a PostgREST error body, falling back to the raw text. */
const parseRestError = (text: string): string => {
  try {
    const j = JSON.parse(text) as RestError;
    return j.message || j.details || j.error || text;
  } catch {
    return text;
  }
};

export type FeedbackSection =
  | 'RELOCATION_BASICS'
  | 'EMPLOYEE_PROFILE'
  | 'FAMILY_MEMBERS'
  | 'ASSIGNMENT_CONTEXT'
  | 'OVERALL';

export interface CaseFeedbackRow {
  id: string;
  case_id: string;
  assignment_id: string;
  author_user_id: string;
  author_role: string;
  section: FeedbackSection;
  message: string;
  created_at_ts: string;
}

export const FEEDBACK_SECTIONS: { value: FeedbackSection; label: string }[] = [
  { value: 'ASSIGNMENT_CONTEXT', label: 'Assignment / Context' },
  { value: 'EMPLOYEE_PROFILE', label: 'Employee Profile' },
  { value: 'FAMILY_MEMBERS', label: 'Family Members' },
  { value: 'OVERALL', label: 'Overall' },
  { value: 'RELOCATION_BASICS', label: 'Relocation Basics' },
];

/** List feedback for an assignment, newest first */
export async function listFeedback(assignmentId: string): Promise<{ data: CaseFeedbackRow[] | null; error: string | null }> {
  try {
    const path = `/rest/v1/case_feedback?assignment_id=eq.${encodeURIComponent(assignmentId)}&order=created_at_ts.desc`;
    const res = await fetchWithAuth(path);
    if (!res.ok) {
      return { data: null, error: parseRestError(await res.text()) };
    }
    const data = (await res.json()) as CaseFeedbackRow[];
    return { data, error: null };
  } catch (err) {
    return { data: null, error: errMessage(err, 'Failed to load feedback') };
  }
}

/** Insert feedback (HR only) */
export async function insertFeedback(params: {
  caseId: string;
  assignmentId: string;
  section: FeedbackSection;
  message: string;
}): Promise<{ data: CaseFeedbackRow | null; error: string | null }> {
  try {
    const token = await getAccessToken();
    if (!token) {
      return { data: null, error: 'Not authenticated' };
    }
    const payload = {
      case_id: params.caseId,
      assignment_id: params.assignmentId,
      author_user_id: null as string | null,
      author_role: 'HR' as const,
      section: params.section,
      message: params.message.trim(),
    };
    const decoded = JSON.parse(atob(token.split('.')[1] ?? '')) as { sub?: string };
    payload.author_user_id = decoded.sub ?? null;

    const res = await fetchWithAuth('/rest/v1/case_feedback', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      return { data: null, error: parseRestError(await res.text()) };
    }
    const rows = (await res.json()) as CaseFeedbackRow[];
    return { data: rows?.[0] ?? null, error: null };
  } catch (err) {
    return { data: null, error: errMessage(err, 'Failed to send feedback') };
  }
}
