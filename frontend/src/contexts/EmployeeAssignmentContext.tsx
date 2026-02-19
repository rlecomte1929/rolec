import React, { createContext, useContext, useEffect, useState } from 'react';
import { employeeAPI } from '../api/client';
import { getAuthItem } from '../utils/demo';

interface EmployeeAssignmentContextValue {
  assignmentId: string | null;
  isLoading: boolean;
}

const defaultValue: EmployeeAssignmentContextValue = {
  assignmentId: null,
  isLoading: false,
};

const EmployeeAssignmentContext = createContext<EmployeeAssignmentContextValue>(defaultValue);

export const EmployeeAssignmentProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [assignmentId, setAssignmentId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const role = getAuthItem('relopass_role');
  const isEmployee = role === 'EMPLOYEE' || role === 'ADMIN';

  useEffect(() => {
    if (!isEmployee || !getAuthItem('relopass_token')) return;
    let cancelled = false;
    setIsLoading(true);
    employeeAPI
      .getCurrentAssignment()
      .then((res) => {
        if (!cancelled && res?.assignment?.id) {
          setAssignmentId(res.assignment.id);
        }
      })
      .catch(() => {
        if (!cancelled) setAssignmentId(null);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isEmployee]);

  return (
    <EmployeeAssignmentContext.Provider value={{ assignmentId, isLoading }}>
      {children}
    </EmployeeAssignmentContext.Provider>
  );
};

export const useEmployeeAssignment = () => useContext(EmployeeAssignmentContext);
