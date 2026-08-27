/**
 * [AIQ-1439] Admin workflow funnel — /admin/workflow/funnel
 *
 * Stage-to-stage conversion across the relocation workflow, read from
 * GET /api/admin/workflow/funnel. Hand-rolled horizontal bars (the repo ships no
 * charting library — see MetricTimeSeriesChart.tsx), scaled to the largest stage.
 */
import React, { useEffect, useState } from 'react';
import { adminOpsAnalyticsAPI, type WorkflowFunnelResponse } from '../../api/client';
import { Card, Alert, Skeleton } from '../../components/antigravity';
import { AdminLayout } from './AdminLayout';

export const AdminWorkflowFunnelPage: React.FC = () => {
  const [data, setData] = useState<WorkflowFunnelResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    adminOpsAnalyticsAPI
      .getWorkflowFunnel({ days })
      .then((res) => { if (!cancelled) setData(res); })
      .catch(() => { if (!cancelled) setError('Couldn’t load the workflow funnel. Please try again.'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [days]);

  const maxCount = data && data.stages.length ? Math.max(1, ...data.stages.map((s) => s.count)) : 1;

  return (
    <AdminLayout
      title="Workflow funnel"
      subtitle="Stage-to-stage conversion across the relocation workflow, from case creation to accepted quote."
    >
      <div className="mb-4 flex items-center gap-2">
        <label htmlFor="funnel-days" className="text-sm text-slate-500">Period</label>
        <select
          id="funnel-days"
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="rounded-md border border-slate-200 px-2 py-1 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-accent-500"
        >
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>

      {loading && <Skeleton className="h-64 w-full" />}
      {error && <Alert variant="error">{error}</Alert>}
      {!loading && !error && data && (
        <Card padding="lg" className="border border-slate-200">
          <div className="space-y-3">
            {data.stages.map((s) => {
              const widthPct = Math.round((s.count / maxCount) * 100);
              return (
                <div key={s.stage}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium text-slate-800">{s.label}</span>
                    <span className="tabular-nums text-slate-500">
                      {s.count.toLocaleString()}
                      {s.conversion_from_prev_pct != null && (
                        <span className="ml-2 text-xs text-slate-500">{s.conversion_from_prev_pct}% from prev</span>
                      )}
                    </span>
                  </div>
                  <div className="mt-1 h-6 w-full overflow-hidden rounded bg-slate-100">
                    <div
                      className="h-6 rounded bg-[#1f8e8b]"
                      style={{ width: `${widthPct}%` }}
                      role="img"
                      aria-label={`${s.label}: ${s.count} (${s.conversion_from_start_pct}% from start)`}
                    />
                  </div>
                </div>
              );
            })}
          </div>
          <p className="mt-4 text-xs text-slate-500">
            Bars are scaled to the largest stage. “% from prev” is conversion from the preceding stage.
          </p>
        </Card>
      )}
    </AdminLayout>
  );
};
