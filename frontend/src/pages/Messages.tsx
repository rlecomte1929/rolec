import React, { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import axios from 'axios';
import { useSearchParams } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { hrAPI, employeeAPI } from '../api/client';
import { markConversationRead } from '../api/messageNotifications';
import { getAuthItem } from '../utils/demo';
import { ConversationList } from '../features/messages/ConversationList';
import { ConversationView } from '../features/messages/ConversationView';
import {
  buildConversationsFromMessages,
  buildConversationsFromQuoteThreads,
  conversationFromSummary,
} from '../features/messages/utils';
import { MOCK_CONVERSATIONS } from '../features/messages/mockData';
import type { Conversation } from '../features/messages/types';

export const Messages: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const role = getAuthItem('relopass_role');
  const userId = getAuthItem('relopass_id') || '';
  const userName = getAuthItem('relopass_name') || getAuthItem('relopass_email') || 'You';

  const isHrLike = role === 'HR' || role === 'ADMIN';

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [typingFrom, setTypingFrom] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);

  /** HR: filters & edit mode */
  const [searchInput, setSearchInput] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [archiveFilter, setArchiveFilter] = useState<'active' | 'archived' | 'all'>('active');
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [selectedAssignmentIds, setSelectedAssignmentIds] = useState<Set<string>>(new Set());
  const [archiveBusy, setArchiveBusy] = useState(false);
  const [deletingMessageId, setDeletingMessageId] = useState<string | null>(null);
  const conversationsRef = useRef<Conversation[]>([]);
  conversationsRef.current = conversations;
  const assignmentIdFromUrl = searchParams.get('assignmentId');

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedSearch(searchInput.trim()), 320);
    return () => window.clearTimeout(t);
  }, [searchInput]);

  const activeConversation = activeId
    ? conversations.find((c) => c.id === activeId) ?? null
    : null;

  /** Employee: HR threads per linked assignment + provider quote threads */
  useEffect(() => {
    if (isHrLike) return;
    const load = async () => {
      try {
        const [res, overview] = await Promise.all([
          employeeAPI.listMessages(),
          employeeAPI.getAssignmentsOverview().catch(() => ({ linked: [] as { assignment_id?: string; company?: { name?: string } }[] })),
        ]);
        const raw = (res.messages || []) as Record<string, unknown>[];
        const quoteRaw = (res.quote_threads || []) as Record<string, unknown>[];
        const labels = new Map<string, string>();
        for (const row of overview.linked || []) {
          const aid = row.assignment_id;
          const nm = row.company?.name?.trim();
          if (aid && nm) labels.set(aid, nm);
        }
        let hrBuilt = buildConversationsFromMessages(raw, userId, role || 'EMPLOYEE', userName);
        hrBuilt = hrBuilt.map((c) => ({
          ...c,
          list_subtitle: labels.get(c.assignment_id) || null,
        }));
        const supplierBuilt = buildConversationsFromQuoteThreads(
          quoteRaw,
          userId,
          userName,
          labels
        );
        let built = [...hrBuilt, ...supplierBuilt];
        if (built.length === 0 && import.meta.env.DEV) {
          built = MOCK_CONVERSATIONS;
        }
        setConversations(built);
        const aidFromUrl = searchParams.get('assignmentId');
        if (aidFromUrl) {
          const convId = `conv-${aidFromUrl}`;
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
        setListError(null);
      } catch {
        setConversations(import.meta.env.DEV ? MOCK_CONVERSATIONS : []);
        if (import.meta.env.DEV) setActiveId(MOCK_CONVERSATIONS[0]?.id ?? null);
        setListError('Could not load messages.');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [isHrLike, role, userId, userName, searchParams, setSearchParams]);

  /** HR: conversation summaries only (no message bodies until thread open). */
  useEffect(() => {
    if (!isHrLike) return;
    const ac = new AbortController();
    let cancelled = false;
    const load = async () => {
      try {
        setLoading(true);
        setListError(null);
        const res = await hrAPI.listMessageConversations({
          q: debouncedSearch || undefined,
          archive: archiveFilter,
          unread_only: unreadOnly,
          limit: 80,
          offset: 0,
          signal: ac.signal,
        });
        if (cancelled) return;
        const built = (res.conversations || []).map((row: Record<string, unknown>) =>
          conversationFromSummary(row)
        );
        setConversations((prev) => {
          const prevByAid = new Map(prev.map((c) => [c.assignment_id, c]));
          return built.map((b) => {
            const p = prevByAid.get(b.assignment_id);
            if (p?.thread_loaded && p.messages.length > 0) {
              return { ...b, messages: p.messages, thread_loaded: true };
            }
            return b;
          });
        });

        if (assignmentIdFromUrl) {
          const convId = `conv-${assignmentIdFromUrl}`;
          if (built.some((c) => c.id === convId)) {
            setActiveId(convId);
            setSearchParams(
              (prev) => {
                const next = new URLSearchParams(prev);
                next.delete('assignmentId');
                return next;
              },
              { replace: true }
            );
          }
        }
      } catch (e: unknown) {
        if (cancelled || axios.isCancel(e)) return;
        setConversations(import.meta.env.DEV ? MOCK_CONVERSATIONS : []);
        setListError('Could not load conversations.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
      ac.abort();
    };
  }, [isHrLike, debouncedSearch, archiveFilter, unreadOnly, assignmentIdFromUrl, setSearchParams]);

  /** HR: lazy-load full thread when a conversation is selected. */
  useEffect(() => {
    if (!isHrLike || !activeId) return;
    const conv = conversationsRef.current.find((c) => c.id === activeId);
    if (!conv || conv.thread_loaded) return;
    const aid = conv.assignment_id;
    let cancelled = false;
    (async () => {
      try {
        const res = await hrAPI.getMessageThread(aid);
        const raw = (res.messages || []) as Record<string, unknown>[];
        const built = buildConversationsFromMessages(raw, userId, role || 'HR', userName);
        const msgs = built[0]?.messages ?? [];
        if (!cancelled) {
          setConversations((p) =>
            p.map((c) =>
              c.assignment_id === aid ? { ...c, messages: msgs, thread_loaded: true } : c
            )
          );
        }
      } catch {
        if (!cancelled) {
          setConversations((p) =>
            p.map((c) => (c.assignment_id === aid ? { ...c, thread_loaded: true, messages: [] } : c))
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isHrLike, activeId, userId, role, userName]);

  /** Clear selection if active thread disappears (e.g. after archive + active filter). */
  useEffect(() => {
    if (!activeId) return;
    if (!conversations.some((c) => c.id === activeId)) {
      setActiveId(null);
    }
  }, [conversations, activeId]);

  useEffect(() => {
    if (!activeConversation?.assignment_id || activeConversation.channel === 'supplier') return;
    markConversationRead(activeConversation.assignment_id).catch(() => {});
  }, [activeConversation?.assignment_id, activeConversation?.channel]);

  const employeeMessageSections = useMemo(() => {
    if (isHrLike) return undefined;
    const hr = conversations.filter((c) => c.channel !== 'supplier');
    const sup = conversations.filter((c) => c.channel === 'supplier');
    return [
      {
        title: 'Employer & HR',
        conversations: hr,
        emptyHint:
          'No HR messages yet. When your employer contacts you about an assignment, it appears here—one thread per assignment.',
      },
      {
        title: 'Service providers',
        conversations: sup,
        emptyHint:
          'No provider conversations yet. When you request quotes, messages with vendors appear here in the same layout as HR threads.',
      },
    ];
  }, [conversations, isHrLike]);

  const handleSend = useCallback(
    (text: string) => {
      if (!activeConversation || !text.trim()) return;
      setTypingFrom(null);
    },
    [activeConversation]
  );

  const toggleSelectAssignment = useCallback((assignmentId: string) => {
    setSelectedAssignmentIds((prev) => {
      const next = new Set(prev);
      if (next.has(assignmentId)) next.delete(assignmentId);
      else next.add(assignmentId);
      return next;
    });
  }, []);

  const selectedList = useMemo(() => Array.from(selectedAssignmentIds), [selectedAssignmentIds]);

  const applyArchive = useCallback(
    async (archived: boolean) => {
      if (selectedList.length === 0) return;
      setArchiveBusy(true);
      setListError(null);
      try {
        await hrAPI.archiveMessageConversations({
          assignment_ids: selectedList,
          archived,
        });
        setSelectedAssignmentIds(new Set());
        setEditMode(false);
        try {
          const res = await hrAPI.listMessageConversations({
            q: debouncedSearch || undefined,
            archive: archiveFilter,
            unread_only: unreadOnly,
            limit: 80,
          });
          const built = (res.conversations || []).map((row: Record<string, unknown>) =>
            conversationFromSummary(row)
          );
          setConversations(built);
        } catch {
          setListError(
            archived
              ? 'Archived, but the list could not be refreshed. Reload the page to see changes.'
              : 'Restored, but the list could not be refreshed. Reload the page to see changes.'
          );
        }
      } catch {
        setListError(archived ? 'Could not archive selection.' : 'Could not restore selection.');
      } finally {
        setArchiveBusy(false);
      }
    },
    [selectedList, debouncedSearch, archiveFilter, unreadOnly]
  );

  const handleDeleteMessage = useCallback(
    async (messageId: string) => {
      if (!isHrLike || !messageId) return;
      if (!window.confirm('Delete this message permanently? This cannot be undone.')) return;
      setDeletingMessageId(messageId);
      setListError(null);
      try {
        await hrAPI.deleteHrMessage(messageId);
        const aid = activeConversation?.assignment_id;
        setConversations((prev) =>
          prev.map((c) => {
            if (!aid || c.assignment_id !== aid) return c;
            const nextMsgs = c.messages.filter((m) => m.id !== messageId);
            const last = nextMsgs[nextMsgs.length - 1];
            const raw = last
              ? (last.body || last.subject || '').replace(/\n/g, ' ').trim()
              : '';
            const preview =
              raw.length > 100 ? `${raw.slice(0, 100).trimEnd()}…` : raw;
            return {
              ...c,
              messages: nextMsgs,
              last_message_preview: preview,
              last_message_at: last?.created_at || c.last_message_at,
            };
          })
        );
      } catch {
        setListError('Could not delete message.');
      } finally {
        setDeletingMessageId(null);
      }
    },
    [isHrLike, activeConversation?.assignment_id]
  );

  const exitEditMode = useCallback(() => {
    setEditMode(false);
    setSelectedAssignmentIds(new Set());
  }, []);

  const hrListHeader = isHrLike && (
    <div className="border-b border-[#e2e8f0] p-3 space-y-2 bg-[#fafbfc] shrink-0">
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:gap-2">
        <input
          type="search"
          placeholder="Search name, email, case id…"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          className="flex-1 min-w-[160px] rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm text-[#1A1A1A] placeholder:text-[#94a3b8] focus:outline-none focus:ring-2 focus:ring-[#1d4ed8]/30"
          aria-label="Search conversations"
        />
        <select
          value={archiveFilter}
          onChange={(e) =>
            setArchiveFilter(e.target.value as 'active' | 'archived' | 'all')
          }
          className="rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm text-[#1A1A1A] bg-white"
          aria-label="Archive filter"
        >
          <option value="active">Active</option>
          <option value="archived">Archived</option>
          <option value="all">All</option>
        </select>
        <label className="flex items-center gap-2 text-sm text-[#475569] whitespace-nowrap cursor-pointer">
          <input
            type="checkbox"
            checked={unreadOnly}
            onChange={(e) => setUnreadOnly(e.target.checked)}
            className="rounded border-[#cbd5e1] text-[#1d4ed8]"
          />
          Unread only
        </label>
        <button
          type="button"
          onClick={() => (editMode ? exitEditMode() : setEditMode(true))}
          className="ml-auto sm:ml-0 rounded-lg border border-[#cbd5e1] bg-white px-3 py-2 text-sm font-medium text-[#0f172a] hover:bg-[#f8fafc]"
        >
          {editMode ? 'Done' : 'Edit'}
        </button>
      </div>
      {listError && <p className="text-sm text-red-600">{listError}</p>}
      {editMode && (
        <div className="flex flex-wrap gap-2 pt-1 border-t border-[#e2e8f0]">
          <p className="text-xs text-[#64748b] w-full sm:w-auto sm:mr-2 sm:self-center">
            Select conversations, then archive (hides from Active) or restore from Archived view.
          </p>
          <button
            type="button"
            disabled={selectedList.length === 0 || archiveBusy}
            onClick={() => applyArchive(true)}
            className="rounded-lg bg-[#0f172a] px-3 py-2 text-sm font-medium text-white disabled:opacity-40"
          >
            Archive selected
          </button>
          <button
            type="button"
            disabled={selectedList.length === 0 || archiveBusy}
            onClick={() => applyArchive(false)}
            className="rounded-lg border border-[#cbd5e1] bg-white px-3 py-2 text-sm font-medium text-[#0f172a] disabled:opacity-40"
          >
            Restore selected
          </button>
        </div>
      )}
    </div>
  );

  return (
    <AppShell title="Messages" subtitle="Case threads and invites">
      <div className="flex flex-col h-[calc(100vh-12rem)] md:h-[calc(100vh-10rem)] min-h-[400px] bg-white rounded-xl border border-[#e2e8f0] overflow-hidden shadow-sm">
        {loading ? (
          <div className="flex-1 flex items-center justify-center text-sm text-[#6b7280]">
            Loading messages…
          </div>
        ) : (
          <div className="flex flex-1 min-h-0">
            {/* Desktop: two-column */}
            <div className="hidden md:flex md:w-[30%] md:min-w-[280px] md:max-w-[380px] flex-col min-h-0">
              {hrListHeader}
              <div className="flex-1 min-h-0 overflow-hidden">
                <ConversationList
                  {...(isHrLike
                    ? { conversations }
                    : { sections: employeeMessageSections, conversations: [] })}
                  activeId={activeId}
                  onSelect={setActiveId}
                  editMode={isHrLike && editMode}
                  selectedAssignmentIds={selectedAssignmentIds}
                  onToggleSelectAssignment={toggleSelectAssignment}
                  showArchivedBadge={archiveFilter !== 'active'}
                />
              </div>
            </div>
            <div className="hidden md:flex md:flex-1 min-w-0">
              <ConversationView
                conversation={activeConversation}
                onSend={handleSend}
                typingFrom={typingFrom ?? undefined}
                hrCanDeleteMessages={isHrLike}
                deletingMessageId={deletingMessageId}
                onDeleteMessage={handleDeleteMessage}
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
                    <div className="min-w-0 flex-1">
                      <span className="font-semibold text-[#1A1A1A] truncate block">
                        {activeConversation?.other_participant_name || 'Conversation'}
                      </span>
                      {activeConversation?.list_subtitle ? (
                        <span className="text-xs text-[#64748b] truncate block">
                          {activeConversation.list_subtitle}
                        </span>
                      ) : null}
                    </div>
                  </div>
                  <ConversationView
                    conversation={activeConversation}
                    onSend={handleSend}
                    typingFrom={typingFrom ?? undefined}
                    hrCanDeleteMessages={isHrLike}
                    deletingMessageId={deletingMessageId}
                    onDeleteMessage={handleDeleteMessage}
                  />
                </>
              ) : (
                <>
                  {hrListHeader}
                  <div className="flex-1 min-h-0 overflow-hidden">
                    <ConversationList
                      {...(isHrLike
                        ? { conversations }
                        : { sections: employeeMessageSections, conversations: [] })}
                      activeId={null}
                      onSelect={setActiveId}
                      editMode={isHrLike && editMode}
                      selectedAssignmentIds={selectedAssignmentIds}
                      onToggleSelectAssignment={toggleSelectAssignment}
                      showArchivedBadge={archiveFilter !== 'active'}
                    />
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
};
