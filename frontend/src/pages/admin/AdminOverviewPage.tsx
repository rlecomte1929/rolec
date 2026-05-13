import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card } from '../../components/antigravity';
import { AdminLayout } from './AdminLayout';
import { adminAPI, suppliersAPI } from '../../api/client';
import { buildRoute } from '../../navigation/routes';
import { getAuthItem, normalizeStoredRole } from '../../utils/demo';

type OverviewStats = {
  companies: number;
  hrUsers: number;
  employees: number;
  assignments: number;
  companiesWithPolicy: number;
  activeSuppliers: number;
  supportOpen: number;
  relocationsBlocked: number;
};

export const AdminOverviewPage: React.FC = () => {
  const role = normalizeStoredRole(getAuthItem('relopass_role'));
  const [stats, setStats] = useState<OverviewStats>({
    companies: 0,
    hrUsers: 0,
    employees: 0,
    assignments: 0,
    companiesWithPolicy: 0,
    activeSuppliers: 0,
    supportOpen: 0,
    relocationsBlocked: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (role !== 'ADMIN') return;
    const load = async () => {
      setLoading(true);
      try {
        const results = await Promise.allSettled([
          adminAPI.listCompanies(),
          adminAPI.listHrUsers(),
          adminAPI.listEmployees(),
          adminAPI.listAssignments(),
          adminAPI.listPolicyOverview(),
          adminAPI.listSupportCases({ status: 'open' }),
          adminAPI.listRelocations({ status: 'blocked' }),
          suppliersAPI.list({ status: 'active' }),
        ]);

        const val = <T,>(r: PromiseSettledResult<T>): T | null =>
          r.status === 'fulfilled' ? r.value : null;

        const companiesRes  = val(results[0]) as { companies?: unknown[] } | null;
        const hrUsersRes    = val(results[1]) as { hr_users?: unknown[] } | null;
        const employeesRes  = val(results[2]) as { employees?: unknown[] } | null;
        const assignmentsRes = val(results[3]) as { assignments?: unknown[] } | null;
        const policyRes     = val(results[4]) as { companies?: { policy_status?: string }[] } | null;
        const supportRes    = val(results[5]) as { support_cases?: unknown[] } | null;
        const relocationsRes = val(results[6]) as { relocations?: unknown[] } | null;
        const suppliersRes  = val(results[7]) as { suppliers?: unknown[] } | null;

        const companiesWithPolicy = (policyRes?.companies || []).filter(
          (c) => c.policy_status === 'published'
        ).length;

        setStats({
          companies:          (companiesRes?.companies || []).length,
          hrUsers:            (hrUsersRes?.hr_users || []).length,
          employees:          (employeesRes?.employees || []).length,
          assignments:        (assignmentsRes?.assignments || []).length,
          companiesWithPolicy,
          activeSuppliers:    (suppliersRes?.suppliers || []).length,
          supportOpen:        (supportRes?.support_cases || []).length,
          relocationsBlocked: (relocationsRes?.relocations || []).length,
        });
      } catch {
        // keep defaults — should never reach here now that allSettled is used
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [role]);

  if (role !== 'ADMIN') {
    return (
      <AdminLayout title="Admin Console" subtitle="Restricted">
        <Card padding="lg">You do not have access to the Admin Console.</Card>
      </AdminLayout>
    );
  }

  const cardClass =
    'hover:border-[#0b2b43]/40 transition-colors cursor-pointer block';
  const cardInner = (label: string, value: number, linkLabel: string) => (
    <>
      <div className="text-sm text-[#6b7280]">{label}</div>
      <div className="text-2xl font-semibold text-[#0b2b43]">
        {loading ? '…' : value}
      </div>
      <div className="text-xs text-[#6b7280] mt-1">{linkLabel} →</div>
    </>
  );

  return (
    <AdminLayout
      title="Dashboard"
      subtitle="Operations overview by company"
    >
      <div className="space-y-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
          <Link to={buildRoute('adminCompanies')}>
            <Card padding="lg" className={cardClass}>
              {cardInner('Companies', stats.companies, 'View companies')}
            </Card>
          </Link>
          <Link to={buildRoute('adminPeople')}>
            <Card padding="lg" className={cardClass}>
              {cardInner('HR users', stats.hrUsers, 'View people')}
            </Card>
          </Link>
          <Link to={buildRoute('adminPeople')}>
            <Card padding="lg" className={cardClass}>
              {cardInner('Employees', stats.employees, 'View people')}
            </Card>
          </Link>
          <Link to={buildRoute('adminAssignments')}>
            <Card padding="lg" className={cardClass}>
              {cardInner('Assignments', stats.assignments, 'View assignments')}
            </Card>
          </Link>
          <Link to={buildRoute('adminPolicies')}>
            <Card padding="lg" className={cardClass}>
              {cardInner(
                'Companies with policy',
                stats.companiesWithPolicy,
                'Open Policy Workspace'
              )}
            </Card>
          </Link>
          <Link to={buildRoute('adminSuppliers')}>
            <Card padding="lg" className={cardClass}>
              {cardInner('Active suppliers', stats.activeSuppliers, 'View suppliers')}
            </Card>
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Link to={buildRoute('adminMessages')}>
            <Card padding="lg" className={cardClass}>
              <div className="text-sm text-[#6b7280]">Open support cases</div>
              <div className="text-2xl font-semibold text-[#0b2b43]">
                {loading ? '…' : stats.supportOpen}
              </div>
              <div className="text-xs text-[#6b7280] mt-1">View messages →</div>
            </Card>
          </Link>
          <Link to={buildRoute('adminAssignments')}>
            <Card padding="lg" className={cardClass}>
              <div className="text-sm text-[#6b7280]">Blocked relocations</div>
              <div className="text-2xl font-semibold text-[#0b2b43]">
                {loading ? '…' : stats.relocationsBlocked}
              </div>
              <div className="text-xs text-[#6b7280] mt-1">View assignments →</div>
            </Card>
          </Link>
        </div>
      </div>
    </AdminLayout>
  );
};
