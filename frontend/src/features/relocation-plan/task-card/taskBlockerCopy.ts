import type { RelocationPlanPhaseTaskDTO } from '../../../types/relocationPlanView';

/**
 * Single explanation for blocked / dependency context (collapsed + expanded).
 */
export function relocationTaskBlockerExplanation(task: RelocationPlanPhaseTaskDTO): string | null {
  const parts: string[] = [];
  if (task.blocked_by?.length) {
    parts.push(`Waiting on prior steps: ${task.blocked_by.join(', ')}.`);
  } else if (task.status === 'blocked') {
    parts.push('This step is blocked until earlier steps are finished.');
  }
  if (task.depends_on?.length) {
    parts.push(`Linked steps: ${task.depends_on.join(', ')}.`);
  }
  return parts.length ? parts.join(' ') : null;
}

export function isRelocationTaskBlocked(task: RelocationPlanPhaseTaskDTO): boolean {
  return task.status === 'blocked' || (task.blocked_by?.length ?? 0) > 0;
}
