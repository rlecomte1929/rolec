// Personal Relocation Data Sheet — type model.
// Placed in lib/ (not a root types/ folder) because the workspace already has a
// root-level types.ts file and the bundler resolves module names case-/shape-
// insensitively; lib/ is the established home for shared non-component code
// (see lib/colors.ts, lib/pricing.ts).

export type FieldSource =
  | 'intake'
  | 'passport_ocr'
  | 'prior_form'
  | 'needs_input'
  | 'consult_professional';

export interface DataSheetFieldValue {
  fact_key: string;
  label_en: string;
  label_no?: string;
  source: FieldSource;
  value: string | null;
  /** 0–1. 1.0 for intake, 0.9 for OCR, 0.8 for prior-form carry, 0 when empty. */
  confidence: number;
  /** For needs_input: what to enter. */
  hint?: string;
  /** For consult_professional: what a regulated professional must determine. */
  guidance?: string;
  is_consult_professional: boolean;
  /** True when this row is a stub because the requirements DB has no fields for the step yet. */
  is_placeholder?: boolean;
}

export interface DataSheetSection {
  step_id: string;
  step_name_en: string;
  step_name_no?: string;
  authority?: string;
  official_source_url: string;
  official_process_note: string;
  fields: DataSheetFieldValue[];
}

export interface PersonalRelocationDataSheet {
  case_ref: string;
  case_id: number;
  employee_name: string;
  corridor: string; // e.g. 'FR-NO'
  corridor_label: string; // e.g. 'France → Norway'
  generated_at: string; // ISO date
  locale: 'en' | 'no';
  display_mode: 'full' | 'sparse';
  sections: DataSheetSection[];
  /** % of non-consult fields with a value (0–100). */
  completion_pct: number;
  /** Count of non-consult fields still needing input. */
  needs_input_count: number;
}

// ── Requirements DB row shapes (WorkspaceDB tables) ─────────────────────────

export interface RequirementEntityRow {
  id: number;
  entity_id: string;
  corridor: string;
  entity_type: string | null;
  step_order: number | null;
  name_en: string;
  name_no: string | null;
  authority: string | null;
  official_source_url: string | null;
  official_process_note: string | null;
  status: string | null;
}

export interface RequirementFactRow {
  id: number;
  fact_uid: string;
  entity_id: string;
  corridor: string;
  fact_key: string;
  label_en: string;
  label_no: string | null;
  required: boolean | null;
  category: string | null;
  professional_review_required: boolean | null;
  hint: string | null;
  guidance: string | null;
  sort_order: number | null;
}

/** Case summary used by the case picker in the Data Sheet view. */
export interface DataSheetCaseSummary {
  case_id: number;
  case_ref: string;
  employee_name: string;
  corridor: string;
  corridor_label: string;
  status: string;
}
