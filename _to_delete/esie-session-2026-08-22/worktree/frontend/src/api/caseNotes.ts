import { apiGet, apiPost } from './client';

/** [AIQ-1136 / NAV-HR-2-FU] One internal note on a relocation case. */
export interface CaseNote {
  id: string;
  case_id: string;
  author_user_id: string;
  author_name?: string | null;
  body: string;
  created_at?: string | null;
}

/** Newest-first list of a case's internal notes. Tenant-scoped server-side. */
export const listCaseNotes = (caseId: string): Promise<CaseNote[]> =>
  apiGet(`/api/hr/cases/${encodeURIComponent(caseId)}/notes`);

/** Append an internal note to a case. */
export const addCaseNote = (caseId: string, body: string): Promise<CaseNote> =>
  apiPost(`/api/hr/cases/${encodeURIComponent(caseId)}/notes`, { body });
