/**
 * Types for the Contradiction Resolution UI (C1-12).
 *
 * Mirrors the C1-08 Pydantic shapes in
 * `backend/relopass/agents/contradiction.py` + Architecture Report §3.6.
 *
 * Keep this file narrow — only what the UI consumes. When new fields
 * appear on the backend, mirror them here AND update the corresponding
 * tanstack-query parser.
 */

import type { ReasonCode } from './reasonCodes';

export type ContradictionType =
  | 'DIRECT_CONTRADICTION'
  | 'MISSING_VALUE'
  | 'TEMPORAL_INCONSISTENCY'
  | 'FORMAT_MISMATCH'
  | 'UNIT_MISMATCH';

export type ResolutionStatus =
  | 'Resolved'
  | 'Requires attention'
  | 'Not resolved'
  | 'No result'
  | 'Ignored';

/** One source of a value for a (canonical_entity, field) pair. */
export interface Candidate {
  /** Stable identifier within the contradiction. Used by the resolve POST. */
  candidate_id: string;
  value_raw: string;
  value_canonical?: Record<string, unknown> | null;
  document_id: string;
  document_type_code?: string | null;
  source_agent_run_id?: string | null;
  confidence: number;
  bbox_page?: number | null;
  bbox?: [number, number, number, number] | null;
  /** Human-readable label for the source: "Employment contract", "Payslip", etc. */
  source_label?: string | null;
}

export interface Contradiction {
  contradiction_id: string;
  case_id: string;
  canonical_entity_id: string | null;
  canonical_entity_label?: string | null;
  field_key: string;
  type: ContradictionType;
  candidates: Candidate[];
  resolution_status: ResolutionStatus;
  suggested_winner: unknown | null;
  content_hash: string;
  detected_at: string;
  detected_by: string;
}

/** One row in the corrections history shown alongside the contradiction. */
export interface PriorCorrection {
  correction_id: string;
  field: string;
  reason_code: ReasonCode;
  reason_freetext?: string | null;
  corrected_at: string;
  corrected_by_label?: string | null;
}

export interface ResolvePayload {
  winner_candidate_id: string;
  reason_code: ReasonCode;
  reason_freetext?: string;
}

export interface ResolveResponse {
  contradiction_id: string;
  resolution_status: ResolutionStatus;
  canonical_value: unknown;
  correction_id: string;
}
