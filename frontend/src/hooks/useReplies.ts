import { useCallback } from 'react';
import { supabase } from '../api/supabase';
import type { ProspectReply, ReplyInsert } from '../types/outreach';

export interface UseRepliesResult {
  logReply: (data: ReplyInsert) => Promise<ProspectReply>;
  getRepliesForProspect: (prospectId: string) => Promise<ProspectReply[]>;
}

export function useReplies(): UseRepliesResult {
  const logReply = useCallback(async (data: ReplyInsert): Promise<ProspectReply> => {
    const resp = await supabase
      .from('prospect_replies')
      .insert(data)
      .select()
      .single();
    if (resp.error) throw new Error(resp.error.message);
    return resp.data as ProspectReply;
  }, []);

  const getRepliesForProspect = useCallback(async (prospectId: string): Promise<ProspectReply[]> => {
    const resp = await supabase
      .from('prospect_replies')
      .select('*')
      .eq('prospect_id', prospectId)
      .order('replied_at', { ascending: false });
    if (resp.error) throw new Error(resp.error.message);
    return (resp.data as ProspectReply[]) ?? [];
  }, []);

  return { logReply, getRepliesForProspect };
}
