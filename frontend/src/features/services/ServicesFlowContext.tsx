import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { RecommendationResponse } from '../recommendations/types';
import type { ServiceKey } from './serviceConfig';
import { normalizeServicesCurrency, SERVICES_DISPLAY_CURRENCY_STORAGE_KEY } from './servicesCurrency';
import { getServicesState, saveServicesState } from '../../api/servicesState';

interface ServicesFlowState {
  selectedServices: Set<ServiceKey>;
  setSelectedServices: (next: Set<ServiceKey>) => void;
  answers: Record<string, unknown>;
  setAnswers: (next: Record<string, unknown> | ((prev: Record<string, unknown>) => Record<string, unknown>)) => void;
  recommendations: Record<string, RecommendationResponse> | null;
  setRecommendations: (next: Record<string, RecommendationResponse> | null) => void;
  shortlist: Map<string, string>;
  setShortlist: (next: Map<string, string>) => void;
  /** ISO 4217 code — used for all service-flow estimates (converted from USD baseline). */
  displayCurrency: string;
  setDisplayCurrency: (code: string) => void;
  /**
   * Per-case server persistence. Pages call setActiveCaseId(assignmentId) on
   * mount so the context can pull saved state and debounce-save changes back.
   * Pass null to fall back to localStorage-only mode.
   */
  setActiveCaseId: (caseId: string | null) => void;
  /** True while the initial server fetch is in-flight; pages can render shells. */
  remoteStateLoading: boolean;
}

const ServicesFlowContext = createContext<ServicesFlowState | null>(null);

const SAVE_DEBOUNCE_MS = 700;

export const ServicesFlowProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [selectedServices, setSelectedServices] = useState<Set<ServiceKey>>(() => {
    try {
      const raw = localStorage.getItem('services_selected');
      return raw ? new Set(JSON.parse(raw)) : new Set();
    } catch {
      return new Set();
    }
  });
  const [answers, setAnswers] = useState<Record<string, unknown>>(() => {
    try {
      const raw = localStorage.getItem('services_answers');
      return raw ? JSON.parse(raw) : {};
    } catch {
      return {};
    }
  });
  const [recommendations, setRecommendations] = useState<Record<string, RecommendationResponse> | null>(() => {
    try {
      const raw = localStorage.getItem('services_recommendations');
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });
  const [shortlist, setShortlist] = useState<Map<string, string>>(() => {
    try {
      const raw = localStorage.getItem('services_shortlist');
      return raw ? new Map(JSON.parse(raw)) : new Map();
    } catch {
      return new Map();
    }
  });
  const [displayCurrency, setDisplayCurrencyState] = useState<string>(() => {
    try {
      const raw = localStorage.getItem(SERVICES_DISPLAY_CURRENCY_STORAGE_KEY);
      return normalizeServicesCurrency(raw || 'USD');
    } catch {
      return 'USD';
    }
  });

  const setDisplayCurrency = useCallback((code: string) => {
    const next = normalizeServicesCurrency(code);
    setDisplayCurrencyState(next);
    try {
      localStorage.setItem(SERVICES_DISPLAY_CURRENCY_STORAGE_KEY, next);
    } catch {
      // ignore
    }
  }, []);

  // ---------------------------------------------------------------------------
  // Per-case server sync
  //
  // Pages set the active case id; we fetch saved state once and replace the
  // in-memory state. Subsequent local changes are debounced-saved back. While
  // the fetch is in-flight we suppress saves so we don't race the seed call.
  // ---------------------------------------------------------------------------
  const [activeCaseId, setActiveCaseId] = useState<string | null>(null);
  const [remoteStateLoading, setRemoteStateLoading] = useState(false);
  const suppressSaveRef = useRef(true);
  const lastFetchedCaseRef = useRef<string | null>(null);

  useEffect(() => {
    if (!activeCaseId) {
      // No case context — keep localStorage-only behavior.
      suppressSaveRef.current = true;
      return;
    }
    if (lastFetchedCaseRef.current === activeCaseId) return;
    let cancelled = false;
    suppressSaveRef.current = true;
    setRemoteStateLoading(true);
    getServicesState(activeCaseId)
      .then((row) => {
        if (cancelled) return;
        if (row?.state) {
          const s = row.state;
          if (Array.isArray(s.selectedServices)) {
            setSelectedServices(new Set(s.selectedServices as ServiceKey[]));
          }
          if (s.answers && typeof s.answers === 'object') {
            setAnswers(s.answers as Record<string, unknown>);
          }
          if (s.recommendations !== undefined) {
            setRecommendations(
              s.recommendations as Record<string, RecommendationResponse> | null,
            );
          }
          if (Array.isArray(s.shortlist)) {
            setShortlist(new Map(s.shortlist as [string, string][]));
          }
          if (typeof s.displayCurrency === 'string') {
            setDisplayCurrency(s.displayCurrency);
          }
        }
      })
      .catch(() => {
        // Non-fatal: keep whatever is in localStorage.
      })
      .finally(() => {
        if (cancelled) return;
        lastFetchedCaseRef.current = activeCaseId;
        setRemoteStateLoading(false);
        // Allow saves on the next tick so the state setters above don't
        // immediately echo a save back to the server.
        setTimeout(() => {
          suppressSaveRef.current = false;
        }, 0);
      });
    return () => {
      cancelled = true;
    };
  }, [activeCaseId, setDisplayCurrency]);

  // Debounced save whenever any persisted slice changes.
  useEffect(() => {
    if (!activeCaseId) return;
    if (suppressSaveRef.current) return;
    const handle = setTimeout(() => {
      const blob = {
        selectedServices: Array.from(selectedServices),
        answers,
        recommendations,
        shortlist: Array.from(shortlist.entries()),
        displayCurrency,
      };
      void saveServicesState(activeCaseId, blob).catch(() => {
        // Non-fatal: localStorage still has the state.
      });
    }, SAVE_DEBOUNCE_MS);
    return () => clearTimeout(handle);
  }, [activeCaseId, selectedServices, answers, recommendations, shortlist, displayCurrency]);

  // localStorage mirrors stay in place as a fallback for unauthenticated /
  // no-case scenarios (and as a fast warm-cache before the server fetch).
  useEffect(() => {
    try {
      localStorage.setItem('services_selected', JSON.stringify(Array.from(selectedServices)));
    } catch {
      // ignore persistence failures
    }
  }, [selectedServices]);

  useEffect(() => {
    try {
      localStorage.setItem('services_answers', JSON.stringify(answers));
    } catch {
      // ignore
    }
  }, [answers]);

  useEffect(() => {
    try {
      localStorage.setItem('services_recommendations', JSON.stringify(recommendations));
    } catch {
      // ignore
    }
  }, [recommendations]);

  useEffect(() => {
    try {
      localStorage.setItem('services_shortlist', JSON.stringify(Array.from(shortlist.entries())));
    } catch {
      // ignore
    }
  }, [shortlist]);

  const value = useMemo(
    () => ({
      selectedServices,
      setSelectedServices,
      answers,
      setAnswers,
      recommendations,
      setRecommendations,
      shortlist,
      setShortlist,
      displayCurrency,
      setDisplayCurrency,
      setActiveCaseId,
      remoteStateLoading,
    }),
    [
      selectedServices,
      answers,
      recommendations,
      shortlist,
      displayCurrency,
      setDisplayCurrency,
      remoteStateLoading,
    ],
  );

  return (
    <ServicesFlowContext.Provider value={value}>
      {children}
    </ServicesFlowContext.Provider>
  );
};

export const useServicesFlow = () => {
  const ctx = useContext(ServicesFlowContext);
  if (!ctx) {
    throw new Error('useServicesFlow must be used within ServicesFlowProvider');
  }
  return ctx;
};
