import { useCallback } from 'react';
import { listMessages, createMessageApi, updateMessageApi } from '../api/outreach';
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
    // Server returns drafts newest-first; take the most recent (or null).
    const drafts = await listMessages(prospectId, 'draft');
    return drafts?.[0] ?? null;
  }, []);

  const getMessagesForProspect = useCallback(async (prospectId: string): Promise<OutreachMessage[]> => {
    return (await listMessages(prospectId)) ?? [];
  }, []);

  const createMessage = useCallback(async (payload: MessageInsert): Promise<OutreachMessage> => {
    return createMessageApi(payload);
  }, []);

  const updateMessage = useCallback(async (id: string, patch: Partial<OutreachMessage>): Promise<void> => {
    await updateMessageApi(id, patch);
  }, []);

  const markSent = useCallback((id: string): Promise<void> =>
    updateMessage(id, { status: 'sent', sent_at: new Date().toISOString() }), [updateMessage]);

  const markCopied = useCallback((id: string): Promise<void> =>
    updateMessage(id, { copied_to_clipboard_at: new Date().toISOString() }), [updateMessage]);

  return { getDraftForProspect, createMessage, updateMessage, markSent, markCopied, getMessagesForProspect };
}
