import { apiGet } from './client';

/**
 * Executive "state of the platform" overview (admin-only). One aggregated payload;
 * each panel carries `available` + a `data_source` flag (live | estimated | mock |
 * unavailable) so estimated/mock is never mistaken for live.
 */
export interface ExecPanel {
  available: boolean;
  data_source: string;
  note?: string;
  [k: string]: unknown;
}

export interface ExecOverview {
  generated_at: string;
  window_days: number;
  growth: ExecPanel & { companies?: number; hr_users?: number; employees?: number; new_companies?: number };
  funnel: ExecPanel & { signups?: number; in_intake?: number; cases?: number; completed?: number };
  throughput: ExecPanel & { median_completion_days?: number | null; created_in_window?: number; completed_in_window?: number };
  ai_cost: ExecPanel & { total_cost_usd?: number | null; call_count?: number | null };
  ai_health: ExecPanel & { score?: number | null; healthy?: number; total?: number };
  reliability: ExecPanel;
  nps: ExecPanel;
}

export async function getExecOverview(windowDays = 30): Promise<ExecOverview> {
  return apiGet<ExecOverview>(`/api/admin/exec-overview?window_days=${windowDays}`);
}
