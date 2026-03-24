import React, { useCallback } from 'react';
import { ChevronDown } from 'lucide-react';
import { Badge, ProgressBar } from '../../../components/antigravity';
import type { RelocationPlanPhaseStatusWire } from '../../../types/relocationPlanView';
import type { RelocationPlanPhaseTaskCountsDTO } from '../../../types/relocationPlanView';
import {
  formatRelocationPhaseTaskCounts,
  getRelocationPhaseStatusMeta,
  relocationPhaseProgressPercent,
  relocationPhaseStatusLabel,
} from './relocationPhaseStatusUtils';

export interface RelocationPhaseSectionProps {
  phaseKey: string;
  title: string;
  status: RelocationPlanPhaseStatusWire;
  /** API completion ratio in [0, 1] (or 0–100; see `relocationPhaseProgressPercent`). */
  completionRatio: number;
  taskCounts: RelocationPlanPhaseTaskCountsDTO;
  expanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
  /** Default 3 — use under page `h1` / timeline section `h2`. */
  headingLevel?: 2 | 3 | 4;
}

function PhaseTitleHeading(props: {
  level: 2 | 3 | 4;
  id: string;
  className: string;
  children: React.ReactNode;
}) {
  const { level, id, className, children } = props;
  switch (level) {
    case 2:
      return (
        <h2 id={id} className={className}>
          {children}
        </h2>
      );
    case 4:
      return (
        <h4 id={id} className={className}>
          {children}
        </h4>
      );
    case 3:
    default:
      return (
        <h3 id={id} className={className}>
          {children}
        </h3>
      );
  }
}

/**
 * Single phase row in a vertical relocation timeline: accordion header + collapsible body.
 * Header uses `role="button"` so block content (progress bar) stays valid and keyboard-accessible.
 */
export const RelocationPhaseSection: React.FC<RelocationPhaseSectionProps> = ({
  phaseKey,
  title,
  status,
  completionRatio,
  taskCounts,
  expanded,
  onToggle,
  children,
  headingLevel = 3,
}) => {
  const meta = getRelocationPhaseStatusMeta(status);
  const pct = relocationPhaseProgressPercent(completionRatio);
  const titleId = `relocation-phase-${phaseKey}-title`;
  const panelId = `relocation-phase-${phaseKey}-panel`;
  const countsText = formatRelocationPhaseTaskCounts(taskCounts);
  const statusHint = relocationPhaseStatusLabel(status);

  const onHeaderKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
        e.preventDefault();
        onToggle();
      }
    },
    [onToggle]
  );

  return (
    <section className="relative" aria-labelledby={titleId}>
      <div
        role="button"
        tabIndex={0}
        aria-expanded={expanded}
        aria-controls={panelId}
        aria-labelledby={titleId}
        onClick={onToggle}
        onKeyDown={onHeaderKeyDown}
        className="relative z-[1] w-full text-left rounded-xl border border-[#e2e8f0] bg-white shadow-sm hover:border-[#cbd5e1] hover:bg-[#fafbfc] transition-colors cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0b2b43] focus-visible:ring-offset-2"
      >
        <div className="flex items-start gap-3 px-4 py-4 min-h-[56px]">
          <span
            className={`mt-2 h-2.5 w-2.5 rounded-full shrink-0 ring-2 ring-white ${meta.markerClass}`}
            aria-hidden
            title={statusHint}
          />
          <div className="flex-1 min-w-0 space-y-2">
            <div className="flex flex-wrap items-center gap-2 gap-y-1">
              <PhaseTitleHeading
                level={headingLevel}
                id={titleId}
                className="text-base font-semibold text-[#0b2b43] leading-snug"
              >
                {title}
              </PhaseTitleHeading>
              <Badge variant={meta.badgeVariant} size="sm">
                {meta.label}
              </Badge>
            </div>
            {taskCounts.total > 0 ? (
              <p className="text-xs text-[#64748b]">{countsText}</p>
            ) : null}
            {taskCounts.total > 0 && !(status === 'completed' && pct >= 99.5) ? (
              <div className="max-w-md">
                <span className="sr-only">
                  {statusHint}. {Math.round(pct)}% complete for this phase.
                </span>
                <ProgressBar
                  value={pct}
                  showLabel={false}
                  color={meta.progressColor}
                  label={undefined}
                />
              </div>
            ) : taskCounts.total > 0 && status === 'completed' && pct >= 99.5 ? (
              <span className="sr-only">Phase complete.</span>
            ) : null}
          </div>
          <ChevronDown
            className={`mt-1 size-5 shrink-0 text-[#64748b] transition-transform duration-200 ${
              expanded ? 'rotate-180' : ''
            }`}
            aria-hidden
          />
        </div>
      </div>

      <div
        id={panelId}
        role="region"
        aria-labelledby={titleId}
        hidden={!expanded}
        className={expanded ? 'mt-3 sm:ml-6 space-y-3 pb-2' : 'hidden'}
      >
        {expanded ? children : null}
      </div>
    </section>
  );
};
