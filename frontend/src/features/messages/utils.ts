/**
 * Transform flat API messages into Conversation structure.
 * Compatible with existing schema: id, assignment_id, hr_user_id, employee_identifier, subject, body, status, created_at.
 */

import type { Message, Conversation } from './types';

/** Map API conversation summary row to a lightweight Conversation (messages loaded later). */
export function conversationFromSummary(row: Record<string, unknown>): Conversation {
  const assignmentId = String(row.assignment_id ?? '');
  return {
    id: `conv-${assignmentId}`,
    assignment_id: assignmentId,
    other_participant_name: String(row.employee_name ?? 'Employee'),
    last_message_preview: String(row.last_message_preview ?? ''),
    last_message_at: String(row.last_message_at ?? new Date().toISOString()),
    unread_count: typeof row.unread_count === 'number' ? row.unread_count : Number(row.unread_count) || 0,
    messages: [],
    thread_loaded: false,
    case_id: (row.case_id as string) ?? null,
    participant_email: (row.employee_email as string) ?? null,
    archived_at: (row.archived_at as string) ?? null,
  };
}

function truncate(str: string, max: number): string {
  if (!str) return '';
  const content = str.replace(/\n/g, ' ').trim();
  return content.length <= max ? content : content.slice(0, max).trimEnd() + '…';
}

/**
 * Build conversation list from flat messages.
 * @param rawMessages - Array from API (subject, body, hr_user_id, employee_identifier, etc.)
 * @param currentUserId - Current user's ID (from profile)
 * @param currentUserRole - 'HR' | 'EMPLOYEE' | 'ADMIN'
 * @param currentUserName - Display name for "from me" labels
 */
export function buildConversationsFromMessages(
  rawMessages: Record<string, unknown>[],
  currentUserId: string,
  currentUserRole: string,
  currentUserName: string
): Conversation[] {
  const byAssignment = new Map<string, Message[]>();

  for (const raw of rawMessages) {
    const msg: Message = {
      id: String(raw.id),
      assignment_id: raw.assignment_id as string | undefined,
      hr_user_id: raw.hr_user_id as string | undefined,
      employee_identifier: raw.employee_identifier as string | undefined,
      subject: raw.subject as string | undefined,
      body: (raw.body as string) || '',
      status: raw.status as string | undefined,
      created_at: raw.created_at as string,
      delivered_at: (raw.delivered_at as string) || undefined,
      read_at: (raw.read_at as string) || undefined,
    };

    const assignmentId = msg.assignment_id || 'unknown';
    const isFromMe = currentUserRole === 'HR' || currentUserRole === 'ADMIN'
      ? !!msg.hr_user_id && msg.hr_user_id === currentUserId
      : false;
    const isFromHr = !!msg.hr_user_id;

    msg.sender_role = isFromHr ? 'HR' : 'EMPLOYEE';
    msg.sender_name = isFromMe ? currentUserName : (isFromHr ? 'HR' : (msg.employee_identifier || 'Employee'));
    msg.is_from_me = isFromMe;

    if (!byAssignment.has(assignmentId)) {
      byAssignment.set(assignmentId, []);
    }
    byAssignment.get(assignmentId)!.push(msg);
  }

  const conversations: Conversation[] = [];
  for (const [assignmentId, messages] of byAssignment) {
    const sorted = [...messages].sort(
      (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    );
    // Set delivery status only on the last outgoing message
    const lastFromMe = [...sorted].reverse().find((m) => m.is_from_me);
    if (lastFromMe) {
      lastFromMe.status_delivery = lastFromMe.read_at
        ? 'read'
        : lastFromMe.delivered_at
          ? 'delivered'
          : 'sent';
    }
    const last = sorted[sorted.length - 1];
    const otherName = currentUserRole === 'HR' || currentUserRole === 'ADMIN'
      ? (last?.employee_identifier || 'Employee')
      : 'HR';

    conversations.push({
      id: `conv-${assignmentId}`,
      assignment_id: assignmentId,
      other_participant_name: otherName,
      last_message_preview: truncate(last?.body || last?.subject || '', 60),
      last_message_at: last?.created_at || new Date().toISOString(),
      unread_count: 0,
      messages: sorted,
    });
  }

  conversations.sort((a, b) =>
    new Date(b.last_message_at).getTime() - new Date(a.last_message_at).getTime()
  );
  return conversations;
}
