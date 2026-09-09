/**
 * Document Data Sheet API — the composed, corridor-agnostic case data sheet.
 *
 * Mirrors backend/app/schemas.py (DataSheetDTO) and the routes in
 * backend/app/routers/data_sheet.py:
 *   GET   /api/cases/{caseId}/datasheet
 *   PATCH /api/cases/{caseId}/datasheet/fields/{fieldId}
 *
 * Types are camelCase to match the backend wire format (which follows the
 * CaseRequirementsDTO convention). {caseId} accepts an assignment id or a case
 * id — the backend resolves it — so pass whatever the page already holds.
 */
import { apiGet, apiPatch } from './client';

/** Where a field's value came from. `consult_professional` = a regulated determination
 *  ReloPass never fills (value is always null). `needs_input` = the employee must supply it. */
export type DataSheetSource =
  | 'intake'
  | 'passport_ocr'
  | 'prior_form'
  | 'needs_input'
  | 'consult_professional'
  | 'ai';

export interface DataSheetField {
  fieldId: string;
  factKey: string | null;
  label: string;
  category: string | null;
  source: DataSheetSource;
  value: string | null;
  confidence: number | null;
  hint: string | null;
  guidance: string | null;
  requiresOriginal: boolean;
  employerActionNote: string | null;
}

export interface DataSheetDeadline {
  date: string | null;
  isSuggested: boolean;
  isHard: boolean;
}

export interface DataSheetSection {
  stepId: string;
  title: string | null;
  authority: string | null;
  sourceUrl: string | null;
  processNote: string | null;
  channels: string[];
  order: number;
  responsibleParty: string | null;
  slaNote: string | null;
  deadline: DataSheetDeadline | null;
  fields: DataSheetField[];
}

export interface DataSheetBanner {
  /** 'moat-fact' (a non-obvious trap) or 'warning' (a hard deadline). */
  type: string;
  text: string;
}

export interface DataSheetConsult {
  topic: string;
  reason: string | null;
}

export interface DataSheet {
  caseRef: string;
  employeeName: string | null;
  corridor: string | null;
  corridorLabel: string | null;
  movementBasis: string | null;
  generatedAt: string;
  completionPct: number;
  needsInputCount: number;
  banners: DataSheetBanner[];
  sections: DataSheetSection[];
  consultProfessional: DataSheetConsult[];
  /** False when the case has no data-sheet form yet — render "not available yet", not "done". */
  covered: boolean;
}

export interface DataSheetQuery {
  audience?: 'employee' | 'hr';
  lang?: 'en' | 'local';
  mode?: 'full' | 'sparse';
}

function queryString(opts?: DataSheetQuery): string {
  if (!opts) return '';
  const p = new URLSearchParams();
  if (opts.audience) p.set('audience', opts.audience);
  if (opts.lang) p.set('lang', opts.lang);
  if (opts.mode) p.set('mode', opts.mode);
  const s = p.toString();
  return s ? `?${s}` : '';
}

export const getDataSheet = (caseId: string, opts?: DataSheetQuery): Promise<DataSheet> =>
  apiGet<DataSheet>(`/api/cases/${encodeURIComponent(caseId)}/datasheet${queryString(opts)}`);

/** Persist an edit to one field; returns the recomposed sheet. Consult-professional fields
 *  are rejected server-side (422). */
export const patchDataSheetField = (
  caseId: string,
  fieldId: string,
  value: string,
  opts?: DataSheetQuery,
): Promise<DataSheet> =>
  apiPatch<DataSheet>(
    `/api/cases/${encodeURIComponent(caseId)}/datasheet/fields/${encodeURIComponent(fieldId)}${queryString(opts)}`,
    { value },
  );
