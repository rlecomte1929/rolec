import { useState, useEffect, useCallback } from 'react';
import {
  listProspects,
  createProspect as createProspectApi,
  updateProspectApi,
  deleteProspectApi,
} from '../api/outreach';
import type { LinkedInProspect, ProspectInsert, ProspectStatus } from '../types/outreach';

export interface UseProspectsResult {
  prospects: LinkedInProspect[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  createProspect: (data: ProspectInsert) => Promise<LinkedInProspect>;
  updateProspect: (id: string, patch: Partial<LinkedInProspect>) => Promise<void>;
  updateStatus: (id: string, status: ProspectStatus, extra?: Partial<LinkedInProspect>) => Promise<void>;
  deleteProspect: (id: string) => Promise<void>;
}

export function useProspects(): UseProspectsResult {
  const [prospects, setProspects] = useState<LinkedInProspect[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listProspects();
      setProspects(data ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load prospects');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void fetch(); }, [fetch]);

  const createProspect = useCallback(async (data: ProspectInsert): Promise<LinkedInProspect> => {
    const prospect = await createProspectApi(data);
    setProspects((prev) => [prospect, ...prev]);
    return prospect;
  }, []);

  const updateProspect = useCallback(async (id: string, patch: Partial<LinkedInProspect>): Promise<void> => {
    await updateProspectApi(id, patch);
    setProspects((prev) => prev.map((p) => (p.id === id ? { ...p, ...patch } : p)));
  }, []);

  const updateStatus = useCallback(async (
    id: string,
    status: ProspectStatus,
    extra?: Partial<LinkedInProspect>
  ): Promise<void> => {
    return updateProspect(id, { status, ...extra });
  }, [updateProspect]);

  const deleteProspect = useCallback(async (id: string): Promise<void> => {
    await deleteProspectApi(id);
    setProspects((prev) => prev.filter((p) => p.id !== id));
  }, []);

  return { prospects, loading, error, refresh: fetch, createProspect, updateProspect, updateStatus, deleteProspect };
}
