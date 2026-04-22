import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';

interface DemoBookingContextValue {
  isOpen: boolean;
  sourcePage: string | null;
  open: (sourcePage?: string) => void;
  close: () => void;
}

const DemoBookingContext = createContext<DemoBookingContextValue | null>(null);

export const DemoBookingProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [sourcePage, setSourcePage] = useState<string | null>(null);

  const open = useCallback((source?: string) => {
    setSourcePage(source ?? (typeof window !== 'undefined' ? window.location.pathname : null));
    setIsOpen(true);
  }, []);

  const close = useCallback(() => {
    setIsOpen(false);
  }, []);

  const value = useMemo(
    () => ({ isOpen, sourcePage, open, close }),
    [isOpen, sourcePage, open, close]
  );

  return <DemoBookingContext.Provider value={value}>{children}</DemoBookingContext.Provider>;
};

export function useDemoBooking(): DemoBookingContextValue {
  const ctx = useContext(DemoBookingContext);
  if (!ctx) {
    throw new Error('useDemoBooking must be used within a DemoBookingProvider');
  }
  return ctx;
}
