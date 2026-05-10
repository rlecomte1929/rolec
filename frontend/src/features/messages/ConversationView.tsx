import React, { useEffect, useRef } from 'react';
import { MessageBubble } from './MessageBubble';
import { DateSeparator } from './DateSeparator';
import { TypingIndicator } from './TypingIndicator';
import { MessageInput } from './MessageInput';
import type { Conversation, Message } from './types';

function groupMessagesByDate(messages: Message[]): Array<{ type: 'date'; date: string } | { type: 'message'; message: Message }> {
  const result: Array<{ type: 'date'; date: string } | { type: 'message'; message: Message }> = [];
  let lastDate = '';

  for (const msg of messages) {
    const d = new Date(msg.created_at);
    const dateKey = d.toISOString().slice(0, 10);
    if (dateKey !== lastDate) {
      lastDate = dateKey;
      result.push({ type: 'date', date: msg.created_at });
    }
    result.push({ type: 'message', message: msg });
  }
  return result;
}

interface ConversationViewProps {
  conversation: Conversation | null;
  onSend?: (text: string) => void;
  typingFrom?: string;
  /** HR: show delete on each message */
  hrCanDeleteMessages?: boolean;
  deletingMessageId?: string | null;
  onDeleteMessage?: (messageId: string) => void;
}

export const ConversationView: React.FC<ConversationViewProps> = ({
  conversation,
  onSend,
  typingFrom,
  hrCanDeleteMessages,
  deletingMessageId,
  onDeleteMessage,
}) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conversation?.messages, typingFrom]);

  if (!conversation) {
    return (
      <div
        className="flex-1 flex flex-col items-center justify-center bg-[#f8fafc] text-[#6b7280] p-8"
        aria-live="polite"
      >
        <p className="text-sm">Select a conversation or start a new one.</p>
      </div>
    );
  }

  if (conversation.thread_loaded === false && conversation.messages.length === 0) {
    return (
      <div
        className="flex-1 flex flex-col items-center justify-center bg-[#f8fafc] text-[#6b7280] p-8"
        aria-live="polite"
      >
        <p className="text-sm">Loading conversation…</p>
      </div>
    );
  }

  const items = groupMessagesByDate(conversation.messages);
  const typingName = typingFrom;

  return (
    <div className="flex-1 flex flex-col bg-[#f8fafc] min-h-0" aria-label={`Conversation with ${conversation.other_participant_name}`}>
      <div className="flex-1 overflow-y-auto px-4 py-4">
        <div className="flex flex-col max-w-2xl mx-auto">
          {items.map((item) => {
            if (item.type === 'date') {
              return <DateSeparator key={`date-${item.date}`} date={item.date} />;
            }
            return (
              <MessageBubble
                key={item.message.id}
                message={item.message}
                showDelete={hrCanDeleteMessages}
                isDeleting={deletingMessageId === item.message.id}
                onDelete={onDeleteMessage}
              />
            );
          })}
          {typingName && <TypingIndicator name={typingName} />}
          <div ref={bottomRef} aria-hidden />
        </div>
      </div>

      {onSend && (
        <div className="flex-shrink-0 bg-white border-t border-[#e2e8f0] shadow-[0_-4px_12px_rgba(0,0,0,0.04)]">
          <MessageInput
            onSend={onSend}
            placeholder={`Message ${conversation.other_participant_name}…`}
          />
        </div>
      )}
    </div>
  );
};
