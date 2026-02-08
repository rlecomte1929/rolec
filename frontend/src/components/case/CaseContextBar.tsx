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
  familyCount = 1,
  targetDate,
  stage,
}) => {
  return (
    <div className="bg-[#0b1d33] text-white rounded-xl px-6 py-3 flex flex-wrap items-center gap-3 text-xs uppercase tracking-wide text-[#bfdbfe]">
      <span>Current case</span>
      <span className="text-white text-sm font-semibold normal-case">
        {origin && destination ? `${origin} → ${destination}` : 'Relocation case'}
      </span>
      <span className="text-[#bfdbfe]">•</span>
      <span className="normal-case">👥 {familyCount} Family Members</span>
      <span className="text-[#bfdbfe]">•</span>
      <span className="normal-case">📅 Target: {targetDate || '—'}</span>
      <span className="text-[#bfdbfe]">•</span>
      <span className="normal-case">🚩 Stage: {stage || 'Intake'}</span>
    </div>
  );
};
