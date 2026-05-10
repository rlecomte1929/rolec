import type { RelocationPlanViewResponseDTO } from '../../../types/relocationPlanView';

export interface NextActionEmptyCopy {
  headline: string;
  /** Optional supporting line (e.g. sync note from API when headline is heuristic). */
  detail?: string;
}

/** Server-authored reasons that should drive the headline (aligned with `relocation_plan_next_action.py`). */
function isPrimaryEmptyStateReason(s: string): boolean {
  const t = s.trim();
  if (!t) return false;
  if (t.startsWith('Waiting for ')) return true;
  return t === 'No action required right now';
}

/**
 * Calm copy when `next_action` is null but the plan has tasks.
 * Prefer authoritative `empty_state_reason` from the API when it is a primary UX message;
 * otherwise use ownership heuristics and treat `empty_state_reason` as supplementary detail.
 */
export function nextActionCardEmptyCopy(data: RelocationPlanViewResponseDTO): NextActionEmptyCopy {
  const rawReason = data.empty_state_reason?.trim() || '';
  if (rawReason && isPrimaryEmptyStateReason(rawReason)) {
    return { headline: rawReason, detail: undefined };
  }
  const detail = rawReason || undefined;

  const incomplete = data.phases.flatMap((p) => p.tasks).filter(
    (t) => t.status !== 'completed' && t.status !== 'not_applicable'
  );

  if (incomplete.length === 0) {
    return { headline: 'No action required right now', detail };
  }

  const employeeOrJointLeft = incomplete.some((t) => t.owner === 'employee' || t.owner === 'joint');
  const hrOnlyPipeline = incomplete.every((t) => t.owner === 'hr');
  const providerBlocking = incomplete.some((t) => t.owner === 'provider');

  if (providerBlocking && !employeeOrJointLeft) {
    return { headline: 'Waiting for provider update', detail };
  }
  if (hrOnlyPipeline && !employeeOrJointLeft) {
    return { headline: 'Waiting for HR review', detail };
  }

  return { headline: 'No action required right now', detail };
}
