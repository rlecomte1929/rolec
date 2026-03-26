import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AdminLayout } from './AdminLayout';
import { Card, Select } from '../../components/antigravity';
import { adminAPI } from '../../api/client';
import type { AdminCompany } from '../../types';
import { PolicyConfigPage } from '../../features/policy-config/PolicyConfigPage';
import { PolicyConfigRouteErrorBoundary } from '../../features/policy-config/PolicyConfigRouteErrorBoundary';
import { AdminPolicyAssistantGroundingSection } from '../../features/admin/policy-workspace/AdminPolicyAssistantGroundingSection';
import { getAuthItem, normalizeStoredRole } from '../../utils/demo';

export const AdminPolicyConfigPage: React.FC = () => {
  const role = normalizeStoredRole(getAuthItem('relopass_role'));
  const [searchParams, setSearchParams] = useSearchParams();
  const companyId = searchParams.get('companyId') || '';
  const [companies, setCompanies] = useState<AdminCompany[]>([]);

  const loadCompanies = useCallback(async () => {
    try {
      const res = await adminAPI.listCompanies();
      setCompanies(res.companies ?? []);
    } catch {
      setCompanies([]);
    }
  }, []);

  useEffect(() => {
    if (role === 'ADMIN') loadCompanies().catch(() => undefined);
  }, [role, loadCompanies]);

  const setCompanyId = (id: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (id) next.set('companyId', id);
      else next.delete('companyId');
      return next;
    });
  };

  if (role !== 'ADMIN') {
    return (
      <AdminLayout title="Compensation & Allowance" subtitle="Restricted">
        <Card padding="lg">Admin only.</Card>
      </AdminLayout>
    );
  }

  const options = [
    { value: '', label: 'Select a company…' },
    ...companies.map((c) => ({ value: c.id, label: c.name || c.id })),
  ];

  return (
    <AdminLayout
      title="Compensation & Allowance"
      subtitle="Per-company structured matrix (draft / publish)"
    >
      <Card padding="lg" className="mb-6 max-w-xl">
        <Select
          label="Company"
          value={companyId}
          onChange={(v) => setCompanyId(v)}
          options={options}
        />
      </Card>
      {companyId ? (
        <PolicyConfigRouteErrorBoundary>
          <PolicyConfigPage mode="admin" adminCompanyId={companyId} />
          <AdminPolicyAssistantGroundingSection companyId={companyId} />
        </PolicyConfigRouteErrorBoundary>
      ) : (
        <Card padding="lg">
          <p className="text-sm text-[#64748b]">Choose a company to load or edit its compensation configuration.</p>
        </Card>
      )}
    </AdminLayout>
  );
};
