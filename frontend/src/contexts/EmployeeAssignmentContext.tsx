import React, { createContext, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { employeeAPI, invalidateApiCache } from '../api/client';
import { getAuthItem } from '../utils/demo';
import type { EmployeeLinkedOverviewRow, EmployeePendingOverviewRow } from '../types/employeeAssignmentOverview';
import { shouldLoadEmployeeAssignmentOverview } from '../utils/employeeAssignmentScope';
import { trackAssignmentFlow, ASSIGNMENT_FLOW_EVENTS } from '../perf/assignmentLinkingInstrumentation';

const CURRENT_ASSIGNMENT_CACHE_KEY = 'employee:current-assignment';

interface EmployeeAssignmentContextValue {
  /** Primary linked assignment id (first by recency) for nav and case stats. */
  assignmentId: string | null;
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
  isLoading: false,
  linkedCount: 0,
  pendingCount: 0,
  linkedSummaries: [],
  pendingSummaries: [],
  overviewError: null,
  refetch: async () => {},
};

const EmployeeAssignmentContext = createContext<EmployeeAssignmentContextValue>(defaultValue);

export const EmployeeAssignmentProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [assignmentId, setAssignmentId] = useState<string | null>(null);
  const [linkedSummaries, setLinkedSummaries] = useState<EmployeeLinkedOverviewRow[]>([]);
  const [pendingSummaries, setPendingSummaries] = useState<EmployeePendingOverviewRow[]>([]);
  const [overviewError, setOverviewError] = useState<string | null>(null);
  const location = useLocation();
  const pathname = location.pathname;
  const role = getAuthItem('relopass_role');
  const isEmployee = role === 'EMPLOYEE' || role === 'ADMIN';
  const token = Boolean(getAuthItem('relopass_token'));
  const shouldFetch = isEmployee && token && shouldLoadEmployeeAssignmentOverview(pathname);

  const [isLoading, setIsLoading] = useState(shouldFetch);
  const fetchGenRef = useRef(0);

  const linkedCount = linkedSummaries.length;
  const pendingCount = pendingSummaries.length;

  useLayoutEffect(() => {
    if (!shouldFetch) {
      setIsLoading(false);
      if (!isEmployee || !token) {
        setAssignmentId(null);
        setLinkedSummaries([]);
        setPendingSummaries([]);
        setOverviewError(null);
      }
      return;
    }
    setIsLoading(true);
  }, [shouldFetch, isEmployee, token]);

  const loadAssignment = useCallback(
    async (clearCache: boolean): Promise<void> => {
      if (!isEmployee || !getAuthItem('relopass_token') || !shouldLoadEmployeeAssignmentOverview(pathname)) {
        fetchGenRef.current += 1;
        setIsLoading(false);
        if (!isEmployee || !getAuthItem('relopass_token')) {
          setAssignmentId(null);
          setLinkedSummaries([]);
          setPendingSummaries([]);
          setOverviewError(null);
        }
        return;
      }
      const gen = ++fetchGenRef.current;
      if (clearCache) invalidateApiCache(CURRENT_ASSIGNMENT_CACHE_KEY);
      setIsLoading(true);
      setOverviewError(null);
      const t0 = typeof performance !== 'undefined' ? performance.now() : Date.now();
      trackAssignmentFlow(ASSIGNMENT_FLOW_EVENTS.overviewLookupStart, {
        pathname,
        clearCache,
      });
      try {
        const overview = await employeeAPI.getAssignmentsOverview();
        const t1 = typeof performance !== 'undefined' ? performance.now() : Date.now();
        if (gen !== fetchGenRef.current) return;
        const linked = (overview?.linked || []) as EmployeeLinkedOverviewRow[];
        const pending = (overview?.pending || []) as EmployeePendingOverviewRow[];
        setLinkedSummaries(linked);
        setPendingSummaries(pending);
        const primary = linked[0]?.assignment_id ?? null;
        setAssignmentId(primary);
        trackAssignmentFlow(ASSIGNMENT_FLOW_EVENTS.overviewLookupComplete, {
          pathname,
          ok: true,
          durationMs: Math.round(t1 - t0),
          linkedCount: linked.length,
          pendingCount: pending.length,
        });
      } catch {
        const t1 = typeof performance !== 'undefined' ? performance.now() : Date.now();
        if (gen !== fetchGenRef.current) return;
        setAssignmentId(null);
        setLinkedSummaries([]);
        setPendingSummaries([]);
        setOverviewError('Could not load assignments. Check your connection, then refresh.');
        trackAssignmentFlow(ASSIGNMENT_FLOW_EVENTS.overviewLookupComplete, {
          pathname,
          ok: false,
          durationMs: Math.round(t1 - t0),
          linkedCount: 0,
          pendingCount: 0,
        });
      } finally {
        if (gen === fetchGenRef.current) setIsLoading(false);
      }
    },
    [isEmployee, pathname]
  );

  useEffect(() => {
    void loadAssignment(false);
  }, [loadAssignment]);

  const refetch = useCallback(() => loadAssignment(true), [loadAssignment]);

  return (
    <EmployeeAssignmentContext.Provider
      value={{
        assignmentId,
        isLoading,
        linkedCount,
        pendingCount,
        linkedSummaries,
        pendingSummaries,
        overviewError,
        refetch,
      }}
    >
      {children}
    </EmployeeAssignmentContext.Provider>
  );
};

export const useEmployeeAssignment = () => useContext(EmployeeAssignmentContext);
