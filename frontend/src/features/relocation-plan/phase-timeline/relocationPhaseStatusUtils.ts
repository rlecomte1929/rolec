import type { RelocationPlanPhaseStatusWire } from '../../../types/relocationPlanView';
import type { RelocationPlanPhaseTaskCountsDTO } from '../../../types/relocationPlanView';

export type PhaseBadgeVariant = 'success' | 'warning' | 'error' | 'info' | 'neutral';

/** Matches antigravity `ProgressBar` `color` prop */
export type RelocationPhaseProgressColor = 'indigo' | 'green' | 'yellow' | 'red';

export interface RelocationPhaseStatusMeta {
  /** Short label for badges and assistive context */
  label: string;
  badgeVariant: PhaseBadgeVariant;
  /** Tailwind background class for the timeline node dot */
  markerClass: string;
  progressColor: RelocationPhaseProgressColor;
}

const STATUS_TABLE: Record<RelocationPlanPhaseStatusWire, RelocationPhaseStatusMeta> = {
  completed: {
    label: 'Completed',
    badgeVariant: 'success',
    markerClass: 'bg-[#1f8e8b]',
    progressColor: 'green',
  },
  active: {
    label: 'Active',
    badgeVariant: 'info',
    markerClass: 'bg-[#0b2b43]',
    progressColor: 'indigo',
  },
  upcoming: {
    label: 'Upcoming',
    badgeVariant: 'neutral',
    markerClass: 'bg-[#cbd5e1]',
    progressColor: 'indigo',
  },
  blocked: {
    label: 'Blocked',
    badgeVariant: 'error',
    markerClass: 'bg-amber-500',
    progressColor: 'yellow',
  },
};

export function getRelocationPhaseStatusMeta(
  status: RelocationPlanPhaseStatusWire
): RelocationPhaseStatusMeta {
  return STATUS_TABLE[status] ?? STATUS_TABLE.upcoming;
}

/** Human-readable phase status (timeline + summaries). */
export function relocationPhaseStatusLabel(status: RelocationPlanPhaseStatusWire): string {
  switch (status) {
    case 'active':
      return 'In focus';
    case 'completed':
      return 'Completed';
    case 'upcoming':
      return 'Up next';
    case 'blocked':
      return 'Needs attention';
    default:
      return status;
  }
}

/**
 * `completion_ratio` from API is in [0, 1]. ProgressBar expects [0, 100].
 */
export function relocationPhaseProgressPercent(completionRatio: number): number {
  if (!Number.isFinite(completionRatio)) return 0;
  return Math.min(100, Math.max(0, completionRatio <= 1 ? completionRatio * 100 : completionRatio));
}

export function formatRelocationPhaseTaskCounts(c: RelocationPlanPhaseTaskCountsDTO): string {
  const parts = [`${c.completed}/${c.total} done`, `${c.in_progress} in progress`];
  if (c.blocked > 0) parts.push(`${c.blocked} blocked`);
  return parts.join(' · ');
}
