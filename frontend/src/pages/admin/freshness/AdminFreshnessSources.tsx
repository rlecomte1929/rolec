import React, { useEffect, useState } from 'react';
import { AdminFreshnessLayout } from './AdminFreshnessLayout';
import { FreshnessStatusBadge } from '../../../components/admin/freshness/FreshnessStatusBadge';
import { adminFreshnessAPI } from '../../../api/client';

type SourceItem = {
  source_name?: string;
  country_code?: string;
  city_name?: string;
  content_domain?: string;
  last_crawl?: string;
  expected_cadence_days?: number;
  freshness_state?: string;
};

export const AdminFreshnessSources: React.FC = () => {
  const [items, setItems] = useState<SourceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    adminFreshnessAPI
      .getSources()
      .then((r) => setItems(r.items ?? []))
      .catch((e) => setError((e as Error)?.message || 'Failed'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <AdminFreshnessLayout title="Source freshness" subtitle="Per-source operational status">
        <div className="py-12 text-center text-slate-500">Loading...</div>
      </AdminFreshnessLayout>
    );
  }
  if (error) {
    return (
      <AdminFreshnessLayout title="Source freshness" subtitle="Per-source operational status">
        <div className="rounded-lg bg-red-50 p-4 text-red-700">{error}</div>
      </AdminFreshnessLayout>
    );
  }

  return (
    <AdminFreshnessLayout title="Source freshness" subtitle="Per-source operational status">
      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-left text-slate-600">
              <th className="px-4 py-2">Source</th>
              <th className="px-4 py-2">Country</th>
              <th className="px-4 py-2">City</th>
              <th className="px-4 py-2">Domain</th>
              <th className="px-4 py-2">Cadence</th>
              <th className="px-4 py-2">Last crawl</th>
              <th className="px-4 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {items.map((s) => (
              <tr key={String(s.source_name)} className="border-b border-slate-100 hover:bg-slate-50">
                <td className="px-4 py-2 font-medium">{s.source_name ?? '-'}</td>
                <td className="px-4 py-2">{s.country_code ?? '-'}</td>
                <td className="px-4 py-2">{s.city_name ?? '-'}</td>
                <td className="px-4 py-2">{s.content_domain ?? '-'}</td>
                <td className="px-4 py-2">{s.expected_cadence_days ?? '-'}d</td>
                <td className="px-4 py-2">
                  {s.last_crawl ? new Date(s.last_crawl).toLocaleString() : '-'}
                </td>
                <td className="px-4 py-2">
                  <FreshnessStatusBadge state={s.freshness_state ?? 'stale'} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {items.length === 0 && (
        <div className="py-8 text-center text-slate-500">No source data</div>
      )}
    </AdminFreshnessLayout>
  );
};
