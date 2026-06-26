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
  /** [P1-05] Official Tier-1 authority URL where this form is completed/submitted. */
  source_url: string | null;
  /** [P1-05d] When the source URL was last fetched/verified (ISO), from source_pages. */
  source_last_verified: string | null;
  /** [P1-05 checklist] Required supporting documents (derived from requires_original fields).
   *  [AIQ-1257b] `format` carries optional acceptance guidance (e.g. "Original + copy"). */
  required_documents: Array<{ key: string; label: string; format?: string | null }>;
  /**
   * [WS1] Content-maturity flag. 'representative' (default scaffolding, not yet
   * human-verified), 'draft' (under review), or 'verified' (ops/legal confirmed
   * against the issuing authority). Anything other than 'verified' surfaces an
   * "indicative — confirm with the authority" notice so we never imply the
   * content is authoritative.
   */
  verification_status: 'verified' | 'draft' | 'representative' | null;
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
  /** [P2-6] Server-computed convenience flag — true when blocker_form_id is set
   *  and the blocker has not yet been submitted/approved. */
  is_blocked?: boolean;
  original_file_url: string | null;
  draft_pdf_url: string | null;
  submitted_at: string | null;
  receipt_ref: string | null;
  rejection_reason: string | null;  // [P4-5] set when status='rejected'
  roadmap_step_id?: string | null;  // [P1-6] step that triggered this form
  roadmap_step_title?: string | null;  // [P1-05] human-readable title of that step
  is_adhoc?: boolean;                // [P4-3] true for ad-hoc "Add document" entries
  notes?: string | null;             // [P4-3] free-text notes from the Add-document modal
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

// ── [P1-05c] Per-form supporting documents ───────────────────────────────────

export interface FormDocument {
  id: string;
  case_form_id: string;
  case_id: string;
  file_name: string;
  content_type: string | null;
  size_bytes: number | null;
  uploaded_by: string | null;
  /** [P1-05 checklist] required-document item this upload satisfies, if any. */
  doc_key: string | null;
  created_at: string;
  /** 1-hour signed download URL; null when storage is unavailable. */
  download_url: string | null;
}

export const formDocumentsAPI = {
  list: (caseId: string, formId: string): Promise<FormDocument[]> =>
    api
      .get(`/api/cases/${caseId}/forms/${formId}/documents`)
      .then((r: { data: FormDocument[] }) => r.data),

  upload: (caseId: string, formId: string, file: File, docKey?: string | null): Promise<FormDocument> => {
    const form = new FormData();
    form.append('file', file);
    if (docKey) form.append('doc_key', docKey);
    return api
      .post(`/api/cases/${caseId}/forms/${formId}/documents`, form, { timeout: 120_000 })
      .then((r: { data: FormDocument }) => r.data);
  },

  remove: (caseId: string, formId: string, documentId: string): Promise<void> =>
    api
      .delete(`/api/cases/${caseId}/forms/${formId}/documents/${documentId}`)
      .then(() => undefined),
};

// ── [P4-3] Ad-hoc "Add document" ─────────────────────────────────────────────

export interface CreateAdhocFormPayload {
  name: string;
  authority?: string | null;
  personId?: string | null;
  deadline?: string | null;
  notes?: string | null;
  file?: File | null;
}

function buildAdhocFormData(payload: CreateAdhocFormPayload): FormData {
  const fd = new FormData();
  fd.append('name', payload.name);
  if (payload.authority) fd.append('authority', payload.authority);
  if (payload.personId) fd.append('person_id', payload.personId);
  if (payload.deadline) fd.append('deadline', payload.deadline);
  if (payload.notes) fd.append('notes', payload.notes);
  if (payload.file) fd.append('file', payload.file);
  return fd;
}

export const adhocFormsAPI = {
  create: async (caseId: string, payload: CreateAdhocFormPayload): Promise<CaseFormSummary> =>
    api
      .post(`/api/cases/${caseId}/forms/adhoc`, buildAdhocFormData(payload))
      .then((r: { data: CaseFormSummary }) => r.data),

  replacePdf: async (caseId: string, formId: string, file: File): Promise<CaseFormSummary> => {
    const fd = new FormData();
    fd.append('file', file);
    return api
      .post(`/api/cases/${caseId}/forms/${formId}/replace-pdf`, fd)
      .then((r: { data: CaseFormSummary }) => r.data);
  },
};

// ── [P3-4] Dossier Package ────────────────────────────────────────────────────

export interface DossierPackage {
  id: string;
  case_id: string;
  name: string;
  form_ids: string[];
  cover_page: boolean;
  pdf_url: string | null;
  generated_at: string | null;
  created_at: string;
}

/** [P3-6] DossierPackage with server-computed staleness flag. */
export interface DossierPackageDetail extends DossierPackage {
  is_stale: boolean;
}

export interface CreateDossierPackagePayload {
  name: string;
  form_ids: string[];
  cover_page: boolean;
}

export const dossierPackageAPI = {
  create: async (caseId: string, payload: CreateDossierPackagePayload): Promise<DossierPackage> =>
    api
      .post(`/api/cases/${caseId}/dossiers`, payload)
      .then((r: { data: DossierPackage }) => r.data),

  /** [P3-6] List all saved dossier packages for a case. */
  list: async (caseId: string): Promise<DossierPackageDetail[]> =>
    api
      .get(`/api/cases/${caseId}/dossiers`)
      .then((r: { data: DossierPackageDetail[] }) => r.data),

  /** [P3-6] Get a single dossier package with staleness flag. */
  get: async (caseId: string, dossierId: string): Promise<DossierPackageDetail> =>
    api
      .get(`/api/cases/${caseId}/dossiers/${dossierId}`)
      .then((r: { data: DossierPackageDetail }) => r.data),

  /** [P3-6] Rebuild the merged PDF with current field values. */
  regenerate: async (caseId: string, dossierId: string): Promise<DossierPackageDetail> =>
    api
      .post(`/api/cases/${caseId}/dossiers/${dossierId}/regenerate`, {})
      .then((r: { data: DossierPackageDetail }) => r.data),

  /** [P3-6] Delete a dossier package. */
  delete: async (caseId: string, dossierId: string): Promise<void> =>
    api.delete(`/api/cases/${caseId}/dossiers/${dossierId}`).then(() => undefined),

  getPdfUrl: (caseId: string, dossierId: string): string =>
    `/api/cases/${caseId}/dossiers/${dossierId}/pdf`,

  getZipUrl: (caseId: string, dossierId: string): string =>
    `/api/cases/${caseId}/dossiers/${dossierId}/zip`,
};

// ── [P4-2] Comments, events, flag ────────────────────────────────────────────

export interface FormComment {
  id: string;
  case_form_id: string;
  author_id: string;
  author_name: string | null;
  content: string;
  created_at: string;
}

export interface FormEvent {
  id: string;
  case_form_id: string;
  event_type: string;
  actor_id: string | null;
  actor_name: string | null;
  from_status: string | null;
  to_status: string | null;
  note: string | null;
  created_at: string;
}

export interface FormFlagResponse {
  id: string;
  flag_note: string | null;
  flagged_at: string | null;
  flagged_by: string | null;
}

export const commentsAPI = {
  list: (caseId: string, formId: string): Promise<FormComment[]> =>
    api
      .get(`/api/cases/${caseId}/forms/${formId}/comments`)
      .then((r: { data: FormComment[] }) => r.data),

  create: (caseId: string, formId: string, content: string): Promise<FormComment> =>
    api
      .post(`/api/cases/${caseId}/forms/${formId}/comments`, { content })
      .then((r: { data: FormComment }) => r.data),
};

export const eventsAPI = {
  list: (caseId: string, formId: string): Promise<FormEvent[]> =>
    api
      .get(`/api/cases/${caseId}/forms/${formId}/events`)
      .then((r: { data: FormEvent[] }) => r.data),
};

export const flagAPI = {
  patch: (caseId: string, formId: string, flagNote: string | null): Promise<FormFlagResponse> =>
    api
      .patch(`/api/cases/${caseId}/forms/${formId}/flag`, { flag_note: flagNote })
      .then((r: { data: FormFlagResponse }) => r.data),
};
