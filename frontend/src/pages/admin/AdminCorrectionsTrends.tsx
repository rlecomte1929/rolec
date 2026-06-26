import React, { useEffect, useMemo, useState } from 'react';
import { Card, Select, Alert } from '../../components/antigravity';
import {
  getCorrectionsByReason,
  type CorrectionsByReasonResponse,
} from '../../api/corrections';
import { AdminLayout } from './AdminLayout';

// ── 90-day window helpers ─────────────────────────────────────────────────────

const WINDOW_OPTIONS = [
  { value: '30', label: 'Last 30 days' },
  { value: '90', label: 'Last 90 days' },
  { value: '180', label: 'Last 180 days' },
] as const;

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - days);
  return d.toISOString().slice(0, 10);
}

function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}

function formatWeekLabel(weekStart: string): string {
  // weekStart is an ISO date (YYYY-MM-DD); render as "May 25".
  const d = new Date(`${weekStart}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return weekStart;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', timeZone: 'UTC' });
}

// WCAG-AA-contrast categorical palette (all ≥ 3:1 against white as fills; legend
// text uses slate-700 for AA on white). Cycles if series outnumber colours.
const SERIES_COLORS = [
  '#1d4ed8', // blue-700
  '#b45309', // amber-700
  '#047857', // emerald-700
  '#be123c', // rose-700
  '#6d28d9', // violet-700
  '#0369a1', // sky-700
  '#a16207', // yellow-700
  '#4d7c0f', // lime-700
  '#9d174d', // pink-800
  '#374151', // gray-700
];

function colorFor(index: number): string {
  return SERIES_COLORS[index % SERIES_COLORS.length]!;
}

// ── Stacked bar chart (inline SVG — repo has no charting library) ──────────────

interface StackedBarChartProps {
  data: CorrectionsByReasonResponse;
  /** Accessible title describing the chart for screen readers. */
  title: string;
}

const CHART_HEIGHT = 240;
const BAR_GAP = 12;
const TOP_PAD = 8;
const AXIS_PAD = 28; // room for the week label under each bar

const StackedBarChart: React.FC<StackedBarChartProps> = ({ data, title }) => {
  const { buckets, series } = data;

  const maxTotal = useMemo(() => {
    let max = 0;
    for (const b of buckets) {
      const total = Object.values(b.counts).reduce((s, n) => s + n, 0);
      if (total > max) max = total;
    }
    return max;
  }, [buckets]);

  if (buckets.length === 0) {
    return (
      <p className="text-sm text-slate-500 py-10 text-center">
        No corrections recorded in this window.
      </p>
    );
  }

  const plotHeight = CHART_HEIGHT - TOP_PAD - AXIS_PAD;
  const barWidth = Math.max(
    8,
    Math.min(56, (640 - BAR_GAP * (buckets.length - 1)) / buckets.length),
  );
  const totalWidth = buckets.length * barWidth + (buckets.length - 1) * BAR_GAP;

  return (
    <div className="overflow-x-auto">
      <svg
        role="img"
        aria-label={title}
        width={totalWidth}
        height={CHART_HEIGHT}
        viewBox={`0 0 ${totalWidth} ${CHART_HEIGHT}`}
        className="min-w-full"
      >
        <title>{title}</title>
        {/* Baseline */}
        <line
          x1={0}
          y1={TOP_PAD + plotHeight}
          x2={totalWidth}
          y2={TOP_PAD + plotHeight}
          stroke="#cbd5e1"
          strokeWidth={1}
        />
        {buckets.map((bucket, bi) => {
          const x = bi * (barWidth + BAR_GAP);
          let yCursor = TOP_PAD + plotHeight;
          const total = Object.values(bucket.counts).reduce((s, n) => s + n, 0);
          return (
            <g key={bucket.week_start}>
              {series.map((s, si) => {
                const value = bucket.counts[s] ?? 0;
                if (value === 0) return null;
                const segHeight = maxTotal > 0 ? (value / maxTotal) * plotHeight : 0;
                yCursor -= segHeight;
                return (
                  <rect
                    key={s}
                    x={x}
                    y={yCursor}
                    width={barWidth}
                    height={segHeight}
                    fill={colorFor(si)}
                  >
                    <title>{`${formatWeekLabel(bucket.week_start)} · ${s}: ${value}`}</title>
                  </rect>
                );
              })}
              {/* Total label above the bar */}
              {total > 0 && (
                <text
                  x={x + barWidth / 2}
                  y={yCursor - 4}
                  textAnchor="middle"
                  className="fill-slate-600"
                  fontSize={10}
                >
                  {total}
                </text>
              )}
              {/* Week label */}
              <text
                x={x + barWidth / 2}
                y={CHART_HEIGHT - 8}
                textAnchor="middle"
                className="fill-slate-500"
                fontSize={10}
              >
                {formatWeekLabel(bucket.week_start)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
};

// ── Legend ─────────────────────────────────────────────────────────────────────

const ChartLegend: React.FC<{ series: string[] }> = ({ series }) => (
  <ul className="flex flex-wrap gap-x-4 gap-y-1 mt-4" aria-label="Chart legend">
    {series.map((s, i) => (
      <li key={s} className="flex items-center gap-1.5 text-xs text-slate-700">
        <span
          aria-hidden="true"
          className="inline-block w-3 h-3 rounded-sm"
          style={{ backgroundColor: colorFor(i) }}
        />
        {s}
      </li>
    ))}
  </ul>
);

// ── Chart card (loads its own data for a given grouping) ───────────────────────

interface ChartCardProps {
  heading: string;
  description: string;
  groupBy: 'reason' | 'agent';
  windowDays: number;
}

const ChartCard: React.FC<ChartCardProps> = ({ heading, description, groupBy, windowDays }) => {
  const [data, setData] = useState<CorrectionsByReasonResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    getCorrectionsByReason(
      { groupBy, from: isoDaysAgo(windowDays), to: isoToday() },
      { signal: controller.signal },
    )
      .then((res) => setData(res))
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setError(e instanceof Error ? e.message : 'Failed to load corrections data.');
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [groupBy, windowDays]);

  return (
    <Card className="flex flex-col">
      <h2 className="text-base font-semibold text-slate-900">{heading}</h2>
      <p className="text-sm text-slate-500 mt-0.5 mb-4">{description}</p>
      {loading && (
        <div className="py-16 text-center text-sm text-slate-400" role="status">
          Loading…
        </div>
      )}
      {!loading && error && (
        <Alert variant="error" title="Could not load chart">
          {error}
        </Alert>
      )}
      {!loading && !error && data && (
        <>
          <StackedBarChart data={data} title={heading} />
          {data.series.length > 0 && <ChartLegend series={data.series} />}
        </>
      )}
    </Card>
  );
};

// ── Page ───────────────────────────────────────────────────────────────────────

export const AdminCorrectionsTrends: React.FC = () => {
  const [windowDays, setWindowDays] = useState(90);

  const windowControl = (
    <Select
      label="Time window"
      value={String(windowDays)}
      onChange={(value) => setWindowDays(Number(value))}
      options={WINDOW_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
    />
  );

  return (
    <AdminLayout
      title="Corrections trends"
      subtitle="Are we getting better at extraction, or are we getting harder documents? Weekly HR corrections by reason and by agent. Scoped to your tenant."
      headerRight={windowControl}
    >
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <ChartCard
          heading="Corrections per week, by reason"
          description="Stacked weekly count of corrections, broken down by reason code."
          groupBy="reason"
          windowDays={windowDays}
        />
        <ChartCard
          heading="Corrections per week, by agent"
          description="Stacked weekly count of corrections, broken down by the extracting agent."
          groupBy="agent"
          windowDays={windowDays}
        />
      </div>
    </AdminLayout>
  );
};
