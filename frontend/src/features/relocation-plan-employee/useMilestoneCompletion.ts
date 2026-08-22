import { useCallback, useEffect, useRef, useState } from 'react';
import { timelineAPI } from '../../api/client';
import type { RelocationPlanTaskStatusWire } from '../../types/relocationPlanView';

/**
 * [AIQ-2057] Let the employee tick a step off their relocation plan.
 *
 * `PATCH /api/cases/{case_id}/timeline/milestones/{milestone_id}` and its wrapper
 * (`timelineAPI.updateMilestone`) both already existed — nothing in the employee UI ever
 * called them. So a plan was something to read, not to work through. This hook is the
 * missing half.
 *
 * TWO VOCABULARIES, DELIBERATELY NOT MERGED. The plan view speaks
 * `not_started | in_progress | completed | blocked`; `case_milestones.status` speaks
 * `pending | done | …`, and `map_milestone_status_to_plan_status` (backend/relocation_plan_service.py:75)
 * is the one-way map between them. The write has to speak the DB's vocabulary, so the
 * translation lives here, in one place, rather than being spelled out at each call site.
 *
 * WHY THE OVERRIDE OUTLIVES THE REQUEST. A naive optimistic update clears itself when the
 * PATCH resolves, and the row then flashes back to its old status for as long as the
 * refetch takes — the tick appears to bounce. So the override is held until *fresh data
 * arrives*; the caller drops it by calling `clearOverrides()` when the new view lands.
 *
 * WHY FAILURE IS LOUD. On a rejected write the override is removed (the row goes back to
 * what the server still believes) AND an error is surfaced. Silently reverting is worse
 * than not offering the control: the employee sees their tick undo itself with no reason,
 * and reasonably concludes the product is broken. The server can legitimately refuse —
 * `assert_roadmap_released` 409s while HR still holds the plan for review.
 */

/** `case_milestones.status` values this hook writes. The DB vocabulary, not the plan's. */
type MilestoneStatusWire = 'done' | 'pending';

const COMPLETED: RelocationPlanTaskStatusWire = 'completed';
const NOT_STARTED: RelocationPlanTaskStatusWire = 'not_started';

const FAILURE_MESSAGE =
  'We couldn’t save that just now — your step is unchanged. Please try again.';

export interface MilestoneCompletion {
  /** taskId → the status to render instead of the one in the fetched plan. */
  statusOverrides: Record<string, RelocationPlanTaskStatusWire>;
  /** Tasks with a write in flight. The control should be disabled for these. */
  savingTaskIds: Set<string>;
  /** Non-null when the last write failed. Cleared by the next success. */
  error: string | null;
  /** Flip a task between completed and not-started. `current` is what is on screen now. */
  toggle: (taskId: string, current: RelocationPlanTaskStatusWire) => Promise<void>;
  /** Drop the optimistic overrides — call when a fresh plan view has arrived. */
  clearOverrides: () => void;
}

export function useMilestoneCompletion(
  caseId: string | undefined,
  refetch: () => void | Promise<unknown>,
): MilestoneCompletion {
  const [statusOverrides, setStatusOverrides] = useState<Record<string, RelocationPlanTaskStatusWire>>({});
  const [savingTaskIds, setSavingTaskIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  // Read synchronously inside `toggle` so a double-click is rejected on the spot; the state
  // copy above is only for rendering, and would still be stale on the second click.
  const inFlight = useRef<Set<string>>(new Set());

  useEffect(() => {
    // A different case is a different plan — nothing from the old one should survive.
    inFlight.current = new Set();
    setStatusOverrides({});
    setSavingTaskIds(new Set());
    setError(null);
  }, [caseId]);

  const clearOverrides = useCallback(() => setStatusOverrides({}), []);

  const toggle = useCallback(
    async (taskId: string, current: RelocationPlanTaskStatusWire) => {
      if (!caseId || !taskId) return;
      if (inFlight.current.has(taskId)) return;

      const nextPlanStatus = current === COMPLETED ? NOT_STARTED : COMPLETED;
      const nextWireStatus: MilestoneStatusWire = nextPlanStatus === COMPLETED ? 'done' : 'pending';

      inFlight.current.add(taskId);
      setSavingTaskIds(new Set(inFlight.current));
      setStatusOverrides((prev) => ({ ...prev, [taskId]: nextPlanStatus }));

      try {
        await timelineAPI.updateMilestone(caseId, taskId, { status: nextWireStatus });
        setError(null);
        // Override deliberately retained — see the note above. The refetch replaces the
        // plan underneath it, and the page drops it via clearOverrides once that lands.
        await refetch();
      } catch {
        setStatusOverrides((prev) => {
          const next = { ...prev };
          delete next[taskId];
          return next;
        });
        setError(FAILURE_MESSAGE);
      } finally {
        inFlight.current.delete(taskId);
        setSavingTaskIds(new Set(inFlight.current));
      }
    },
    [caseId, refetch],
  );

  return { statusOverrides, savingTaskIds, error, toggle, clearOverrides };
}
