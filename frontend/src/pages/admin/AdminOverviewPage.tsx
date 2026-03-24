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
        const [
          companiesRes,
          hrUsersRes,
          employeesRes,
          assignmentsRes,
          policyRes,
          supportRes,
          relocationsRes,
        ] = await Promise.all([
          adminAPI.listCompanies(),
          adminAPI.listHrUsers(),
          adminAPI.listEmployees(),
          adminAPI.listAssignments(),
          adminAPI.listPolicyOverview(),
          adminAPI.listSupportCases({ status: 'open' }),
          adminAPI.listRelocations({ status: 'blocked' }),
        ]);
        let activeSuppliers = 0;
        try {
          const suppliersRes = await suppliersAPI.list({ status: 'active' });
          activeSuppliers = (suppliersRes.suppliers || []).length;
        } catch {
          // ignore
        }
        const companiesWithPolicy = (policyRes.companies || []).filter(
          (c: { policy_status?: string }) => c.policy_status === 'published'
        ).length;
        setStats({
          companies: (companiesRes.companies || []).length,
          hrUsers: (hrUsersRes.hr_users || []).length,
          employees: (employeesRes.employees || []).length,
          assignments: (assignmentsRes.assignments || []).length,
          companiesWithPolicy,
          activeSuppliers,
          supportOpen: (supportRes.support_cases || []).length,
          relocationsBlocked: (relocationsRes.relocations || []).length,
        });
      } catch {
        // keep defaults
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
