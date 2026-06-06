/**
 * [P4-1] DossierHealthRing — SVG ring showing dossier completeness + worst status.
 * Used in the Mobility Control case list Dossier column.
 */
import React from 'react';

import { Button } from '../../../components/antigravity/Button';
export type DossierRingStatus = 'green' | 'amber' | 'red' | 'empty';

export interface DossierHealthRingProps {
  pct: number;          // 0–100
  status: DossierRingStatus;
  totalForms: number;
  readyCount: number;
  actionCount: number;
  blockedCount: number;
  onClick?: () => void;
  disabled?: boolean;
}

const STATUS_COLOR: Record<DossierRingStatus, string> = {
  green:  '#10b981', // emerald-500
  amber:  '#f59e0b', // amber-500
  red:    '#f43f5e', // rose-500
  empty:  '#cbd5e1', // slate-300
};

export const DossierHealthRing: React.FC<DossierHealthRingProps> = ({
  pct,
  status,
  totalForms,
  readyCount,
  actionCount,
  blockedCount,
  onClick,
  disabled = false,
}) => {
  const size = 36;
  const stroke = 3;
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const dashOffset = circ * (1 - pct / 100);
  const color = STATUS_COLOR[status];

  const tooltip = totalForms === 0
    ? 'No documents yet'
    : `${readyCount} ready · ${actionCount} in progress · ${blockedCount} blocked`;

  return (
    <Button unstyled
      type="button"
      onClick={onClick}
      disabled={disabled || totalForms === 0}
      title={tooltip}
      className={`inline-flex flex-col items-center gap-0.5 ${disabled || totalForms === 0 ? 'opacity-40 cursor-default' : 'cursor-pointer hover:opacity-80'}`}
      aria-label={`Dossier: ${pct}% complete. ${tooltip}`}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: 'rotate(-90deg)' }}>
        {/* track */}
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#e2e8f0" strokeWidth={stroke} />
        {/* progress */}
        {totalForms > 0 && (
          <circle
            cx={size/2} cy={size/2} r={r}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeDasharray={`${circ}`}
            strokeDashoffset={`${dashOffset}`}
            strokeLinecap="round"
            style={{ transition: 'stroke-dashoffset 0.3s ease' }}
          />
        )}
        {/* pct label — un-rotate it */}
        <text
          x="50%" y="50%"
          textAnchor="middle" dominantBaseline="central"
          style={{ transform: 'rotate(90deg)', transformOrigin: '50% 50%', fontSize: '9px', fontWeight: 700, fill: totalForms === 0 ? '#94a3b8' : color }}
        >
          {totalForms === 0 ? '—' : `${pct}%`}
        </text>
      </svg>
    </Button>
  );
};
