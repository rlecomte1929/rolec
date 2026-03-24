import React, { useId } from 'react';
import type { RelocationPlanPhaseDTO } from '../../../types/relocationPlanView';
import { RelocationPhaseSection } from './RelocationPhaseSection';

export interface RelocationPhaseTimelineProps {
  phases: RelocationPlanPhaseDTO[];
  /** Map phase_key → expanded; parent owns state and default seeding (e.g. active phase open). */
  expandedByPhaseKey: Record<string, boolean>;
  onPhaseToggle: (phaseKey: string) => void;
  renderPhaseContent: (phase: RelocationPlanPhaseDTO) => React.ReactNode;
  /** Accessible name for the timeline region (rendered as visually hidden `h2`). */
  timelineLabel?: string;
  className?: string;
  /** Each phase title heading level (default 3, under the timeline `h2`). */
  phaseHeadingLevel?: 2 | 3 | 4;
}

/**
 * Vertical phased timeline for relocation plans: accordion sections with a shared rail.
 * Passes real `phases` from the API — no embedded mock data.
 */
export const RelocationPhaseTimeline: React.FC<RelocationPhaseTimelineProps> = ({
  phases,
  expandedByPhaseKey,
  onPhaseToggle,
  renderPhaseContent,
  timelineLabel = 'Relocation phases',
  className = '',
  phaseHeadingLevel = 3,
}) => {
  const timelineHeadingId = useId();

  return (
    <section className={className} aria-labelledby={timelineHeadingId}>
      <h2 id={timelineHeadingId} className="sr-only">
        {timelineLabel}
      </h2>
      <div className="space-y-6 border-l-2 border-[#e2e8f0] pl-4 sm:pl-5 ml-1">
        {phases.map((phase) => (
          <RelocationPhaseSection
            key={phase.phase_key}
            phaseKey={phase.phase_key}
            title={phase.title}
            status={phase.status}
            completionRatio={phase.completion_ratio}
            taskCounts={phase.task_counts}
            expanded={Boolean(expandedByPhaseKey[phase.phase_key])}
            onToggle={() => onPhaseToggle(phase.phase_key)}
            headingLevel={phaseHeadingLevel}
          >
            {renderPhaseContent(phase)}
          </RelocationPhaseSection>
        ))}
      </div>
    </section>
  );
};
