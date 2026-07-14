export type ProspectStatus =
  | 'flagged'
  | 'message_drafted'
  | 'message_sent'
  | 'replied'
  | 'follow_up_sent'
  | 'converted'
  | 'not_interested'
  | 'archived';

export type MessageType = 'initial' | 'follow_up' | 'reply_response';
export type MessageStatus = 'draft' | 'approved' | 'sent' | 'archived';
export type Sentiment = 'positive' | 'neutral' | 'negative' | 'not_set';

export interface LinkedInProspect {
  id: string;
  created_at: string;
  updated_at: string;
  full_name: string;
  linkedin_url: string;
  profile_headline: string | null;
  company_name: string;
  company_size: string | null;
  job_title: string;
  corridor_relevance: string | null;
  notes: string | null;
  source: string;
  status: ProspectStatus;
  message_sent_at: string | null;
  last_reply_at: string | null;
  follow_up_sent_at: string | null;
  converted_at: string | null;
}

export type ProspectInsert = Omit<LinkedInProspect, 'id' | 'created_at' | 'updated_at'>;

export interface OutreachMessage {
  id: string;
  created_at: string;
  updated_at: string;
  prospect_id: string;
  message_type: MessageType;
  subject_line: string | null;
  body: string;
  personalisation_notes: string | null;
  status: MessageStatus;
  approved_at: string | null;
  sent_at: string | null;
  copied_to_clipboard_at: string | null;
}

export type MessageInsert = Omit<OutreachMessage, 'id' | 'created_at' | 'updated_at'>;

export interface ProspectReply {
  id: string;
  created_at: string;
  prospect_id: string;
  reply_text: string | null;
  replied_at: string;
  sentiment: Sentiment;
  next_action: string | null;
  next_action_due: string | null;
  outreach_message_id: string | null;
}

export type ReplyInsert = Omit<ProspectReply, 'id' | 'created_at'>;

export interface MessageTemplate {
  id: string;
  created_at: string;
  updated_at: string;
  name: string;
  message_type: MessageType;
  body_template: string;
  is_active: boolean;
}

export type TemplateInsert = Omit<MessageTemplate, 'id' | 'created_at' | 'updated_at'>;
