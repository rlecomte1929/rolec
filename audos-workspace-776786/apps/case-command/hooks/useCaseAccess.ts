/**
 * useCaseAccess — access-tier state for a ReloPass Case Command case, plus
 * the fetch helpers for the three customer-facing relopass server hooks.
 *
 * All payment truth lives SERVER-SIDE in the Audos workspace hooks:
 *   - case creation → POST /api/workspaces/776786/hooks/relopass-create-case/execute
 *   - checkout      → POST /api/workspaces/776786/hooks/relopass-checkout/execute
 *   - access check  → GET  /api/workspaces/776786/hooks/relopass-access/execute?caseId=<id>
 *
 * This hook never flips access client-side — after the Stripe redirect the
 * caller simply re-reads (polls) the server state until it reports paid.
 */

import { useState, useEffect, useCallback } from 'react';

const HOOK_BASE = '/api/workspaces/776786/hooks';

export interface CaseAccess {
  caseId: number;
  accessTier: string;
  paymentStatus: string;
  accountTier: string | null;
  availableAddons: string[];
  employeeType?: string | null;
  moveDate?: string | null;
  unlockedAt?: string | null;
}

export interface CreateCaseInput {
  corridor: string;
  employeeType: string;
  moveDate: string;
  sessionId?: string | null;
}

/** POST relopass-create-case → { caseId } */
export async function createCase(input: CreateCaseInput): Promise<number | null> {
  try {
    const res = await fetch(`${HOOK_BASE}/relopass-create-case/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return typeof data?.caseId === 'number' ? data.caseId : null;
  } catch {
    return null;
  }
}

/** GET relopass-access?caseId=<id> → CaseAccess */
export async function fetchCaseAccess(caseId: number): Promise<CaseAccess | null> {
  try {
    const res = await fetch(`${HOOK_BASE}/relopass-access/execute?caseId=${encodeURIComponent(caseId)}`);
    if (!res.ok) return null;
    const data = await res.json();
    return typeof data?.caseId === 'number' ? (data as CaseAccess) : null;
  } catch {
    return null;
  }
}

/** POST relopass-checkout { caseId, tier } → { checkoutUrl, sessionId } */
export async function startCheckout(
  caseId: number,
  tier: 'roadmap' | 'essentials',
  successUrl: string,
  cancelUrl: string,
): Promise<{ checkoutUrl: string; sessionId: string } | null> {
  try {
    const res = await fetch(`${HOOK_BASE}/relopass-checkout/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ caseId, tier, successUrl, cancelUrl }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return typeof data?.checkoutUrl === 'string'
      ? { checkoutUrl: data.checkoutUrl, sessionId: data.sessionId }
      : null;
  } catch {
    return null;
  }
}

export interface UseCaseAccessResult {
  access: CaseAccess | null;
  loading: boolean;
  error: boolean;
  refetch: () => Promise<CaseAccess | null>;
}

/** Loads (and re-loads on demand) the access state for a known caseId. */
export function useCaseAccess(caseId: number | null): UseCaseAccessResult {
  const [access, setAccess] = useState<CaseAccess | null>(null);
  const [loading, setLoading] = useState<boolean>(Boolean(caseId));
  const [error, setError] = useState(false);

  const refetch = useCallback(async () => {
    if (!caseId) return null;
    const state = await fetchCaseAccess(caseId);
    if (state) {
      setAccess(state);
      setError(false);
    } else {
      setError(true);
    }
    setLoading(false);
    return state;
  }, [caseId]);

  useEffect(() => {
    if (!caseId) {
      setAccess(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setAccess(null);
    refetch();
  }, [caseId, refetch]);

  return { access, loading, error, refetch };
}
