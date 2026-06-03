/**
 * Types for the Case Detail surface (C1-11c).
 *
 * Mirrors the subset of fields the 5 sections read. The full domain
 * types live in the existing frontend/src/types/ contract (RelocationCase,
 * Employee, FamilyMember, Document, ExtractedField) — we re-declare a
 * UI-narrow view here rather than importing across the app boundary, so
 * a backend reshape only ripples through this one file.
 */

export type CaseStatus =
  | 'draft'
  | 'in_progress'
  | 'on_hold'
  | 'completed'
  | 'cancelled'
  | (string & {});

/**
 * Family member as exposed by the C1-01 schema. Used in the Overview
 * section. The full schema also has passport_number etc — we don't
 * surface PII in this view, only what helps the HR reviewer build
 * mental context about the case scope.
 */
export interface FamilyMember {
  family_member_id: string;
  relationship: 'spouse' | 'partner' | 'child' | 'parent' | 'other' | (string & {});
  display_name: string;
  date_of_birth?: string | null;
  is_dependent?: boolean | null;
}

export interface CaseOverview {
  case_id: string;
  employee: {
    employee_id: string;
    display_name: string;
    primary_email?: string | null;
    nationality?: string | null;
  };
  origin_country_code?: string | null;
  dest_country_code?: string | null;
  corridor?: string | null;
  status: CaseStatus;
  stage?: string | null;
  target_start_date?: string | null;
  actual_start_date?: string | null;
  target_close_date?: string | null;
  family_members: FamilyMember[];
}

/**
 * One document row in the Documents section. The confidence comes from
 * the aggregate of ExtractedField.confidence for this document — the
 * backend computes the rollup so the UI doesn't have to.
 */
export interface CaseDocument {
  document_id: string;
  document_type_code: string;
  document_type_label?: string | null;
  filename: string;
  uploaded_at: string;
  /** Mean ExtractedField confidence across this document. 0..1 or null. */
  confidence_mean?: number | null;
  /** Lowest single-field confidence — surfaces extraction weak spots. */
  confidence_min?: number | null;
  /** Number of fields extracted from this document. */
  extracted_field_count?: number | null;
  /** Signed URL for the PDF viewer — short-lived, server-issued. */
  document_uri?: string | null;
  /** Page count (for the viewer's lazy mount placeholder list). */
  page_count?: number | null;
}

/**
 * One step row in the Steps section. Cohort 1 ships a flat list; the
 * real StepGraph (DAG, dependencies, parallel arms) lands with C2-07.
 */
export interface CaseStep {
  step_id: string;
  label: string;
  status: 'pending' | 'in_progress' | 'blocked' | 'done' | (string & {});
  due_date?: string | null;
  owner_label?: string | null;
}

/**
 * Aggregate summary for the Contradictions inbox tab badge. The full
 * list (the C1-12 ResolutionPage) renders the items themselves.
 */
export interface ContradictionsSummary {
  case_id: string;
  total: number;
  /** Status breakdown so the badge can show e.g. "3 pending" without an extra fetch. */
  pending: number;
  resolved: number;
}

export type SectionKey = 'overview' | 'documents' | 'steps' | 'contradictions' | 'policy';
