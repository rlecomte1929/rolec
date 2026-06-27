import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Archive,
  Briefcase,
  Building2,
  Home,
  Inbox,
  Mail,
  Paperclip,
  Send,
  Sparkles,
  Star,
  Users,
} from 'lucide-react';
import { Input } from '../../../components/antigravity/Input';
import { Button } from '../../../components/antigravity/Button';
import { hrAPI, employeeAPI } from '../../../api/client';
import { markConversationRead } from '../../../api/messageNotifications';
import { getAuthItem } from '../../../utils/demo';
import {
  buildConversationsFromMessages,
  buildConversationsFromQuoteThreads,
  conversationFromSummary,
} from '../../messages/utils';
import type { Conversation, Message } from '../../messages/types';
import { AppShell } from '../../../components/AppShell';

type MailboxKey = 'inbox' | 'hr' | 'vendors' | 'authorities' | 'family' | 'sent' | 'archive';

interface MailboxDef {
  key: MailboxKey;
  label: string;
  icon: typeof Inbox;
  match: (c: Conversation) => boolean;
}

// M-08 (AIQ-1266): contextual empty states so a new employee knows WHEN messages
// will arrive, instead of a bare "No threads in this mailbox."
const MAILBOX_EMPTY_COPY: Record<MailboxKey, string> = {
  inbox: 'Your HR team will message you here once your intake is reviewed. Your first message usually arrives within 2 business days.',
  hr: 'Messages from your HR team appear here once your intake is reviewed.',
  vendors: 'Vendor quotes appear here after you request services from the Services page.',
  authorities: 'Messages from authorities appear here during the immigration process.',
  family: 'Family-related messages appear here.',
  sent: 'Messages you send appear here.',
  archive: 'Archived conversations appear here.',
};

const MAILBOXES: MailboxDef[] = [
  { key: 'inbox', label: 'Inbox', icon: Inbox, match: () => true },
  { key: 'hr', label: 'From HR', icon: Briefcase, match: (c) => c.channel !== 'supplier' },
  { key: 'vendors', label: 'Vendors', icon: Building2, match: (c) => c.channel === 'supplier' },
  {
    key: 'authorities',
    label: 'Authorities',
    icon: Mail,
    match: (c) =>
      /\b(UDI|consulate|préfecture|prefecture|immigration|embassy|directorate)\b/i.test(
        `${c.last_message_preview} ${c.other_participant_name}`
      ),
  },
  {
    key: 'family',
    label: 'Family',
    icon: Home,
    match: (c) =>
      /\b(school|children|family|spouse|partner|kid|household)\b/i.test(
        `${c.last_message_preview} ${c.other_participant_name}`
      ),
  },
  { key: 'sent', label: 'Sent', icon: Send, match: (c) => (c.messages || []).some((m) => m.is_from_me) },
  { key: 'archive', label: 'Archive', icon: Archive, match: () => true },
];

function formatThreadTime(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  if (sameDay) return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  const diffDays = Math.floor((now.getTime() - d.getTime()) / 86_400_000);
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return d.toLocaleDateString('en-GB', { weekday: 'short' });
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
}

function formatMessageTime(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const wasYesterday = d.toDateString() === yesterday.toDateString();
  const time = d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  if (sameDay) return `Today ${time}`;
  if (wasYesterday) return `Yesterday ${time}`;
  return `${d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })} ${time}`;
}

function initials(name: string): string {
  const cleaned = (name || '').trim();
  if (!cleaned) return '·';
  const parts = cleaned.split(/\s+/).filter(Boolean);
  if (parts.length === 1) return parts[0]!.slice(0, 2).toUpperCase();
  return (parts[0]![0]! + parts[parts.length - 1]![0]!).toUpperCase();
}

function deriveSubject(c: Conversation): string {
  const firstWithSubject = (c.messages || []).find((m) => m.subject && m.subject.trim());
  if (firstWithSubject?.subject) return firstWithSubject.subject;
  return c.last_message_preview || 'Conversation';
}

interface Stakeholder {
  name: string;
  subtitle: string;
  conversationId: string;
}

function deriveStakeholders(conversations: Conversation[]): Stakeholder[] {
  const map = new Map<string, Stakeholder>();
  for (const c of conversations) {
    const name = c.other_participant_name || 'Unknown';
    const key = name.toLowerCase();
    if (map.has(key)) continue;
    map.set(key, {
      name,
      subtitle: c.list_subtitle || (c.channel === 'supplier' ? 'Service provider' : 'HR contact'),
      conversationId: c.id,
    });
  }
  return Array.from(map.values()).slice(0, 6);
}

export function InboxV2Page() {
  const [searchParams, setSearchParams] = useSearchParams();
  const role = (getAuthItem('relopass_role') || '').toUpperCase();
  const userId = getAuthItem('relopass_id') || '';
  const userName = getAuthItem('relopass_name') || getAuthItem('relopass_email') || 'You';
  const isHrLike = role === 'HR' || role === 'ADMIN';


  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  // Bumped by the "Try again" recovery action to re-run the conversation fetch
  // effects (HR + employee) without a full page reload (AIQ-419 / P15).
  const [reloadKey, setReloadKey] = useState(0);
  const [mailbox, setMailbox] = useState<MailboxKey>('inbox');
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [archiving, setArchiving] = useState(false);
  const [starred, setStarred] = useState<Set<string>>(new Set());
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const conversationsRef = useRef<Conversation[]>([]);
  conversationsRef.current = conversations;

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedSearch(search.trim()), 280);
    return () => window.clearTimeout(t);
  }, [search]);

  // HR/ADMIN: conversation summaries (lazy thread load on select)
  useEffect(() => {
    if (!isHrLike) return;
    let cancelled = false;
    const ac = new AbortController();
    void (async () => {
      try {
        setLoading(true);
        setListError(null);
        const res = await hrAPI.listMessageConversations({
          q: debouncedSearch || undefined,
          archive: mailbox === 'archive' ? 'archived' : 'active',
          unread_only: false,
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
      } catch (e) {
        if (cancelled) return;
        // axios cancel surfaces as ERR_CANCELED — ignore.
        if ((e as { code?: string })?.code === 'ERR_CANCELED') return;
        setConversations([]);
        setListError('Could not load conversations.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
      ac.abort();
    };
  }, [isHrLike, debouncedSearch, mailbox, reloadKey]);

  // EMPLOYEE: HR threads + supplier (vendor) threads
  useEffect(() => {
    if (isHrLike) return;
    let cancelled = false;
    void (async () => {
      try {
        setLoading(true);
        setListError(null);
        const [res, overview] = await Promise.all([
          employeeAPI.listMessages(),
          employeeAPI
            .getAssignmentsOverview()
            .catch(() => ({ linked: [] as Array<{ assignment_id?: string; company?: { name?: string } }> })),
        ]);
        if (cancelled) return;
        const labels = new Map<string, string>();
        for (const row of overview.linked || []) {
          const aid = row.assignment_id;
          const nm = row.company?.name?.trim();
          if (aid && nm) labels.set(aid, nm);
        }
        const raw = (res.messages || []) as Record<string, unknown>[];
        const quoteRaw = (res.quote_threads || []) as Record<string, unknown>[];
        let hrBuilt = buildConversationsFromMessages(raw, userId, role || 'EMPLOYEE', userName);
        hrBuilt = hrBuilt.map((c) => ({
          ...c,
          list_subtitle: labels.get(c.assignment_id) || null,
        }));
        const supplierBuilt = buildConversationsFromQuoteThreads(quoteRaw, userId, userName, labels);
        setConversations([...hrBuilt, ...supplierBuilt]);
      } catch {
        if (!cancelled) {
          setConversations([]);
          setListError('Could not load messages.');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isHrLike, role, userId, userName, reloadKey]);

  // Honour ?assignmentId= deep-link
  const assignmentIdFromUrl = searchParams.get('assignmentId');
  useEffect(() => {
    if (!assignmentIdFromUrl) return;
    const target = `conv-${assignmentIdFromUrl}`;
    if (conversations.some((c) => c.id === target)) {
      setActiveId(target);
      const next = new URLSearchParams(searchParams);
      next.delete('assignmentId');
      setSearchParams(next, { replace: true });
    }
  }, [assignmentIdFromUrl, conversations, searchParams, setSearchParams]);

  // Default-select first conversation in the active mailbox once loaded.
  const filteredConversations = useMemo(() => {
    const def = MAILBOXES.find((m) => m.key === mailbox) ?? MAILBOXES[0]!;
    const needle = debouncedSearch.toLowerCase();
    const matches = conversations.filter((c) => {
      if (!def.match(c)) return false;
      if (!needle) return true;
      const hay = `${c.other_participant_name} ${c.last_message_preview} ${c.list_subtitle || ''} ${c.case_id || ''}`.toLowerCase();
      return hay.includes(needle);
    });
    return matches.sort(
      (a, b) => new Date(b.last_message_at).getTime() - new Date(a.last_message_at).getTime()
    );
  }, [conversations, mailbox, debouncedSearch]);

  useEffect(() => {
    if (activeId && filteredConversations.some((c) => c.id === activeId)) return;
    setActiveId(filteredConversations[0]?.id ?? null);
  }, [filteredConversations, activeId]);

  const activeConversation = useMemo(
    () => (activeId ? conversations.find((c) => c.id === activeId) ?? null : null),
    [conversations, activeId]
  );

  // HR: lazy-load full thread when opened
  useEffect(() => {
    if (!isHrLike || !activeConversation) return;
    if (activeConversation.thread_loaded) return;
    const aid = activeConversation.assignment_id;
    let cancelled = false;
    void (async () => {
      try {
        const res = await hrAPI.getMessageThread(aid);
        const built = buildConversationsFromMessages(
          (res.messages || []) as Record<string, unknown>[],
          userId,
          role || 'HR',
          userName
        );
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
            p.map((c) =>
              c.assignment_id === aid ? { ...c, thread_loaded: true, messages: [] } : c
            )
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isHrLike, activeConversation, userId, role, userName]);

  // Mark conversation read on open
  useEffect(() => {
    if (!activeConversation?.assignment_id || activeConversation.channel === 'supplier') return;
    markConversationRead(activeConversation.assignment_id).catch(() => {});
  }, [activeConversation?.assignment_id, activeConversation?.channel]);

  // Auto-scroll to bottom when the thread changes
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeConversation?.id, activeConversation?.messages?.length]);

  const mailboxCounts = useMemo(() => {
    const counts: Record<MailboxKey, number> = {
      inbox: 0,
      hr: 0,
      vendors: 0,
      authorities: 0,
      family: 0,
      sent: 0,
      archive: 0,
    };
    for (const c of conversations) {
      for (const m of MAILBOXES) {
        if (m.key === 'archive') continue;
        if (m.match(c)) counts[m.key] += 1;
      }
    }
    return counts;
  }, [conversations]);

  const stakeholders = useMemo(() => deriveStakeholders(conversations), [conversations]);

  const handleArchive = useCallback(async () => {
    if (!activeConversation || !isHrLike) return;
    setArchiving(true);
    try {
      const restore = mailbox === 'archive';
      await hrAPI.archiveMessageConversations({
        assignment_ids: [activeConversation.assignment_id],
        archived: !restore,
      });
      setConversations((prev) => prev.filter((c) => c.id !== activeConversation.id));
      setActiveId(null);
    } catch {
      setListError('Could not update archive state.');
    } finally {
      setArchiving(false);
    }
  }, [activeConversation, isHrLike, mailbox]);

  const toggleStar = useCallback(() => {
    if (!activeConversation) return;
    setStarred((prev) => {
      const next = new Set(prev);
      if (next.has(activeConversation.id)) next.delete(activeConversation.id);
      else next.add(activeConversation.id);
      return next;
    });
  }, [activeConversation]);

  const handleSend = useCallback(async () => {
    const text = draft.trim();
    if (!text || !activeConversation) return;
    const aid = activeConversation.assignment_id;
    const convId = activeConversation.id;
    const localId = `local-${Date.now()}`;
    setSending(true);
    setSendError(null);
    // Optimistically append so the user gets immediate feedback, then POST.
    const optimistic: Message = {
      id: localId,
      assignment_id: aid,
      body: text,
      created_at: new Date().toISOString(),
      sender_user_id: userId,
      sender_name: userName,
      sender_role: isHrLike ? 'HR' : 'EMPLOYEE',
      is_from_me: true,
      status_delivery: 'sending',
    };
    setConversations((prev) =>
      prev.map((c) =>
        c.id === convId
          ? {
              ...c,
              messages: [...c.messages, optimistic],
              last_message_preview: text.slice(0, 100),
              last_message_at: optimistic.created_at,
            }
          : c
      )
    );
    setDraft('');
    try {
      const send = isHrLike ? hrAPI.sendMessage : employeeAPI.sendMessage;
      await send(aid, text);
      // Confirm delivery on the optimistic row.
      setConversations((prev) =>
        prev.map((c) =>
          c.id === convId
            ? { ...c, messages: c.messages.map((m) => (m.id === localId ? { ...m, status_delivery: 'sent' } : m)) }
            : c
        )
      );
    } catch {
      // Roll the optimistic message back and restore the draft so the user can retry.
      setConversations((prev) =>
        prev.map((c) =>
          c.id === convId ? { ...c, messages: c.messages.filter((m) => m.id !== localId) } : c
        )
      );
      setDraft(text);
      setSendError("Couldn't send your message. Please try again.");
    } finally {
      setSending(false);
    }
  }, [draft, activeConversation, userId, userName, isHrLike]);

  const handleDraftWithAi = useCallback(() => {
    if (!activeConversation) return;
    const last = [...activeConversation.messages].reverse().find((m) => !m.is_from_me);
    const subject = activeConversation.last_message_preview || 'your last message';
    const stub = last
      ? `Hi ${activeConversation.other_participant_name.split(' ')[0] || 'there'} — thanks for the update on "${subject}". `
      : `Hi ${activeConversation.other_participant_name.split(' ')[0] || 'there'} — `;
    setDraft((d) => (d ? d : stub));
  }, [activeConversation]);

  return (
    <AppShell section={role === 'EMPLOYEE' ? 'Employee' : 'HR Operations'} title="Inbox" subtitle={undefined} wide>
      <div className="-mx-6 -my-6 flex h-[calc(100vh-10rem)] min-h-[560px] flex-col overflow-hidden bg-slate-100">
        {/* E4: breadcrumb removed — the AppShell already renders "Employee / Inbox".
            Keep just the thread count to avoid a duplicated breadcrumb trail. */}
        <div className="flex items-center justify-end border-b border-slate-200 bg-white px-6 py-3 shrink-0">
          <div className="text-xs text-slate-400">
            {filteredConversations.length} thread{filteredConversations.length === 1 ? '' : 's'}
          </div>
        </div>

        <div className="flex min-h-0 flex-1">
          {/* Mailboxes + Stakeholders */}
          <aside className="hidden w-[224px] shrink-0 flex-col border-r border-slate-200 bg-white md:flex">
            <div className="px-4 pt-5 pb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Mailboxes
            </div>
            <nav className="px-2">
              {MAILBOXES.map((m) => {
                const count = mailboxCounts[m.key];
                const active = mailbox === m.key;
                const Icon = m.icon;
                return (
                  <Button unstyled
                    key={m.key}
                    type="button"
                    onClick={() => setMailbox(m.key)}
                    className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm transition-colors ${
                      active
                        ? 'bg-slate-900 text-white'
                        : 'text-slate-700 hover:bg-slate-100'
                    }`}
                  >
                    <span className="flex items-center gap-2.5">
                      <Icon className="h-4 w-4" />
                      {m.label}
                    </span>
                    {m.key !== 'archive' && count > 0 && (
                      <span
                        className={`rounded-full px-1.5 text-[11px] font-medium ${
                          active ? 'bg-white/15 text-white' : 'bg-slate-200 text-slate-600'
                        }`}
                      >
                        {count}
                      </span>
                    )}
                  </Button>
                );
              })}
            </nav>

            <div className="mt-6 px-4 pb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Stakeholders
            </div>
            <div className="px-2 pb-6">
              {stakeholders.length === 0 ? (
                <div className="px-3 py-3 text-xs text-slate-400">No people yet.</div>
              ) : (
                stakeholders.map((s) => (
                  <Button unstyled
                    key={s.conversationId + s.name}
                    type="button"
                    onClick={() => setActiveId(s.conversationId)}
                    className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-100"
                  >
                    <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-200 text-[11px] font-semibold text-slate-700">
                      {initials(s.name)}
                    </span>
                    <span className="min-w-0 flex-1 truncate">
                      <span className="block truncate font-medium">{s.name}</span>
                      <span className="block truncate text-[11px] text-slate-400">{s.subtitle}</span>
                    </span>
                  </Button>
                ))
              )}
            </div>
          </aside>

          {/* Thread list */}
          <section className="flex w-full max-w-[380px] shrink-0 flex-col border-r border-slate-200 bg-white md:w-[360px]">
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <div className="flex items-baseline gap-2">
                <h2 className="text-sm font-semibold text-slate-900">
                  {MAILBOXES.find((m) => m.key === mailbox)?.label || 'Inbox'}
                </h2>
                <span className="text-xs text-slate-400">
                  {filteredConversations.length} thread{filteredConversations.length === 1 ? '' : 's'}
                </span>
              </div>
              <Button unstyled
                type="button"
                title="Start a new message"
                onClick={() => {
                  // Conversations are one-per-assignment and always exist, so a
                  // "new message" is: open a thread (the active one, or the first)
                  // and focus the composer to start writing.
                  const target = activeId ?? filteredConversations[0]?.id ?? null;
                  if (target && target !== activeId) setActiveId(target);
                  setTimeout(() => document.getElementById('inbox-v2-composer')?.focus(), 50);
                }}
                className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
              >
                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                New
              </Button>
            </div>
            <div className="px-3 py-2">
              <Input unstyled
                type="search"
                value={search}
                onChange={(v) => setSearch(v)}
                placeholder="Search threads…"
                className="w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm text-slate-800 placeholder:text-slate-400 focus:border-slate-400 focus:bg-white focus:outline-none"
              />
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto">
              {loading ? (
                <div className="px-4 py-6 text-sm text-slate-400">Loading conversations…</div>
              ) : listError ? (
                <div className="px-4 py-6">
                  <p className="text-sm text-rose-600">{listError}</p>
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-3"
                    onClick={() => setReloadKey((k) => k + 1)}
                  >
                    Try again
                  </Button>
                </div>
              ) : filteredConversations.length === 0 ? (
                <div className="px-4 py-6 text-sm text-slate-500">
                {isHrLike && mailbox === 'inbox'
                  ? 'No conversations yet. Open a case and message the employee to start a thread.'
                  : MAILBOX_EMPTY_COPY[mailbox]}
              </div>
              ) : (
                filteredConversations.map((c) => {
                  const isActive = activeId === c.id;
                  const subject = deriveSubject(c);
                  const unread = (c.unread_count || 0) > 0;
                  return (
                    <Button unstyled
                      key={c.id}
                      type="button"
                      onClick={() => setActiveId(c.id)}
                      className={`block w-full border-b border-slate-100 px-4 py-3 text-left transition-colors ${
                        isActive ? 'bg-blue-50/60' : 'hover:bg-slate-50'
                      }`}
                    >
                      <div className="flex items-baseline justify-between gap-3">
                        <span
                          className={`truncate text-sm ${
                            unread ? 'font-semibold text-slate-900' : 'font-medium text-slate-800'
                          }`}
                        >
                          {c.other_participant_name}
                        </span>
                        <span className="shrink-0 text-[11px] text-slate-400">
                          {formatThreadTime(c.last_message_at)}
                        </span>
                      </div>
                      <div className="mt-0.5 flex items-baseline justify-between gap-3">
                        <span className="truncate text-[13px] text-slate-700">{subject}</span>
                        {unread ? (
                          <span className="inline-flex h-4 min-w-4 shrink-0 items-center justify-center rounded-full bg-blue-600 px-1 text-[10px] font-semibold text-white">
                            {c.unread_count}
                          </span>
                        ) : c.messages.length > 0 ? (
                          <span className="shrink-0 rounded-full bg-slate-100 px-1.5 text-[10px] font-medium text-slate-500">
                            {c.messages.length}
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-1 line-clamp-2 text-[12.5px] text-slate-500">
                        {c.last_message_preview || 'No preview available.'}
                      </p>
                    </Button>
                  );
                })
              )}
            </div>
          </section>

          {/* Conversation view */}
          <section className="flex min-w-0 flex-1 flex-col bg-white">
            {activeConversation ? (
              <>
                {/* Header — always-visible action bar */}
                <header className="flex items-start justify-between gap-4 border-b border-slate-200 px-6 py-4 shrink-0">
                  <div className="min-w-0">
                    <h1 className="truncate text-[17px] font-semibold text-slate-900">
                      {deriveSubject(activeConversation)}
                    </h1>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-[12px] text-slate-500">
                      <span className="inline-flex items-center rounded bg-slate-900 px-1.5 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide text-white">
                        {activeConversation.channel === 'supplier' ? 'Vendor' : 'HR'}
                      </span>
                      <span>
                        {activeConversation.messages.length} message
                        {activeConversation.messages.length === 1 ? '' : 's'}
                      </span>
                      {activeConversation.case_id && (
                        <>
                          <span className="text-slate-300">·</span>
                          <span>Case {activeConversation.case_id}</span>
                        </>
                      )}
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Button unstyled
                      type="button"
                      onClick={toggleStar}
                      aria-pressed={starred.has(activeConversation.id)}
                      title="Star conversation"
                      className={`inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 transition-colors ${
                        starred.has(activeConversation.id)
                          ? 'bg-amber-100 text-amber-600'
                          : 'bg-white text-slate-500 hover:bg-slate-50'
                      }`}
                    >
                      <Star className="h-4 w-4" fill={starred.has(activeConversation.id) ? 'currentColor' : 'none'} />
                    </Button>
                    {isHrLike && (
                      <Button unstyled
                        type="button"
                        onClick={handleArchive}
                        disabled={archiving}
                        className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                      >
                        <Archive className="h-4 w-4" />
                        {mailbox === 'archive' ? 'Restore' : 'Archive'}
                      </Button>
                    )}
                    <Button unstyled
                      type="button"
                      onClick={() => {
                        const ta = document.getElementById('inbox-v2-composer') as HTMLTextAreaElement | null;
                        ta?.focus();
                      }}
                      className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-slate-900 px-3 text-sm font-medium text-white hover:bg-slate-800"
                    >
                      <Send className="h-4 w-4" />
                      Reply
                    </Button>
                  </div>
                </header>

                {/* Messages */}
                <div className="min-h-0 flex-1 overflow-y-auto bg-slate-50 px-6 py-5">
                  {!activeConversation.thread_loaded && activeConversation.messages.length === 0 ? (
                    <div className="text-sm text-slate-400">Loading conversation…</div>
                  ) : activeConversation.messages.length === 0 ? (
                    <div className="text-sm text-slate-400">No messages in this thread yet.</div>
                  ) : (
                    <div className="mx-auto flex max-w-3xl flex-col gap-3">
                      {activeConversation.messages.map((m) => (
                        <MessageCard
                          key={m.id}
                          message={m}
                          counterparty={activeConversation.other_participant_name}
                        />
                      ))}
                      <div ref={messagesEndRef} />
                    </div>
                  )}
                </div>

                {/* Composer — always visible */}
                <div className="border-t border-slate-200 bg-white px-6 py-4 shrink-0">
                  <div className="mb-2 flex items-center justify-between">
                    <p className="text-xs text-slate-500">
                      Reply to <span className="font-medium text-slate-700">{activeConversation.other_participant_name}</span>
                    </p>
                    <Button unstyled
                      type="button"
                      onClick={handleDraftWithAi}
                      className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                    >
                      <Sparkles className="h-3.5 w-3.5 text-blue-500" />
                      Draft with AI
                    </Button>
                  </div>
                  {sendError && (
                    <p className="mb-1 text-xs text-red-500" role="alert">{sendError}</p>
                  )}
                  <textarea
                    id="inbox-v2-composer"
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                        e.preventDefault();
                        void handleSend();
                      }
                    }}
                    rows={3}
                    placeholder="Write a reply…"
                    className="w-full resize-none rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none"
                  />
                  <div className="mt-2 flex items-center justify-between">
                    <Button unstyled
                      type="button"
                      className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                    >
                      <Paperclip className="h-3.5 w-3.5" />
                      Attach
                    </Button>
                    <Button unstyled
                      type="button"
                      onClick={handleSend}
                      disabled={!draft.trim() || sending}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-navy-800 px-3 py-1.5 text-sm font-medium text-white hover:bg-navy-900 disabled:opacity-50"
                    >
                      <Send className="h-3.5 w-3.5" />
                      {sending ? 'Sending…' : 'Send'}
                    </Button>
                  </div>
                </div>
              </>
            ) : (
              <div className="flex flex-1 flex-col items-center justify-center bg-slate-50 px-8 text-center">
                <Users className="h-10 w-10 text-slate-300" />
                {listError ? (
                  <p className="mt-4 text-sm text-slate-500">Messages could not be loaded.</p>
                ) : (
                  <>
                    <p className="mt-4 text-sm font-medium text-slate-700">No conversation selected</p>
                    <p className="mt-1 max-w-xs text-xs text-slate-400">
                      Pick a thread on the left. Threads appear once HR opens a case or a vendor sends a quote.
                    </p>
                  </>
                )}
              </div>
            )}
          </section>
        </div>
      </div>
    </AppShell>
  );
}

function MessageCard({ message, counterparty }: { message: Message; counterparty: string }) {
  const isMine = !!message.is_from_me;
  const displayName = isMine ? 'You' : message.sender_name || counterparty;
  return (
    <div
      className={`rounded-lg border bg-white p-4 shadow-sm ${
        isMine ? 'border-blue-100 bg-blue-50/40' : 'border-slate-200'
      }`}
    >
      <div className="mb-2 flex items-start gap-3">
        <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-200 text-[11px] font-semibold text-slate-700">
          {initials(displayName)}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline justify-between gap-2">
            <span className="truncate text-sm font-semibold text-slate-900">{displayName}</span>
            <span className="shrink-0 text-[11px] text-slate-400">{formatMessageTime(message.created_at)}</span>
          </div>
          <div className="text-[11px] text-slate-400">
            {isMine ? `to ${counterparty}` : 'to You'}
          </div>
        </div>
      </div>
      {message.subject && (
        <p className="mb-1 text-[13px] font-medium text-slate-800">{message.subject}</p>
      )}
      <p className="whitespace-pre-wrap text-[13.5px] leading-relaxed text-slate-800">
        {message.body}
      </p>
      {message.status_delivery === 'sending' && (
        <p className="mt-2 text-[11px] italic text-slate-400">Sending…</p>
      )}
    </div>
  );
}

export default InboxV2Page;
