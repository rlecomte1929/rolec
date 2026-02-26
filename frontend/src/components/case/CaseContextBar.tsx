import React from 'react';

interface CaseContextBarProps {
  origin?: string;
  destination?: string;
  familyCount?: number;
  targetDate?: string;
  stage?: string;
}

export const CaseContextBar: React.FC<CaseContextBarProps> = ({
  origin,
  destination,
  familyCount,
  targetDate,
  stage,
}) => {
  const route = origin && destination ? `${origin} → ${destination}` : '-';
  const members = familyCount != null ? `${familyCount} Family Members` : '-';
  const target = targetDate || '-';
  const stageLabel = stage || '-';
  return (
    <div className="bg-[#0b1d33] text-white rounded-xl px-6 py-3 flex flex-wrap items-center gap-3 text-xs uppercase tracking-wide text-[#bfdbfe]">
      <span>Current case</span>
      <span className="text-white text-sm font-semibold normal-case">{route}</span>
      <span className="text-[#bfdbfe]">•</span>
      <span className="normal-case">👥 {members}</span>
      <span className="text-[#bfdbfe]">•</span>
      <span className="normal-case">📅 Target: {target}</span>
      <span className="text-[#bfdbfe]">•</span>
      <span className="normal-case">🚩 Stage: {stageLabel}</span>
    </div>
  );
};
