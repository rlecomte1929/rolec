/**
 * immigrationForms.ts — employee AcroForm pre-fill (IMM-11, System B).
 *
 * Wraps the two employee immigration-form endpoints:
 *   GET  /api/employee/cases/{caseId}/immigration/available-forms
 *   POST /api/employee/cases/{caseId}/immigration/generate-form   body {form_id}
 *
 * generate-form fills the real government AcroForm from the case's vault profile, stores it in
 * Supabase Storage and returns a time-limited download URL plus a per-field fill report. Values
 * come only from real case data (form_prefill_service never invents); a field it cannot source
 * is reported blank, not guessed.
 */
import { api } from './client';

export interface AvailableForm {
  form_id: string;
  form_name: string;
  corridor_to: string;
  visa_type: string;
  field_count: number;
  form_url: string | null;
}

export interface AvailableFormsResponse {
  corridor_to: string | null;
  visa_type: string | null;
  forms: AvailableForm[];
}

/** filled = written to the PDF; blank_missing_data = no value in the vault; warning = written but
 *  needs a human check (special characters on an exact-match field); not_in_pdf = the mapped field
 *  name is not in this template, so nothing landed. */
export type FillFieldStatus = 'filled' | 'blank_missing_data' | 'warning' | 'not_in_pdf';

export interface FillReportField {
  form_field_id: string;
  vault_field_path: string;
  label: string | null;
  status: FillFieldStatus;
  value: string | null;
  warning: string | null;
}

export interface FillReport {
  form_id: string;
  case_id: string;
  storage_path: string;
  download_url: string | null;
  filled_count: number;
  blank_count: number;
  warning_count: number;
  not_in_pdf_count: number;
  fields: FillReportField[];
}

export interface GenerateFormResponse {
  download_url: string | null;
  fill_report: FillReport;
}

export const immigrationFormsAPI = {
  async getAvailableForms(
    caseId: string,
    opts?: { visaType?: string; corridorTo?: string },
  ): Promise<AvailableFormsResponse> {
    const params: Record<string, string> = {};
    if (opts?.visaType) params.visa_type = opts.visaType;
    if (opts?.corridorTo) params.corridor_to = opts.corridorTo;
    const res = await api.get<AvailableFormsResponse>(
      `/api/employee/cases/${encodeURIComponent(caseId)}/immigration/available-forms`,
      { params },
    );
    return res.data;
  },

  async generateForm(caseId: string, formId: string): Promise<GenerateFormResponse> {
    const res = await api.post<GenerateFormResponse>(
      `/api/employee/cases/${encodeURIComponent(caseId)}/immigration/generate-form`,
      { form_id: formId },
    );
    return res.data;
  },
};
