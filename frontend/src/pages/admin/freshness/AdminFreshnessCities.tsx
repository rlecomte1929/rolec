import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AdminFreshnessLayout } from './AdminFreshnessLayout';
import { adminFreshnessAPI } from '../../../api/client';

type CityItem = {
  country_code?: string;
  city_name?: string;
  fresh_count?: number;
  stale_count?: number;
  overdue_count?: number;
};

export const AdminFreshnessCities: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const countryCode = searchParams.get('country') || undefined;
  const [filter, setFilter] = useState('');
  const [items, setItems] = useState<CityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setFilter(countryCode ?? '');
  }, [countryCode]);

  useEffect(() => {
    adminFreshnessAPI
      .getCities(countryCode ? { country_code: countryCode } : undefined)
      .then((r) => setItems(r.items ?? []))
      .catch((e) => setError((e as Error)?.message || 'Failed'))
      .finally(() => setLoading(false));
  }, [countryCode]);

  const applyFilter = () => {
    if (filter.trim()) setSearchParams({ country: filter.trim() });
    else setSearchParams({});
  };

  if (loading) {
    return (
      <AdminFreshnessLayout title="Freshness by city" subtitle="City-level freshness">
        <div className="py-12 text-center text-slate-500">Loading...</div>
      </AdminFreshnessLayout>
    );
  }
  if (error) {
    return (
      <AdminFreshnessLayout title="Freshness by city" subtitle="City-level freshness">
        <div className="rounded-lg bg-red-50 p-4 text-red-700">{error}</div>
      </AdminFreshnessLayout>
    );
  }

  return (
    <AdminFreshnessLayout title="Freshness by city" subtitle="City-level freshness">
      <div className="mb-4 flex items-center gap-2">
        <label className="text-sm text-slate-600">Country:</label>
        <input
          type="text"
          placeholder="e.g. NO"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && applyFilter()}
          className="w-24 rounded border border-slate-300 px-2 py-1 text-sm"
        />
        <button onClick={applyFilter} className="rounded bg-slate-200 px-2 py-1 text-sm hover:bg-slate-300">
          Filter
        </button>
      </div>
      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-left text-slate-600">
              <th className="px-4 py-2">Country</th>
              <th className="px-4 py-2">City</th>
              <th className="px-4 py-2">Fresh</th>
              <th className="px-4 py-2">Stale</th>
              <th className="px-4 py-2">Overdue</th>
            </tr>
          </thead>
          <tbody>
            {items.map((c, i) => (
              <tr key={i} className="border-b border-slate-100 hover:bg-slate-50">
                <td className="px-4 py-2">{c.country_code ?? '-'}</td>
                <td className="px-4 py-2 font-medium">{c.city_name ?? '-'}</td>
                <td className="px-4 py-2">{c.fresh_count ?? 0}</td>
                <td className="px-4 py-2">{c.stale_count ?? 0}</td>
                <td className="px-4 py-2">{c.overdue_count ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {items.length === 0 && (
        <div className="py-8 text-center text-slate-500">No city data</div>
      )}
    </AdminFreshnessLayout>
  );
};
