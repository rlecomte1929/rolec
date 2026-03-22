/**
 * Mock message data for testing the messaging UI.
 * Use when API returns empty or in development.
 */

import type { Conversation } from './types';

const baseDate = new Date();
const yesterday = new Date(baseDate);
yesterday.setDate(yesterday.getDate() - 1);

function iso(d: Date) {
  return d.toISOString();
}

export const MOCK_CONVERSATIONS: Conversation[] = [
  {
    id: 'conv-1',
    assignment_id: 'assign-1',
    channel: 'hr',
    thread_loaded: true,
    other_participant_name: 'Sarah Jenkins',
    other_participant_avatar: 'SJ',
    last_message_preview: 'I\'ve completed the relocation basics. Should I proceed with the family members section?',
    last_message_at: iso(baseDate),
    unread_count: 1,
    messages: [
      {
        id: 'msg-1',
        assignment_id: 'assign-1',
        hr_user_id: 'hr-1',
        employee_identifier: 'sarah.jenkins@relopass.local',
        subject: 'Your relocation case is ready',
        body: 'Hi Sarah, your relocation case has been created. Please complete the intake wizard at your earliest convenience.',
        status: 'sent',
        created_at: iso(yesterday),
        sender_role: 'HR',
        sender_name: 'HR Manager',
        is_from_me: true,
        status_delivery: 'read',
      },
      {
        id: 'msg-2',
        assignment_id: 'assign-1',
        hr_user_id: 'hr-1',
        employee_identifier: 'sarah.jenkins@relopass.local',
        subject: 'Re: Your relocation case',
        body: 'Thanks! I\'ve started the wizard. Quick question: do I need to upload documents in Step 5 or can I do that later?',
        status: 'sent',
        created_at: iso(new Date(yesterday.getTime() + 3600000)),
        sender_role: 'EMPLOYEE',
        sender_name: 'Sarah Jenkins',
        is_from_me: false,
      },
      {
        id: 'msg-3',
        assignment_id: 'assign-1',
        hr_user_id: 'hr-1',
        employee_identifier: 'sarah.jenkins@relopass.local',
        subject: 'Re: Documents',
        body: 'You can complete the documents in Step 5 after the initial profile. We\'ll review and let you know if anything is missing.',
        status: 'sent',
        created_at: iso(new Date(baseDate.getTime() - 7200000)),
        sender_role: 'HR',
        sender_name: 'HR Manager',
        is_from_me: true,
        status_delivery: 'delivered',
      },
      {
        id: 'msg-4',
        assignment_id: 'assign-1',
        hr_user_id: 'hr-1',
        employee_identifier: 'sarah.jenkins@relopass.local',
        subject: 'Re: Documents',
        body: 'I\'ve completed the relocation basics. Should I proceed with the family members section?',
        status: 'sent',
        created_at: iso(baseDate),
        sender_role: 'EMPLOYEE',
        sender_name: 'Sarah Jenkins',
        is_from_me: false,
      },
    ],
  },
  {
    id: 'conv-2',
    assignment_id: 'assign-2',
    channel: 'hr',
    thread_loaded: true,
    other_participant_name: 'Mark Thompson',
    other_participant_avatar: 'MT',
    last_message_preview: 'Your relocation case is ready for review.',
    last_message_at: iso(new Date(baseDate.getTime() - 86400000 * 2)),
    unread_count: 0,
    messages: [
      {
        id: 'msg-5',
        assignment_id: 'assign-2',
        hr_user_id: 'hr-1',
        employee_identifier: 'mark.thompson@relopass.local',
        subject: 'Your relocation case is ready',
        body: 'Hi Mark, your relocation case has been created for Singapore. Please complete the intake wizard.',
        status: 'sent',
        created_at: iso(new Date(baseDate.getTime() - 86400000 * 2)),
        sender_role: 'HR',
        sender_name: 'HR Manager',
        is_from_me: true,
        status_delivery: 'read',
      },
    ],
  },
];
