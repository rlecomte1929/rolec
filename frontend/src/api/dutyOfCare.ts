/**
 * HR duty-of-care board — GET /api/hr/duty-of-care
 *
 * Company-scoped server-side. Do not send a company_id from the client.
 */
import api from './client';

export type DutyOfCareStatus =
  | 'red'
  | 'amber'
  | 'green'
  | 'unknown'
  | 'not_tracked';

export interface DutyOfCarePermit {
  status: DutyOfCareStatus;
  expiry_date: string | null;
  type: string | null;
}

export interface DutyOfCareChecklist {
  status: DutyOfCareStatus;
  completed: number;
  total: number;
}

export interface DutyOfCareCase {
  case_id: string;
  company_id: string | null;
  employee_id: string | null;
  employee_name: string | null;
  host_country: string | null;
  home_country: string | null;
  expected_start_date: string | null;
  departing_soon: boolean;
  overall: DutyOfCareStatus;
  permit: DutyOfCarePermit;
  alert: { status: DutyOfCareStatus };
  checklist: DutyOfCareChecklist;
  a1: { status: DutyOfCareStatus };
  medical: { status: DutyOfCareStatus };
  insurance: { status: DutyOfCareStatus };
}

export interface DutyOfCareResponse {
  cases: DutyOfCareCase[];
}

export async function listDutyOfCare(): Promise<DutyOfCareResponse> {
  const { data } = await api.get<DutyOfCareResponse>('/api/hr/duty-of-care');
  return data;
}

/** Honesty: unknown / not_tracked must never be styled as an all-clear. */
export function isUntracked(status: DutyOfCareStatus): boolean {
  return status === 'unknown' || status === 'not_tracked';
}
