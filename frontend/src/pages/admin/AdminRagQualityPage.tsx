import React, { useEffect, useState } from 'react';
import { AdminLayout } from './AdminLayout';
import { Card, Badge, Alert } from '../../components/antigravity';
import { MetricTimeSeriesChart } from './MetricTimeSeriesChart';
import { getRagEvalMetrics } from '../../api/ragEval';
import type { RagEvalDashboard, RagEvalMetric } from '../../api/ragEval';

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

const MetricCard: React.FC<{ metric: RagEvalMetric }> = ({ metric }) => {
  const alert = ALERT_LABEL[metric.alert.reason] ?? ALERT_LABEL.no_data ?? { variant: 'info', text: 'No data' };
  return (
    <Card className="border border-slate-200">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h2 className="text-base font-semibold text-slate-900">{metric.label}</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Latest <span className="font-semibold text-slate-700">{fmtPct(metric.latest)}</span>
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
      subtitle="Retrieval & generation health over time — context precision, factual consistency, and outcome accuracy against their alert thresholds."
    >
      {loading && <p className="text-sm text-slate-400">Loading…</p>}

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
