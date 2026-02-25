import React, { useEffect, useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { hrAPI, employeeAPI } from '../api/client';
import { markConversationRead } from '../api/messageNotifications';
import { getAuthItem } from '../utils/demo';
import { ConversationList } from '../features/messages/ConversationList';
import { ConversationView } from '../features/messages/ConversationView';
import { buildConversationsFromMessages } from '../features/messages/utils';
import { MOCK_CONVERSATIONS } from '../features/messages/mockData';
import type { Conversation } from '../features/messages/types';

export const Messages: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const role = getAuthItem('relopass_role');
  const userId = getAuthItem('relopass_id') || '';
  const userName = getAuthItem('relopass_name') || getAuthItem('relopass_email') || 'You';

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [typingFrom, setTypingFrom] = useState<string | null>(null);

  const activeConversation = activeId
    ? conversations.find((c) => c.id === activeId) ?? null
    : null;

  useEffect(() => {
    const load = async () => {
      try {
        const res = role === 'HR' || role === 'ADMIN'
          ? await hrAPI.listMessages()
          : await employeeAPI.listMessages();
        const raw = (res.messages || []) as Record<string, unknown>[];
        let built = buildConversationsFromMessages(
          raw,
          userId,
          role || 'EMPLOYEE',
          userName
        );
        if (built.length === 0 && import.meta.env.DEV) {
          built = MOCK_CONVERSATIONS;
        }
        setConversations(built);
        const assignmentIdFromUrl = searchParams.get('assignmentId');
        if (assignmentIdFromUrl) {
          const convId = `conv-${assignmentIdFromUrl}`;
          if (built.some((c) => c.id === convId)) {
            setActiveId(convId);
            searchParams.delete('assignmentId');
            setSearchParams(searchParams, { replace: true });
          } else if (built.length > 0) {
            setActiveId(built[0].id);
          }
        } else if (built.length > 0) {
          setActiveId(built[0].id);
        }
      } catch {
        setConversations(import.meta.env.DEV ? MOCK_CONVERSATIONS : []);
        if (import.meta.env.DEV) setActiveId(MOCK_CONVERSATIONS[0]?.id ?? null);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [role, userId, userName]);

  useEffect(() => {
    if (activeConversation?.assignment_id) {
      markConversationRead(activeConversation.assignment_id).catch(() => {});
    }
  }, [activeConversation?.assignment_id]);

  const handleSend = useCallback(
    (text: string) => {
      if (!activeConversation || !text.trim()) return;
      setTypingFrom(null);
    },
    [activeConversation]
  );

  return (
    <AppShell title="Messages" subtitle="Case communications and invitations">
      <div className="flex flex-col h-[calc(100vh-12rem)] md:h-[calc(100vh-10rem)] min-h-[400px] bg-white rounded-xl border border-[#e2e8f0] overflow-hidden shadow-sm">
        {loading ? (
          <div className="flex-1 flex items-center justify-center text-sm text-[#6b7280]">
            Loading messages…
          </div>
        ) : (
          <div className="flex flex-1 min-h-0">
            {/* Desktop: two-column */}
            <div className="hidden md:flex md:w-[30%] md:min-w-[280px] md:max-w-[360px]">
              <ConversationList
                conversations={conversations}
                activeId={activeId}
                onSelect={setActiveId}
              />
            </div>
            <div className="hidden md:flex md:flex-1 min-w-0">
              <ConversationView
                conversation={activeConversation}
                onSend={handleSend}
                typingFrom={typingFrom ?? undefined}
              />
            </div>

            {/* Mobile: single view with toggle */}
            <div className="flex md:hidden flex-1 flex-col min-w-0">
              {activeId ? (
                <>
                  <div className="flex items-center gap-2 px-4 py-3 border-b border-[#e2e8f0] bg-white shrink-0">
                    <button
                      type="button"
                      onClick={() => setActiveId(null)}
                      className="p-2 -ml-2 rounded-lg text-[#6b7280] hover:bg-[#f5f7fa] hover:text-[#1A1A1A] transition-colors"
                      aria-label="Back to conversations"
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                      </svg>
                    </button>
                    <span className="font-semibold text-[#1A1A1A] truncate">
                      {activeConversation?.other_participant_name || 'Conversation'}
                    </span>
                  </div>
                  <ConversationView
                    conversation={activeConversation}
                    onSend={handleSend}
                    typingFrom={typingFrom ?? undefined}
                  />
                </>
              ) : (
                <ConversationList
                  conversations={conversations}
                  activeId={null}
                  onSelect={setActiveId}
                />
              )}
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
};
