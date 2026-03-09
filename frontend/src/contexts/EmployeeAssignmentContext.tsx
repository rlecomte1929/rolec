import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { employeeAPI } from '../api/client';
import { invalidateApiCache } from '../api/client';
import { getAuthItem } from '../utils/demo';

const CURRENT_ASSIGNMENT_CACHE_KEY = 'employee:current-assignment';

interface EmployeeAssignmentContextValue {
  assignmentId: string | null;
  isLoading: boolean;
  /** Refetch assignment (clears cache). Call when user retries or returns to Services. */
  refetch: () => Promise<void>;
}

const defaultValue: EmployeeAssignmentContextValue = {
  assignmentId: null,
  isLoading: false,
  refetch: async () => {},
};

const EmployeeAssignmentContext = createContext<EmployeeAssignmentContextValue>(defaultValue);

export const EmployeeAssignmentProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [assignmentId, setAssignmentId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const role = getAuthItem('relopass_role');
  const isEmployee = role === 'EMPLOYEE' || role === 'ADMIN';

  const fetchAssignment = useCallback(async (clearCache = false) => {
    if (!isEmployee || !getAuthItem('relopass_token')) return;
    if (clearCache) invalidateApiCache(CURRENT_ASSIGNMENT_CACHE_KEY);
    setIsLoading(true);
    try {
      const res = await employeeAPI.getCurrentAssignment();
      if (res?.assignment?.id) {
        setAssignmentId(res.assignment.id);
      } else {
        setAssignmentId(null);
      }
    } catch {
      setAssignmentId(null);
    } finally {
      setIsLoading(false);
    }
  }, [isEmployee]);

  useEffect(() => {
    fetchAssignment(false);
  }, [fetchAssignment]);

  const refetch = useCallback(() => fetchAssignment(true), [fetchAssignment]);

  return (
    <EmployeeAssignmentContext.Provider value={{ assignmentId, isLoading, refetch }}>
      {children}
    </EmployeeAssignmentContext.Provider>
  );
};

export const useEmployeeAssignment = () => useContext(EmployeeAssignmentContext);
