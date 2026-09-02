import React from 'react';

/** `indigo` is a deprecated alias for `navy` (off-brand name kept so callers compile). */
export type ProgressBarColor = 'navy' | 'indigo' | 'green' | 'yellow' | 'red';

interface ProgressBarProps {
  value: number; // 0-100
  label?: string;
  showLabel?: boolean;
  color?: ProgressBarColor;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  value,
  label,
  showLabel = true,
  color = 'navy',
}) => {
  const colors: Record<ProgressBarColor, string> = {
    navy: 'bg-[#0b2b43]',
    indigo: 'bg-[#0b2b43]',
    green: 'bg-emerald-600',
    yellow: 'bg-amber-600',
    red: 'bg-rose-700',
  };

  return (
    <div className="w-full">
      {label && <div className="text-sm font-medium text-[#374151] mb-1">{label}</div>}
      <div className="w-full bg-[#e2e8f0] rounded-full h-2.5">
        <div
          className={`h-2.5 rounded-full transition-all duration-300 ${colors[color]}`}
          style={{ width: `${Math.min(Math.max(value, 0), 100)}%` }}
        ></div>
      </div>
      {showLabel && (
        <div className="text-xs text-slate-500 mt-1 text-right">{Math.round(value)}%</div>
      )}
    </div>
  );
};
