import React from 'react';
import type { RagEvalPoint } from '../../api/ragEval';

// Self-contained SVG line chart (no charting dependency — the repo ships none and
// keeps vendor chunks lean). Plots one metric's weekly aggregate over time with a
// dashed threshold line. A fixed [0.7, 1.0] y-domain keeps the three metric charts
// visually comparable and the threshold lines (0.85 / 0.90 / 0.95) in view.

interface MetricTimeSeriesChartProps {
  points: RagEvalPoint[];
  threshold: number;
  /** Stroke colour for the series line + points. */
  color: string;
  label: string;
}

const VIEW_W = 600;
const VIEW_H = 220;
const PAD = { top: 16, right: 16, bottom: 28, left: 40 };
const Y_MIN = 0.7;
const Y_MAX = 1.0;

const plotW = VIEW_W - PAD.left - PAD.right;
const plotH = VIEW_H - PAD.top - PAD.bottom;

const yToPx = (v: number): number => {
  const clamped = Math.max(Y_MIN, Math.min(Y_MAX, v));
  return PAD.top + (1 - (clamped - Y_MIN) / (Y_MAX - Y_MIN)) * plotH;
};

const xToPx = (i: number, n: number): number => {
  if (n <= 1) return PAD.left + plotW / 2;
  return PAD.left + (i / (n - 1)) * plotW;
};

const fmtPct = (v: number): string => `${(v * 100).toFixed(0)}%`;
const fmtDate = (iso: string): string => iso.slice(5); // MM-DD

export const MetricTimeSeriesChart: React.FC<MetricTimeSeriesChartProps> = ({
  points,
  threshold,
  color,
  label,
}) => {
  const n = points.length;

  if (n === 0) {
    return (
      <div className="flex items-center justify-center h-[180px] text-sm text-slate-400">
        No data yet
      </div>
    );
  }

  // n > 0 here (early return above), so first/last always exist.
  const first = points[0];
  const last = points[n - 1];
  if (!first || !last) return null;

  const linePath = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${xToPx(i, n).toFixed(1)} ${yToPx(p.aggregate).toFixed(1)}`)
    .join(' ');

  const thresholdY = yToPx(threshold);
  const gridValues = [0.7, 0.8, 0.9, 1.0];

  return (
    <svg
      viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
      className="w-full h-auto"
      role="img"
      aria-label={`${label} over time. Latest ${fmtPct(last.aggregate)}, threshold ${fmtPct(threshold)}.`}
    >
      {/* Y gridlines + labels */}
      {gridValues.map((g) => (
        <g key={g}>
          <line
            x1={PAD.left}
            x2={VIEW_W - PAD.right}
            y1={yToPx(g)}
            y2={yToPx(g)}
            stroke="#f1f5f9"
            strokeWidth={1}
          />
          <text x={PAD.left - 6} y={yToPx(g) + 3} textAnchor="end" fontSize={10} fill="#94a3b8">
            {fmtPct(g)}
          </text>
        </g>
      ))}

      {/* Threshold line */}
      <line
        x1={PAD.left}
        x2={VIEW_W - PAD.right}
        y1={thresholdY}
        y2={thresholdY}
        stroke="#f43f5e"
        strokeWidth={1.5}
        strokeDasharray="5 4"
      />
      <text x={VIEW_W - PAD.right} y={thresholdY - 4} textAnchor="end" fontSize={10} fill="#f43f5e">
        threshold {fmtPct(threshold)}
      </text>

      {/* Series line */}
      <path d={linePath} fill="none" stroke={color} strokeWidth={2} />

      {/* Points (native title tooltip on hover) */}
      {points.map((p, i) => (
        <circle
          key={p.date}
          cx={xToPx(i, n)}
          cy={yToPx(p.aggregate)}
          r={3}
          fill={p.passes_threshold ? color : '#f43f5e'}
        >
          <title>{`${p.date}: ${fmtPct(p.aggregate)}`}</title>
        </circle>
      ))}

      {/* X axis: first + last date labels */}
      <text x={PAD.left} y={VIEW_H - 8} textAnchor="start" fontSize={10} fill="#94a3b8">
        {fmtDate(first.date)}
      </text>
      {n > 1 && (
        <text x={VIEW_W - PAD.right} y={VIEW_H - 8} textAnchor="end" fontSize={10} fill="#94a3b8">
          {fmtDate(last.date)}
        </text>
      )}
    </svg>
  );
};
