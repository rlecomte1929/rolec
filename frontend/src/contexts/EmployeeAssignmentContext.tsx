import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocation } from 'react-router-dom';
import { employeeAPI, invalidateApiCache } from '../api/client';
import { getAuthItem } from '../utils/demo';
import type { EmployeeLinkedOverviewRow, EmployeePendingOverviewRow } from '../types/employeeAssignmentOverview';
import {
  dedupeLinkedSummariesByAssignmentId,
  setPreferredEmployeeAssignmentId,
  shouldLoadEmployeeAssignmentOverview,
} from '../utils/employeeAssignmentScope';
import { trackAssignmentFlow, ASSIGNMENT_FLOW_EVENTS } from '../perf/assignmentLinkingInstrumentation';
import { classifyOverviewLoadError } from '../features/employee-journey/overviewLoadError';

const CURRENT_ASSIGNMENT_CACHE_KEY = 'employee:current-assignment';
const ASSIGNMENTS_OVERVIEW_CACHE_KEY = 'employee:assignments-overview';

const OVERVIEW_QUERY_KEY = ['employee', 'assignments-overview'] as const;

export type EmployeePrimaryCompany = { id: string | null; name: string | null };

interface EmployeeAssignmentContextValue {
  /** Primary linked assignment id (first by recency) for nav and case stats. */
  assignmentId: string | null;
  /** Primary linked case id (first by recency). Distinct from assignmentId — case-scoped routes (roadmap/dossier) need this. */
  primaryCaseId: string | null;
  /** Company on the primary linked assignment (from overview); prefer over generic /api/company for employees. */
  primaryAssignmentCompany: EmployeePrimaryCompany | null;
  isLoading: boolean;
  linkedCount: number;
  pendingCount: number;
  linkedSummaries: EmployeeLinkedOverviewRow[];
  pendingSummaries: EmployeePendingOverviewRow[];
  /** Bootstrap failed (overview unreachable). */
  overviewError: string | null;
  refetch: () => Promise<void>;
}

const defaultValue: EmployeeAssignmentContextValue = {
  assignmentId: null,
  primaryCaseId: null,
  primaryAssignmentCompany: null,
  isLoading: false,
  linkedCount: 0,
  pendingCount: 0,
  linkedSummaries: [],
  pendingSummaries: [],
  overviewError: null,
  refetch: async () => {},
};

const EmployeeAssignmentContext = createContext<EmployeeAssignmentContextValue>(defaultValue);

const EMPTY_LINKED: EmployeeLinkedOverviewRow[] = [];
const EMPTY_PENDING: EmployeePendingOverviewRow[] = [];

export const EmployeeAssignmentProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const queryClient = useQueryClient();
  const location = useLocation();
  const pathname = location.pathname;
  const pathnameRef = useRef(pathname);
  pathnameRef.current = pathname;

  const role = getAuthItem('relopass_role');
  const isEmployee = role === 'EMPLOYEE' || role === 'ADMIN';
  const token = Boolean(getAuthItem('relopass_token'));
  const routeNeedsOverview = useMemo(() => shouldLoadEmployeeAssignmentOverview(pathname), [pathname]);
  const shouldFetch = isEmployee && token && routeNeedsOverview;

  const query = useQuery({
    queryKey: [...OVERVIEW_QUERY_KEY],
    queryFn: async () => {
      const path = pathnameRef.current;
      const t0 = typeof performance !== 'undefined' ? performance.now() : Date.now();
      trackAssignmentFlow(ASSIGNMENT_FLOW_EVENTS.overviewLookupStart, {
        pathname: path,
        clearCache: false,
      });
      try {
        const result = await employeeAPI.getAssignmentsOverview();
        const t1 = typeof performance !== 'undefined' ? performance.now() : Date.now();
        trackAssignmentFlow(ASSIGNMENT_FLOW_EVENTS.overviewLookupComplete, {
          pathname: path,
          ok: true,
          durationMs: Math.round(t1 - t0),
          linkedCount: (result?.linked || []).length,
          pendingCount: (result?.pending || []).length,
        });
        return result;
      } catch (e) {
        const t1 = typeof performance !== 'undefined' ? performance.now() : Date.now();
        trackAssignmentFlow(ASSIGNMENT_FLOW_EVENTS.overviewLookupComplete, {
          pathname: path,
          ok: false,
          durationMs: Math.round(t1 - t0),
          linkedCount: 0,
          pendingCount: 0,
        });
        throw e;
      }
    },
    enabled: shouldFetch,
    staleTime: 0,
  });

  const overview = query.data;

  const linked = useMemo(
    () => overview ? dedupeLinkedSummariesByAssignmentId((overview.linked || []) as EmployeeLinkedOverviewRow[]) : EMPTY_LINKED,
    [overview],
  );
  const pending = useMemo(
    () => overview ? (overview.pending || []) as EmployeePendingOverviewRow[] : EMPTY_PENDING,
    [overview],
  );

  const assignmentId = linked[0]?.assignment_id ?? null;
  const primaryCaseId = linked[0]?.case_id ?? null;

  const primaryAssignmentCompany = useMemo<EmployeePrimaryCompany | null>(() => {
    const c0 = linked[0]?.company;
    if (!c0) return null;
    const cn = (c0?.name && String(c0.name).trim()) || null;
    const cid = (c0?.id && String(c0.id).trim()) || null;
    return cn || cid ? { id: cid, name: cn } : null;
  }, [linked]);

  useEffect(() => {
    if (linked.length === 1 && assignmentId) {
      setPreferredEmployeeAssignmentId(assignmentId);
    }
  }, [linked.length, assignmentId]);

  const refetch = useCallback(async () => {
    invalidateApiCache(CURRENT_ASSIGNMENT_CACHE_KEY);
    invalidateApiCache(ASSIGNMENTS_OVERVIEW_CACHE_KEY);
    await queryClient.invalidateQueries({ queryKey: [...OVERVIEW_QUERY_KEY] });
  }, [queryClient]);

  const authed = isEmployee && token;
  const isLoading = shouldFetch && query.isLoading;
  const overviewError = query.isError
    ? classifyOverviewLoadError(query.error).message
    : null;

  return (
    <EmployeeAssignmentContext.Provider
      value={{
        assignmentId: authed ? assignmentId : null,
        primaryCaseId: authed ? primaryCaseId : null,
        primaryAssignmentCompany: authed ? primaryAssignmentCompany : null,
        isLoading,
        linkedCount: authed ? linked.length : 0,
        pendingCount: authed ? pending.length : 0,
        linkedSummaries: authed ? linked : EMPTY_LINKED,
        pendingSummaries: authed ? pending : EMPTY_PENDING,
        overviewError: authed ? overviewError : null,
        refetch,
      }}
    >
      {children}
    </EmployeeAssignmentContext.Provider>
  );
};

export const useEmployeeAssignment = () => useContext(EmployeeAssignmentContext);
