import { apiGet, apiPost, API_BASE_URL } from './client';

/** TD-10 (AIQ-1428) — admin Test-Drive dashboard read model. */

export interface TestDriveFunnel {
  invited: number;
  clicked: number;
  provisioned: number;
  // TD-FIX-4 (AIQ-1505): mid-journey stages (distinct sessions per stage).
  hr_handoff: number;
  intake_start: number;
  intake_completed: number;
  roadmap_reached: number;
  vendor_selected: number;
  completed: number;
  surveyed: number;
  pilot: number;
  intro: number;
}

export interface PilotLead {
  tester_name: string | null;
  tester_email: string | null;
  tester_company_role: string | null;
  tester_sector: string | null;
  pilot_interest: string | null;
  pilot_note: string | null;
  corridor_id: string | null;
  tester_segment: string | null;
  created_at: string | null;
}

export interface Testimonial {
  testimonial: string | null;
  tester_name: string | null;
  tester_company_role: string | null;
  corridor_id: string | null;
  created_at: string | null;
}

/** TD-12 — every surveyed tester with a contact email, for the per-completer thank-you. */
export interface Completion {
  tester_name: string | null;
  tester_email: string | null;
  tester_company_role: string | null;
  tester_sector: string | null;
  q1_overall: number | null;
  pilot_interest: string | null;
  corridor_id: string | null;
  tester_segment: string | null;
  created_at: string | null;
}

export interface TestDriveOverview {
  funnel: TestDriveFunnel;
  scorecard: { avg_overall: number | null; problem_fit: Record<string, number>; totals: TestDriveFunnel };
  pilot_leads: PilotLead[];
  completions: Completion[];
  testimonials: Testimonial[];
  corridor: string | null;
  segment: string | null;
  generated_at: string;
}

export interface TestDriveSlice {
  corridor?: string;
  segment?: string;
}

function toQuery(params?: TestDriveSlice): string {
  const qs = new URLSearchParams();
  if (params?.corridor) qs.set('corridor', params.corridor);
  if (params?.segment) qs.set('segment', params.segment);
  const q = qs.toString();
  return q ? `?${q}` : '';
}

export async function getTestDriveOverview(params?: TestDriveSlice): Promise<TestDriveOverview> {
  const data = await apiGet<TestDriveOverview>(`/api/admin/test-drive/overview${toQuery(params)}`);
  // Guarantee the list fields exist so the tab never crashes on a partial payload.
  return {
    ...data,
    pilot_leads: data.pilot_leads ?? [],
    completions: data.completions ?? [],
    testimonials: data.testimonials ?? [],
  };
}

export function testDriveContactsCsvUrl(params?: TestDriveSlice): string {
  return `${API_BASE_URL}/api/admin/test-drive/contacts.csv${toQuery(params)}`;
}

// TD-FIX-3 (AIQ-1504): record invites sent so the funnel has a denominator.
export type InviteChannel = 'whatsapp' | 'email' | 'other';

export interface RecordInvitesInput {
  count: number;
  segment?: 'internal' | 'prospect';
  channel: InviteChannel;
}

export async function recordInvitesSent(
  input: RecordInvitesInput,
): Promise<{ ok: boolean; recorded: number }> {
  return apiPost<{ ok: boolean; recorded: number }>('/api/admin/test-drive/invites', input);
}
