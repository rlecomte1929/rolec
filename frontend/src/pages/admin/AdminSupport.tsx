import React, { useEffect, useState } from 'react';
import { Card, Button, Badge } from '../../components/antigravity';
import { AdminLayout } from './AdminLayout';
import { adminAPI } from '../../api/client';
import type { AdminSupportCase } from '../../types';

export const AdminSupport: React.FC = () => {
  const [cases, setCases] = useState<AdminSupportCase[]>([]);

  const load = async () => {
    const res = await adminAPI.listSupportCases();
    setCases(res.support_cases);
  };

  useEffect(() => {
    load().catch(() => undefined);
  }, []);

  const addNote = async (caseId: string) => {
    const note = window.prompt('Internal note:');
    if (!note) return;
    const reason = window.prompt('Reason for note (required):');
    if (!reason) return;
    await adminAPI.addSupportNote(caseId, { note, reason });
  };

  const exportBundle = async (caseId: string) => {
    const reason = window.prompt('Reason for export (required):');
    if (!reason) return;
    await adminAPI.adminAction('export-support-bundle', {
      reason,
      payload: { support_case_id: caseId },
    });
    alert('Export bundle generated (see response in logs).');
  };

  return (
    <AdminLayout title="Support Center" subtitle="Queue of customer support cases">
      <Card padding="lg">
        <div className="text-sm text-[#6b7280] mb-2">Support cases ({cases.length})</div>
        <div className="space-y-3">
          {cases.map((c) => (
            <div key={c.id} className="flex flex-wrap items-center justify-between border-b border-[#e2e8f0] py-2 gap-3">
              <div>
                <div className="font-medium text-[#0b2b43]">{c.summary || c.id}</div>
                <div className="text-xs text-[#6b7280]">
                  {c.category} · {c.severity} · {c.status} · Error: {c.last_error_code || '—'}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="neutral" size="sm">{c.status.toUpperCase()}</Badge>
                <Button size="sm" variant="outline" onClick={() => addNote(c.id)}>Add note</Button>
                <Button size="sm" onClick={() => exportBundle(c.id)}>Export bundle</Button>
              </div>
            </div>
          ))}
          {cases.length === 0 && (
            <div className="text-sm text-[#6b7280]">No support cases found.</div>
          )}
        </div>
      </Card>
    </AdminLayout>
  );
};
