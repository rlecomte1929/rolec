import { useState, useEffect } from 'react';
import { companyAPI } from '../api/client';
import { getAuthItem } from '../utils/demo';
import type { Company } from '../types';

export interface UseCompanyResult {
  company: Company | null;
  loading: boolean;
  refresh: () => Promise<void>;
}

export function useCompany(): UseCompanyResult {
  const [company, setCompany] = useState<Company | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchCompany = async () => {
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
  }, []);

  return { company, loading, refresh: fetchCompany };
}
