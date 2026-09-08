/**
 * GAP 2 & GAP 5: Multi-track roadmap API — GET /api/cases/{id}/roadmap
 *
 * Replaces window.PATHWAY_V2.deriveTimeline() with a real server-side call.
 * Also adds research status polling for GAP 9.
 */
import { apiGet, apiPost } from './client';

export interface RoadmapStep {
  n: number;
  key: string;
  title: string;
  status: 'active' | 'locked' | 'done' | 'todo';
  owner: string;
  where: string;
  time: string;
  cost: string;
  depends: string | null;
  line: string;
  subs: string[];
  waitingNote?: string;
  note?: { variant: string; title: string; body: string };
  member?: { name: string; initials: string; label: string };
}

export interface RoadmapTrack {
  id: string;
  name: string;
  icon: string;
  steps: RoadmapStep[];
}

export interface RoadmapLane {
  memberKey: string;
  memberName: string;
  memberInitials: string;
  memberLabel: string;
  step: {
    title: string;
    anchorTo: string;
    owner: string;
    where: string;
    time: string;
    cost: string;
    line: string;
    subs: string[];
  };
}

export interface RoadmapTotals {
  time: string;
  cost: string;
  employerCovers: string;
}

export interface RoadmapResponse {
  totals: RoadmapTotals;
  outcomes: string[];
  tracks: RoadmapTrack[];
  /** Flat step list for Pathway V2 compatibility */
  steps: RoadmapStep[];
  /** Family parallel lanes */
  lanes: RoadmapLane[];
}

export interface ResearchStatusEvent {
  ts: string;
  msg: string;
}

export interface ResearchStatusResponse {
  status: 'not_started' | 'in_progress' | 'completed' | 'failed';
  progress_pct: number;
  job_id: string | null;
  events: ResearchStatusEvent[];
  hint?: string;
}

/**
 * GAP 2 / GAP 5: Get the multi-track roadmap for a case.
 * Server-side equivalent of window.PATHWAY_V2.deriveTimeline().
 */
export async function getCaseRoadmap(caseId: string): Promise<RoadmapResponse> {
  return apiGet<RoadmapResponse>(`/api/cases/${caseId}/roadmap`);
}

/**
 * GAP 9: Poll the discovery research status for a case.
 * Use instead of SSE — poll every 2s until status === 'completed'.
 */
export async function getResearchStatus(caseId: string): Promise<ResearchStatusResponse> {
  return apiGet<ResearchStatusResponse>(`/api/cases/${caseId}/research/status`);
}

/**
 * GAP 1b: Update household members and pets for a case.
 */
export interface FamilyMemberInput {
  type: 'spouse' | 'child' | 'other';
  full_name?: string;
  date_of_birth?: string;
  nationality?: string;
  passport_number?: string;
}

export interface PetInput {
  name?: string;
  breed?: string;
  species?: string;
  weight_kg?: number;
  origin_country?: string;
  microchipped?: boolean;
  vaccinations_up_to_date?: boolean;
}

export interface HouseholdPayload {
  family_members?: FamilyMemberInput[];
  pets?: PetInput[];
}

export async function updateHousehold(
  caseId: string,
  payload: HouseholdPayload,
): Promise<{ case_id: string; household_updated: boolean; family_member_count: number; pet_count: number }> {
  return apiPost<ReturnType<typeof updateHousehold>>(`/api/cases/${caseId}/household`, payload);
}
