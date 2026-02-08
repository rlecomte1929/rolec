import React from 'react';

interface ProgressBarProps {
  value: number; // 0-100
  label?: string;
  showLabel?: boolean;
  color?: 'indigo' | 'green' | 'yellow' | 'red';
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  value,
  label,
  showLabel = true,
  color = 'indigo',
}) => {
  const colors = {
    indigo: 'bg-[#0b2b43]',
    green: 'bg-[#1f8e8b]',
    yellow: 'bg-[#7a5e2a]',
    red: 'bg-[#7a2a2a]',
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
        <div className="text-xs text-[#6b7280] mt-1 text-right">{Math.round(value)}%</div>
      )}
    </div>
  );
};
