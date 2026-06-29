/**
 * [P2-02e] Case rule-update notifications — GET/dismiss for the roadmap banner.
 * Backed by public.case_rule_update_notifications (written by P2-02d on approval).
 */
import api from './client';

export interface CaseRuleUpdate {
  id: string;
  source_change_review_id?: string;
  source_name?: string;
  source_url?: string;
  created_at?: string;
}

export interface CaseRuleUpdatesResponse {
  items: CaseRuleUpdate[];
  count: number;
}

export async function getCaseRuleUpdates(caseId: string): Promise<CaseRuleUpdatesResponse> {
  const r = await api.get<CaseRuleUpdatesResponse>(`/api/cases/${caseId}/rule-updates`);
  return r.data;
}

export async function dismissCaseRuleUpdate(caseId: string, id: string): Promise<void> {
  await api.post(`/api/cases/${caseId}/rule-updates/${id}/dismiss`);
}
