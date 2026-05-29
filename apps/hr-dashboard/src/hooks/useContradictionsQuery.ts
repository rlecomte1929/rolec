import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  listCaseContradictions,
  listCorrectionHistory,
  resolveContradiction,
} from '../api/contradictions';
import type {
  Contradiction,
  PriorCorrection,
  ResolvePayload,
  ResolveResponse,
} from '../features/resolution/types';

/**
 * Server-state hooks for the Contradiction Resolution surface.
 *
 * Per the brief: NO optimistic updates on resolve — the canonical value
 * change is the trigger for downstream side-effects (audit log,
 * agent_runs re-write), so the UI waits for the 200.
 */

export function useCaseContradictionsQuery(caseId: string | undefined) {
  return useQuery({
    queryKey: ['hr-contradictions', caseId],
    enabled: Boolean(caseId),
    queryFn: () => listCaseContradictions(caseId as string),
  });
}

export function useCorrectionHistoryQuery(
  caseId: string | undefined,
  contradictionId: string | undefined,
) {
  return useQuery({
    queryKey: ['hr-corrections', caseId, contradictionId],
    enabled: Boolean(caseId && contradictionId),
    queryFn: () => listCorrectionHistory(caseId as string, contradictionId as string),
  });
}

export function useResolveContradictionMutation(caseId: string | undefined) {
  const qc = useQueryClient();
  return useMutation<
    ResolveResponse,
    Error,
    { contradictionId: string; payload: ResolvePayload }
  >({
    mutationFn: ({ contradictionId, payload }) => {
      if (!caseId) {
        throw new Error('resolveContradiction called without a caseId');
      }
      return resolveContradiction(caseId, contradictionId, payload);
    },
    onSuccess: () => {
      // Invalidate so the next render fetches the post-resolve state.
      qc.invalidateQueries({ queryKey: ['hr-contradictions', caseId] });
      qc.invalidateQueries({ queryKey: ['hr-corrections', caseId] });
    },
  });
}

/** Local-state types re-exported for convenience. */
export type { Contradiction, PriorCorrection };
