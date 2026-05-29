import { useQuery } from '@tanstack/react-query';
import {
  fetchCaseDocuments,
  fetchCaseOverview,
  fetchCaseSteps,
  fetchContradictionsSummary,
} from '../api/case-detail';

/**
 * Per-section hooks for the Case Detail page.
 *
 * Each section gets its own hook so they fetch in parallel and have
 * independent loading / error states. Section components own the
 * `isLoading` / `isError` rendering — see OverviewSection / etc.
 */

const STALE_MS = 30_000;

export function useCaseOverviewQuery(caseId: string | undefined) {
  return useQuery({
    queryKey: ['hr-case-overview', caseId],
    enabled: Boolean(caseId),
    queryFn: () => fetchCaseOverview(caseId as string),
    staleTime: STALE_MS,
  });
}

export function useCaseDocumentsQuery(caseId: string | undefined) {
  return useQuery({
    queryKey: ['hr-case-documents', caseId],
    enabled: Boolean(caseId),
    queryFn: () => fetchCaseDocuments(caseId as string),
    staleTime: STALE_MS,
  });
}

export function useCaseStepsQuery(caseId: string | undefined) {
  return useQuery({
    queryKey: ['hr-case-steps', caseId],
    enabled: Boolean(caseId),
    queryFn: () => fetchCaseSteps(caseId as string),
    staleTime: STALE_MS,
  });
}

export function useContradictionsSummaryQuery(caseId: string | undefined) {
  return useQuery({
    queryKey: ['hr-case-contradictions-summary', caseId],
    enabled: Boolean(caseId),
    queryFn: () => fetchContradictionsSummary(caseId as string),
    // Contradictions count drives the inbox badge; keep it fresher.
    staleTime: 10_000,
  });
}
