import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { adminAPI } from '../../api/client';
import { getAuthItem } from '../../utils/demo';
import type { AdminCompany } from '../../types';

/**
 * AdminViewingCompanyContext — the company an admin operator is "viewing as".
 *
 * The admin sidebar exposes this as a dropdown switcher; tenant-scoped admin
 * pages can `useAdminViewingCompany()` to filter their data by the selected
 * company id. Selection is persisted to localStorage so it survives reloads,
 * and defaults to the first company in the list on first paint.
 *
 * Distinct from HrCompanyContext, which is the HR user's own company (read
 * from /api/hr/company-profile and not switchable). This context is admin-only
 * and is mounted under the existing RequireAdminRoute layer.
 */

const STORAGE_KEY = 'admin_selected_company_id';

interface AdminViewingCompanyValue {
  companies: AdminCompany[];
  selectedCompanyId: string | null;
  selectedCompany: AdminCompany | null;
  loading: boolean;
  error: string | null;
  setSelectedCompanyId: (id: string | null) => void;
  refresh: () => Promise<void>;
}

const AdminViewingCompanyContext = createContext<AdminViewingCompanyValue>({
  companies: [],
  selectedCompanyId: null,
  selectedCompany: null,
  loading: false,
  error: null,
  setSelectedCompanyId: () => {},
  refresh: async () => {},
});

function readStored(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeStored(value: string | null): void {
  if (typeof window === 'undefined') return;
  try {
    if (value === null) window.localStorage.removeItem(STORAGE_KEY);
    else window.localStorage.setItem(STORAGE_KEY, value);
  } catch {
    /* ignore */
  }
}

interface ProviderProps {
  children: ReactNode;
}

export function AdminViewingCompanyProvider({ children }: ProviderProps) {
  const [companies, setCompanies] = useState<AdminCompany[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCompanyId, setSelectedCompanyIdState] = useState<string | null>(() => readStored());

  const refresh = useCallback(async () => {
    // This provider wraps the whole app but the company list is an admin-only
    // surface. Non-admin sessions (employee/HR) would get a 403 — a wasted
    // request + console error on every page. Skip the call entirely for them.
    const role = (getAuthItem('relopass_role') || '').toUpperCase();
    if (role !== 'ADMIN') {
      setCompanies([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await adminAPI.listCompanies();
      setCompanies(res.companies ?? []);
    } catch (e) {
      // 403/404 are expected for non-admin sessions; treat as empty list.
      const status = (e as { response?: { status?: number } })?.response?.status;
      if (status === 403 || status === 404) {
        setCompanies([]);
      } else {
        setError((e as Error)?.message ?? 'Failed to load companies');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // When the company list arrives, pick a default if nothing was stored or
  // if the stored id no longer exists in the list (e.g. company was deleted).
  useEffect(() => {
    if (companies.length === 0) return;
    const storedExists = selectedCompanyId && companies.some((c) => c.id === selectedCompanyId);
    if (!storedExists) {
      const first = companies[0];
      if (first) {
        setSelectedCompanyIdState(first.id);
        writeStored(first.id);
      }
    }
  }, [companies, selectedCompanyId]);

  const setSelectedCompanyId = useCallback((id: string | null) => {
    setSelectedCompanyIdState(id);
    writeStored(id);
  }, []);

  const selectedCompany = useMemo(
    () => companies.find((c) => c.id === selectedCompanyId) ?? null,
    [companies, selectedCompanyId],
  );

  const value: AdminViewingCompanyValue = useMemo(
    () => ({
      companies,
      selectedCompanyId,
      selectedCompany,
      loading,
      error,
      setSelectedCompanyId,
      refresh,
    }),
    [companies, selectedCompanyId, selectedCompany, loading, error, setSelectedCompanyId, refresh],
  );

  return <AdminViewingCompanyContext.Provider value={value}>{children}</AdminViewingCompanyContext.Provider>;
}

export function useAdminViewingCompany(): AdminViewingCompanyValue {
  return useContext(AdminViewingCompanyContext);
}
