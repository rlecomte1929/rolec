import React from 'react';
import { Badge } from '../../components/antigravity';
import type { RelocationPlanSummaryDTO } from '../../types/relocationPlanView';

export interface RelocationPlanSummaryStripProps {
  summary: RelocationPlanSummaryDTO;
}

export const RelocationPlanSummaryStrip: React.FC<RelocationPlanSummaryStripProps> = ({ summary }) => {
  return (
    <div
      className="flex flex-wrap gap-2 py-3 px-1 sm:px-0 border-y border-[#e2e8f0] bg-[#fafbfc]/80 transition-colors duration-200"
      aria-label="Plan progress summary"
    >
      <Badge variant="neutral">Total {summary.total_tasks}</Badge>
      <Badge variant="success">Done {summary.completed_tasks}</Badge>
      {summary.in_progress_tasks > 0 ? (
        <Badge variant="info">In progress {summary.in_progress_tasks}</Badge>
      ) : null}
      {summary.blocked_tasks > 0 ? (
        <Badge variant="error">Blocked {summary.blocked_tasks}</Badge>
      ) : null}
      {summary.overdue_tasks > 0 ? (
        <Badge variant="error">Overdue {summary.overdue_tasks}</Badge>
      ) : null}
      {summary.due_soon_tasks > 0 ? (
        <Badge variant="warning">Due soon {summary.due_soon_tasks}</Badge>
      ) : null}
    </div>
  );
};
