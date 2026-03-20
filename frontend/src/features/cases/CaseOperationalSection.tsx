import React from 'react';

type Props = {
  step: 1 | 2 | 3;
  title: string;
  subtitle: string;
  id?: string;
  children: React.ReactNode;
};

/**
 * Visual spine for the HR case page: numbered steps so essentials → readiness → tracker read as one workflow.
 */
export const CaseOperationalSection: React.FC<Props> = ({ step, title, subtitle, id, children }) => {
  return (
    <section id={id} className="scroll-mt-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:gap-4 mb-3">
        <div
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#0b2b43] text-sm font-bold text-white shadow-sm"
          aria-hidden
        >
          {step}
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[#0b2b43]">{title}</h2>
          <p className="text-xs text-[#64748b] mt-0.5 max-w-3xl leading-relaxed">{subtitle}</p>
        </div>
      </div>
      {children}
    </section>
  );
};

/** Scroll to a relocation plan row (see RelocationTaskTracker anchor ids). */
export function scrollToPlanTask(milestoneType: string): void {
  const safe = milestoneType.replace(/[^a-zA-Z0-9_-]/g, '');
  if (!safe) return;
  const el = document.getElementById(`hr-op-task-${safe}`);
  el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
}
