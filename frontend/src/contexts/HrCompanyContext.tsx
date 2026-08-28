/**
 * Canonical HR company context. Resolves company_id and company profile once per session,
 * shared across HR pages. Prevents duplicate fetches and re-discovery of company.
 */
import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { hrAPI } from '../api/client';
import { safeNavigate } from '../navigation/safeNavigate';
import { invalidateApiCache } from '../api/client';
import { getAuthItem } from '../utils/demo';
import { trackRequestStart, trackRequestEnd } from '../perf/pagePerf';

export interface HrCompanyContextValue {
  companyId: string | null;
  company: Record<string, unknown> | null;
  loading: boolean;
  error: string | null;
  /** Refetch company profile. Call after save/upload. */
  refresh: () => Promise<void>;
  /**
   * Seed the context from a mutation's own response, so a save does not have to
   * re-read what it just wrote. Falls back to refresh() when the server did not
   * return the row (older backend) — see CompanyProfileV2Page.handleSave.
   */
  applyCompany: (company: Record<string, unknown>) => void;
}

const defaultValue: HrCompanyContextValue = {
  companyId: null,
  company: null,
  loading: false,
  error: null,
  refresh: async () => {},
  applyCompany: () => {},
};

const HrCompanyContext = createContext<HrCompanyContextValue>(defaultValue);

function isHrRoute(pathname: string): boolean {
  return pathname.startsWith('/hr');
}

function shouldFetchHrCompany(role: string | null, pathname: string): boolean {
  if (!role || (role !== 'HR' && role !== 'ADMIN')) return false;
  if (!isHrRoute(pathname)) return false;
  return !!getAuthItem('relopass_token');
}

export const HrCompanyContextProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const pathname = location.pathname;
  const role = getAuthItem('relopass_role');

  const [companyId, setCompanyId] = useState<string | null>(null);
  const [company, setCompany] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchCompany = useCallback(async () => {
    if (!shouldFetchHrCompany(role, pathname)) {
      setCompany(null);
      setCompanyId(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    const reqTrack = trackRequestStart({
      requestName: 'hrCompanyContext',
      endpoint: '/api/hr/company-profile',
      route: pathname,
      caller: 'HrCompanyContextProvider',
      blockedInitialRender: false,
    });
    try {
      const res = await hrAPI.getCompanyProfile();
      const c = res?.company as Record<string, unknown> | null | undefined;
      if (c) {
        setCompany(c);
        setCompanyId((c.id as string) ?? null);
      } else {
        setCompany(null);
        setCompanyId(null);
      }
    } catch (e: unknown) {
      setCompany(null);
      setCompanyId(null);
      const err = e as { response?: { status?: number } };
      if (err?.response?.status === 401) {
        safeNavigate(navigate, 'landing');
      } else {
        setError('Company profile did not load. Refresh to try again.');
      }
    } finally {
      setLoading(false);
      trackRequestEnd({
        requestName: 'hrCompanyContext',
        endpoint: '/api/hr/company-profile',
        route: pathname,
        startTs: reqTrack.startTs,
      });
    }
  }, [role, pathname, navigate]);

  useEffect(() => {
    void fetchCompany();
  }, [fetchCompany]);

  const refresh = useCallback(async () => {
    invalidateApiCache('hr:company-profile');
    invalidateApiCache('company:get');
    await fetchCompany();
  }, [fetchCompany]);

  const applyCompany = useCallback((next: Record<string, unknown>) => {
    // The cached GET is now stale relative to what we just stored; drop it so a later
    // consumer does not read back the pre-save row from the 60s TTL.
    invalidateApiCache('hr:company-profile');
    invalidateApiCache('company:get');
    setCompany(next);
    setCompanyId((next.id as string) ?? null);
  }, []);

  const value: HrCompanyContextValue = {
    companyId,
    company,
    loading,
    error,
    refresh,
    applyCompany,
  };

  return (
    <HrCompanyContext.Provider value={value}>
      {children}
    </HrCompanyContext.Provider>
  );
};

export function useHrCompanyContext(): HrCompanyContextValue {
  return useContext(HrCompanyContext);
}
