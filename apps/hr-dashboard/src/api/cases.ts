import { api } from '../lib/api';
import type { CaseRow, CasesListResponse } from '../features/cases/types';

/**
 * Fetch the HR case list. Backend route: GET /api/hr/cases.
 *
 * The endpoint takes an optional `?status=...` query (string-typed) that
 * filters server-side. For multi-status filtering and corridor / employee
 * filtering, the API currently does the simple thing and we filter on the
 * client. That's fine while pilot tenants stay under ~500 cases. The brief
 * lists virtualization as a hard requirement; we honor that. A follow-up
 * task can push search + corridor into the SQL once it matters.
 *
 * RLS / scoping: the route already enforces `employer_id = JWT.company_id`
 * server-side via `_get_hr_company_id(effective)`. We don't pass any
 * tenant-scoping query from here — the JWT does the work.
 */
export async function listCases(opts?: { status?: string }): Promise<CaseRow[]> {
  const params = opts?.status ? { status: opts.status } : undefined;
  const { data } = await api.get<CasesListResponse>('/api/hr/cases', { params });
  return data?.cases ?? [];
}
