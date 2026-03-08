import React from 'react';

type PriorityBand = 'critical' | 'high' | 'medium' | 'low';

const STYLES: Record<PriorityBand, string> = {
  critical: 'bg-red-200 text-red-900',
  high: 'bg-orange-100 text-orange-800',
  medium: 'bg-amber-100 text-amber-800',
  low: 'bg-slate-100 text-slate-700',
};

interface Props {
  band: PriorityBand | string;
  score?: number;
  label?: string;
}

export const ReviewQueuePriorityBadge: React.FC<Props> = ({ band, score, label }) => {
  const b = (band || 'medium').toLowerCase() as PriorityBand;
  const cls = STYLES[b] || STYLES.medium;
  const text = label ?? (score != null ? `${b} (${score})` : b);
  return (
    <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ${cls}`}>
      {text}
    </span>
  );
};
