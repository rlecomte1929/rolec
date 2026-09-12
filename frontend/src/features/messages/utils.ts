/**
 * Transform flat API messages into Conversation structure.
 * Compatible with existing schema: id, assignment_id, hr_user_id, employee_identifier, subject, body, status, created_at.
 */

import { getCountryName } from '../../utils/countries';
import type { Message, Conversation } from './types';

function destinationSubtitle(row: Record<string, unknown>): string | null {
  const host = typeof row.host_country === 'string' ? row.host_country.trim() : '';
  if (host) return getCountryName(host) || host;
  const caseId = typeof row.case_id === 'string' ? row.case_id.trim() : '';
  return caseId ? `Case ${caseId.slice(-8).toUpperCase()}` : null;
}

/** Map API conversation summary row to a lightweight Conversation (messages loaded later). */
export function conversationFromSummary(row: Record<string, unknown>): Conversation {
  const assignmentId = (row.assignment_id as string | null | undefined) ?? '';
  return {
    id: `conv-${assignmentId}`,
    assignment_id: assignmentId,
    other_participant_name: (row.employee_name as string | null | undefined) ?? 'Employee',
    last_message_preview: (row.last_message_preview as string | null | undefined) ?? '',
    last_message_at: (row.last_message_at as string | null | undefined) ?? new Date().toISOString(),
    unread_count: typeof row.unread_count === 'number' ? row.unread_count : Number(row.unread_count) || 0,
    messages: [],
    thread_loaded: false,
    case_id: (row.case_id as string | null | undefined) ?? null,
    list_subtitle: destinationSubtitle(row),
    participant_email: (row.employee_email as string | null | undefined) ?? null,
    archived_at: (row.archived_at as string | null | undefined) ?? null,
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
      sender_user_id: raw.sender_user_id as string | undefined,
      employee_identifier: raw.employee_identifier as string | undefined,
      subject: raw.subject as string | undefined,
      body: (raw.body as string) || '',
      status: raw.status as string | undefined,
      created_at: raw.created_at as string,
      delivered_at: (raw.delivered_at as string) || undefined,
      read_at: (raw.read_at as string) || undefined,
    };

    const assignmentId = msg.assignment_id || 'unknown';
    const senderUid = msg.sender_user_id || msg.hr_user_id;
    const isFromMe = currentUserRole === 'HR' || currentUserRole === 'ADMIN'
      ? !!senderUid && senderUid === currentUserId
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
      channel: currentUserRole === 'EMPLOYEE' ? 'hr' : undefined,
      other_participant_name: otherName,
      last_message_preview: truncate(last?.body || last?.subject || '', 60),
      last_message_at: last?.created_at || new Date().toISOString(),
      unread_count: 0,
      messages: sorted,
      thread_loaded: true,
    });
  }

  conversations.sort((a, b) =>
    new Date(b.last_message_at).getTime() - new Date(a.last_message_at).getTime()
  );
  return conversations;
}

/** Map RFQ / vendor quote_threads from GET /api/employee/messages into Conversation rows. */
export function buildConversationsFromQuoteThreads(
  rawThreads: Record<string, unknown>[],
  currentUserId: string,
  currentUserName: string,
  assignmentLabels?: Map<string, string>
): Conversation[] {
  const out: Conversation[] = [];
  for (const t of rawThreads) {
    const conversationId = (t.conversation_id as string | null | undefined) ?? '';
    const assignmentId = (t.assignment_id as string | null | undefined) ?? '';
    if (!conversationId || !assignmentId) continue;
    const label = (t.counterparty_label as string | null | undefined) ?? 'Service provider';
    const rawMsgs = (t.messages as Record<string, unknown>[]) || [];
    const messages: Message[] = rawMsgs.map((raw) => {
      const sid = (raw.sender_user_id as string | null | undefined) ?? '';
      const isFromMe = Boolean(currentUserId) && sid === currentUserId;
      return {
        id: String(raw.id),
        body: (raw.body as string | null | undefined) ?? '',
        created_at: (raw.created_at as string | null | undefined) ?? '',
        sender_user_id: sid || undefined,
        sender_role: isFromMe ? 'EMPLOYEE' : 'SUPPLIER',
        sender_name: isFromMe ? currentUserName : label,
        is_from_me: isFromMe,
      };
    });
    const last = messages[messages.length - 1];
    const rfqRef = t.rfq_ref != null ? (t.rfq_ref as string | null | undefined) ?? '' : '';
    out.push({
      id: `qconv-${conversationId}`,
      assignment_id: assignmentId,
      channel: 'supplier',
      supplier_conversation_id: conversationId,
      list_subtitle: assignmentLabels?.get(assignmentId) || rfqRef || null,
      other_participant_name: label,
      other_participant_avatar: label.slice(0, 2).toUpperCase(),
      last_message_preview: truncate(last?.body ?? '', 60),
      last_message_at: last?.created_at || ((t.created_at as string | null | undefined) ?? new Date().toISOString()),
      unread_count: 0,
      messages,
      thread_loaded: true,
    });
  }
  out.sort(
    (a, b) => new Date(b.last_message_at).getTime() - new Date(a.last_message_at).getTime()
  );
  return out;
}
