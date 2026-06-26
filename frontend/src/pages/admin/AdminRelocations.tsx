import React from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Card, Button, Badge } from '../../components/antigravity';
import { adminAPI } from '../../api/client';
import type { AdminRelocationCase } from '../../types';
import { AdminLayout } from './AdminLayout';

export const AdminRelocations: React.FC = () => {
  const queryClient = useQueryClient();

  const casesQuery = useQuery({
    queryKey: ['admin', 'relocations'],
    queryFn: async () => (await adminAPI.listRelocations()).relocations,
  });
  const cases: AdminRelocationCase[] = casesQuery.data ?? [];

  const unlockCase = async (c: AdminRelocationCase) => {
    const reason = window.prompt('Reason for unlock (required):');
    if (!reason) return;
    await adminAPI.adminAction('unlock-case', {
      reason,
      payload: {
        case_id: c.id,
        company_id: c.company_id,
        employee_id: c.employee_id,
        host_country: c.host_country,
        home_country: c.home_country,
        stage: c.stage,
      },
    });
    await queryClient.invalidateQueries({ queryKey: ['admin', 'relocations'] });
  };

  return (
    <AdminLayout title="Assignments" subtitle="All companies, search and drill in">
      <Card padding="lg">
        <div className="text-sm text-[#6b7280] mb-2">Cases ({cases.length})</div>
        <div className="space-y-3">
          {cases.map((c) => (
            <div key={c.id} className="flex flex-wrap items-center justify-between border-b border-[#e2e8f0] py-2 gap-3">
              <div>
                <div className="font-medium text-[#0b2b43]">{c.id}</div>
                <div className="text-xs text-[#6b7280]">
                  {c.host_country || '-'} · Stage: {c.stage || '-'} · Employee: {c.employee_id || '-'}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="neutral" size="sm">{(c.status || 'unknown').toUpperCase()}</Badge>
                <Button size="sm" onClick={() => unlockCase(c)}>Unlock</Button>
              </div>
            </div>
          ))}
          {cases.length === 0 && (
            <div className="text-sm text-[#6b7280]">No relocation cases found.</div>
          )}
        </div>
      </Card>
    </AdminLayout>
  );
};
