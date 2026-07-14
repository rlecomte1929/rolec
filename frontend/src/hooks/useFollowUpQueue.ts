import { useMemo } from 'react';
import type { LinkedInProspect } from '../types/outreach';

const FOLLOW_UP_DAYS = 10;

function daysSince(dateStr: string): number {
  const ms = Date.now() - new Date(dateStr).getTime();
  return Math.floor(ms / (1000 * 60 * 60 * 24));
}

export function isFollowUpDue(prospect: LinkedInProspect): boolean {
  if (prospect.status !== 'message_sent') return false;
  if (!prospect.message_sent_at) return false;
  if (prospect.follow_up_sent_at) return false;
  return daysSince(prospect.message_sent_at) >= FOLLOW_UP_DAYS;
}

export function daysSinceSent(prospect: LinkedInProspect): number | null {
  if (!prospect.message_sent_at) return null;
  return daysSince(prospect.message_sent_at);
}

export function useFollowUpQueue(prospects: LinkedInProspect[]): LinkedInProspect[] {
  return useMemo(() => prospects.filter(isFollowUpDue), [prospects]);
}
