import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AdminOpsLayout } from './AdminOpsLayout';
import { adminOpsAnalyticsAPI } from '../../../api/client';
import { buildRoute } from '../../../navigation/routes';

export const AdminOpsSlaPage: React.FC = () => {
  const [sla, setSla] = useState<Record<string, unknown> | null>(null);
  const [breaches, setBreaches] = useState<Array<Record<string, unknown>>>([]);
  const [bottlenecks, setBottlenecks] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [slaRes, breachesRes, botRes] = await Promise.all([
        adminOpsAnalyticsAPI.getSlaOverview({ days }),
        adminOpsAnalyticsAPI.getQueueBreaches({ limit: 20 }),
        adminOpsAnalyticsAPI.getBottlenecks(),
      ]);
      setSla(slaRes);
      setBreaches(breachesRes.items ?? []);
      setBottlenecks(botRes);
    } catch (e) {
      setError((e as Error)?.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <AdminOpsLayout
      title="SLA & Operations Dashboard"
      subtitle="Review performance, SLA compliance, and operational bottlenecks"
    >
      <div className="space-y-6">
        <div className="flex justify-between">
          <select
            className="rounded border border-slate-300 px-2 py-1 text-sm"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>

        {error && <div className="rounded-lg bg-red-50 p-3 text-red-700">{error}</div>}

        {loading ? (
          <div className="py-12 text-center text-slate-500">Loading...</div>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-6">
              <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-2xl font-semibold text-[#0b2b43]">{Number(sla?.open_count ?? 0)}</div>
                <div className="text-sm text-slate-600">Open items</div>
              </div>
              <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-2xl font-semibold text-red-600">{Number(sla?.overdue_count ?? 0)}</div>
                <div className="text-sm text-slate-600">Overdue</div>
              </div>
              <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-2xl font-semibold text-amber-600">{Number(sla?.breached_count ?? 0)}</div>
                <div className="text-sm text-slate-600">SLA breaches</div>
              </div>
              <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-2xl font-semibold text-green-600">{Number(sla?.on_time_resolution_rate_pct ?? 0)}%</div>
                <div className="text-sm text-slate-600">On-time rate</div>
              </div>
              <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-2xl font-semibold text-slate-700">{Number(sla?.avg_time_to_resolve_hours ?? 0)}h</div>
                <div className="text-sm text-slate-600">Avg resolve time</div>
              </div>
              <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-2xl font-semibold text-slate-700">{Number(sla?.resolved_count ?? 0)}</div>
                <div className="text-sm text-slate-600">Resolved</div>
              </div>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                <h3 className="mb-3 font-semibold text-slate-700">Bottlenecks</h3>
                <div className="space-y-2 text-sm">
                  <div>Total backlog: {Number(bottlenecks?.total_backlog ?? 0)}</div>
                  <div>Unassigned: {Number(bottlenecks?.unassigned_count ?? 0)}</div>
                  {(bottlenecks?.top_backlog_destination as Record<string, unknown> | null) && (
                    <div>
                      Top destination:{' '}
                      {String((bottlenecks?.top_backlog_destination as Record<string, unknown>)?.country_code ?? '')} /{' '}
                      {String((bottlenecks?.top_backlog_destination as Record<string, unknown>)?.city_name ?? '')} (
                      {Number((bottlenecks?.top_backlog_destination as Record<string, unknown>)?.total ?? 0)} items)
                    </div>
                  )}
                </div>
              </div>

              <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                <h3 className="mb-3 font-semibold text-slate-700">Recent SLA breaches</h3>
                <div className="space-y-2">
                  {breaches.length === 0 ? (
                    <p className="text-sm text-slate-500">No breaches in current open items</p>
                  ) : (
                    breaches.slice(0, 10).map((b) => (
                      <Link
                        key={String(b.id)}
                        to={buildRoute('adminReviewQueueDetail', { id: String(b.id) })}
                        className="block rounded bg-slate-50 px-2 py-1 text-sm hover:bg-slate-100"
                      >
                        {String((b.title as string)?.slice(0, 50) || 'Queue item')} — {String(b.priority_band ?? '')}
                      </Link>
                    ))
                  )}
                  {breaches.length > 0 && (
                    <Link
                      to={buildRoute('adminReviewQueue') + '?overdue=1'}
                      className="text-sm text-[#0b2b43] underline"
                    >
                      View all overdue →
                    </Link>
                  )}
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </AdminOpsLayout>
  );
};
