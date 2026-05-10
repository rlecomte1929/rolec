import React, { useCallback, useEffect, useState } from 'react';
import { AdminOpsLayout } from './AdminOpsLayout';
import { adminOpsAnalyticsAPI } from '../../../api/client';

export const AdminOpsDestinationsPage: React.FC = () => {
  const [data, setData] = useState<{ items?: Array<Record<string, unknown>> } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminOpsAnalyticsAPI.getDestinations();
      setData(res);
    } catch (e) {
      setError((e as Error)?.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const items = data?.items ?? [];

  return (
    <AdminOpsLayout title="Destination Analytics" subtitle="Queue volume by country and city">
      <div className="space-y-6">
        {error && <div className="rounded-lg bg-red-50 p-3 text-red-700">{error}</div>}
        {loading ? (
          <div className="py-12 text-center text-slate-500">Loading...</div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Country</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">City</th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-slate-600">Total</th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-slate-600">Critical</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 bg-white">
                {items.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-slate-500">No destination data</td>
                  </tr>
                ) : (
                  items.map((d, i) => (
                    <tr key={i} className="hover:bg-slate-50">
                      <td className="px-3 py-2 font-medium">{String(d.country_code ?? '-')}</td>
                      <td className="px-3 py-2">{String(d.city_name ?? '-')}</td>
                      <td className="px-3 py-2 text-right">{Number(d.total ?? 0)}</td>
                      <td className="px-3 py-2 text-right text-red-600">{Number(d.critical ?? 0)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AdminOpsLayout>
  );
};
