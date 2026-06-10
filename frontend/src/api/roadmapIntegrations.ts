/**
 * I-4 — case plan delivery (email this plan + download deadlines as .ics).
 * Calls the case-integrations endpoints through the shared axios instance
 * (auth token injected). The .ics endpoint is auth-gated, so it's fetched as a
 * blob and downloaded client-side rather than linked directly.
 */
import api from './client';

export async function emailRoadmapPlan(
  caseId: string,
  to?: string,
): Promise<{ emailed_to: string; subject: string }> {
  const r = await api.post(`/api/cases/${caseId}/roadmap/email`, to ? { to } : {});
  return r.data;
}

export async function downloadCaseCalendar(caseId: string): Promise<void> {
  const r = await api.get(`/api/cases/${caseId}/calendar.ics`, { responseType: 'blob' });
  const url = URL.createObjectURL(new Blob([r.data], { type: 'text/calendar' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = `relopass-case-${caseId}.ics`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
