/**
 * Outreach message templates + drafting helpers.
 *
 * These are the hardcoded default templates for founder-managed LinkedIn
 * outreach. The founder can edit the drafted text in the UI before copying —
 * nothing is ever sent automatically (LinkedIn does not permit automated
 * sending, so this is a drafting + tracking system only).
 */

export type OutreachStatus =
  | 'prospected'
  | 'messaged'
  | 'awaiting_reply'
  | 'replied'
  | 'converted'
  | 'no_response';

export const OUTREACH_STATUSES: OutreachStatus[] = [
  'prospected',
  'messaged',
  'awaiting_reply',
  'replied',
  'converted',
  'no_response',
];

export const STATUS_LABELS: Record<OutreachStatus, string> = {
  prospected: 'Prospected',
  messaged: 'Messaged',
  awaiting_reply: 'Awaiting reply',
  replied: 'Replied',
  converted: 'Converted',
  no_response: 'No response',
};

export interface OutreachContact {
  id: number;
  full_name: string;
  company: string | null;
  job_title: string | null;
  linkedin_url: string | null;
  status: OutreachStatus;
  first_message_sent_at: string | null;
  last_activity_at: string | null;
  notes: string | null;
  follow_up_reminder_sent: boolean | null;
  reply_summary: string | null;
  next_action: string | null;
  created_at: string;
  updated_at: string;
}

/** Days between 10-day-old first message and "follow up due" flag. */
export const FOLLOW_UP_DUE_DAYS = 10;

export function firstNameOf(fullName: string): string {
  return (fullName || '').trim().split(/\s+/)[0] || 'there';
}

export function draftFirstOutreach(fullName: string, company?: string | null): string {
  const name = firstNameOf(fullName);
  const co = (company || '').trim() || 'your company';
  return `Hi ${name}, I'm building ReloPass — a relocation operating layer specifically for HR generalists at companies like ${co} who are managing international employee moves without a specialist team. We've started with the 5 corridors, and the core product flags the non-obvious requirements before they become missed deadlines. Would love to get 15 minutes with you to understand whether this is something you've run into.
Happy to work around your schedule.`;
}

export function draftFollowUp(fullName: string, daysAgo: number | null): string {
  const name = firstNameOf(fullName);
  const when = daysAgo !== null && daysAgo > 0 ? `${daysAgo} days ago` : 'a little while back';
  return `Hi ${name}, just circling back on my note from ${when}. No pressure at all — I know timing matters. If international relocation compliance isn't a current pain point, completely understood. If it is, I'd still love a quick chat.
Either way, thanks for your time.`;
}

/** Whole days elapsed since a date string (date or timestamp). Null if unset/invalid. */
export function daysSince(dateStr: string | null | undefined): number | null {
  if (!dateStr) return null;
  const then = new Date(dateStr);
  if (isNaN(then.getTime())) return null;
  const ms = Date.now() - then.getTime();
  return Math.floor(ms / (1000 * 60 * 60 * 24));
}

/**
 * A follow-up is due when the contact was messaged, 10+ days have passed since
 * the first message, no reply has been logged, and the follow-up reminder
 * hasn't been sent yet.
 */
export function isFollowUpDue(c: OutreachContact): boolean {
  if (c.status !== 'messaged' && c.status !== 'awaiting_reply') return false;
  if (c.follow_up_reminder_sent) return false;
  const d = daysSince(c.first_message_sent_at);
  return d !== null && d >= FOLLOW_UP_DUE_DAYS;
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

export function todayISODate(): string {
  return new Date().toISOString().slice(0, 10);
}
