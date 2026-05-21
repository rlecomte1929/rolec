/**
 * [P1-5] Dossier & Forms API client.
 *
 * Backend: backend/app/routers/cases.py @ GET /api/cases/{case_id}/forms
 */
import api from './client';

export type CaseFormStatus =
  | 'not_started'
  | 'auto_filled'
  | 'in_progress'
  | 'pending_doc'
  | 'ready'
  | 'submitted'
  | 'approved'
  | 'rejected';

export interface DossierFormTemplate {
  id: string;
  code: string;
  name: string;
  authority_code: string | null;
  authority_name: string | null;
  country: string;
  category: string | null;
  version: string;
  fields_total: number;
}

export type DossierPersonKind = 'employee' | 'spouse' | 'child' | 'other';

export interface DossierFormPerson {
  kind: DossierPersonKind;
  name: string | null;
  dependent_id: string | null;
  profile_id: string | null;
}

export interface DossierFieldsSummary {
  total: number;
  filled_by_ai: number;
  filled_by_human: number;
  reviewed: number;
  overridden: number;
  missing_required: number;
}

export interface CaseFormSummary {
  id: string;
  case_id: string;
  status: CaseFormStatus;
  completion_pct: number;
  deadline: string | null;
  deadline_trigger: string | null;
  blocker_form_id: string | null;
  blocker_form_code: string | null;
  original_file_url: string | null;
  draft_pdf_url: string | null;
  submitted_at: string | null;
  receipt_ref: string | null;
  template: DossierFormTemplate;
  person: DossierFormPerson;
  fields_summary: DossierFieldsSummary;
  created_at: string;
  updated_at: string;
}

export const dossierAPI = {
  list: async (caseId: string, params?: { status?: CaseFormStatus }): Promise<CaseFormSummary[]> =>
    api.get(`/api/cases/${caseId}/forms`, { params }).then((r: { data: CaseFormSummary[] }) => r.data),
};
