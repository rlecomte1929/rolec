/**
 * Mobility graph API (FastAPI): case context + next actions.
 * Requires auth (same Bearer as rest of app). Access is assignment-gated via assignment_mobility_links.
 * mobility_cases.id: prefer assignment.mobility_case_id from case-details; ?mcid= is debug-only.
 */

import api from './client';

export interface MobilityCaseRow {
  id?: string;
  origin_country?: string | null;
  destination_country?: string | null;
  case_type?: string | null;
  metadata?: Record<string, unknown>;
}

export interface MobilityEvaluationRow {
  id?: string;
  requirement_id?: string;
  requirement_code?: string;
  evaluation_status?: string;
  reason_text?: string | null;
  evaluated_at?: string | null;
  evaluated_by?: string | null;
}

export interface MobilityContextResponse {
  meta: {
    ok?: boolean;
    case_id?: string | null;
    case_found?: boolean;
    error?: unknown;
  };
  case: MobilityCaseRow | null;
  people: unknown[];
  documents: unknown[];
  applicable_rules: unknown[];
  requirements: unknown[];
  evaluations: MobilityEvaluationRow[];
}

export interface MobilityNextAction {
  id: string;
  action_title: string;
  action_description: string;
  priority: number;
  related_requirement_code: string | null;
}

export interface MobilityNextActionsResponse {
  meta: {
    ok?: boolean;
    case_id?: string | null;
    case_found?: boolean;
    action_count?: number;
    error?: unknown;
  };
  actions: MobilityNextAction[];
}

export async function fetchMobilityContext(mobilityCaseId: string): Promise<MobilityContextResponse> {
  const res = await api.get<MobilityContextResponse>(`/api/mobility/cases/${encodeURIComponent(mobilityCaseId)}/context`);
  return res.data;
}

export async function fetchMobilityNextActions(mobilityCaseId: string): Promise<MobilityNextActionsResponse> {
  const res = await api.get<MobilityNextActionsResponse>(
    `/api/mobility/cases/${encodeURIComponent(mobilityCaseId)}/next-actions`
  );
  return res.data;
}
