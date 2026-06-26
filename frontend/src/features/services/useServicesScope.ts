/**
 * useServicesScope (AIQ-1249a)
 *
 * Single source of truth for resolving the services flow's scope from the URL.
 * The flow is case-id-native (the URL may carry :caseId) but the services APIs
 * key on assignment_id, so this hook resolves BOTH and keeps ?assignment= back-compat:
 *
 *   - :caseId in path → resolve its assignment_id from linkedSummaries (never
 *     falls back to another case; an unknown caseId yields no assignment).
 *   - no :caseId      → existing behaviour: ?assignment= / preferred / primary,
 *     with a picker when ambiguous.
 *
 * `linkTo(step)` returns the correct next-step URL (case-scoped when a caseId is
 * known, else legacy + ?assignment=).
 */
import { useCallback, useMemo } from 'react';
import { useLocation, useParams } from 'react-router-dom';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import {
  parseAssignmentSearchParam,
  resolveAssignmentIdForCaseId,
  resolveCaseIdForAssignmentId,
  resolveScopedAssignmentId,
} from '../../utils/employeeAssignmentScope';
import { servicesStepPath, type ServicesStep } from './servicesRoutes';

export interface ServicesScope {
  /** Resolved assignment_id the services APIs key on (null until resolvable). */
  assignmentId: string | null;
  /** Resolved case_id (from the URL or from the assignment), null if unknown. */
  caseId: string | null;
  /** True when the assignment is ambiguous and the page should show a picker. */
  needsPicker: boolean;
  /** Bootstrap of linked assignments is in-flight. */
  isLoading: boolean;
  /** Build the URL for a services step, case-scoped when possible. */
  linkTo: (step: ServicesStep) => string;
}

export function useServicesScope(): ServicesScope {
  const params = useParams();
  const location = useLocation();
  const {
    assignmentId: primaryAssignmentId,
    linkedSummaries,
    isLoading,
  } = useEmployeeAssignment();

  const caseIdParam = (params.caseId || '').trim() || null;
  const queryAssignmentId = useMemo(
    () => parseAssignmentSearchParam(location.search),
    [location.search],
  );

  const scoped = useMemo(
    () => resolveScopedAssignmentId({ linkedSummaries, primaryAssignmentId, queryAssignmentId }),
    [linkedSummaries, primaryAssignmentId, queryAssignmentId],
  );

  // When the URL pins a case, that case wins and there is never a picker. We do
  // NOT fall back to the primary assignment for an unknown caseId — that would be
  // a cross-case switch.
  const assignmentId = caseIdParam
    ? resolveAssignmentIdForCaseId(linkedSummaries, caseIdParam)
    : scoped.effectiveId;
  const needsPicker = caseIdParam ? false : scoped.needsPicker;
  const caseId = caseIdParam ?? resolveCaseIdForAssignmentId(linkedSummaries, assignmentId);

  const linkTo = useCallback(
    (step: ServicesStep) => servicesStepPath(step, { caseId, assignmentId }),
    [caseId, assignmentId],
  );

  return { assignmentId, caseId, needsPicker, isLoading, linkTo };
}
