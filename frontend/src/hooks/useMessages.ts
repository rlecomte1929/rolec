import { useCallback } from 'react';
import { supabase } from '../api/supabase';
import type { OutreachMessage, MessageInsert } from '../types/outreach';

export interface UseMessagesResult {
  getDraftForProspect: (prospectId: string) => Promise<OutreachMessage | null>;
  createMessage: (data: MessageInsert) => Promise<OutreachMessage>;
  updateMessage: (id: string, patch: Partial<OutreachMessage>) => Promise<void>;
  markSent: (id: string) => Promise<void>;
  markCopied: (id: string) => Promise<void>;
  getMessagesForProspect: (prospectId: string) => Promise<OutreachMessage[]>;
}

export function useMessages(): UseMessagesResult {
  const getDraftForProspect = useCallback(async (prospectId: string): Promise<OutreachMessage | null> => {
    const resp = await supabase
      .from('outreach_messages')
      .select('*')
      .eq('prospect_id', prospectId)
      .eq('status', 'draft')
      .order('created_at', { ascending: false })
      .limit(1)
      .maybeSingle();
    if (resp.error) throw new Error(resp.error.message);
    return resp.data as OutreachMessage | null;
  }, []);

  const getMessagesForProspect = useCallback(async (prospectId: string): Promise<OutreachMessage[]> => {
    const resp = await supabase
      .from('outreach_messages')
      .select('*')
      .eq('prospect_id', prospectId)
      .order('created_at', { ascending: false });
    if (resp.error) throw new Error(resp.error.message);
    return (resp.data as OutreachMessage[]) ?? [];
  }, []);

  const createMessage = useCallback(async (payload: MessageInsert): Promise<OutreachMessage> => {
    const resp = await supabase
      .from('outreach_messages')
      .insert(payload)
      .select()
      .single();
    if (resp.error) throw new Error(resp.error.message);
    return resp.data as OutreachMessage;
  }, []);

  const updateMessage = useCallback(async (id: string, patch: Partial<OutreachMessage>): Promise<void> => {
    const resp = await supabase
      .from('outreach_messages')
      .update(patch)
      .eq('id', id);
    if (resp.error) throw new Error(resp.error.message);
  }, []);

  const markSent = useCallback((id: string): Promise<void> =>
    updateMessage(id, { status: 'sent', sent_at: new Date().toISOString() }), [updateMessage]);

  const markCopied = useCallback((id: string): Promise<void> =>
    updateMessage(id, { copied_to_clipboard_at: new Date().toISOString() }), [updateMessage]);

  return { getDraftForProspect, createMessage, updateMessage, markSent, markCopied, getMessagesForProspect };
}
