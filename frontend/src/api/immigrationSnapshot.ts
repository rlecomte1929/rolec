import { apiGet } from './client';

/**
 * Employee immigration snapshot (relocation-assistant Slice 2).
 * GET /api/employee/cases/{caseId}/immigration-snapshot — the proactive
 * "your move at a glance": risk flags + checklist summary for the employee's
 * OWN case. PII-safe; fail-closed (covered=false) on an unknown/unseeded corridor.
 */
export interface SnapshotRiskFlag {
  flag_type: string;
  severity: 'critical' | 'warning' | 'info' | string;
  title: string;
  description: string;
  recommended_action: string;
  deadline?: string | null;
}

export interface ImmigrationSnapshot {
  covered: boolean;
  corridor_from?: string | null;
  corridor_to?: string | null;
  visa_type: string;
  risk_flags: SnapshotRiskFlag[];
  checklist_summary: { total: number; required?: number; conditional?: number };
}

export async function getImmigrationSnapshot(caseId: string): Promise<ImmigrationSnapshot> {
  return apiGet<ImmigrationSnapshot>(`/api/employee/cases/${encodeURIComponent(caseId)}/immigration-snapshot`);
}
