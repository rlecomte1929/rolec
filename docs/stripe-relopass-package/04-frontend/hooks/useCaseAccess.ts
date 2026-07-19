// hooks/useCaseAccess.ts
// ReloPass — Stripe Integration v1.0
//
// Read-only mirror of the server-side access state for one case.
// NEVER writes access state — the webhook is the only writer.

import { useState, useEffect, useCallback, useRef } from 'react';

export interface CaseAccess {
  caseId: string;
  accessTier: 'free' | 'roadmap' | 'essentials';
  paymentStatus: 'unpaid' | 'roadmap_paid' | 'essentials_paid';
  accountTier: 'starter' | 'growth' | null;
  availableAddons: string[];
}

export interface UseCaseAccessResult {
  access: CaseAccess | null;
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
  /** True when the case is unlocked, either per-case or via a retainer account. */
  hasFullAccess: boolean;
}

/** Delay before the post-payment refetch — gives the webhook time to land. */
const PAYMENT_SUCCESS_REFETCH_MS = 1500;

export function useCaseAccess(caseId: string | null): UseCaseAccessResult {
  const [access, setAccess] = useState<CaseAccess | null>(null);
  const [loading, setLoading] = useState(!!caseId);
  const [error, setError] = useState<Error | null>(null);
  const paymentParamHandledRef = useRef(false);

  const refetch = useCallback(async () => {
    if (!caseId) return;
    try {
      const res = await fetch(`/api/relopass/cases/${encodeURIComponent(caseId)}/access`, {
        credentials: 'include',
      });
      if (!res.ok) throw new Error(`access fetch failed: ${res.status}`);
      const data = (await res.json()) as CaseAccess;
      setAccess(data);
      setError(null);
    } catch (err) {
      setError(err as Error);
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  // Initial load (and whenever the case changes).
  useEffect(() => {
    setAccess(null);
    setError(null);
    if (!caseId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    refetch();
  }, [caseId, refetch]);

  // Returning from Stripe: ?payment=success. The webhook usually lands
  // within a second — refetch after a short delay, then strip the param so
  // reloads/bookmarks don't re-trigger this path.
  useEffect(() => {
    if (!caseId || paymentParamHandledRef.current) return;
    const params = new URLSearchParams(window.location.search);
    if (params.get('payment') !== 'success') return;
    paymentParamHandledRef.current = true;

    const timer = setTimeout(() => {
      refetch();
      const url = new URL(window.location.href);
      url.searchParams.delete('payment');
      window.history.replaceState({}, '', url.toString());
    }, PAYMENT_SUCCESS_REFETCH_MS);

    return () => clearTimeout(timer);
  }, [caseId, refetch]);

  const hasFullAccess =
    !!access &&
    (access.accessTier !== 'free' ||
      access.accountTier === 'starter' ||
      access.accountTier === 'growth');

  return { access, loading, error, refetch, hasFullAccess };
}

export default useCaseAccess;
