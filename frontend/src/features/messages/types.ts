/**
 * Message types for the ReloPass messaging UI.
 * Compatible with existing backend schema (id, assignment_id, hr_user_id, employee_identifier, subject, body, status, created_at).
 */

export type SenderRole = 'HR' | 'EMPLOYEE' | 'ADMIN' | 'SYSTEM' | 'SUPPLIER';

export interface Message {
  id: string;
  assignment_id?: string;
  hr_user_id?: string;
  /** When set (HR-sent via newer API), use with hr_user_id for "from me" detection */
  sender_user_id?: string;
  employee_identifier?: string;
  subject?: string;
  body: string;
  status?: string;
  created_at: string;
  delivered_at?: string | null;
  read_at?: string | null;
  /** Derived: who sent this message */
  sender_role?: SenderRole;
  /** Display name of sender */
  sender_name?: string;
  /** Current user sent this */
  is_from_me?: boolean;
  /** Delivery status: delivered (visible) | read (opened): show only on last outgoing */
  status_delivery?: 'sending' | 'sent' | 'delivered' | 'read';
}

export type MessageChannel = 'hr' | 'supplier';

export interface Conversation {
  id: string;
  assignment_id: string;
  /** HR vs quote/vendor thread (employee UI). */
  channel?: MessageChannel;
  /** quote_conversations.id when channel === 'supplier' */
  supplier_conversation_id?: string;
  /** Secondary line in list row (e.g. employer name) */
  list_subtitle?: string | null;
  /** Display name of the other participant */
  other_participant_name: string;
  /** Avatar initial or URL */
  other_participant_avatar?: string;
  /** Last message preview (truncated) */
  last_message_preview: string;
  /** ISO timestamp of last message */
  last_message_at: string;
  /** Unread count */
  unread_count?: number;
  /** Messages in this conversation */
  messages: Message[];
  /** HR summaries: full thread loaded on demand */
  thread_loaded?: boolean;
  /** Linked case id for filters / tags */
  case_id?: string | null;
  participant_email?: string | null;
  archived_at?: string | null;
}
