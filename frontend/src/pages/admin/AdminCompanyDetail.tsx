import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Card, Badge } from '../../components/antigravity';
import { AdminLayout } from './AdminLayout';
import { adminAPI } from '../../api/client';
import type { AdminCompany, AdminEmployee, AdminHrUser } from '../../types';

export const AdminCompanyDetail: React.FC = () => {
  const { companyId } = useParams();
  const [company, setCompany] = useState<AdminCompany | null>(null);
  const [hrUsers, setHrUsers] = useState<AdminHrUser[]>([]);
  const [employees, setEmployees] = useState<AdminEmployee[]>([]);
  const [policies, setPolicies] = useState<any[]>([]);

  useEffect(() => {
    if (!companyId) return;
    adminAPI.getCompanyDetail(companyId).then((res) => {
      setCompany(res.company);
      setHrUsers(res.hr_users || []);
      setEmployees(res.employees || []);
      setPolicies(res.policies || []);
    }).catch(() => undefined);
  }, [companyId]);

  return (
    <AdminLayout title="Company Detail" subtitle={company?.name || companyId}>
      <Card padding="lg" className="mb-4">
        <div className="text-sm text-[#6b7280]">Company</div>
        <div className="text-lg font-semibold text-[#0b2b43]">{company?.name || '—'}</div>
        <div className="text-xs text-[#6b7280]">{company?.country || '—'} · {company?.size_band || '—'}</div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card padding="lg">
          <div className="text-sm text-[#6b7280] mb-2">HR Users</div>
          <div className="space-y-2">
            {hrUsers.map((h) => (
              <div key={h.id} className="flex items-center justify-between border-b border-[#e2e8f0] py-2">
                <div className="text-sm text-[#0b2b43]">{h.profile_id}</div>
                <Badge variant="neutral" size="sm">HR</Badge>
              </div>
            ))}
            {hrUsers.length === 0 && <div className="text-sm text-[#6b7280]">No HR users.</div>}
          </div>
        </Card>

        <Card padding="lg">
          <div className="text-sm text-[#6b7280] mb-2">Employees</div>
          <div className="space-y-2">
            {employees.map((e) => (
              <div key={e.id} className="flex items-center justify-between border-b border-[#e2e8f0] py-2">
                <div className="text-sm text-[#0b2b43]">{e.profile_id}</div>
                <Badge variant="neutral" size="sm">{e.status || 'active'}</Badge>
              </div>
            ))}
            {employees.length === 0 && <div className="text-sm text-[#6b7280]">No employees.</div>}
          </div>
        </Card>

        <Card padding="lg">
          <div className="text-sm text-[#6b7280] mb-2">Policy versions</div>
          <div className="space-y-2">
            {policies.map((p) => (
              <div key={p.id} className="flex items-center justify-between border-b border-[#e2e8f0] py-2">
                <div>
                  <div className="text-sm text-[#0b2b43]">{p.policyName || p.id}</div>
                  <div className="text-xs text-[#6b7280]">v{p._meta?.version || 1} · {p._meta?.status || 'draft'}</div>
                </div>
                <Badge variant="neutral" size="sm">{p._meta?.status || 'draft'}</Badge>
              </div>
            ))}
            {policies.length === 0 && <div className="text-sm text-[#6b7280]">No policies found.</div>}
          </div>
        </Card>
      </div>
    </AdminLayout>
  );
};
