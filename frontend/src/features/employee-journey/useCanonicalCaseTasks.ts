import { useEffect, useState } from 'react';
import { fetchRelocationPlanView } from '../../api/relocationPlanView';
import type {
  RelocationPlanViewResponseDTO,
  RelocationPlanPhaseTaskDTO,
} from '../../types/relocationPlanView';
import { deriveCanonicalProgress, type CanonicalProgress } from './caseStage';

export interface CanonicalCaseTasks {
  view: RelocationPlanViewResponseDTO | null;
  /** Flattened tasks across all phases (the canonical task set for the case). */
  tasks: RelocationPlanPhaseTaskDTO[];
  progress: CanonicalProgress;
  loading: boolean;
  error: string | null;
}

const EMPTY_PROGRESS: CanonicalProgress = {
  completed: 0,
  total: 0,
  pct: 0,
  blocked: 0,
  readyNow: 0,
};

/**
 * The ONE source of truth for a case's tasks + overall task progress — the
 * relocation-plan view (case_milestones). Roadmap, Tasks page, and any top-level
 * task % must read from this so the numbers can never disagree across pages.
 */
export function useCanonicalCaseTasks(caseId: string | null | undefined): CanonicalCaseTasks {
  const [view, setView] = useState<RelocationPlanViewResponseDTO | null>(null);
  const [loading, setLoading] = useState<boolean>(!!caseId);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!caseId) {
      setView(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchRelocationPlanView(caseId, { role: 'employee' })
      .then((res) => {
        if (!cancelled) setView(res);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError((e as Error)?.message ?? 'Failed to load tasks');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  const tasks = view ? view.phases.flatMap((p) => p.tasks) : [];
  const progress = view ? deriveCanonicalProgress(view.summary) : EMPTY_PROGRESS;
  return { view, tasks, progress, loading, error };
}
