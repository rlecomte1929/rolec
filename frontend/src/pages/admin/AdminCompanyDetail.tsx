import React, { useCallback, useEffect, useState } from 'react';
import { useParams, Link, useLocation } from 'react-router-dom';
import { Card, Badge, Button } from '../../components/antigravity';
import { AdminLayout } from './AdminLayout';
import { adminAPI } from '../../api/client';
import { buildRoute } from '../../navigation/routes';
import type {
  AdminCompany,
  AdminEmployee,
  AdminHrUser,
  AdminCompanyDetailAssignment,
  AdminCompanyDetailPolicy,
  AdminCompanyDetailCounts,
  AdminCompanyDetailOrphanDiagnostics,
} from '../../types';

export const AdminCompanyDetail: React.FC = () => {
  const { companyId } = useParams<{ companyId: string }>();
  const location = useLocation();
  const [company, setCompany] = useState<AdminCompany | null>(null);
  const [hrUsers, setHrUsers] = useState<AdminHrUser[]>([]);
  const [employees, setEmployees] = useState<AdminEmployee[]>([]);
  const [assignments, setAssignments] = useState<AdminCompanyDetailAssignment[]>([]);
  const [policies, setPolicies] = useState<AdminCompanyDetailPolicy[]>([]);
  const [counts, setCounts] = useState<AdminCompanyDetailCounts | null>(null);
  const [orphanDiagnostics, setOrphanDiagnostics] = useState<AdminCompanyDetailOrphanDiagnostics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDetail = useCallback(() => {
    if (!companyId) return Promise.resolve();
    setLoading(true);
    setError(null);
    return adminAPI
      .getCompanyDetail(companyId)
      .then((res) => {
        setCompany(res.company);
        setHrUsers(res.hr_users ?? []);
        setEmployees(res.employees ?? []);
        setAssignments(res.assignments ?? []);
        setPolicies(res.policies ?? []);
        const summary = (res as { summary?: AdminCompanyDetailCounts; counts_summary?: AdminCompanyDetailCounts }).summary
          ?? (res as { counts_summary?: AdminCompanyDetailCounts }).counts_summary ?? null;
        setCounts(summary);
        setOrphanDiagnostics(res.orphan_diagnostics ?? null);
      })
      .catch((e: unknown) => {
        const err = e as { response?: { status?: number; data?: { detail?: string } }; message?: string };
        const detail = err?.response?.data?.detail;
        const status = err?.response?.status;
        const msg = typeof detail === 'string' ? detail : err?.message || 'Failed to load company';
        setError(status ? `[${status}] ${msg}` : msg);
      })
      .finally(() => setLoading(false));
  }, [companyId]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail, location.key]);

  const hasOrphanIssues =
    orphanDiagnostics &&
    ((orphanDiagnostics.assignments_case_missing_company_id ?? 0) > 0 ||
      (orphanDiagnostics.hr_users_missing_profile ?? 0) > 0 ||
      (orphanDiagnostics.employees_missing_profile ?? 0) > 0);

  if (loading && !company) {
    return (
      <AdminLayout title="Company Detail" subtitle="-">
        <div className="py-8 text-center text-[#6b7280]">Loading...</div>
      </AdminLayout>
    );
  }

  if (error || !company) {
    return (
      <AdminLayout title="Company Detail" subtitle="-">
        <Card padding="lg">
          <div className="text-[#7a2a2a] font-medium">{error || 'Company not found.'}</div>
          <p className="text-sm text-[#6b7280] mt-1">
            If the problem persists, check that the company exists and you have access. Retry or return to the list.
          </p>
          <div className="flex flex-wrap gap-2 mt-4">
            <Button
              variant="outline"
              size="sm"
              onClick={() => window.location.reload()}
            >
              Retry
            </Button>
            <Link to={buildRoute('adminCompanies')}>
              <Button variant="outline" size="sm">← Back to Companies</Button>
            </Link>
          </div>
        </Card>
      </AdminLayout>
    );
  }

  const hrCount = counts?.hr_users_count ?? hrUsers.length;
  const empCount = (counts as { employee_count?: number; employees_count?: number })?.employee_count
    ?? (counts as { employees_count?: number })?.employees_count ?? employees.length;
  const assignCount = counts?.assignments_count ?? assignments.length;
  const policyCount = counts?.policies_count ?? policies.length;

  return (
    <AdminLayout title="Company Detail" subtitle={company.name}>
      {/* Company summary */}
      <Card padding="lg" className="mb-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-lg font-semibold text-[#0b2b43]">{company.name}</h2>
              {company.missing_from_registry && (
                <Badge variant="warning" size="sm">Not in registry</Badge>
              )}
              {company.status && (
                <Badge variant={company.status === 'active' ? 'success' : 'neutral'} size="sm">
                  {String(company.status)}
                </Badge>
              )}
            </div>
            <div className="text-sm text-[#6b7280] mt-1">
              Plan: {(company as { plan_tier?: string }).plan_tier ?? '-'} · {company.country ?? '-'} · {company.size_band ?? '-'}
            </div>
            <div className="text-xs text-[#6b7280] mt-1">
              Primary contact: {company.hr_contact ?? (hrUsers[0]?.name || hrUsers[0]?.email) ?? '-'}
            </div>
            <div className="text-xs text-[#6b7280] mt-0.5">
              {company.address ?? '-'} · {company.phone ?? '-'}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => void loadDetail()} disabled={loading}>
              {loading ? 'Refreshing…' : 'Refresh'}
            </Button>
            <Link to={buildRoute('adminCompanies')} className="text-sm text-[#0b2b43] underline">
              ← Companies
            </Link>
          </div>
        </div>
      </Card>

      {/* Orphan diagnostics */}
      {hasOrphanIssues && orphanDiagnostics && (
        <Card padding="lg" className="mb-4 border-amber-200 bg-amber-50/50">
          <div className="text-sm font-medium text-amber-800 mb-1">Linkage diagnostics</div>
          <ul className="text-xs text-amber-700 space-y-0.5">
            {(orphanDiagnostics.assignments_case_missing_company_id ?? 0) > 0 && (
              <li>Assignments whose case has no company_id: {orphanDiagnostics.assignments_case_missing_company_id}</li>
            )}
            {(orphanDiagnostics.hr_users_missing_profile ?? 0) > 0 && (
              <li>HR users with missing profile: {orphanDiagnostics.hr_users_missing_profile}</li>
            )}
            {(orphanDiagnostics.employees_missing_profile ?? 0) > 0 && (
              <li>Employees with missing profile: {orphanDiagnostics.employees_missing_profile}</li>
            )}
          </ul>
        </Card>
      )}

      {/* HR Users */}
      <Card padding="lg" className="mb-4">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <h3 className="text-sm font-semibold text-[#0b2b43]">HR Users ({hrCount})</h3>
          <Link
            to={`${buildRoute('adminPeople')}?company_id=${encodeURIComponent(company.id)}&role=HR`}
            className="text-sm text-[#0b2b43] underline"
          >
            Add HR user
          </Link>
        </div>
        {hrUsers.length === 0 ? (
          <div className="text-sm text-[#6b7280] py-2">No HR users linked to this company.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b border-[#e2e8f0] text-left text-[#6b7280] font-medium">
                  <th className="py-2 pr-4">Name</th>
                  <th className="py-2 pr-4">Email</th>
                  <th className="py-2 pr-4">Status</th>
                </tr>
              </thead>
              <tbody>
                {hrUsers.map((h) => (
                  <tr key={h.id} className="border-b border-[#e2e8f0]">
                    <td className="py-2 pr-4 text-[#0b2b43]">{h.name ?? h.profile_id}</td>
                    <td className="py-2 pr-4 text-[#374151]">{h.email ?? '-'}</td>
                    <td className="py-2 pr-4">
                      <Badge variant="neutral" size="sm">{h.status ?? 'active'}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Employees */}
      <Card padding="lg" className="mb-4">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <h3 className="text-sm font-semibold text-[#0b2b43]">Employees ({empCount})</h3>
          <Link
            to={`${buildRoute('adminPeople')}?company_id=${encodeURIComponent(company.id)}&role=EMPLOYEE`}
            className="text-sm text-[#0b2b43] underline"
          >
            Add employee
          </Link>
        </div>
        {employees.length === 0 ? (
          <div className="text-sm text-[#6b7280] py-2">No employees linked to this company.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b border-[#e2e8f0] text-left text-[#6b7280] font-medium">
                  <th className="py-2 pr-4">Name</th>
                  <th className="py-2 pr-4">Email</th>
                  <th className="py-2 pr-4">Status</th>
                </tr>
              </thead>
              <tbody>
                {employees.map((e) => (
                  <tr key={e.id} className="border-b border-[#e2e8f0]">
                    <td className="py-2 pr-4 text-[#0b2b43]">{e.name ?? e.profile_id}</td>
                    <td className="py-2 pr-4 text-[#374151]">{e.email ?? '-'}</td>
                    <td className="py-2 pr-4">
                      <Badge variant="neutral" size="sm">{e.status ?? 'active'}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Assignments / cases */}
      <Card padding="lg" className="mb-4">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <h3 className="text-sm font-semibold text-[#0b2b43]">Assignments ({assignCount})</h3>
          <Link
            to={`${buildRoute('adminAssignments')}?company_id=${encodeURIComponent(company.id)}`}
            className="text-sm text-[#0b2b43] underline"
          >
            View assignments
          </Link>
        </div>
        {assignments.length === 0 ? (
          <div className="text-sm text-[#6b7280] py-2">No assignments linked to this company.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b border-[#e2e8f0] text-left text-[#6b7280] font-medium">
                  <th className="py-2 pr-4">Employee</th>
                  <th className="py-2 pr-4">Destination</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pl-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {assignments.map((a) => (
                  <tr key={a.id} className="border-b border-[#e2e8f0]">
                    <td className="py-2 pr-4 text-[#0b2b43]">{a.employee_name ?? '-'}</td>
                    <td className="py-2 pr-4 text-[#374151]">{a.destination ?? '-'}</td>
                    <td className="py-2 pr-4">
                      <Badge variant="neutral" size="sm">{a.status ?? '-'}</Badge>
                    </td>
                    <td className="py-2 pl-2">
                      <Link to={buildRoute('hrAssignmentReview', { id: a.id })} className="text-sm text-[#0b2b43] underline">
                        Open
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Policy workspace */}
      <Card padding="lg" className="mb-4">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <h3 className="text-sm font-semibold text-[#0b2b43]">Policy records ({policyCount})</h3>
          <Link
            to={`${buildRoute('adminPolicies')}?company_id=${encodeURIComponent(company.id)}`}
            className="text-sm text-[#0b2b43] underline"
          >
            Open Policy Workspace
          </Link>
        </div>
        {policies.length === 0 ? (
          <div className="text-sm text-[#6b7280] py-2">No policies linked to this company.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b border-[#e2e8f0] text-left text-[#6b7280] font-medium">
                  <th className="py-2 pr-4">Title</th>
                  <th className="py-2 pr-4">Version</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Published</th>
                  <th className="py-2 pl-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {policies.map((p) => (
                  <tr key={p.policy_id} className="border-b border-[#e2e8f0]">
                    <td className="py-2 pr-4 text-[#0b2b43]">{p.title ?? p.policy_id}</td>
                    <td className="py-2 pr-4 text-[#374151]">{p.latest_version ?? '-'}</td>
                    <td className="py-2 pr-4">
                      <Badge variant="neutral" size="sm">{p.status ?? 'draft'}</Badge>
                    </td>
                    <td className="py-2 pr-4">{p.published ? 'Yes' : 'No'}</td>
                    <td className="py-2 pl-2">
                      <Link
                        to={`${buildRoute('hrPolicy')}?adminCompanyId=${encodeURIComponent(company.id)}`}
                        className="text-sm text-[#0b2b43] underline"
                      >
                        Open
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Quick actions */}
      <Card padding="lg">
        <h3 className="text-sm font-semibold text-[#0b2b43] mb-3">Quick actions</h3>
        <div className="flex flex-wrap gap-2">
          <Link to={`${buildRoute('adminPeople')}?company_id=${encodeURIComponent(company.id)}`}>
            <Button variant="outline" size="sm">People (company filter)</Button>
          </Link>
          <Link to={`${buildRoute('adminAssignments')}?company_id=${encodeURIComponent(company.id)}`}>
            <Button variant="outline" size="sm">Assignments</Button>
          </Link>
          <Link to={`${buildRoute('adminPolicies')}?company_id=${encodeURIComponent(company.id)}`}>
            <Button variant="outline" size="sm">Policy Workspace</Button>
          </Link>
          <Link to={buildRoute('adminCompanies')}>
            <Button variant="outline" size="sm">Edit company (Companies list)</Button>
          </Link>
        </div>
      </Card>
    </AdminLayout>
  );
};
