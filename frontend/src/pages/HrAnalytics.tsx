import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { AppShell } from '../components/AppShell';
import { Card } from '../components/antigravity';
import { hrAPI } from '../api/client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type DelayCause = { cause: string; count: number };
type Corridor = { corridor: string; avg_days: number; case_count: number };
type TrendPoint = { month: string; avg_completion_days: number | null };

interface AnalyticsData {
  workspace: {
    avg_completion_days: number | null;
    compliance_incident_rate: number | null;
    total_cases_in_window: number;
    closed_cases_in_window: number;
    top_delay_causes: DelayCause[];
    corridor_breakdown: Corridor[];
    computed_at: string | null;
  };
  industry: {
    median_completion_days: number | null;
    median_compliance_rate: number | null;
    case_count: number;
    workspace_count: number;
    is_valid: boolean;
    computed_at: string | null;
  } | null;
  trend: TrendPoint[];
}

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

function fmt(n: number | null, decimals = 1): string {
  if (n === null || n === undefined) return '—';
  return n.toFixed(decimals);
}

function pct(n: number | null): string {
  if (n === null || n === undefined) return '—';
  return `${(n * 100).toFixed(1)}%`;
}

/** Format "YYYY-MM" as "Jan 2026" etc. */
function fmtMonth(ym: string): string {
  const [y, m] = ym.split('-');
  const d = new Date(Number(y), Number(m) - 1, 1);
  return d.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
}

/** Compute delta label (e.g. "23% faster") vs industry median. */
function completionDelta(
  workspace: number | null,
  industry: number | null,
): { label: string; positive: boolean } | null {
  if (workspace === null || industry === null || industry === 0) return null;
  const delta = ((industry - workspace) / industry) * 100;
  if (Math.abs(delta) < 0.5) return { label: 'on par with the industry median', positive: true };
  const absDelta = Math.abs(delta).toFixed(0);
  if (delta > 0) return { label: `${absDelta}% faster than the industry median`, positive: true };
  return { label: `${absDelta}% slower than the industry median`, positive: false };
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Big-number metric card */
function BigMetric({
  label,
  value,
  unit,
  comparison,
  comparisonPositive,
}: {
  label: string;
  value: string;
  unit?: string;
  comparison?: string;
  comparisonPositive?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1">
      <p className="text-xs font-medium text-[#6b7280] uppercase tracking-wide">{label}</p>
      <div className="flex items-baseline gap-1">
        <span className="text-3xl font-bold text-[#111827]">{value}</span>
        {unit && <span className="text-sm text-[#6b7280]">{unit}</span>}
      </div>
      {comparison && (
        <p
          className={`text-xs font-medium ${
            comparisonPositive ? 'text-emerald-600' : 'text-rose-600'
          }`}
        >
          {comparison}
        </p>
      )}
    </div>
  );
}

/** Horizontal bar chart for top delay causes */
function HorizontalBars({ items }: { items: DelayCause[] }) {
  if (!items.length) {
    return <p className="text-sm text-[#6b7280] italic">No delay cause data available yet.</p>;
  }
  const max = Math.max(...items.map((i) => i.count), 1);
  return (
    <div className="space-y-3">
      {items.map((item) => (
        <div key={item.cause} className="flex items-center gap-3">
          <span className="w-36 shrink-0 text-sm text-[#374151] truncate" title={item.cause}>
            {item.cause}
          </span>
          <div className="flex-1 bg-[#f3f4f6] rounded-full h-2.5">
            <div
              className="bg-[#1f4870] h-2.5 rounded-full transition-all duration-500"
              style={{ width: `${Math.round((item.count / max) * 100)}%` }}
            />
          </div>
          <span className="w-8 shrink-0 text-sm text-[#6b7280] text-right">{item.count}</span>
        </div>
      ))}
    </div>
  );
}

/** Corridor breakdown table */
function CorridorTable({ corridors }: { corridors: Corridor[] }) {
  if (!corridors.length) {
    return <p className="text-sm text-[#6b7280] italic">No corridor data available yet.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[#e5e7eb]">
            <th className="text-left py-2 pr-4 text-xs font-semibold text-[#6b7280] uppercase tracking-wide">
              Corridor
            </th>
            <th className="text-right py-2 pr-4 text-xs font-semibold text-[#6b7280] uppercase tracking-wide">
              Avg days
            </th>
            <th className="text-right py-2 text-xs font-semibold text-[#6b7280] uppercase tracking-wide">
              Cases
            </th>
          </tr>
        </thead>
        <tbody>
          {corridors.map((c) => (
            <tr key={c.corridor} className="border-b border-[#f3f4f6] hover:bg-[#f9fafb]">
              <td className="py-2.5 pr-4 font-medium text-[#111827]">{c.corridor}</td>
              <td className="py-2.5 pr-4 text-right text-[#374151]">{fmt(c.avg_days, 0)} days</td>
              <td className="py-2.5 text-right text-[#6b7280]">{c.case_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** SVG line chart for month-over-month trend */
function TrendChart({ points }: { points: TrendPoint[] }) {
  const validPoints = points.filter((p) => p.avg_completion_days !== null);
  if (validPoints.length < 2) {
    return (
      <p className="text-sm text-[#6b7280] italic">
        Not enough trend data yet — the chart will populate after a few nightly runs.
      </p>
    );
  }

  const W = 600;
  const H = 160;
  const PAD = { top: 16, right: 24, bottom: 32, left: 40 };
  const chartW = W - PAD.left - PAD.right;
  const chartH = H - PAD.top - PAD.bottom;

  const values = validPoints.map((p) => p.avg_completion_days as number);
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const range = maxVal - minVal || 1;

  const xStep = chartW / (validPoints.length - 1);

  const toX = (i: number) => PAD.left + i * xStep;
  const toY = (v: number) => PAD.top + chartH - ((v - minVal) / range) * chartH;

  const pathD = validPoints
    .map((p, i) => {
      const x = toX(i);
      const y = toY(p.avg_completion_days as number);
      return i === 0 ? `M ${x} ${y}` : `L ${x} ${y}`;
    })
    .join(' ');

  // Pick at most 4 x-axis labels
  const labelIndices = [
    0,
    Math.floor(validPoints.length / 3),
    Math.floor((2 * validPoints.length) / 3),
    validPoints.length - 1,
  ].filter((v, i, a) => a.indexOf(v) === i);

  return (
    <div className="overflow-x-auto">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full max-w-[600px]"
        aria-label="Month-over-month average case completion trend"
      >
        {/* Y-axis gridlines */}
        {[0, 0.5, 1].map((ratio) => {
          const y = PAD.top + chartH - ratio * chartH;
          const val = minVal + ratio * range;
          return (
            <g key={ratio}>
              <line
                x1={PAD.left}
                x2={W - PAD.right}
                y1={y}
                y2={y}
                stroke="#e5e7eb"
                strokeWidth={1}
              />
              <text
                x={PAD.left - 4}
                y={y + 4}
                textAnchor="end"
                className="text-[10px] fill-[#9ca3af]"
                fontSize={10}
                fill="#9ca3af"
              >
                {val.toFixed(0)}d
              </text>
            </g>
          );
        })}

        {/* Line */}
        <path d={pathD} fill="none" stroke="#1f4870" strokeWidth={2} strokeLinejoin="round" />

        {/* Dots */}
        {validPoints.map((p, i) => (
          <circle
            key={p.month}
            cx={toX(i)}
            cy={toY(p.avg_completion_days as number)}
            r={3}
            fill="#1f4870"
          />
        ))}

        {/* X-axis labels */}
        {labelIndices.map((i) => {
          const pt = validPoints[i];
          if (!pt) return null;
          return (
            <text
              key={i}
              x={toX(i)}
              y={H - 6}
              textAnchor="middle"
              fontSize={10}
              fill="#9ca3af"
            >
              {fmtMonth(pt.month)}
            </text>
          );
        })}
      </svg>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export const HrAnalytics: React.FC = () => {
  const analyticsQuery = useQuery({
    queryKey: ['hr', 'analytics'],
    queryFn: () => hrAPI.getAnalytics(),
  });
  const data: AnalyticsData | null = analyticsQuery.data ?? null;
  const loading = analyticsQuery.isLoading;
  const error = analyticsQuery.isError
    ? (analyticsQuery.error instanceof Error
        ? analyticsQuery.error.message
        : 'Failed to load analytics data.')
    : '';

  const ws = data?.workspace;
  const ind = data?.industry;
  const trend = data?.trend ?? [];

  const isEmpty = !loading && (!ws || ws.total_cases_in_window < 5);
  const delta =
    ws && ind ? completionDelta(ws.avg_completion_days, ind.median_completion_days) : null;

  return (
    <AppShell section="HR Operations" title="Analytics" subtitle="Benchmarking and performance insights across your relocation cases.">
      <div className="space-y-6 pb-12">

        {/* Error */}
        {error && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </div>
        )}

        {/* Empty state */}
        {isEmpty && !error && (
          <Card className="p-10 text-center">
            <p className="text-lg font-semibold text-[#111827] mb-2">Benchmarks build over time.</p>
            <p className="text-sm text-[#6b7280]">
              Run at least 5 cases to see performance data across corridors.
            </p>
          </Card>
        )}

        {/* Section 1 + 2: Key metrics */}
        {!isEmpty && (
          <Card className="p-6">
            <h2 className="text-sm font-semibold text-[#111827] mb-5 uppercase tracking-wide">
              Key metrics — rolling 90-day window
            </h2>
            {loading ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8 animate-pulse">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="h-16 bg-[#f3f4f6] rounded-lg" />
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
                {/* 1. Avg completion — workspace */}
                <BigMetric
                  label="Your avg. completion"
                  value={fmt(ws?.avg_completion_days ?? null, 0)}
                  unit="days"
                  comparison={delta?.label}
                  comparisonPositive={delta?.positive}
                />
                {/* 2. Industry median */}
                {ind ? (
                  <BigMetric
                    label="Industry median"
                    value={fmt(ind.median_completion_days, 0)}
                    unit="days"
                    comparison={`across ${ind.case_count.toLocaleString()} cases`}
                  />
                ) : (
                  <BigMetric
                    label="Industry median"
                    value="—"
                    comparison="Available when n ≥ 50 cases globally"
                  />
                )}
                {/* 3. Compliance incident rate */}
                <BigMetric
                  label="Compliance incidents"
                  value={pct(ws?.compliance_incident_rate ?? null)}
                  comparison={
                    ind
                      ? `Industry: ${pct(ind.median_compliance_rate)}`
                      : undefined
                  }
                  comparisonPositive={
                    ws && ind && ws.compliance_incident_rate !== null && ind.median_compliance_rate !== null
                      ? ws.compliance_incident_rate <= ind.median_compliance_rate
                      : undefined
                  }
                />
                {/* 4. Cases in window */}
                <BigMetric
                  label="Cases in window"
                  value={String(ws?.total_cases_in_window ?? 0)}
                  comparison={`${ws?.closed_cases_in_window ?? 0} closed`}
                />
              </div>
            )}
          </Card>
        )}

        {/* Section 3: Top delay causes */}
        {!isEmpty && (
          <Card className="p-6">
            <h2 className="text-sm font-semibold text-[#111827] mb-5 uppercase tracking-wide">
              Top delay causes
            </h2>
            {loading ? (
              <div className="space-y-3 animate-pulse">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="h-5 bg-[#f3f4f6] rounded" />
                ))}
              </div>
            ) : (
              <HorizontalBars items={ws?.top_delay_causes ?? []} />
            )}
          </Card>
        )}

        {/* Section 4 + 5: Corridor breakdown + Trend side by side on lg */}
        {!isEmpty && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Section 4: Corridor breakdown */}
            <Card className="p-6">
              <h2 className="text-sm font-semibold text-[#111827] mb-5 uppercase tracking-wide">
                Corridor breakdown
              </h2>
              {loading ? (
                <div className="space-y-2 animate-pulse">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="h-8 bg-[#f3f4f6] rounded" />
                  ))}
                </div>
              ) : (
                <CorridorTable corridors={ws?.corridor_breakdown ?? []} />
              )}
            </Card>

            {/* Section 5: Month-over-month trend */}
            <Card className="p-6">
              <h2 className="text-sm font-semibold text-[#111827] mb-5 uppercase tracking-wide">
                Completion trend — last 12 months
              </h2>
              {loading ? (
                <div className="h-40 bg-[#f3f4f6] rounded animate-pulse" />
              ) : (
                <TrendChart points={trend} />
              )}
            </Card>
          </div>
        )}

        {/* Data freshness note */}
        {!loading && ws?.computed_at && (
          <p className="text-xs text-gray-500 text-right">
            Stats last computed:{' '}
            {new Date(ws.computed_at).toLocaleDateString('en-US', {
              year: 'numeric',
              month: 'short',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            })}
            {' '}UTC · Updated nightly
          </p>
        )}
      </div>
    </AppShell>
  );
};
