/**
 * Block 5: HR Review - Assigned cases from Supabase
 * case_assignments + wizard_cases
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
      ...opts?.headers,
    },
  });
  return res;
}

/** Decoded Supabase JWT claims we read (the `sub` is the auth user id). */
interface JwtClaims {
  sub?: string;
}

/** The wizard-case `draft_json` blob, narrowed to the fields these reviews read. */
interface WizardDraftBasics {
  originCity?: string;
  originCountry?: string;
  destCity?: string;
  destCountry?: string;
  targetMoveDate?: string;
}
interface WizardDraft {
  relocationBasics?: WizardDraftBasics;
  employeeProfile?: { fullName?: string };
  [key: string]: unknown;
}

/** A `wizard_cases` row as selected by getWizardCaseForReview (`select=*`). */
interface WizardCaseRow {
  draft_json?: string | null;
  origin_country?: string | null;
  origin_city?: string | null;
  dest_country?: string | null;
  dest_city?: string | null;
  target_move_date?: string | null;
}

const errMessage = (err: unknown, fallback: string): string =>
  err instanceof Error ? err.message : fallback;

const decodeUid = (token: string): string => {
  const decoded = JSON.parse(atob(token.split('.')[1] ?? '')) as JwtClaims;
  return decoded.sub ?? '';
};

const parseDraft = (raw?: string | null): WizardDraft => {
  try {
    return JSON.parse(raw || '{}') as WizardDraft;
  } catch {
    return {};
  }
};

export interface AssignedCaseForReview {
  id: string;
  case_id: string;
  caseName: string;
  origin: string;
  destination: string;
  targetMoveDate: string | null;
  lastUpdated: string | null;
}

/** List cases assigned to the current HR user (from case_assignments + wizard_cases) */
export async function listAssignedCasesForReview(): Promise<{
  data: AssignedCaseForReview[] | null;
  error: string | null;
}> {
  try {
    const token = await getAccessToken();
    if (!token) {
      return { data: null, error: 'Not authenticated' };
    }
    const uid = decodeUid(token);

    const path = `/rest/v1/case_assignments?hr_user_id=eq.${encodeURIComponent(uid)}&select=id,case_id,updated_at`;
    const res = await fetchWithAuth(path);
    if (!res.ok) {
      const text = await res.text();
      return { data: null, error: text || 'Failed to load assignments' };
    }
    const assignments = (await res.json()) as { id: string; case_id: string; updated_at: string | null }[];
    if (assignments.length === 0) {
      return { data: [], error: null };
    }

    const caseIds = [...new Set(assignments.map((a) => a.case_id))];
    const inClause = caseIds.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(',');
    const casesPath = `/rest/v1/wizard_cases?id=in.(${inClause})&select=id,draft_json,updated_at,origin_country,origin_city,dest_country,dest_city,target_move_date`;
    const casesRes = await fetchWithAuth(casesPath);
    if (!casesRes.ok) {
      return { data: null, error: 'Failed to load case details' };
    }
    const cases = (await casesRes.json()) as {
      id: string;
      draft_json: string;
      updated_at: string;
      origin_country: string | null;
      origin_city: string | null;
      dest_country: string | null;
      dest_city: string | null;
      target_move_date: string | null;
    }[];

    const caseMap = new Map(cases.map((c) => [c.id, c]));

    const result: AssignedCaseForReview[] = assignments.map((a) => {
      const wc = caseMap.get(a.case_id);
      let caseName = `Case ${a.case_id.slice(0, 8)}`;
      let origin = '-';
      let destination = '-';
      let targetMoveDate: string | null = null;
      if (wc) {
        const draft = parseDraft(wc.draft_json);
        const basics = draft.relocationBasics || {};
        const prof = draft.employeeProfile || {};
        caseName = prof.fullName || basics.originCountry || caseName;
        origin = [basics.originCity, basics.originCountry].filter(Boolean).join(', ') || [wc.origin_city, wc.origin_country].filter(Boolean).join(', ') || '-';
        destination = [basics.destCity, basics.destCountry].filter(Boolean).join(', ') || [wc.dest_city, wc.dest_country].filter(Boolean).join(', ') || '-';
        targetMoveDate = basics.targetMoveDate || wc.target_move_date || null;
      }
      return {
        id: a.id,
        case_id: a.case_id,
        caseName,
        origin,
        destination,
        targetMoveDate,
        lastUpdated: a.updated_at || (wc?.updated_at ?? null),
      };
    });

    result.sort((a, b) => (b.lastUpdated || '').localeCompare(a.lastUpdated || ''));
    return { data: result, error: null };
  } catch (err) {
    return { data: null, error: errMessage(err, 'Failed to load assigned cases') };
  }
}

/** Get a single wizard case by id (for read-only summary) */
export async function getWizardCaseForReview(caseId: string): Promise<{
  data: { draft: WizardDraft; origin?: string; dest?: string; targetDate?: string } | null;
  error: string | null;
}> {
  try {
    const path = `/rest/v1/wizard_cases?id=eq.${encodeURIComponent(caseId)}&select=*&limit=1`;
    const res = await fetchWithAuth(path);
    if (!res.ok) {
      return { data: null, error: 'Case not found' };
    }
    const rows = (await res.json()) as WizardCaseRow[];
    const row = rows?.[0];
    if (!row) return { data: null, error: 'Case not found' };

    const draft = parseDraft(row.draft_json);
    const basics = draft.relocationBasics || {};
    const origin = [basics.originCity, basics.originCountry].filter(Boolean).join(', ') || [row.origin_city, row.origin_country].filter(Boolean).join(', ') || undefined;
    const dest = [basics.destCity, basics.destCountry].filter(Boolean).join(', ') || [row.dest_city, row.dest_country].filter(Boolean).join(', ') || undefined;
    const targetDate = basics.targetMoveDate || row.target_move_date || undefined;

    return { data: { draft, origin, dest, targetDate }, error: null };
  } catch (err) {
    return { data: null, error: errMessage(err, 'Failed to load case') };
  }
}

/** Get assignment id for current employee (by assignment id or case id) */
export async function getEmployeeAssignmentId(idOrCaseId: string): Promise<{ assignmentId: string | null; error: string | null }> {
  try {
    const token = await getAccessToken();
    if (!token) return { assignmentId: null, error: 'Not authenticated' };
    const uid = decodeUid(token);

    const path = `/rest/v1/case_assignments?employee_user_id=eq.${encodeURIComponent(uid)}&or=(id.eq.${encodeURIComponent(idOrCaseId)},case_id.eq.${encodeURIComponent(idOrCaseId)})&select=id&limit=1`;
    const res = await fetchWithAuth(path);
    if (!res.ok) return { assignmentId: null, error: 'Not authorized' };
    const rows = (await res.json()) as { id: string }[];
    return { assignmentId: rows?.[0]?.id ?? null, error: null };
  } catch (err) {
    return { assignmentId: null, error: errMessage(err, 'Failed') };
  }
}

/** Get assignment id for a case_id (for current HR user) */
export async function getAssignmentIdForCase(caseId: string): Promise<{ assignmentId: string | null; error: string | null }> {
  try {
    const token = await getAccessToken();
    if (!token) return { assignmentId: null, error: 'Not authenticated' };
    const uid = decodeUid(token);

    const path = `/rest/v1/case_assignments?case_id=eq.${encodeURIComponent(caseId)}&hr_user_id=eq.${encodeURIComponent(uid)}&select=id&limit=1`;
    const res = await fetchWithAuth(path);
    if (!res.ok) return { assignmentId: null, error: 'Not authorized' };
    const rows = (await res.json()) as { id: string }[];
    return { assignmentId: rows?.[0]?.id ?? null, error: null };
  } catch (err) {
    return { assignmentId: null, error: errMessage(err, 'Failed') };
  }
}
