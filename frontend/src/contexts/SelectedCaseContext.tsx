import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

interface SelectedCaseContextValue {
  selectedCaseId: string | null;
  setSelectedCaseId: (id: string | null) => void;
}

const SelectedCaseContext = createContext<SelectedCaseContextValue>({
  selectedCaseId: null,
  setSelectedCaseId: () => {},
});

const LS_KEY = 'relopass_last_assignment_id';

export const SelectedCaseProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const paramCaseId = searchParams.get('caseId');
  const storedId = localStorage.getItem(LS_KEY);

  const [selectedCaseId, setInternalId] = useState<string | null>(paramCaseId || storedId || null);

  // Sync from URL → state when query param changes externally
  useEffect(() => {
    if (paramCaseId && paramCaseId !== selectedCaseId) {
      setInternalId(paramCaseId);
      localStorage.setItem(LS_KEY, paramCaseId);
    }
  }, [paramCaseId]);

  const setSelectedCaseId = useCallback(
    (id: string | null) => {
      setInternalId(id);
      if (id) {
        localStorage.setItem(LS_KEY, id);
      } else {
        localStorage.removeItem(LS_KEY);
      }
    },
    [setSearchParams],
  );

  return (
    <SelectedCaseContext.Provider value={{ selectedCaseId, setSelectedCaseId }}>
      {children}
    </SelectedCaseContext.Provider>
  );
};

export const useSelectedCase = () => useContext(SelectedCaseContext);
