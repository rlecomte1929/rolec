/**
 * AnswerProvenanceWidget — W2-5: Policy Assistant answer provenance
 *
 * Surfaces how trustworthy the company's Policy Assistant answers have been over
 * a recent window: grounded% (of answered questions verified against policy
 * sources), refusal% (of all questions), and the count of answers the grounding
 * verifier could not confirm (failed open).
 *
 * Renders nothing when the company has had no assistant traffic in the window —
 * an empty state would just be noise on the HR dashboard.
 */
import React, { useEffect, useState } from 'react';
import { Card, Badge } from './antigravity';
import { getAnswerProvenance, type AnswerProvenanceResponse } from '../api/hrAnalytics';
import { logger } from '../lib/logger';

const pct = (v: number) => `${Math.round(v * 100)}%`;

interface MetricProps {
  label: string;
  value: string;
  variant: 'success' | 'warning' | 'error' | 'info' | 'neutral';
  hint: string;
}

const Metric: React.FC<MetricProps> = ({ label, value, variant, hint }) => (
  <div className="flex-1 min-w-[120px]">
    <div className="flex items-center gap-2">
      <span className="text-2xl font-semibold text-[#0b2b43]">{value}</span>
      <Badge variant={variant} size="sm">{label}</Badge>
    </div>
    <p className="text-xs text-[#6b7280] mt-1">{hint}</p>
  </div>
);

export const AnswerProvenanceWidget: React.FC<{ windowDays?: number }> = ({
  windowDays = 30,
}) => {
  const [data, setData] = useState<AnswerProvenanceResponse | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getAnswerProvenance(windowDays)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err) => {
        // Provenance is informational — never block the dashboard on it.
        logger.warn('answer-provenance fetch failed', err);
      })
      .finally(() => {
        if (!cancelled) setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [windowDays]);

  // No data yet, fetch failed, or no assistant traffic in the window → render nothing.
  if (!loaded || !data || data.total === 0) return null;

  // grounded_rate is denominated on answered questions; show N/A if none answered.
  const groundedValue = data.answers > 0 ? pct(data.grounded_rate) : '—';
  const groundedVariant =
    data.answers === 0
      ? 'neutral'
      : data.grounded_rate >= 0.9
        ? 'success'
        : data.grounded_rate >= 0.7
          ? 'warning'
          : 'error';

  return (
    <Card padding="md">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-[#0b2b43]">
          Policy Assistant answer quality
        </h3>
        <span className="text-xs text-[#6b7280]">
          {data.total} question{data.total !== 1 ? 's' : ''} · last {data.window_days} days
        </span>
      </div>
      <div className="flex flex-wrap gap-6">
        <Metric
          label="grounded"
          value={groundedValue}
          variant={groundedVariant}
          hint="answers verified against policy sources"
        />
        <Metric
          label="refusals"
          value={pct(data.refusal_rate)}
          variant={data.refusal_rate <= 0.2 ? 'success' : 'warning'}
          hint="questions outside the company policy"
        />
        <Metric
          label="unverified"
          value={String(data.unverified_count)}
          variant={data.unverified_count === 0 ? 'success' : 'warning'}
          hint="answers grounding could not confirm"
        />
      </div>
    </Card>
  );
};
