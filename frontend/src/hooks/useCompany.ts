import { useState, useEffect } from 'react';
import { companyAPI } from '../api/client';
import { getAuthItem } from '../utils/demo';
import type { Company } from '../types';

export interface UseCompanyResult {
  company: Company | null;
  loading: boolean;
  refresh: () => Promise<void>;
}

export interface UseCompanyOptions {
  /** When true, skip fetch (e.g. when HR context supplies company on HR routes). */
  skip?: boolean;
}

export function useCompany(opts?: UseCompanyOptions): UseCompanyResult {
  const [company, setCompany] = useState<Company | null>(null);
  const [loading, setLoading] = useState(!opts?.skip);

  const fetchCompany = async () => {
    if (opts?.skip) {
      setLoading(false);
      return;
    }
    const token = getAuthItem('relopass_token');
    const role = getAuthItem('relopass_role');
    if (!token || (!role || (role !== 'HR' && role !== 'EMPLOYEE' && role !== 'ADMIN'))) {
      setCompany(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const res = await companyAPI.get();
      setCompany(res.company ?? null);
    } catch {
      setCompany(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCompany();
  }, [opts?.skip]);

  return { company, loading, refresh: fetchCompany };
}
