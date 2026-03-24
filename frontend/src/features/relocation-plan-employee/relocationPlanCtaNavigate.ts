import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import type { RelocationPlanCtaDTO } from '../../types/relocationPlanView';
import { resolveRelocationTaskCtaTarget, type CtaNavigateTarget } from '../relocation-plan/task-card/relocationTaskCtaMap';

export type { CtaNavigateTarget, RelocationPlanCtaNavigateContext } from '../relocation-plan/task-card/relocationTaskCtaMap';

export type RelocationPlanCtaNavigateOptions = {
  resourceCaseId?: string | null;
  role?: 'employee' | 'hr';
};

/**
 * @deprecated Prefer `resolveRelocationTaskCtaTarget` from `relocation-plan/task-card`.
 */
export function relocationPlanCtaNavigateTarget(
  routeCaseId: string,
  cta: RelocationPlanCtaDTO | null | undefined,
  options?: RelocationPlanCtaNavigateOptions
): CtaNavigateTarget {
  return resolveRelocationTaskCtaTarget(
    {
      routeCaseId,
      resourceCaseId: options?.resourceCaseId,
      role: options?.role ?? 'employee',
    },
    cta
  );
}

export function useRelocationPlanCtaHandler(
  routeCaseId: string,
  options?: RelocationPlanCtaNavigateOptions
) {
  const navigate = useNavigate();
  const resourceCaseId = options?.resourceCaseId;
  const role = options?.role ?? 'employee';

  return useCallback(
    (cta: RelocationPlanCtaDTO | null | undefined) => {
      const t = resolveRelocationTaskCtaTarget({ routeCaseId, resourceCaseId, role }, cta);
      if (t.kind === 'internal') navigate(t.to);
      else if (t.kind === 'external') window.open(t.href, '_blank', 'noopener,noreferrer');
    },
    [routeCaseId, resourceCaseId, role, navigate]
  );
}
