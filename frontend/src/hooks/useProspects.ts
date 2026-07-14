import { useState, useEffect, useCallback } from 'react';
import { supabase } from '../api/supabase';
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
    const { data, error: err } = await supabase
      .from('linkedin_prospects')
      .select('*')
      .order('created_at', { ascending: false });
    if (err) {
      setError(err.message);
    } else {
      setProspects((data as LinkedInProspect[]) ?? []);
    }
    setLoading(false);
  }, []);

  useEffect(() => { void fetch(); }, [fetch]);

  const createProspect = useCallback(async (data: ProspectInsert): Promise<LinkedInProspect> => {
    const resp = await supabase
      .from('linkedin_prospects')
      .insert(data)
      .select()
      .single();
    if (resp.error) throw new Error(resp.error.message);
    const prospect = resp.data as LinkedInProspect;
    setProspects((prev) => [prospect, ...prev]);
    return prospect;
  }, []);

  const updateProspect = useCallback(async (id: string, patch: Partial<LinkedInProspect>): Promise<void> => {
    const { error: err } = await supabase
      .from('linkedin_prospects')
      .update(patch)
      .eq('id', id);
    if (err) throw new Error(err.message);
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
    const { error: err } = await supabase
      .from('linkedin_prospects')
      .delete()
      .eq('id', id);
    if (err) throw new Error(err.message);
    setProspects((prev) => prev.filter((p) => p.id !== id));
  }, []);

  return { prospects, loading, error, refresh: fetch, createProspect, updateProspect, updateStatus, deleteProspect };
}
