import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { track } from '../analytics';

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
    const resolvedSource = source ?? (typeof window !== 'undefined' ? window.location.pathname : null);
    setSourcePage(resolvedSource);
    setIsOpen(true);
    track('demo_modal_opened', { source_page: resolvedSource });
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
