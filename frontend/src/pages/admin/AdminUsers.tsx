import React, { useEffect, useState } from 'react';
import { Card, Button, Badge } from '../../components/antigravity';
import { AdminLayout } from './AdminLayout';
import { adminAPI } from '../../api/client';
import type { AdminProfile } from '../../types';

export const AdminUsers: React.FC = () => {
  const [query, setQuery] = useState('');
  const [profiles, setProfiles] = useState<AdminProfile[]>([]);

  const load = async () => {
    const res = await adminAPI.listProfiles(query);
    setProfiles(res.profiles);
  };

  useEffect(() => {
    load().catch(() => undefined);
  }, []);

  const startViewAs = async (profile: AdminProfile, mode: 'hr' | 'employee') => {
    const reason = window.prompt('Reason for view-as (required):');
    if (!reason) return;
    await adminAPI.startImpersonation({ targetUserId: profile.id, mode, reason });
    window.location.href = mode === 'hr' ? '/hr/dashboard' : '/employee/journey';
  };

  return (
    <AdminLayout title="People" subtitle="HR and employee accounts — view-as and manage">
      <Card padding="lg" className="mb-4">
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by email or name"
            className="w-64 rounded-full border border-[#e2e8f0] px-4 py-2 text-sm"
          />
          <Button onClick={() => load()}>Apply</Button>
        </div>
      </Card>
      <Card padding="lg">
        <div className="text-sm text-[#6b7280] mb-2">Profiles ({profiles.length})</div>
        <div className="space-y-3">
          {profiles.map((p) => (
            <div key={p.id} className="flex flex-wrap items-center justify-between border-b border-[#e2e8f0] py-2 gap-3">
              <div>
                <div className="font-medium text-[#0b2b43]">{p.full_name || p.email || p.id}</div>
                <div className="text-xs text-[#6b7280]">{p.email || '—'} · {p.id}</div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="neutral" size="sm">{(p.role || '').toUpperCase()}</Badge>
                <Button size="sm" onClick={() => startViewAs(p, 'employee')}>
                  View as employee
                </Button>
                <Button size="sm" variant="outline" onClick={() => startViewAs(p, 'hr')}>
                  View as HR
                </Button>
              </div>
            </div>
          ))}
          {profiles.length === 0 && (
            <div className="py-8 text-center text-[#6b7280]">
              <div className="text-sm font-medium">No profiles found</div>
              <div className="text-xs mt-1">Profiles appear when users register or are provisioned.</div>
            </div>
          )}
        </div>
      </Card>
    </AdminLayout>
  );
};
