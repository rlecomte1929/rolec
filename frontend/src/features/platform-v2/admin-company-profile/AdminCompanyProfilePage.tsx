import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { AdminLayout } from '../../../pages/admin/AdminLayout';
import { adminAPI } from '../../../api/client';
import type { AdminCompany, CompanyProfilePayload } from '../../../types';
import { CompanyProfileForm } from '../company-profile/CompanyProfileForm';

/**
 * Admin-scoped tenant profile.
 *
 * Mounts the same CompanyProfileForm as /hr/company-profile-v2 but its data
 * source is the admin endpoint:
 *   GET  /api/admin/companies/{id}    — load
 *   PATCH /api/admin/companies/{id}   — save (via adminAPI.updateCompany)
 *
 * URL drives scope. Refreshing /admin/companies/abc/profile shows the same
 * tenant; closing the tab "exits". No global state to leak — see DECISIONS
 * "Admin tenant scoping" entry for the rationale.
 *
 * Logo upload/remove are intentionally NOT wired here: the existing endpoints
 * (/api/hr/company-profile/logo) operate in HR session scope, not admin
 * tenant scope. The shared form hides the upload UI when those handlers are
 * absent and surfaces a small notice ("Logo upload only available to HR…").
 */
export function AdminCompanyProfilePage() {
  const { companyId } = useParams<{ companyId: string }>();
  const queryClient = useQueryClient();

  const companyQuery = useQuery({
    queryKey: ['admin', 'company-detail', companyId],
    queryFn: () => adminAPI.getCompanyDetail(companyId as string),
    enabled: !!companyId,
  });
  const company: AdminCompany | null = companyQuery.data?.company ?? null;
  const loading = companyId ? companyQuery.isLoading : false;
  const loadError = !companyId
    ? 'Missing :companyId in URL.'
    : companyQuery.isError
      ? (() => {
          const err = companyQuery.error as {
            response?: { status?: number; data?: { detail?: string } };
            message?: string;
          } | null;
          const status = err?.response?.status;
          const detail = err?.response?.data?.detail ?? err?.message ?? 'Failed to load tenant';
          return status ? `[${status}] ${detail}` : detail;
        })()
      : null;

  async function handleSave(payload: CompanyProfilePayload) {
    if (!companyId) throw new Error('Missing :companyId');
    await adminAPI.updateCompany(companyId, payload);
    await queryClient.invalidateQueries({ queryKey: ['admin', 'company-detail', companyId] });
  }

  const tenantName = company?.name ?? '…';

  return (
    <AdminLayout>
      <CompanyProfileForm
        company={company as unknown as Record<string, unknown> | null}
        loading={loading}
        loadError={loadError}
        onSave={handleSave}
        eyebrow={`ReloPass · /admin/companies/${companyId}/profile`}
        title={tenantName}
        subtitle="Admin view of this tenant's profile. Changes save against the tenant. To see what this tenant's HR sees, use the impersonation flow (not yet wired)."
        badge="tenant"
        backTo={`/admin/companies/${companyId}`}
        backLabel="Back to tenant"
        topSlot={
          <nav className="mb-3 flex items-center gap-2 text-[12px] text-slate-500">
            <Link to="/admin/companies-v2" className="text-accent-600 hover:underline">
              ← Companies
            </Link>
            <span className="text-slate-500">/</span>
            <Link to={`/admin/companies/${companyId}`} className="text-accent-600 hover:underline">
              {tenantName}
            </Link>
            <span className="text-slate-500">/</span>
            <span className="text-slate-700">Profile</span>
          </nav>
        }
      />
    </AdminLayout>
  );
}

export default AdminCompanyProfilePage;
