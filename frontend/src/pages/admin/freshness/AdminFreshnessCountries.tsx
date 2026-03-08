import React, { useEffect, useState } from 'react';
import { AdminFreshnessLayout } from './AdminFreshnessLayout';
import { adminFreshnessAPI } from '../../../api/client';

type CountryItem = {
  country_code?: string;
  fresh_count?: number;
  stale_count?: number;
  overdue_count?: number;
  sources?: string[];
};

export const AdminFreshnessCountries: React.FC = () => {
  const [items, setItems] = useState<CountryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    adminFreshnessAPI
      .getCountries()
      .then((r) => setItems(r.items ?? []))
      .catch((e) => setError((e as Error)?.message || 'Failed'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <AdminFreshnessLayout title="Freshness by country" subtitle="Country-level freshness">
        <div className="py-12 text-center text-slate-500">Loading...</div>
      </AdminFreshnessLayout>
    );
  }
  if (error) {
    return (
      <AdminFreshnessLayout title="Freshness by country" subtitle="Country-level freshness">
        <div className="rounded-lg bg-red-50 p-4 text-red-700">{error}</div>
      </AdminFreshnessLayout>
    );
  }

  return (
    <AdminFreshnessLayout title="Freshness by country" subtitle="Country-level freshness">
      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-left text-slate-600">
              <th className="px-4 py-2">Country</th>
              <th className="px-4 py-2">Fresh</th>
              <th className="px-4 py-2">Stale</th>
              <th className="px-4 py-2">Overdue</th>
              <th className="px-4 py-2">Sources</th>
            </tr>
          </thead>
          <tbody>
            {items.map((c) => (
              <tr key={String(c.country_code)} className="border-b border-slate-100 hover:bg-slate-50">
                <td className="px-4 py-2 font-medium">{c.country_code ?? '-'}</td>
                <td className="px-4 py-2">{c.fresh_count ?? 0}</td>
                <td className="px-4 py-2">{c.stale_count ?? 0}</td>
                <td className="px-4 py-2">{c.overdue_count ?? 0}</td>
                <td className="px-4 py-2 text-slate-600">
                  {(c.sources ?? []).slice(0, 3).join(', ')}
                  {(c.sources?.length ?? 0) > 3 ? '…' : ''}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {items.length === 0 && (
        <div className="py-8 text-center text-slate-500">No country data</div>
      )}
    </AdminFreshnessLayout>
  );
};
