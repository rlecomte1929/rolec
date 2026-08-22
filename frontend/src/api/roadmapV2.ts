/**
 * [P1-6] Roadmap V2 API — GET /api/cases/{id}/roadmap/tracks
 * Returns roadmap_tracks + roadmap_steps with embedded CaseForm doc counts.
 */
import api from './client';

export interface RoadmapV2Step {
  id: string;
  title: string;
  description: string | null;
  status: 'pending' | 'in_progress' | 'awaiting_employee' | 'awaiting_vendor' | 'awaiting_hr' | 'blocked' | 'completed' | 'skipped';
  owner: string;
  due_date: string | null;
  // [AIQ-1258c/d] True when due_date is an auto-estimate from the case move date
  // (move_date − track lead time) rather than a real form deadline.
  due_date_is_suggested?: boolean;
  sort_order: number;
  ai_suggestion: string | null;
  dependency_ids: string[];
  vendor_id: string | null;
  doc_count: number;
  worst_doc_status: string | null;
  // [P3-04e] Confidence + source provenance derived from the linked requirement.
  confidence_level?: 'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN';
  source_url?: string | null;
  source_fetched_at?: string | null;
  source_excerpt?: string | null;
  // [AIQ-869] Short effort label ('~15 min' | '~1 hour' | 'Half a day'); null
  // once the step is done. Rendered by the AvailableNowWidget effort Pill.
  estimated_effort?: string | null;
  // The "easy to miss" trap flag and its plain-language explanation, present on a
  // corridor step that carries one (the emergency-tax 40%, the proof-of-address
  // catch-22, …). false / absent for a form-projected step.
  non_obvious?: boolean;
  non_obvious_note?: string | null;
}

/**
 * A corridor exception case — the non-obvious traps a mover would not expect.
 *
 * `asserted` is the honesty bit and callers MUST respect it. `false` means the condition
 * depends on an input the platform does not hold (the ES→IE pathway declares
 * `visa_required_nationality` as an EXTERNAL_LOOKUP that does not exist), so the text is
 * worded as something to check and must never be rendered as a statement about this reader.
 * `true` means we resolved it from the case itself.
 */
export interface RoadmapV2Advisory {
  id: string;
  text: string;
  asserted: boolean;
  cite?: string | null;
  provenance?: { corridor?: string; pathway?: string; verification?: string } | null;
}

export interface RoadmapV2Track {
  id: string;
  name: string;
  icon: string;
  sort_order: number;
  progress_pct: number;
  steps: RoadmapV2Step[];
}

export interface RoadmapV2Response {
  tracks: RoadmapV2Track[];
  /** Empty when the case has no corridor pathway, and for a resolved free mover. */
  advisories?: RoadmapV2Advisory[];
}

export async function getCaseRoadmapV2(caseId: string): Promise<RoadmapV2Response> {
  const r = await api.get<RoadmapV2Response>(`/api/cases/${caseId}/roadmap/tracks`);
  return r.data;
}
