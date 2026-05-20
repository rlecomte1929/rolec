import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AdminOpsLayout } from './AdminOpsLayout';
import { adminOpsAnalyticsAPI } from '../../../api/client';
import { buildRoute } from '../../../navigation/routes';
import {
  ConnectedPill,
  OnHoldPill,
  MiniStat,
  SectionHeading,
  OpsPageActions,
  fmtNum,
  fmtPct,
} from './opsShared';

/**
 * SLA tab — drill-down into open / overdue / breached counts, on-time
 * resolution rate, average assign/resolve times, and a list of the most
 * recent SLA breaches. Sibling of the Ops dashboard.
 */

interface SlaOverview {
  open_count?: number;
  overdue_count?: number;
  breached_count?: number;
  resolved_count?: number;
  on_time_resolution_rate_pct?: number;
  avg_time_to_assign_hours?: number;
  avg_time_to_resolve_hours?: number;
}

interface BreachItem {
  id: string;
  title?: string;
  priority_band?: string;
}

export const AdminOpsSlaPage: React.FC = () => {
  const [sla, setSla] = useState<SlaOverview | null>(null);
  const [breaches, setBreaches] = useState<BreachItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const results = await Promise.allSettled([
      adminOpsAnalyticsAPI.getSlaOverview({ days }),
      adminOpsAnalyticsAPI.getQueueBreaches({ limit: 20 }),
    ]);
    if (results[0].status === 'fulfilled') setSla(results[0].value as SlaOverview);
    if (results[1].status === 'fulfilled') {
      const v = results[1].value as { items?: BreachItem[] };
      setBreaches(v.items ?? []);
    }
    if (results[0].status === 'rejected' && results[1].status === 'rejected') {
      setError('Backend unavailable — SLA endpoints are not returning data in this environment.');
    }
    setLoading(false);
  }, [days]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <AdminOpsLayout
      title="Ops analytics"
      subtitle="SLA — open / overdue / breached counts and recent SLA breaches."
      headerRight={<OpsPageActions days={days} onDaysChange={setDays} />}
    >
      {error && (
        <div className="mb-4 flex items-start justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <span>{error}</span>
          <button type="button" onClick={() => void load()} className="text-amber-700 hover:underline">
            Retry
          </button>
        </div>
      )}

      {loading ? (
        <div className="py-12 text-center text-slate-500">Loading…</div>
      ) : (
        <div className="space-y-5">
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="mb-3 flex items-baseline justify-between">
              <SectionHeading label="SLA snapshot" />
              {sla ? <ConnectedPill /> : <OnHoldPill />}
            </div>
            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
              <MiniStat label="Open" value={fmtNum(sla?.open_count)} />
              <MiniStat label="Overdue" value={fmtNum(sla?.overdue_count)} tone="warning" />
              <MiniStat label="Breached" value={fmtNum(sla?.breached_count)} tone="danger" />
              <MiniStat label="On-time" value={fmtPct(sla?.on_time_resolution_rate_pct)} tone="success" />
              <MiniStat
                label="Avg resolve"
                value={typeof sla?.avg_time_to_resolve_hours === 'number' ? `${sla.avg_time_to_resolve_hours}h` : '—'}
              />
              <MiniStat label="Resolved" value={fmtNum(sla?.resolved_count)} />
            </div>
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="mb-3 flex items-baseline justify-between">
              <SectionHeading label="Recent SLA breaches" />
              {breaches.length > 0 ? <ConnectedPill /> : <OnHoldPill />}
            </div>
            {breaches.length === 0 ? (
              <p className="text-[12.5px] text-slate-500">No breaches in current open items.</p>
            ) : (
              <ul className="space-y-1">
                {breaches.slice(0, 10).map((b) => (
                  <li key={b.id}>
                    <Link
                      to={buildRoute('adminReviewQueueDetail', { id: b.id })}
                      className="block rounded bg-slate-50 px-3 py-1.5 text-[12.5px] hover:bg-slate-100"
                    >
                      <span className="font-medium text-slate-800">{(b.title ?? 'Queue item').slice(0, 80)}</span>
                      <span className="ml-2 text-[11px] text-slate-500">· {b.priority_band ?? 'unknown'}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            {breaches.length > 0 && (
              <Link to={`${buildRoute('adminReviewQueue')}?overdue=1`} className="mt-2 inline-block text-[12px] text-indigo-700 underline">
                View all overdue →
              </Link>
            )}
          </div>
        </div>
      )}
    </AdminOpsLayout>
  );
};
