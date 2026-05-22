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
  sort_order: number;
  ai_suggestion: string | null;
  dependency_ids: string[];
  vendor_id: string | null;
  doc_count: number;
  worst_doc_status: string | null;
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
}

export async function getCaseRoadmapV2(caseId: string): Promise<RoadmapV2Response> {
  const r = await api.get<RoadmapV2Response>(`/api/cases/${caseId}/roadmap/tracks`);
  return r.data;
}
