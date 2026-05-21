/**
 * T15 — Inbox Screen (S10) /inbox
 * Three-column messaging layout: thread list, message view, thread detail.
 */

import { useEffect, useRef, useState, KeyboardEvent } from 'react';
import { Avatar, DateFormatter, EmptyState } from '../shared';
import type { ThreadParticipantRole } from '../../../types/relopass-api-contracts';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ThreadParticipant {
  id: string;
  name: string;
  role: ThreadParticipantRole;
  avatar_url?: string;
}

export interface Message {
  id: string;
  sender_id: string;
  sender_name: string;
  content: string;
  sent_at: string;
  is_mine: boolean;
}

export interface Thread {
  id: string;
  subject: string;
  participants: ThreadParticipant[];
  messages: Message[];
  case_id: string | null;
  case_label: string | null;
  tags: string[];
  unread_count: number;
  last_message_at: string;
}

export interface InboxScreenProps {
  threads?: Thread[];
  currentUserId?: string;
  onSend?: (threadId: string, content: string) => void;
}

// ─── Mock ─────────────────────────────────────────────────────────────────────

const MOCK_THREADS: Thread[] = [
  {
    id: 't1',
    subject: 'Documents for FR→DE relocation',
    participants: [
      { id: 'u1', name: 'Alice Martin', role: 'employee' },
      { id: 'u2', name: 'Sophie L.', role: 'hr' },
    ],
    messages: [
      { id: 'm1', sender_id: 'u2', sender_name: 'Sophie L.', content: 'Hi Alice, please upload your passport copy when you get a chance.', sent_at: '2026-05-19T10:00:00Z', is_mine: false },
      { id: 'm2', sender_id: 'u1', sender_name: 'Alice Martin', content: 'Done! I just uploaded it to the Documents section.', sent_at: '2026-05-19T10:32:00Z', is_mine: true },
      { id: 'm3', sender_id: 'u2', sender_name: 'Sophie L.', content: 'Thank you! I\'ll review it today.', sent_at: '2026-05-19T11:05:00Z', is_mine: false },
    ],
    case_id: 'c1',
    case_label: 'FR → DE — Alice Martin',
    tags: ['immigration', 'documents'],
    unread_count: 0,
    last_message_at: '2026-05-19T11:05:00Z',
  },
  {
    id: 't2',
    subject: 'Housing search update',
    participants: [
      { id: 'u3', name: 'Bob Chen', role: 'employee' },
      { id: 'u4', name: 'Marc D.', role: 'hr' },
      { id: 'u5', name: 'NestFinder Europe', role: 'vendor' },
    ],
    messages: [
      { id: 'm4', sender_id: 'u5', sender_name: 'NestFinder Europe', content: 'We have 3 shortlisted properties in Kreuzberg matching your criteria.', sent_at: '2026-05-18T14:00:00Z', is_mine: false },
      { id: 'm5', sender_id: 'u3', sender_name: 'Bob Chen', content: 'Great! Can we schedule viewings for next week?', sent_at: '2026-05-18T14:45:00Z', is_mine: false },
    ],
    case_id: 'c2',
    case_label: 'US → GB — Bob Chen',
    tags: ['housing'],
    unread_count: 2,
    last_message_at: '2026-05-18T14:45:00Z',
  },
  {
    id: 't3',
    subject: 'Visa extension timeline',
    participants: [
      { id: 'u6', name: 'Clara Singh', role: 'employee' },
      { id: 'u2', name: 'Sophie L.', role: 'hr' },
    ],
    messages: [
      { id: 'm6', sender_id: 'u6', sender_name: 'Clara Singh', content: 'What is the expected processing time for the NL work permit?', sent_at: '2026-05-17T09:00:00Z', is_mine: false },
    ],
    case_id: 'c3',
    case_label: 'IN → NL — Clara Singh',
    tags: ['immigration'],
    unread_count: 1,
    last_message_at: '2026-05-17T09:00:00Z',
  },
];

// ─── Thread List Item ─────────────────────────────────────────────────────────

interface ThreadItemProps {
  thread: Thread;
  selected: boolean;
  onClick: () => void;
}

function ThreadItem({ thread, selected, onClick }: ThreadItemProps) {
  const last = thread.messages[thread.messages.length - 1];
  const names = thread.participants.map(p => p.name).join(', ');

  return (
    <button
      onClick={onClick}
      style={{
        width: '100%',
        padding: '14px 16px',
        textAlign: 'left',
        background: selected ? 'var(--accent-soft)' : 'none',
        border: 'none',
        borderBottom: '1px solid var(--border)',
        cursor: 'pointer',
        display: 'flex',
        gap: '10px',
        alignItems: 'flex-start',
        transition: 'background 0.1s',
      }}
      onMouseEnter={e => { if (!selected) (e.currentTarget as HTMLElement).style.background = 'var(--surface-hover)'; }}
      onMouseLeave={e => { if (!selected) (e.currentTarget as HTMLElement).style.background = 'none'; }}
    >
      <Avatar name={thread.participants[0]?.name ?? '?'} size={36} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '2px' }}>
          <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '150px' }}>
            {names}
          </span>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', flexShrink: 0 }}>
            <DateFormatter date={thread.last_message_at} format="relative" tooltip={false} />
          </span>
        </div>
        <p style={{ margin: '0 0 3px', fontSize: '12px', fontWeight: 600, color: selected ? 'var(--accent)' : 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {thread.subject}
        </p>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
            {last?.content ?? ''}
          </p>
          {thread.unread_count > 0 && (
            <span style={{ marginLeft: '6px', minWidth: '18px', height: '18px', borderRadius: 'var(--radius-full)', background: 'var(--accent)', color: '#fff', fontSize: '11px', fontWeight: 700, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', padding: '0 5px', flexShrink: 0 }}>
              {thread.unread_count}
            </span>
          )}
        </div>
      </div>
    </button>
  );
}

// ─── Message Bubble ───────────────────────────────────────────────────────────

function MessageBubble({ msg }: { msg: Message }) {
  return (
    <div style={{ display: 'flex', flexDirection: msg.is_mine ? 'row-reverse' : 'row', gap: '8px', alignItems: 'flex-end', marginBottom: '12px' }}>
      {!msg.is_mine && <Avatar name={msg.sender_name} size={28} />}
      <div style={{ maxWidth: '72%' }}>
        {!msg.is_mine && (
          <p style={{ margin: '0 0 3px 4px', fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)' }}>{msg.sender_name}</p>
        )}
        <div style={{
          padding: '10px 14px',
          borderRadius: msg.is_mine ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
          background: msg.is_mine ? 'var(--accent)' : 'var(--surface)',
          color: msg.is_mine ? '#fff' : 'var(--text)',
          fontSize: '14px',
          lineHeight: 1.5,
          border: msg.is_mine ? 'none' : '1px solid var(--border)',
        }}>
          {msg.content}
        </div>
        <p style={{ margin: '3px 4px 0', fontSize: '11px', color: 'var(--text-muted)', textAlign: msg.is_mine ? 'right' : 'left' }}>
          <DateFormatter date={msg.sent_at} format="relative" />
        </p>
      </div>
    </div>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export function InboxScreen({ threads = MOCK_THREADS, onSend }: InboxScreenProps) {
  const [search, setSearch] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const selected = threads.find(t => t.id === selectedId) ?? null;
  const filtered = threads.filter(t => !search || t.subject.toLowerCase().includes(search.toLowerCase()));

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [selectedId, selected?.messages.length]);

  function handleSend() {
    if (!draft.trim() || !selectedId) return;
    onSend?.(selectedId, draft.trim());
    setDraft('');
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: 'var(--bg)' }}>

      {/* Column 1 — Thread list */}
      <div style={{ width: '280px', flexShrink: 0, borderRight: '1px solid var(--border)', background: 'var(--surface)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)' }}>
          <h2 style={{ margin: '0 0 10px', fontSize: '16px', fontWeight: 700, color: 'var(--text)' }}>Inbox</h2>
          <div style={{ position: 'relative' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2" style={{ position: 'absolute', left: '9px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}>
              <path d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z" />
            </svg>
            <input
              type="search"
              placeholder="Search threads…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{ width: '100%', padding: '7px 10px 7px 30px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text)', fontSize: '13px', outline: 'none', boxSizing: 'border-box' }}
            />
          </div>
        </div>
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {filtered.map(t => (
            <ThreadItem key={t.id} thread={t} selected={t.id === selectedId} onClick={() => setSelectedId(t.id)} />
          ))}
        </div>
      </div>

      {/* Column 2 — Messages */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
        {!selected ? (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <EmptyState icon="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" title="Select a conversation" description="Choose a thread from the left to view messages." />
          </div>
        ) : (
          <>
            {/* Messages */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px' }}>
              <h3 style={{ margin: '0 0 20px', fontSize: '15px', fontWeight: 700, color: 'var(--text)' }}>{selected.subject}</h3>
              {selected.messages.map(msg => <MessageBubble key={msg.id} msg={msg} />)}
              <div ref={messagesEndRef} />
            </div>
            {/* Composer */}
            <div style={{ padding: '12px 20px', borderTop: '1px solid var(--border)', background: 'var(--surface)', display: 'flex', gap: '10px', alignItems: 'flex-end' }}>
              <textarea
                value={draft}
                onChange={e => setDraft(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type a message… (Enter to send, Shift+Enter for newline)"
                rows={2}
                style={{ flex: 1, padding: '10px 12px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text)', fontSize: '14px', resize: 'none', outline: 'none', lineHeight: 1.5 }}
              />
              <button
                onClick={handleSend}
                disabled={!draft.trim()}
                style={{ padding: '10px 16px', borderRadius: 'var(--radius-md)', border: 'none', background: draft.trim() ? 'var(--accent)' : 'var(--surface-hover)', color: draft.trim() ? '#fff' : 'var(--text-muted)', cursor: draft.trim() ? 'pointer' : 'not-allowed', fontWeight: 600, fontSize: '13px', flexShrink: 0, display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z" /></svg>
                Send
              </button>
            </div>
          </>
        )}
      </div>

      {/* Column 3 — Thread detail */}
      <div style={{ width: '320px', flexShrink: 0, borderLeft: '1px solid var(--border)', background: 'var(--surface)', overflowY: 'auto', padding: '20px 20px' }}>
        {selected ? (
          <>
            <p style={{ margin: '0 0 4px', fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)' }}>Subject</p>
            <p style={{ margin: '0 0 16px', fontSize: '14px', fontWeight: 600, color: 'var(--text)' }}>{selected.subject}</p>

            {selected.case_label && (
              <>
                <p style={{ margin: '0 0 4px', fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)' }}>Linked case</p>
                <p style={{ margin: '0 0 16px', fontSize: '13px', color: 'var(--link)' }}>{selected.case_label}</p>
              </>
            )}

            {selected.tags.length > 0 && (
              <>
                <p style={{ margin: '0 0 8px', fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)' }}>Tags</p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '16px' }}>
                  {selected.tags.map(tag => (
                    <span key={tag} style={{ padding: '2px 8px', borderRadius: 'var(--radius-full)', background: 'var(--surface-2)', border: '1px solid var(--border)', fontSize: '12px', color: 'var(--text-secondary)' }}>{tag}</span>
                  ))}
                </div>
              </>
            )}

            <p style={{ margin: '0 0 10px', fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)' }}>Participants</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {selected.participants.map(p => (
                <div key={p.id} style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                  <Avatar name={p.name} src={p.avatar_url} size={32} />
                  <div>
                    <p style={{ margin: '0 0 2px', fontSize: '13px', fontWeight: 600, color: 'var(--text)' }}>{p.name}</p>
                    <p style={{ margin: 0, fontSize: '11px', color: 'var(--text-muted)', textTransform: 'capitalize' }}>{p.role}</p>
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : (
          <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>No conversation selected.</p>
        )}
      </div>
    </div>
  );
}
