import React, { useEffect, useState } from 'react';
import { Card } from '../../components/antigravity';
import { AdminLayout } from './AdminLayout';
import { adminAPI } from '../../api/client';
import { getAuthItem } from '../../utils/demo';

export const AdminDashboard: React.FC = () => {
  const role = getAuthItem('relopass_role');
  const [stats, setStats] = useState({
    companies: 0,
    supportOpen: 0,
    relocationsBlocked: 0,
  });
  const [purging, setPurging] = useState(false);

  useEffect(() => {
    if (role !== 'ADMIN') return;
    Promise.all([
      adminAPI.listCompanies(),
      adminAPI.listSupportCases({ status: 'open' }),
      adminAPI.listRelocations({ status: 'blocked' }),
    ]).then(([companies, support, relocations]) => {
      setStats({
        companies: companies.companies.length,
        supportOpen: support.support_cases.length,
        relocationsBlocked: relocations.relocations.length,
      });
    }).catch(() => {
      // Ignore errors for now
    });
  }, [role]);

  if (role !== 'ADMIN') {
    return (
      <AdminLayout title="Admin Console" subtitle="Restricted">
        <Card padding="lg">
          You do not have access to the Admin Console.
        </Card>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout title="Admin Console" subtitle="Overview of support and operations">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card padding="lg">
          <div className="text-sm text-[#6b7280]">Active companies</div>
          <div className="text-2xl font-semibold text-[#0b2b43]">{stats.companies}</div>
        </Card>
        <Card padding="lg">
          <div className="text-sm text-[#6b7280]">Open support cases</div>
          <div className="text-2xl font-semibold text-[#0b2b43]">{stats.supportOpen}</div>
        </Card>
        <Card padding="lg">
          <div className="text-sm text-[#6b7280]">Blocked relocations</div>
          <div className="text-2xl font-semibold text-[#0b2b43]">{stats.relocationsBlocked}</div>
        </Card>
      </div>
      <Card padding="lg" className="mt-6 border border-amber-200 bg-amber-50">
        <div className="text-sm font-semibold text-amber-900 mb-2">Danger zone</div>
        <div className="text-sm text-amber-900 mb-4">
          Purge inactive cases and related data. This keeps only active, registered cases.
        </div>
        <button
          onClick={async () => {
            const confirmText = window.prompt('Type PURGE to confirm:');
            if (confirmText !== 'PURGE') return;
            const reason = window.prompt('Reason for purge (required):');
            if (!reason) return;
            setPurging(true);
            try {
              const res = await adminAPI.adminAction('purge-cases', {
                reason,
                payload: {
                  active_statuses: ['IN_PROGRESS', 'EMPLOYEE_SUBMITTED', 'HR_REVIEW'],
                },
              });
              alert(`Purge complete. Assignments deleted: ${res.stats?.assignments_deleted ?? 0}, Relocation cases deleted: ${res.stats?.relocation_cases_deleted ?? 0}`);
            } finally {
              setPurging(false);
            }
          }}
          className="text-xs px-4 py-2 rounded-full bg-amber-100 text-amber-900 hover:bg-amber-200"
          disabled={purging}
        >
          {purging ? 'Purging…' : 'Purge inactive cases'}
        </button>
      </Card>
    </AdminLayout>
  );
};
