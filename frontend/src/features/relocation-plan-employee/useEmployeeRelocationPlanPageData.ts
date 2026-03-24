import { useCallback, useEffect, useRef } from 'react';
import { timelineAPI } from '../../api/client';
import { useRelocationPlanView } from '../../hooks/useRelocationPlanView';

/** Session-scoped guard so we only auto-ensure default milestones once per assignment. */
function timelineEnsureSessionKey(aid: string) {
  return `rolec_timeline_ensured:${aid}`;
}

/**
 * Phased plan view for the employee plan page, with a one-shot default-milestone bootstrap
 * when the plan is still empty after the first view fetch.
 */
export function useEmployeeRelocationPlanPageData(assignmentId: string | undefined) {
  const enabled = Boolean(assignmentId);
  const { data, loading, error, refetch } = useRelocationPlanView(assignmentId, {
    enabled,
    role: 'employee',
  });

  const deferredRanForAssignment = useRef<string | null>(null);

  useEffect(() => {
    deferredRanForAssignment.current = null;
  }, [assignmentId]);

  const ensureDefaultsAndReload = useCallback(async () => {
    if (!assignmentId) return;
    await timelineAPI.getByAssignment(assignmentId, { ensureDefaults: true, includeLinks: false });
    await refetch();
  }, [assignmentId, refetch]);

  useEffect(() => {
    if (!enabled || !assignmentId || loading || error) return;
    if (!data || data.summary.total_tasks > 0) return;
    if (deferredRanForAssignment.current === assignmentId) return;
    const key = timelineEnsureSessionKey(assignmentId);
    if (typeof sessionStorage !== 'undefined' && sessionStorage.getItem(key)) return;

    const t = window.setTimeout(() => {
      deferredRanForAssignment.current = assignmentId;
      void (async () => {
        try {
          await timelineAPI.getByAssignment(assignmentId, { ensureDefaults: true, includeLinks: false });
          await refetch();
        } finally {
          try {
            sessionStorage.setItem(key, '1');
          } catch {
            // ignore quota / private mode
          }
        }
      })();
    }, 400);
    return () => window.clearTimeout(t);
  }, [enabled, assignmentId, loading, error, data, refetch]);

  return { data, loading, error, refetch, ensureDefaultsAndReload };
}
