import React from 'react';

interface CaseContextBarProps {
  origin?: string;
  destination?: string;
  /** Accompanying family members (NOT counting the employee). */
  familyCount?: number;
  targetDate?: string;
  stage?: string;
}

// TASK-009: format the target move date into employee-facing arrival copy.
function arrivalLabel(targetDate?: string): string {
  if (!targetDate) return 'Target arrival: Not set yet';
  const dt = new Date(targetDate);
  if (Number.isNaN(dt.getTime())) return `Arriving ${targetDate}`;
  return `Arriving ${dt.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })}`;
}

export const CaseContextBar: React.FC<CaseContextBarProps> = ({
  origin,
  destination,
  familyCount,
  targetDate,
  stage,
}) => {
  const route = origin && destination ? `${origin} → ${destination}` : '-';
  // TASK-009: human, first-person framing — pluralized, "Moving alone" at 0.
  const familyLabel =
    familyCount == null
      ? null
      : familyCount === 0
        ? 'Moving alone'
        : `With ${familyCount} family member${familyCount !== 1 ? 's' : ''}`;
  return (
    <div className="bg-[#0b1d33] text-white rounded-xl px-6 py-3 flex flex-wrap items-center gap-3 text-xs uppercase tracking-wide text-[#bfdbfe]">
      <span>Current case</span>
      <span className="text-white text-sm font-semibold normal-case">{route}</span>
      {familyLabel && (
        <>
          <span className="text-[#bfdbfe]">•</span>
          <span className="normal-case">👤 {familyLabel}</span>
        </>
      )}
      <span className="text-[#bfdbfe]">•</span>
      <span className="normal-case">📅 {arrivalLabel(targetDate)}</span>
      {stage && (
        <>
          <span className="text-[#bfdbfe]">•</span>
          <span className="normal-case inline-flex items-center gap-1.5">
            {/* TASK-009: neutral status dot instead of the 🚩 flag emoji. */}
            <span className="w-2 h-2 rounded-full bg-[#38bdf8] inline-block" aria-hidden="true" />
            {stage}
          </span>
        </>
      )}
    </div>
  );
};
