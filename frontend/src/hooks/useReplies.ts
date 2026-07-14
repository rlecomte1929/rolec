import { useState, useCallback } from 'react';
import { supabase } from '../api/supabase';
import type { ProspectReply, ReplyInsert } from '../types/outreach';

export interface UseRepliesResult {
  logReply: (data: ReplyInsert) => Promise<ProspectReply>;
  getRepliesForProspect: (prospectId: string) => Promise<ProspectReply[]>;
  loading: boolean;
  error: string | null;
}

export function useReplies(): UseRepliesResult {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const logReply = useCallback(async (data: ReplyInsert): Promise<ProspectReply> => {
    setLoading(true);
    setError(null);
    const resp = await supabase
      .from('prospect_replies')
      .insert(data)
      .select()
      .single();
    setLoading(false);
    if (resp.error) { setError(resp.error.message); throw new Error(resp.error.message); }
    return resp.data as ProspectReply;
  }, []);

  const getRepliesForProspect = useCallback(async (prospectId: string): Promise<ProspectReply[]> => {
    setLoading(true);
    setError(null);
    const resp = await supabase
      .from('prospect_replies')
      .select('*')
      .eq('prospect_id', prospectId)
      .order('replied_at', { ascending: false });
    setLoading(false);
    if (resp.error) { setError(resp.error.message); throw new Error(resp.error.message); }
    return (resp.data as ProspectReply[]) ?? [];
  }, []);

  return { logReply, getRepliesForProspect, loading, error };
}
