import React, { useEffect, useState } from 'react';
import { Card, Alert } from '../../components/antigravity';
import { getAutopilotMetrics } from '../../api/autopilotMetrics';
import type { AutopilotMetrics } from '../../api/autopilotMetrics';
import { AdminLayout } from './AdminLayout';

// Feedback Autopilot Phase 4 — read-only dashboard over GET /api/admin/autopilot-metrics.
// The funnel + cost populate as the automation runs; near-empty while dormant.

const usd = (v: number): string => `$${v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const num = (v: number | null): string => (v === null || v === undefined ? '—' : v.toLocaleString());
const pct = (v: number | null): string => (v === null || v === undefined ? '—' : `${Math.round(v * 100)}%`);

const Tile: React.FC<{ label: string; value: string; sub?: string }> = ({ label, value, sub }) => (
  <Card className="border border-slate-200">
    <p className="text-xs font-medium text-slate-500">{label}</p>
    <p className="mt-1 text-2xl font-semibold text-slate-900">{value}</p>
    {sub && <p className="mt-0.5 text-xs text-slate-500">{sub}</p>}
  </Card>
);

// Funnel stages in order, mapped to their event_type keys.
const FUNNEL: { label: string; key: string }[] = [
  { label: 'Ingested', key: 'autopilot.feedback_ingested' },
  { label: 'Deduped', key: 'autopilot.feedback_deduped' },
  { label: 'Dispatched', key: 'autopilot.task_dispatched' },
  { label: 'PR opened', key: 'autopilot.fix_pr_opened' },
  { label: 'Merged', key: 'autopilot.merged' },
  { label: 'Reverted', key: 'autopilot.reverted' },
  { label: 'Done', key: 'autopilot.task_done' },
];

export const AdminAutopilotMetricsPage: React.FC = () => {
  const [data, setData] = useState<AutopilotMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    getAutopilotMetrics()
      .then((d) => { if (active) setData(d); })
      .catch(() => { if (active) setError('Could not load autopilot metrics.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const totalEvents = data ? Object.values(data.funnel).reduce((a, b) => a + b, 0) : 0;

  return (
    <AdminLayout
      title="Autopilot"
      subtitle="Feedback → dedup → fix → merge funnel, cost against the monthly ceiling, and quality KPIs. Populates as the automation runs."
    >
      {loading && <p className="text-sm text-slate-500">Loading…</p>}

      {error && <Alert variant="error" title="Failed to load">{error}</Alert>}

      {data && totalEvents === 0 && (
        <Alert variant="info" title="No autopilot activity recorded yet">
          The autopilot is dormant (flags off) or hasn&apos;t run. Funnel, cost, and KPI figures
          appear here automatically once the nightly ingest and the autofix pipeline start emitting events.
        </Alert>
      )}

      {data && (
        <div className="space-y-6">
          {/* KPI tiles */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Tile label="Dedup factor" value={data.kpis.dedup_factor ? `${data.kpis.dedup_factor}×` : '—'}
                  sub={`${num(data.dedup.raw)} → ${num(data.dedup.unique)}`} />
            <Tile label="Dispatched" value={num(data.kpis.tasks_dispatched)} />
            <Tile label="Merged" value={num(data.kpis.merged)} sub={`${num(data.kpis.tasks_done)} done`} />
            <Tile label="Reverted" value={num(data.kpis.reverted)} sub={`revert ${pct(data.kpis.revert_rate)}`} />
            <Tile label="Canary pass rate" value={pct(data.kpis.canary_pass_rate)} />
            <Tile label="Escalated to human" value={num(data.kpis.escalated_to_human)} />
            <Tile label="Runs halted" value={num(data.kpis.runs_halted)} sub="gate / budget" />
            <Tile label="Spend (MTD)" value={usd(data.cost.total_usd)}
                  sub={`of ${usd(data.cost.monthly_cap_usd)} · ${usd(data.cost.remaining_usd)} left`} />
          </div>

          {/* Funnel */}
          <Card padding="lg" className="border border-slate-200">
            <h2 className="mb-3 text-sm font-semibold text-slate-900">Funnel</h2>
            <div className="flex flex-wrap gap-2">
              {FUNNEL.map((f) => (
                <div key={f.key} className="rounded-lg border border-slate-200 px-3 py-2 min-w-[92px]">
                  <p className="text-xs text-slate-500">{f.label}</p>
                  <p className="text-lg font-semibold text-slate-900 tabular-nums">{num(data.funnel[f.key] ?? 0)}</p>
                </div>
              ))}
            </div>
          </Card>

          {/* Cost by stage */}
          {data.cost.by_stage.length > 0 && (
            <Card padding="lg" className="border border-slate-200">
              <h2 className="mb-3 text-sm font-semibold text-slate-900">Cost by stage</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="border-b border-slate-200 text-left text-slate-500 font-medium">
                      <th className="py-2 pr-4">Stage</th>
                      <th className="py-2 pr-4 text-right">Calls</th>
                      <th className="py-2 pr-4 text-right">Cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.cost.by_stage.map((s) => (
                      <tr key={s.stage} className="border-b border-slate-100">
                        <td className="py-2 pr-4 font-medium text-slate-900">{s.stage}</td>
                        <td className="py-2 pr-4 text-right tabular-nums text-slate-500">{num(s.n_calls ?? 0)}</td>
                        <td className="py-2 pr-4 text-right tabular-nums text-slate-900">{usd(s.cost_usd)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </div>
      )}
    </AdminLayout>
  );
};
