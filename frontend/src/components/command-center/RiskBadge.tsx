import React from 'react';

export type RiskStatus = 'green' | 'yellow' | 'red';

interface RiskBadgeProps {
  status: RiskStatus;
  size?: 'sm' | 'md';
  showLabel?: boolean;
}

const styles: Record<RiskStatus, { dot: string; label: string }> = {
  green: { dot: 'bg-[#22c55e]', label: 'On track' },
  yellow: { dot: 'bg-[#eab308]', label: 'Attention needed' },
  red: { dot: 'bg-[#ef4444]', label: 'At risk' },
};

export const RiskBadge: React.FC<RiskBadgeProps> = ({ status, size = 'md', showLabel = false }) => {
  const s = styles[status] || styles.green;
  const dotSize = size === 'sm' ? 'w-2 h-2' : 'w-3 h-3';
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`rounded-full ${dotSize} ${s.dot} shrink-0`} aria-hidden />
      {showLabel && <span className="text-sm text-[#4b5563]">{s.label}</span>}
    </span>
  );
};
