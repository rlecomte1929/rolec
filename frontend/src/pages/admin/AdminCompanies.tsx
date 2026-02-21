import React, { useEffect, useState } from 'react';
import { Card, Button } from '../../components/antigravity';
import { AdminLayout } from './AdminLayout';
import { adminAPI } from '../../api/client';
import type { AdminCompany } from '../../types';
import { Link } from 'react-router-dom';

export const AdminCompanies: React.FC = () => {
  const [query, setQuery] = useState('');
  const [companies, setCompanies] = useState<AdminCompany[]>([]);

  const load = async () => {
    const res = await adminAPI.listCompanies(query);
    setCompanies(res.companies);
  };

  useEffect(() => {
    load().catch(() => undefined);
  }, []);

  return (
    <AdminLayout title="Companies" subtitle="Search and inspect company accounts">
      <Card padding="lg" className="mb-4">
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search company name"
            className="w-64 rounded-full border border-[#e2e8f0] px-4 py-2 text-sm"
          />
          <Button onClick={() => load()}>Search</Button>
        </div>
      </Card>
      <Card padding="lg">
        <div className="text-sm text-[#6b7280] mb-2">Companies ({companies.length})</div>
        <div className="space-y-2">
          {companies.map((c) => (
            <div key={c.id} className="flex items-center justify-between border-b border-[#e2e8f0] py-2">
              <div>
                <Link to={`/admin/companies/${c.id}`} className="font-medium text-[#0b2b43] hover:underline">
                  {c.name}
                </Link>
                <div className="text-xs text-[#6b7280]">{c.country || '—'} · {c.size_band || '—'}</div>
              </div>
              <div className="text-xs text-[#6b7280]">{c.id}</div>
            </div>
          ))}
          {companies.length === 0 && (
            <div className="text-sm text-[#6b7280]">No companies found.</div>
          )}
        </div>
      </Card>
    </AdminLayout>
  );
};
