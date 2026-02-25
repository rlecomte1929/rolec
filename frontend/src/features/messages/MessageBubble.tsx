import React from 'react';
import type { Message } from './types';

const ROLE_BG: Record<string, string> = {
  HR: 'bg-[#E3F2FD]',
  EMPLOYEE: 'bg-[#E8F5E9]',
  ADMIN: 'bg-[#F3E5F5]',
  SYSTEM: 'bg-[#F5F5F5]',
};

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }) + ' • ' + d.toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
  });
}

interface MessageBubbleProps {
  message: Message;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const role = message.sender_role || 'SYSTEM';
  const bgClass = ROLE_BG[role] ?? ROLE_BG.SYSTEM;
  const isFromMe = message.is_from_me ?? false;

  return (
    <div
      className={`flex flex-col max-w-[65%] mb-3 animate-fade-in ${
        isFromMe ? 'self-end items-end' : 'self-start items-start'
      }`}
      role="article"
      aria-label={`Message from ${message.sender_name || 'Unknown'} at ${formatTimestamp(message.created_at)}`}
    >
      <div
        className={`
          rounded-[20px] px-4 py-3 text-[15px] text-[#1A1A1A] leading-relaxed
          ${bgClass}
          ${isFromMe ? 'rounded-br-md' : 'rounded-bl-md'}
        `}
      >
        <div className="whitespace-pre-wrap break-words">{message.body}</div>
      </div>
      <div
        className={`
          mt-1.5 flex items-center gap-2 text-[12px] opacity-60 text-[#6b7280]
          ${isFromMe ? 'flex-row-reverse' : ''}
        `}
      >
        {message.sender_name && (
          <span>{message.sender_name}</span>
        )}
        <span>{formatTimestamp(message.created_at)}</span>
        {isFromMe && message.status_delivery && message.status_delivery !== 'sending' && (
          <span className="text-[10px] uppercase tracking-wide capitalize">
            {message.status_delivery === 'read' ? 'Read' : message.status_delivery === 'delivered' ? 'Delivered' : message.status_delivery}
          </span>
        )}
      </div>
    </div>
  );
};
