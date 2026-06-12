import React from 'react';

export type PhaseStatus = 'done' | 'current' | 'upcoming';
export interface Phase {
  key: string;
  label: string;
  status: PhaseStatus;
}

interface PhaseContextBarProps {
  phases: Phase[];
  /** Fired when a navigable (done) phase is selected. Upcoming phases are not clickable. */
  onSelect?: (key: string) => void;
  className?: string;
}

export const PhaseContextBar: React.FC<PhaseContextBarProps> = ({ phases, onSelect, className = '' }) => (
  <nav
    aria-label="Relocation phases"
    className={`flex items-center gap-3 rounded-xl border border-[#e2e8f0] bg-white px-5 py-3 shadow-sm ${className}`}
  >
    {phases.map((p, i) => {
      const navigable = p.status === 'done' && Boolean(onSelect);
      const dotClass =
        p.status === 'done' ? 'bg-navy-800 text-white'
        : p.status === 'current' ? 'ring-2 ring-accent-500 text-accent-600 bg-white'
        : 'border border-[#e2e8f0] text-[#9aa6b2] bg-white';
      return (
        <React.Fragment key={p.key}>
          {i > 0 && <span className="h-px w-6 flex-none bg-[#e2e8f0]" aria-hidden="true" />}
          <button
            type="button"
            disabled={!navigable}
            aria-current={p.status === 'current' ? 'step' : undefined}
            onClick={() => navigable && onSelect?.(p.key)}
            className={`inline-flex items-center gap-2 rounded-lg px-2 py-1 text-[13px] font-semibold ${navigable ? 'hover:bg-navy-50 cursor-pointer' : 'cursor-default'} ${p.status === 'upcoming' ? 'text-[#9aa6b2]' : 'text-navy-800'}`}
          >
            <span className={`flex h-6 w-6 items-center justify-center rounded-full text-[11px] ${dotClass}`}>
              {p.status === 'done' ? '✓' : i + 1}
            </span>
            {p.label}
          </button>
        </React.Fragment>
      );
    })}
  </nav>
);
