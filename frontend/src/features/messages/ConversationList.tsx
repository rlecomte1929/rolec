import React from 'react';
import type { Conversation } from './types';

function formatTime(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diffDays = Math.floor((now.getTime() - d.getTime()) / 86400000);
  if (diffDays === 0) {
    return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  }
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return d.toLocaleDateString('en-GB', { weekday: 'short' });
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
}

function truncate(str: string, max: number): string {
  if (!str) return '';
  return str.length <= max ? str : str.slice(0, max).trimEnd() + '…';
}

interface ConversationListProps {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
}

export const ConversationList: React.FC<ConversationListProps> = ({
  conversations,
  activeId,
  onSelect,
}) => {
  return (
    <div
      className="h-full flex flex-col bg-white border-r border-[#e2e8f0] overflow-hidden"
      role="list"
      aria-label="Conversations"
    >
      <div className="flex-1 overflow-y-auto">
        {conversations.length === 0 ? (
          <div className="p-6 text-sm text-[#6b7280] text-center">
            No conversations yet.
          </div>
        ) : (
          conversations.map((conv) => {
            const isActive = activeId === conv.id;
            return (
              <button
                key={conv.id}
                type="button"
                onClick={() => onSelect(conv.id)}
                className={`
                  w-full flex items-start gap-3 px-4 py-3 text-left border-b border-[#e2e8f0]/80
                  transition-colors duration-150
                  ${isActive ? 'bg-[#E8F0FE]' : 'hover:bg-[#F5F7FA]'}
                `}
                aria-pressed={isActive}
                aria-label={`Conversation with ${conv.other_participant_name}, last message: ${truncate(conv.last_message_preview, 40)}`}
              >
                <div
                  className="flex-shrink-0 w-10 h-10 rounded-full bg-[#e2e8f0] flex items-center justify-center text-sm font-semibold text-[#0b2b43]"
                  aria-hidden
                >
                  {conv.other_participant_avatar || conv.other_participant_name.slice(0, 2).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="font-semibold text-[#1A1A1A] truncate">
                      {conv.other_participant_name}
                    </span>
                    <span className="flex-shrink-0 text-[11px] text-[#94a3b8]">
                      {formatTime(conv.last_message_at)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between gap-2 mt-0.5">
                    <span className="text-[13px] text-[#6b7280] truncate">
                      {truncate(conv.last_message_preview, 50)}
                    </span>
                    {conv.unread_count && conv.unread_count > 0 && (
                      <span
                        className="flex-shrink-0 min-w-[18px] h-[18px] rounded-full bg-[#1d4ed8] text-white text-[11px] font-medium flex items-center justify-center px-1.5"
                        aria-label={`${conv.unread_count} unread`}
                      >
                        {conv.unread_count > 9 ? '9+' : conv.unread_count}
                      </span>
                    )}
                  </div>
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
};
