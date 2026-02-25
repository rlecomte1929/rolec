/**
 * Message state / notification bell API.
 * Delivered, Unread, Read states for platform messages.
 */

import api from './client';

export interface MessageNotificationItem {
  message_id: string;
  conversation_id: string;
  sender_name: string;
  snippet: string;
  created_at: string;
}

export async function getUnreadMessageCount(): Promise<number> {
  const res = await api.get<{ count: number }>('/api/messages/unread-count');
  return res.data?.count ?? 0;
}

export async function listUnreadMessageNotifications(limit = 20): Promise<MessageNotificationItem[]> {
  const res = await api.get<{ notifications: MessageNotificationItem[] }>(
    '/api/messages/unread-list',
    { params: { limit } }
  );
  return res.data?.notifications ?? [];
}

export async function markConversationRead(assignmentId: string): Promise<void> {
  await api.post('/api/messages/mark-conversation-read', {
    assignment_id: assignmentId,
    conversation_id: assignmentId,
  });
}

export async function dismissMessageNotification(messageId: string): Promise<void> {
  await api.post(`/api/messages/dismiss/${messageId}`);
}
