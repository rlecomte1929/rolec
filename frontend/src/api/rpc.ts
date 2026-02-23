import { supabase } from './supabase';

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL;
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY;
const FALLBACK_ACCESS_TOKEN = import.meta.env.VITE_SUPABASE_ACCESS_TOKEN;

type RpcResult<T> = {
  data: T | null;
  error: string | null;
};

const isJwt = (value?: string | null) => typeof value === 'string' && value.split('.').length === 3;

const callRpc = async <T>(fn: string, params: Record<string, unknown>): Promise<RpcResult<T>> => {
  const session = await supabase.auth.getSession();
  const accessToken = session.data?.session?.access_token || FALLBACK_ACCESS_TOKEN;

  if (!accessToken || !isJwt(accessToken)) {
    return {
      data: null,
      error: 'Supabase access token missing or invalid. Set VITE_SUPABASE_ACCESS_TOKEN for local tests.',
    };
  }

  // Prefer direct REST call so we can use a dev-only access token if needed.
  if (SUPABASE_URL && SUPABASE_ANON_KEY) {
    try {
      const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/${fn}`, {
        method: 'POST',
        headers: {
          apikey: SUPABASE_ANON_KEY,
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(params),
      });
      const bodyText = await res.text();
      if (!res.ok) {
        let message = bodyText;
        try {
          const parsed = JSON.parse(bodyText);
          message = parsed?.message || parsed?.error || bodyText;
        } catch {
          // keep raw bodyText
        }
        const friendly =
          message.includes('Expected 3 parts in JWT')
            ? 'Supabase access token invalid. Set VITE_SUPABASE_ACCESS_TOKEN for local tests.'
            : message.includes('No suitable key') || message.includes('wrong key type')
              ? 'JWT verification failed. Token may be expired or project keys changed. Get a fresh access token from Supabase Auth.'
              : message;
        if (import.meta.env.DEV) {
          console.debug('RPC error', fn, friendly);
        }
        return { data: null, error: friendly };
      }
      const data = bodyText ? (JSON.parse(bodyText) as T) : null;
      return { data: data as T, error: null };
    } catch (err: any) {
      const message = err?.message || 'Unable to reach Supabase';
      if (import.meta.env.DEV) {
        console.debug('RPC error', fn, message);
      }
      return { data: null, error: message };
    }
  }

  // Fallback to supabase-js rpc if env vars are missing.
  const { data, error } = await supabase.rpc(fn, params);
  if (error) {
    if (import.meta.env.DEV) {
      console.debug('RPC error', fn, error.message);
    }
    return { data: null, error: error.message };
  }
  return { data: data as T, error: null };
};

export const transitionAssignment = async (
  assignmentId: string,
  action: 'EMPLOYEE_SUBMIT' | 'EMPLOYEE_UNSUBMIT' | 'HR_REOPEN',
  note?: string
) => {
  return callRpc<{ assignment_id: string; from_status: string; to_status: string }>(
    'transition_assignment',
    {
      p_assignment_id: assignmentId,
      p_action: action,
      p_note: note ?? null,
    }
  );
};

export const employeeUnsubmitAssignment = async (assignmentId: string) => {
  return transitionAssignment(assignmentId, 'EMPLOYEE_UNSUBMIT');
};

export const hrReopenAssignment = async (assignmentId: string, note?: string) => {
  return transitionAssignment(assignmentId, 'HR_REOPEN', note);
};

export const employeeSubmitAssignment = async (assignmentId: string) => {
  return transitionAssignment(assignmentId, 'EMPLOYEE_SUBMIT');
};

// Manual test checklist:
// 1) Call transitionAssignment with EMPLOYEE_SUBMIT from DRAFT.
// 2) Call transitionAssignment with EMPLOYEE_UNSUBMIT from EMPLOYEE_SUBMITTED.
// 3) Call transitionAssignment with HR_REOPEN from EMPLOYEE_SUBMITTED.
