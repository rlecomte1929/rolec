import React from 'react';

export type SlaStatus = 'on_track' | 'at_risk' | 'overdue';

interface SLABadgeProps {
  /** Timeline SLA from the backend; null/unknown renders an em-dash. */
  status?: SlaStatus | string | null;
  /** Signed days to the target move date (negative = past). */
  daysUntilMove?: number | null;
  size?: 'sm' | 'md';
}

const STYLES: Record<SlaStatus, { cls: string; label: string }> = {
  on_track: { cls: 'bg-[#dcfce7] text-[#166534]', label: 'On track' },
  at_risk: { cls: 'bg-[#fef9c3] text-[#854d0e]', label: 'At risk' },
  overdue: { cls: 'bg-[#fee2e2] text-[#991b1b]', label: 'Overdue' },
};

function daysLabel(days?: number | null): string | null {
  if (days === null || days === undefined) return null;
  if (days < 0) return `${Math.abs(days)}d ago`;
  if (days === 0) return 'today';
  return `${days}d`;
}

export const SLABadge: React.FC<SLABadgeProps> = ({ status, daysUntilMove, size = 'sm' }) => {
  if (!status || !(status in STYLES)) {
    return <span className="text-gray-500">—</span>;
  }
  const s = STYLES[status as SlaStatus];
  const dl = daysLabel(daysUntilMove);
  const pad = size === 'sm' ? 'px-2 py-0.5 text-[11px]' : 'px-2.5 py-1 text-xs';
  return (
    <span className={`inline-flex items-center gap-1 rounded-full font-medium ${pad} ${s.cls}`}>
      {s.label}
      {dl ? <span className="opacity-70">· {dl}</span> : null}
    </span>
  );
};
