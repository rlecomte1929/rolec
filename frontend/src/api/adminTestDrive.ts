import { apiGet, API_BASE_URL } from './client';

/** TD-10 (AIQ-1428) — admin Test-Drive dashboard read model. */

export interface TestDriveFunnel {
  invited: number;
  clicked: number;
  provisioned: number;
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

export interface TestDriveOverview {
  funnel: TestDriveFunnel;
  scorecard: { avg_overall: number | null; problem_fit: Record<string, number>; totals: TestDriveFunnel };
  pilot_leads: PilotLead[];
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
  return apiGet<TestDriveOverview>(`/api/admin/test-drive/overview${toQuery(params)}`);
}

export function testDriveContactsCsvUrl(params?: TestDriveSlice): string {
  return `${API_BASE_URL}/api/admin/test-drive/contacts.csv${toQuery(params)}`;
}
