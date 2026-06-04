/**
 * BL-Compliance.4 — Compliance alerts API client.
 *
 * Backend: backend/app/routers/compliance.py
 *   GET   /api/compliance/alerts
 *   POST  /api/compliance/evaluate
 *   PATCH /api/compliance/alerts/{id}
 *
 * All endpoints are company-scoped server-side via the caller's HR session.
 */
import api from './client';

export type AlertSeverity = 'critical' | 'high' | 'medium' | 'low';

export interface ComplianceAlert {
  id: string;
  case_id: string;
  status: string;
  severity: AlertSeverity;
  category: string;
  description: string | null;
  detail: Record<string, unknown>;
  fired_at: string | null;
  employee_id: string | null;
  host_country: string | null;
  home_country: string | null;
}

export interface AlertsResponse {
  alerts: ComplianceAlert[];
  counts_by_severity: Record<string, number>;
}

export interface EvaluateResult {
  cases_evaluated: number;
  alerts_created: number;
  alerts_skipped_existing: number;
}

export async function listComplianceAlerts(): Promise<AlertsResponse> {
  const { data } = await api.get<AlertsResponse>('/api/compliance/alerts');
  return data;
}

export async function evaluateCompliance(): Promise<EvaluateResult> {
  const { data } = await api.post<EvaluateResult>('/api/compliance/evaluate');
  return data;
}

export async function resolveComplianceAlert(
  id: string,
  status: 'resolved' | 'dismissed',
): Promise<void> {
  await api.patch(`/api/compliance/alerts/${id}`, { status });
}
