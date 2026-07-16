import { useCallback } from 'react';
import { listReplies, createReply } from '../api/outreach';
import type { ProspectReply, ReplyInsert } from '../types/outreach';

export interface UseRepliesResult {
  logReply: (data: ReplyInsert) => Promise<ProspectReply>;
  getRepliesForProspect: (prospectId: string) => Promise<ProspectReply[]>;
}

export function useReplies(): UseRepliesResult {
  const logReply = useCallback(async (data: ReplyInsert): Promise<ProspectReply> => {
    return createReply(data);
  }, []);

  const getRepliesForProspect = useCallback(async (prospectId: string): Promise<ProspectReply[]> => {
    return (await listReplies(prospectId)) ?? [];
  }, []);

  return { logReply, getRepliesForProspect };
}
