/**
 * [P2-3 / P3-3] Form Editor API client.
 *
 * Covers the endpoints that power the per-field Form Editor:
 *   GET  /api/cases/{case_id}/forms/{form_id}/fields  → list fields + stored values
 *   PUT  /api/cases/{case_id}/forms/{form_id}/fields  → bulk upsert (save draft)
 *   PATCH /api/cases/{case_id}/forms/{form_id}        → status transition (mark ready)
 *   GET  /api/cases/{case_id}/forms/{form_id}/pdf     → [P3-1] download filled PDF
 *
 * Backend: backend/app/routers/cases.py
 */
import api from './client';
import type { CaseFormSummary } from './dossier';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/**
 * A single field merged with its stored value.
 * Matches the backend FieldValueItem Pydantic model.
 */
export interface FieldValueItem {
  field_id: string;
  label: string;
  field_type: string;         // text | date | select | boolean | number | ...
  required: boolean;
  position: number;
  prefill_source: string | null;
  requires_original: boolean;
  options: string[] | null;   // only for select fields
  /** Current stored value — null if no value has been saved yet */
  value: string | null;
  /** Who last wrote this value: ai | system | employee | specialist | hr */
  filled_by: string | null;
  ai_confidence: number | null;
  reviewed: boolean;
  overridden: boolean;
  /** Optional section label — not present in all form templates */
  section?: string | null;
}

export interface FieldUpsertInput {
  field_id: string;
  value: string | null;
}

export interface FormStatusPatchPayload {
  status: 'ready' | 'submitted';
  receipt_ref?: string;
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

export const formEditorAPI = {
  /**
   * Load all fields for a form, merged with stored values.
   * Fields with no stored value still appear with value=null.
   */
  getFields: async (caseId: string, formId: string): Promise<FieldValueItem[]> =>
    api
      .get(`/api/cases/${caseId}/forms/${formId}/fields`)
      .then((r: { data: FieldValueItem[] }) => r.data),

  /**
   * Bulk-upsert field values (employee save / draft).
   * Returns the updated CaseFormSummary (with new completion_pct).
   */
  putFields: async (
    caseId: string,
    formId: string,
    fields: FieldUpsertInput[],
  ): Promise<CaseFormSummary> =>
    api
      .put(`/api/cases/${caseId}/forms/${formId}/fields`, { fields })
      .then((r: { data: CaseFormSummary }) => r.data),

  /**
   * Transition the form status (ready | submitted).
   * 'ready' validates server-side that all required fields are filled.
   * Returns the updated CaseFormSummary.
   */
  patchStatus: async (
    caseId: string,
    formId: string,
    payload: FormStatusPatchPayload,
  ): Promise<CaseFormSummary> =>
    api
      .patch(`/api/cases/${caseId}/forms/${formId}`, payload)
      .then((r: { data: CaseFormSummary }) => r.data),

  /**
   * [P3-3] Download the filled PDF for a form.
   * Uses responseType: 'blob' so auth headers are applied automatically.
   * Triggers a browser download with the server-provided filename.
   */
  downloadPdf: async (caseId: string, formId: string): Promise<void> => {
    const response = await api.get(
      `/api/cases/${caseId}/forms/${formId}/pdf`,
      { responseType: 'blob' },
    );
    const blob = new Blob([response.data as BlobPart], { type: 'application/pdf' });
    const objectUrl = URL.createObjectURL(blob);

    // Extract filename from Content-Disposition header (server provides it)
    const cd = (response.headers as Record<string, string>)['content-disposition'] ?? '';
    const match = /filename="?([^";\n]+)"?/.exec(cd);
    const filename = match?.[1] ?? `form_${formId}.pdf`;

    const anchor = document.createElement('a');
    anchor.href = objectUrl;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    setTimeout(() => URL.revokeObjectURL(objectUrl), 10_000);
  },

  /**
   * [P2-4] Fetch a 1-hour signed URL for the blank template PDF.
   * Returns null when no original PDF has been attached to the template yet.
   *
   * Backend contract: GET /api/cases/{case_id}/forms/{form_id}/original
   * Always returns 200 with { signed_url, file_name, ... }. signed_url is
   * null when the template hasn't been associated with a PDF yet, or when
   * Supabase Storage is unavailable (dev mode).
   */
  getOriginalUrl: async (caseId: string, formId: string): Promise<string | null> => {
    try {
      const r = await api.get<{ signed_url: string | null }>(
        `/api/cases/${caseId}/forms/${formId}/original`,
      );
      return r.data.signed_url ?? null;
    } catch {
      // 404 = form not found / no access — surface as null so the drawer
      // renders the empty-state without throwing.
      return null;
    }
  },
};
