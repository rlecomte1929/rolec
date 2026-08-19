import api from './client';

/**
 * Admin API for the corridor candidate beam.
 *
 * Everything here is unreviewed model output on its way to a human. There is deliberately
 * no `promote` call: the backend router has no such endpoint, and adding one on this side
 * would only produce a button that 404s. Approved candidates reach customers through the
 * existing /admin staging gate, never from this screen.
 */

export type BeamRunStatus = 'generating' | 'pending_review' | 'failed';
export type BeamItemStatus = 'pending_review' | 'approved' | 'rejected' | 'imported';
export type ConfidenceBand = 'near-certain' | 'strong' | 'moderate' | 'low';

export interface BeamRun {
  id: string;
  set_uid: string | null;
  corridor: string;
  employee_type: string;
  status: BeamRunStatus;
  passes_requested: number;
  passes_completed: number;
  llm_provider: string | null;
  llm_model: string | null;
  candidate_count: number;
  error: string | null;
  created_by: string | null;
  created_at: string;
}

/** One contributing per-pass variant, kept so a reviewer can see where passes diverged. */
export interface BeamVariant {
  pass: number;
  arrival_ordinal?: number;
  framing: string | null;
  title: string;
  official_guidance?: string;
  actual_reality?: string;
  action_required?: string;
  source?: string | null;
  category?: string | null;
}

export interface BeamItem {
  id: string;
  candidate_uid: string;
  rank: number;
  pass_frequency: number;
  passes_total: number;
  confidence_band: ConfidenceBand;
  flagged: boolean;
  source_missing: boolean;
  title: string;
  official_guidance: string | null;
  actual_reality: string | null;
  action_required: string | null;
  /** The model's CLAIM, stored verbatim and unverified. Never rendered as a checked citation. */
  source: string | null;
  category: string | null;
  variants: BeamVariant[];
  status: BeamItemStatus;
  review_note: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  import_country: string | null;
  import_requirement_type: string | null;
  imported_ref: string | null;
  imported_at: string | null;
}

export interface BeamItemCounts {
  total: number;
  pending_review: number;
  approved: number;
  rejected: number;
  imported: number;
  /** The research worklist. Its own number on purpose — burying it in `total` hides it. */
  source_missing: number;
}

export interface ImportSkip {
  candidate_uid: string;
  title: string;
  reason: string;
}

export interface ImportPlan {
  importable: number;
  skipped: ImportSkip[];
  skips_by_reason: Record<string, number>;
  pillar_by_uid: Record<string, string>;
  /** Always false. The endpoint plans; it never writes. */
  written: boolean;
}

const BASE = '/api/admin/candidate-beam';

export const candidateBeamAPI = {
  listRuns: async (status?: BeamRunStatus): Promise<BeamRun[]> => {
    const res = await api.get<{ runs: BeamRun[] }>(`${BASE}/runs`, {
      params: status ? { status } : undefined,
    });
    return res.data.runs;
  },

  listItems: async (
    runId: string,
    status?: BeamItemStatus,
  ): Promise<{ items: BeamItem[]; counts: BeamItemCounts }> => {
    const res = await api.get<{ items: BeamItem[]; counts: BeamItemCounts }>(
      `${BASE}/runs/${encodeURIComponent(runId)}/items`,
      { params: status ? { status } : undefined },
    );
    return res.data;
  },

  review: async (
    itemId: string,
    status: 'approved' | 'rejected',
    reviewNote?: string,
  ): Promise<void> => {
    await api.post(`${BASE}/items/${encodeURIComponent(itemId)}/review`, {
      status,
      review_note: reviewNote || undefined,
    });
  },

  /** Ask what an import WOULD do. Writes nothing — show it before staging. */
  importPlan: async (
    runId: string,
    country: string,
    pillarOverrides: Record<string, string> = {},
  ): Promise<ImportPlan> => {
    const res = await api.post<ImportPlan>(
      `${BASE}/runs/${encodeURIComponent(runId)}/import-plan`,
      { country, pillar_overrides: pillarOverrides },
    );
    return res.data;
  },

  pillars: async (): Promise<{ pillars: string[]; grounded_categories: Record<string, string> }> => {
    const res = await api.get<{ pillars: string[]; grounded_categories: Record<string, string> }>(
      `${BASE}/pillars`,
    );
    return res.data;
  },
};
