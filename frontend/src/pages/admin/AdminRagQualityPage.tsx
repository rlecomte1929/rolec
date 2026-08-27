import React, { useEffect, useState } from 'react';
import { Card, Badge, Alert } from '../../components/antigravity';
import { getRagEvalMetrics } from '../../api/ragEval';
import type { RagEvalDashboard, RagEvalMetric, RagEvalSlice } from '../../api/ragEval';
import { MetricTimeSeriesChart } from './MetricTimeSeriesChart';
import { AdminLayout } from './AdminLayout';

// P3-01e — RAG-quality metrics dashboard. Time-series of context precision,
// factual consistency, and outcome accuracy with threshold alert lines. Reads
// committed eval reports; falls back to a flagged mock series until real
// reports land (see backend rag_eval_reports.build_dashboard).

const SERIES_COLOR = '#1f4870'; // accent-600

const ALERT_LABEL: Record<string, { variant: 'success' | 'warning' | 'error' | 'info'; text: string }> = {
  below_threshold: { variant: 'error', text: 'Below threshold' },
  declining: { variant: 'warning', text: 'Declining' },
  healthy: { variant: 'success', text: 'Healthy' },
  no_data: { variant: 'info', text: 'No data' },
};

const fmtPct = (v: number | null): string => (v === null ? '—' : `${(v * 100).toFixed(1)}%`);

const fmtEmployeeType = (t: string): string => t.replace(/_/g, ' ');

const fmtCorridor = (c: string): string => c.replace(/_/g, ' → ');

// Per-(corridor × employee-type) recall vs the lawyer-verified HLP baseline.
// The backend sends slices sorted worst-first; we re-sort defensively so the
// worst slice is ALWAYS on top — never an average, never alphabetical.
const SliceBreakdown: React.FC<{ metric: RagEvalMetric }> = ({ metric }) => {
  const slices = metric.slices ?? [];
  if (slices.length === 0) return null;
  const sorted = [...slices].sort((a, b) => {
    if (a.recall === null) return 1;
    if (b.recall === null) return -1;
    return a.recall - b.recall;
  });
  const worst = sorted[0];
  const worstFailing = worst && worst.recall !== null && worst.recall < metric.threshold;

  return (
    <div className="mt-3 space-y-2">
      {worst && worst.recall !== null && (
        <Alert
          variant={worstFailing ? 'error' : 'success'}
          title={`Worst slice: ${fmtCorridor(worst.corridor)} · ${fmtEmployeeType(worst.employee_type)} — ${fmtPct(worst.recall)}`}
        >
          {worstFailing ? (
            <>
              {worst.total - worst.served} of {worst.total} lawyer-verified non-obvious requirement
              {worst.total - worst.served === 1 ? '' : 's'} missed
              {worst.missing.length > 0 && <> (<code>{worst.missing.join(', ')}</code>)</>}.
              A single missed rare requirement lowers this slice — and only this slice.
            </>
          ) : (
            <>Every slice currently serves its full lawyer-verified non-obvious requirement set.</>
          )}
        </Alert>
      )}
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-slate-500">
            <th className="py-1 pr-2 font-medium">Corridor</th>
            <th className="py-1 pr-2 font-medium">Employee type</th>
            <th className="py-1 pr-2 font-medium">Recall vs HLP</th>
            <th className="py-1 pr-2 font-medium">Served</th>
            <th className="py-1 font-medium">Missed</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((s: RagEvalSlice) => {
            const failing = s.recall !== null && s.recall < metric.threshold;
            return (
              <tr
                key={`${s.corridor}:${s.employee_type}`}
                className={`border-t border-slate-100 ${failing ? 'bg-red-50' : ''}`}
              >
                <td className="py-1.5 pr-2 font-medium text-slate-700">{fmtCorridor(s.corridor)}</td>
                <td className="py-1.5 pr-2 text-slate-600">{fmtEmployeeType(s.employee_type)}</td>
                <td className={`py-1.5 pr-2 font-semibold ${failing ? 'text-red-600' : 'text-slate-700'}`}>
                  {s.recall === null ? 'no data' : fmtPct(s.recall)}
                </td>
                <td className="py-1.5 pr-2 text-slate-600">{s.served}/{s.total}</td>
                <td className="py-1.5 text-slate-500">
                  {s.recall === null ? 'no produced roadmaps yet' : s.missing.length > 0 ? s.missing.join(', ') : '—'}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="text-[11px] text-slate-500">
        Recall per (corridor × employee-type) slice against the lawyer-verified HLP baseline.
        The chart plots the worst slice, never an average.
      </p>
    </div>
  );
};

const MetricCard: React.FC<{ metric: RagEvalMetric }> = ({ metric }) => {
  const alert = ALERT_LABEL[metric.alert.reason] ?? ALERT_LABEL.no_data ?? { variant: 'info', text: 'No data' };
  const isSliced = (metric.slices?.length ?? 0) > 0;
  return (
    <Card className="border border-slate-200">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h2 className="text-base font-semibold text-slate-900">{metric.label}</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            {isSliced ? 'Worst slice' : 'Latest'}{' '}
            <span className="font-semibold text-slate-700">{fmtPct(metric.latest)}</span>
            {' · '}target ≥ {fmtPct(metric.threshold)}
          </p>
        </div>
        <Badge variant={alert.variant}>{alert.text}</Badge>
      </div>
      <MetricTimeSeriesChart
        points={metric.points}
        threshold={metric.threshold}
        color={SERIES_COLOR}
        label={metric.label}
      />
      <SliceBreakdown metric={metric} />
    </Card>
  );
};

export const AdminRagQualityPage: React.FC = () => {
  const [data, setData] = useState<RagEvalDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    getRagEvalMetrics()
      .then((d) => {
        if (active) setData(d);
      })
      .catch(() => {
        if (active) setError('Could not load RAG-quality metrics.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const firingCount = data?.metrics.filter((m) => m.alert.firing).length ?? 0;

  return (
    <AdminLayout
      title="RAG quality"
      subtitle="Retrieval & generation health over time — context precision, factual consistency, outcome accuracy, and non-obvious recall per corridor × employee-type slice (worst slice first, never an average) against their alert thresholds."
    >
      {loading && <p className="text-sm text-slate-500">Loading…</p>}

      {error && (
        <Alert variant="error" title="Failed to load">
          {error}
        </Alert>
      )}

      {data && (
        <div className="space-y-4">
          {data.source === 'mock' && (
            <Alert variant="info" title="Showing mock data">
              No real evaluation reports have been committed to <code>audit/rag_eval/</code> yet,
              so this dashboard is rendering a deterministic sample series to demonstrate the
              charts and alert thresholds. It will switch to live data automatically once the
              first report per metric lands.
            </Alert>
          )}

          {firingCount > 0 && (
            <Alert variant="warning" title={`${firingCount} metric${firingCount > 1 ? 's' : ''} alerting`}>
              One or more metrics are below threshold or trending down. Review the cards below.
            </Alert>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {data.metrics.map((m) => (
              <MetricCard key={m.metric} metric={m} />
            ))}
          </div>
        </div>
      )}
    </AdminLayout>
  );
};
