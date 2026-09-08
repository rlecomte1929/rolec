import { useState, useMemo, useEffect, type ReactNode } from 'react';
import {
  Send, Search, Filter, Plus, X, User, Building2, Clock, AlertTriangle,
  CheckCircle2, MessageCircle, Copy, Check, Sparkles, ChevronRight,
  ChevronLeft, ExternalLink, Lock, FileText, Bell,
} from 'lucide-react';
import { tw } from '../../lib/colors';
import { useSpaceRuntime } from '../../SpaceRuntimeContext';
import {
  OUTREACH_STATUSES,
  STATUS_LABELS,
  FOLLOW_UP_DUE_DAYS,
  draftFirstOutreach,
  draftFollowUp,
  daysSince,
  isFollowUpDue,
  formatDate,
  todayISODate,
  type OutreachContact,
  type OutreachStatus,
} from './templates';

declare global {
  function useWorkspaceDB<T = unknown>(
    table: string,
    options?: {
      shared?: boolean;
      limit?: number;
      offset?: number;
      orderBy?: { column: string; direction: 'asc' | 'desc' };
      filters?: Array<{ column: string; operator: string; value: unknown }>;
    },
  ): { data: T[]; loading: boolean; error: Error | null; total: number; refresh: () => void };
}

const TABLE = 'outreach_contacts';

const STATUS_STYLE: Record<OutreachStatus, string> = {
  prospected: 'bg-[var(--space-surface-muted)] text-[var(--space-text-secondary)] border-[var(--space-border-default)]',
  messaged: 'bg-[var(--space-brand-primary-50)] text-[var(--space-text-brand)] border-[var(--space-border-strong)]',
  awaiting_reply: 'bg-[var(--space-brand-highlight-100)] text-[var(--space-text-accent)] border-[var(--space-border-strong)]',
  replied: 'bg-purple-500/15 text-purple-300 border-purple-500/30',
  converted: 'bg-green-500/15 text-green-300 border-green-500/30',
  no_response: 'bg-[var(--space-surface-muted)] text-[var(--space-text-muted)] border-[var(--space-border-default)]',
};

function dbTable() {
  return (window as any).__workspaceDb.from(TABLE, { shared: true });
}

async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      return true;
    } catch {
      return false;
    }
  }
}

async function summariseReplyAI(contact: OutreachContact, replyText: string): Promise<{ summary: string; next_action: string }> {
  const res = await fetch('/proxy/openai/v1/chat/completions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: 'gpt-4o-mini',
      temperature: 0.3,
      max_tokens: 300,
      messages: [
        {
          role: 'system',
          content:
            'You help the founder of ReloPass (a relocation compliance tool for HR generalists managing international employee moves) triage LinkedIn outreach replies. ' +
            'Given a prospect\'s reply, respond with ONLY a JSON object, no markdown fences, shaped exactly like: ' +
            '{"summary": "<one-line summary of their response>", "next_action": "<one concrete suggested next step, e.g. Schedule a 20-min call / Send product link / Not interested \u2014 archive>"}',
        },
        {
          role: 'user',
          content: `Prospect: ${contact.full_name}${contact.job_title ? `, ${contact.job_title}` : ''}${contact.company ? ` at ${contact.company}` : ''}.\n\nTheir reply:\n"""${replyText}"""`,
        },
      ],
    }),
  });
  if (!res.ok) throw new Error(`AI request failed (${res.status})`);
  const data = await res.json();
  const content: string = data?.choices?.[0]?.message?.content || '';
  const cleaned = content.replace(/```json|```/g, '').trim();
  try {
    const parsed = JSON.parse(cleaned);
    return {
      summary: String(parsed.summary || '').trim() || cleaned,
      next_action: String(parsed.next_action || '').trim() || 'Review manually',
    };
  } catch {
    return { summary: cleaned || 'Could not parse reply summary.', next_action: 'Review manually' };
  }
}

// ─── Sub-components ────────────────────────────────────────────────────────────

function StatusPill({ status }: { status: OutreachStatus }) {
  return (
    <span className={`inline-flex w-fit px-2 py-0.5 rounded-full text-[10px] font-semibold border whitespace-nowrap ${STATUS_STYLE[status] || STATUS_STYLE.prospected}`}>
      {STATUS_LABELS[status] || status}
    </span>
  );
}

function FollowUpBadge() {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/40 whitespace-nowrap">
      <Bell className="w-3 h-3" /> Follow up due
    </span>
  );
}

function ContactRow({ c, selected, onSelect }: { c: OutreachContact; selected: boolean; onSelect: () => void }) {
  const due = isFollowUpDue(c);
  return (
    <button
      onClick={onSelect}
      className={`w-full text-left px-4 py-3 border-b border-[var(--space-border-default)] transition-all hover:bg-[var(--space-surface-card-hover)] ${
        selected
          ? 'bg-[var(--space-brand-primary-50)] border-l-[3px] border-l-[var(--space-brand-primary)]'
          : due
            ? 'bg-amber-500/10 border-l-[3px] border-l-amber-500/60'
            : 'border-l-[3px] border-l-transparent'
      }`}
    >
      <div className="flex items-center gap-3">
        <div className="flex-1 min-w-0 grid grid-cols-1 sm:grid-cols-[1.3fr_1.1fr_1.1fr_0.9fr_0.8fr] gap-1 sm:gap-3 items-center">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-[var(--space-text-primary)] truncate">{c.full_name}</p>
            {due && <span className="sm:hidden"><FollowUpBadge /></span>}
          </div>
          <p className="text-xs text-[var(--space-text-secondary)] truncate">{c.company || '—'}</p>
          <p className="text-xs text-[var(--space-text-muted)] truncate hidden sm:block">{c.job_title || '—'}</p>
          <div className="flex items-center gap-1.5 flex-wrap">
            <StatusPill status={c.status} />
            {due && <span className="hidden sm:inline-flex"><FollowUpBadge /></span>}
          </div>
          <p className="text-[10px] text-[var(--space-text-muted)] hidden sm:block">{formatDate(c.last_activity_at || c.updated_at)}</p>
        </div>
        <ChevronRight className={`w-4 h-4 flex-shrink-0 ${selected ? 'text-[var(--space-brand-primary)]' : 'text-[var(--space-text-muted)]'}`} />
      </div>
    </button>
  );
}

function SectionLabel({ icon: Icon, children }: { icon: typeof User; children: ReactNode }) {
  return (
    <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--space-text-secondary)] mb-2 flex items-center gap-1.5">
      <Icon className="w-3.5 h-3.5" /> {children}
    </h3>
  );
}

// ─── Detail panel ─────────────────────────────────────────────────────────────

function ContactDetail({
  c,
  onBack,
  onChanged,
}: {
  c: OutreachContact;
  onBack: () => void;
  onChanged: () => void;
}) {
  const [draft, setDraft] = useState('');
  const [draftKind, setDraftKind] = useState<'first' | 'follow_up' | null>(null);
  const [copied, setCopied] = useState(false);
  const [showReplyBox, setShowReplyBox] = useState(false);
  const [replyText, setReplyText] = useState('');
  const [notesDraft, setNotesDraft] = useState(c.notes || '');
  const [busy, setBusy] = useState<string | null>(null);
  const [aiError, setAiError] = useState<string | null>(null);

  // Reset per-contact UI state when switching contacts
  useEffect(() => {
    setDraft('');
    setDraftKind(null);
    setCopied(false);
    setShowReplyBox(false);
    setReplyText('');
    setNotesDraft(c.notes || '');
    setAiError(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [c.id]);

  const daysSinceFirst = daysSince(c.first_message_sent_at);
  const due = isFollowUpDue(c);
  const touch = () => ({ last_activity_at: new Date().toISOString() });

  const update = async (label: string, patch: Record<string, unknown>) => {
    setBusy(label);
    try {
      await dbTable().update(c.id, { ...patch, ...touch() });
      onChanged();
    } finally {
      setBusy(null);
    }
  };

  const handleCopy = async () => {
    const ok = await copyToClipboard(draft);
    if (ok) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleLogReply = async () => {
    const text = replyText.trim();
    if (!text) return;
    const stamp = `[Reply logged ${todayISODate()}]`;
    const notes = `${c.notes ? c.notes + '\n\n' : ''}${stamp} ${text}`;
    setNotesDraft(notes);
    await update('log_reply', { status: 'replied', notes, follow_up_reminder_sent: c.follow_up_reminder_sent ?? false });
  };

  const handleSummarise = async () => {
    const source = replyText.trim() || c.notes || '';
    if (!source) return;
    setBusy('summarise');
    setAiError(null);
    try {
      const { summary, next_action } = await summariseReplyAI(c, source);
      await dbTable().update(c.id, { reply_summary: summary, next_action, ...touch() });
      onChanged();
    } catch (e: any) {
      setAiError(e?.message || 'Summarisation failed — try again.');
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* Header */}
      <div className="px-5 py-4 border-b border-[var(--space-border-default)] bg-gradient-to-br from-[var(--space-brand-primary-50)] via-[var(--space-surface-card)] to-[var(--space-brand-highlight-50)]">
        <button onClick={onBack} className="flex items-center gap-1 text-xs text-[var(--space-text-brand)] font-medium mb-3 lg:hidden">
          <ChevronLeft className="w-4 h-4" /> Back to contacts
        </button>
        <div className="flex items-start gap-3">
          <div className="w-11 h-11 rounded-xl bg-[var(--space-brand-primary)] flex items-center justify-center flex-shrink-0 shadow-md">
            <span className="text-sm font-bold text-[var(--space-text-on-primary)]">
              {c.full_name.split(' ').map((n) => n[0]).join('').slice(0, 2).toUpperCase()}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2 mb-0.5">
              <h2 className="text-lg font-bold text-[var(--space-text-primary)]">{c.full_name}</h2>
              <StatusPill status={c.status} />
              {due && <FollowUpBadge />}
            </div>
            <p className="text-sm text-[var(--space-text-secondary)]">
              {c.job_title || 'Unknown role'}{c.company ? ` · ${c.company}` : ''}
            </p>
            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-[var(--space-text-muted)]">
              {c.linkedin_url && (
                <a href={c.linkedin_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-[var(--space-text-brand)] hover:underline">
                  <ExternalLink className="w-3.5 h-3.5" /> LinkedIn profile
                </a>
              )}
              <span className="flex items-center gap-1">
                <Clock className="w-3.5 h-3.5" /> First message: {formatDate(c.first_message_sent_at)}
                {daysSinceFirst !== null && ` (${daysSinceFirst}d ago)`}
              </span>
              <span className="flex items-center gap-1">Last activity: {formatDate(c.last_activity_at || c.updated_at)}</span>
            </div>
          </div>
        </div>
        {due && (
          <div className="mt-3 px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-amber-200 font-medium">
              {daysSinceFirst}d since first message with no reply logged — a polite follow-up is due (threshold: {FOLLOW_UP_DUE_DAYS} days).
            </p>
          </div>
        )}
      </div>

      <div className="flex-1 px-5 py-5 space-y-6">
        {/* Actions */}
        <div>
          <SectionLabel icon={Send}>Actions</SectionLabel>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => { setDraft(draftFirstOutreach(c.full_name, c.company)); setDraftKind('first'); setCopied(false); }}
              className={`px-3 py-2 text-xs rounded-lg flex items-center gap-1.5 ${tw.button.primary}`}
            >
              <FileText className="w-3.5 h-3.5" /> Draft outreach message
            </button>
            <button
              onClick={() => { setDraft(draftFollowUp(c.full_name, daysSinceFirst)); setDraftKind('follow_up'); setCopied(false); }}
              className={`px-3 py-2 text-xs rounded-lg flex items-center gap-1.5 ${due ? tw.button.accent : tw.button.secondary}`}
            >
              <Bell className="w-3.5 h-3.5" /> Draft follow-up
            </button>
            <button
              disabled={busy !== null}
              onClick={() => update('messaged', { status: 'messaged', first_message_sent_at: c.first_message_sent_at || todayISODate() })}
              className={`px-3 py-2 text-xs rounded-lg flex items-center gap-1.5 ${tw.button.secondary} disabled:opacity-50`}
            >
              <Send className="w-3.5 h-3.5" /> Mark as messaged
            </button>
            <button
              disabled={busy !== null}
              onClick={() => setShowReplyBox((v) => !v)}
              className={`px-3 py-2 text-xs rounded-lg flex items-center gap-1.5 ${tw.button.secondary}`}
            >
              <MessageCircle className="w-3.5 h-3.5" /> Log reply received
            </button>
            <button
              disabled={busy !== null}
              onClick={() => update('converted', { status: 'converted' })}
              className={`px-3 py-2 text-xs rounded-lg flex items-center gap-1.5 ${tw.button.secondary} disabled:opacity-50`}
            >
              <CheckCircle2 className="w-3.5 h-3.5" /> Mark as converted
            </button>
            {(c.status === 'messaged' || c.status === 'awaiting_reply') && (
              <button
                disabled={busy !== null}
                onClick={() => update('follow_up_sent', { status: 'awaiting_reply', follow_up_reminder_sent: true })}
                className={`px-3 py-2 text-xs rounded-lg flex items-center gap-1.5 ${tw.button.secondary} disabled:opacity-50`}
                title="Record that you've manually sent the follow-up on LinkedIn"
              >
                <Check className="w-3.5 h-3.5" /> Mark follow-up sent
              </button>
            )}
          </div>
          <div className="mt-2.5 flex items-center gap-2">
            <label className="text-[10px] uppercase tracking-wider font-semibold text-[var(--space-text-muted)]">Status</label>
            <select
              value={c.status}
              onChange={(e) => update('status', { status: e.target.value })}
              disabled={busy !== null}
              className="text-xs border border-[var(--space-border-default)] rounded-lg px-2 py-1.5 bg-[var(--space-surface-card)] text-[var(--space-text-primary)]"
            >
              {OUTREACH_STATUSES.map((s) => (
                <option key={s} value={s}>{STATUS_LABELS[s]}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Drafted message */}
        {draftKind && (
          <div>
            <SectionLabel icon={FileText}>
              {draftKind === 'first' ? 'Drafted first outreach' : 'Drafted follow-up'} — edit, then copy to LinkedIn
            </SectionLabel>
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              rows={7}
              className={`${tw.input.base} ${tw.input.default} text-sm leading-relaxed font-normal`}
            />
            <div className="flex flex-wrap items-center gap-2 mt-2">
              <button onClick={handleCopy} className={`px-3 py-2 text-xs rounded-lg flex items-center gap-1.5 ${tw.button.accent}`}>
                {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                {copied ? 'Copied — paste into LinkedIn' : 'Copy message'}
              </button>
              <p className="text-[10px] text-[var(--space-text-muted)]">
                Sending happens manually on LinkedIn — ReloPass never sends automatically.
              </p>
            </div>
          </div>
        )}

        {/* Reply logging */}
        {showReplyBox && (
          <div className="p-3.5 rounded-xl border border-purple-500/30 bg-purple-500/10">
            <SectionLabel icon={MessageCircle}>Log their reply</SectionLabel>
            <textarea
              value={replyText}
              onChange={(e) => setReplyText(e.target.value)}
              rows={4}
              placeholder="Paste or summarise the prospect's reply here…"
              className={`${tw.input.base} ${tw.input.default} text-sm`}
            />
            <div className="flex flex-wrap gap-2 mt-2">
              <button
                disabled={!replyText.trim() || busy !== null}
                onClick={handleLogReply}
                className={`px-3 py-2 text-xs rounded-lg flex items-center gap-1.5 ${tw.button.primary} disabled:opacity-50`}
              >
                <Check className="w-3.5 h-3.5" /> Save reply (status → Replied)
              </button>
              <button
                disabled={(!replyText.trim() && !c.notes) || busy !== null}
                onClick={handleSummarise}
                className={`px-3 py-2 text-xs rounded-lg flex items-center gap-1.5 ${tw.button.accent} disabled:opacity-50`}
              >
                <Sparkles className="w-3.5 h-3.5" />
                {busy === 'summarise' ? 'Summarising…' : 'Summarise & next step'}
              </button>
            </div>
            {aiError && <p className="text-xs text-red-400 mt-2">{aiError}</p>}
          </div>
        )}

        {/* AI digest */}
        {(c.reply_summary || c.next_action) && (
          <div className="p-3.5 rounded-xl border border-[var(--space-border-default)] bg-[var(--space-surface-accent-soft)]">
            <SectionLabel icon={Sparkles}>Reply digest</SectionLabel>
            {c.reply_summary && (
              <p className="text-sm text-[var(--space-text-primary)] leading-relaxed mb-2">{c.reply_summary}</p>
            )}
            {c.next_action && (
              <p className="text-xs text-[var(--space-text-accent)] font-semibold flex items-center gap-1.5">
                <ChevronRight className="w-3.5 h-3.5" /> Suggested next step: {c.next_action}
              </p>
            )}
          </div>
        )}

        {/* Notes */}
        <div>
          <SectionLabel icon={FileText}>Notes</SectionLabel>
          <textarea
            value={notesDraft}
            onChange={(e) => setNotesDraft(e.target.value)}
            rows={5}
            placeholder="Free-form notes — context, replies, reminders…"
            className={`${tw.input.base} ${tw.input.default} text-sm`}
          />
          {notesDraft !== (c.notes || '') && (
            <button
              disabled={busy !== null}
              onClick={() => update('notes', { notes: notesDraft })}
              className={`mt-2 px-3 py-2 text-xs rounded-lg ${tw.button.primary} disabled:opacity-50`}
            >
              Save notes
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Main App ──────────────────────────────────────────────────────────────────────

const EMPTY_FORM = {
  full_name: '',
  company: '',
  job_title: '',
  linkedin_url: '',
  status: 'prospected' as OutreachStatus,
  first_message_sent_at: '',
  notes: '',
};

export default function Outreach() {
  const { mode, checkRoleAccess } = useSpaceRuntime();
  const { data, loading, error, refresh } = useWorkspaceDB<OutreachContact>(TABLE, {
    shared: true,
    orderBy: { column: 'updated_at', direction: 'desc' },
    limit: 500,
  });

  const [filterStatus, setFilterStatus] = useState<'all' | 'follow_up_due' | OutreachStatus>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [mobileShowDetail, setMobileShowDetail] = useState(false);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [busy, setBusy] = useState(false);

  const contacts = useMemo(() => {
    const list = [...(data || [])];
    // Follow-up-due contacts float to the top, then most recent activity first.
    return list.sort((a, b) => {
      const dueDiff = Number(isFollowUpDue(b)) - Number(isFollowUpDue(a));
      if (dueDiff !== 0) return dueDiff;
      const at = new Date(a.last_activity_at || a.updated_at).getTime() || 0;
      const bt = new Date(b.last_activity_at || b.updated_at).getTime() || 0;
      return bt - at;
    });
  }, [data]);

  const metrics = useMemo(() => {
    const m = { total: contacts.length, messaged: 0, awaiting: 0, replied: 0, converted: 0, due: 0 };
    contacts.forEach((c) => {
      if (c.status === 'messaged') m.messaged += 1;
      if (c.status === 'awaiting_reply') m.awaiting += 1;
      if (c.status === 'replied') m.replied += 1;
      if (c.status === 'converted') m.converted += 1;
      if (isFollowUpDue(c)) m.due += 1;
    });
    return m;
  }, [contacts]);

  const filtered = useMemo(() => {
    let result = contacts;
    if (filterStatus === 'follow_up_due') result = result.filter(isFollowUpDue);
    else if (filterStatus !== 'all') result = result.filter((c) => c.status === filterStatus);
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (c) =>
          c.full_name.toLowerCase().includes(q) ||
          (c.company || '').toLowerCase().includes(q) ||
          (c.job_title || '').toLowerCase().includes(q),
      );
    }
    return result;
  }, [contacts, filterStatus, searchQuery]);

  const selected = useMemo(() => contacts.find((c) => c.id === selectedId) || null, [contacts, selectedId]);

  // Admin gate — this is a founder-only operations tool.
  const allowed = mode === 'entrepreneur' || checkRoleAccess(['admin', 'owner', 'founder']);
  if (!allowed) {
    return (
      <div className="min-h-full flex items-center justify-center p-8">
        <div className="text-center max-w-sm">
          <div className="w-12 h-12 rounded-xl bg-[var(--space-surface-muted)] flex items-center justify-center mx-auto mb-3">
            <Lock className="w-6 h-6 text-[var(--space-text-muted)]" />
          </div>
          <h2 className="text-base font-semibold text-[var(--space-text-primary)] mb-1">Admin only</h2>
          <p className="text-sm text-[var(--space-text-secondary)]">
            Outreach is an internal ReloPass operations tool and is only available to the founder / admin team.
          </p>
        </div>
      </div>
    );
  }

  const handleAddContact = async () => {
    const name = form.full_name.trim();
    if (!name) return;
    setBusy(true);
    try {
      await dbTable().insert({
        full_name: name,
        company: form.company.trim() || null,
        job_title: form.job_title.trim() || null,
        linkedin_url: form.linkedin_url.trim() || null,
        status: form.status,
        first_message_sent_at: form.first_message_sent_at || null,
        notes: form.notes.trim() || null,
        follow_up_reminder_sent: false,
        last_activity_at: new Date().toISOString(),
      });
      setForm({ ...EMPTY_FORM });
      setShowAddForm(false);
      refresh();
    } finally {
      setBusy(false);
    }
  };

  const handleSelect = (id: number) => {
    setSelectedId(id);
    setMobileShowDetail(true);
  };

  return (
    <div className="min-h-full flex flex-col w-full bg-transparent">
      {/* Header */}
      <div className="px-5 py-4 border-b border-[var(--space-border-default)] bg-[var(--space-surface-card)]">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-9 h-9 rounded-xl bg-[var(--space-brand-primary-50)] flex items-center justify-center flex-shrink-0">
              <Send className={`w-5 h-5 ${tw.icon.primary}`} />
            </div>
            <div className="min-w-0">
              <h2 className="font-semibold text-base text-[var(--space-text-primary)]">Outreach</h2>
              <p className="text-xs text-[var(--space-text-secondary)] truncate">
                LinkedIn prospect tracker — draft here, send manually on LinkedIn
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="hidden sm:inline px-2.5 py-1 rounded-full text-xs font-medium bg-[var(--space-surface-muted)] text-[var(--space-text-secondary)]">
              Founder only
            </span>
            <button
              onClick={() => setShowAddForm(!showAddForm)}
              className={`px-3 py-1.5 text-xs rounded-lg flex items-center gap-1 ${tw.button.accent}`}
            >
              {showAddForm ? <X className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
              <span className="hidden sm:inline">{showAddForm ? 'Cancel' : 'Add contact'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Metrics */}
      <div className="px-5 py-3 border-b border-[var(--space-border-default)] bg-[var(--space-surface-panel)]">
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
          {[
            { label: 'Prospects', value: metrics.total, color: 'text-[var(--space-text-primary)]' },
            { label: 'Messaged', value: metrics.messaged, color: 'text-[var(--space-brand-primary)]' },
            { label: 'Awaiting reply', value: metrics.awaiting, color: 'text-[var(--space-text-accent)]' },
            { label: 'Replied', value: metrics.replied, color: 'text-purple-400' },
            { label: 'Converted', value: metrics.converted, color: 'text-[var(--space-semantic-success)]' },
            { label: 'Follow-ups due', value: metrics.due, color: metrics.due > 0 ? 'text-amber-400' : 'text-[var(--space-text-muted)]' },
          ].map((m) => (
            <div key={m.label} className="text-center">
              <p className={`text-lg sm:text-xl font-bold ${m.color}`}>{m.value}</p>
              <p className="text-[10px] sm:text-xs text-[var(--space-text-secondary)]">{m.label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Add contact form */}
      {showAddForm && (
        <div className="px-5 py-4 border-b border-[var(--space-border-default)] bg-[var(--space-brand-highlight-50)]">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--space-text-secondary)] mb-3">New prospect</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            <input type="text" placeholder="Full name *" value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              className={tw.input.default + ' text-sm px-3 py-2 rounded-lg border'} />
            <input type="text" placeholder="Company" value={form.company}
              onChange={(e) => setForm({ ...form, company: e.target.value })}
              className={tw.input.default + ' text-sm px-3 py-2 rounded-lg border'} />
            <input type="text" placeholder="Job title" value={form.job_title}
              onChange={(e) => setForm({ ...form, job_title: e.target.value })}
              className={tw.input.default + ' text-sm px-3 py-2 rounded-lg border'} />
            <input type="url" placeholder="LinkedIn profile URL" value={form.linkedin_url}
              onChange={(e) => setForm({ ...form, linkedin_url: e.target.value })}
              className={tw.input.default + ' text-sm px-3 py-2 rounded-lg border'} />
            <select value={form.status}
              onChange={(e) => setForm({ ...form, status: e.target.value as OutreachStatus })}
              className={tw.input.default + ' text-sm px-3 py-2 rounded-lg border'}>
              {OUTREACH_STATUSES.map((s) => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
            </select>
            <div>
              <input type="date" value={form.first_message_sent_at}
                onChange={(e) => setForm({ ...form, first_message_sent_at: e.target.value })}
                className={tw.input.default + ' text-sm px-3 py-2 rounded-lg border w-full'} />
              <p className="text-[10px] text-[var(--space-text-muted)] mt-1">First message sent date (if already messaged)</p>
            </div>
            <textarea placeholder="Notes" rows={2} value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              className={tw.input.default + ' text-sm px-3 py-2 rounded-lg border sm:col-span-2 lg:col-span-3'} />
          </div>
          <button
            onClick={handleAddContact}
            disabled={busy || !form.full_name.trim()}
            className={`mt-3 px-4 py-2 text-sm rounded-lg ${tw.button.primary} disabled:opacity-50`}
          >
            Add prospect
          </button>
        </div>
      )}

      {/* Master-detail */}
      <div className="flex-1 flex min-h-0">
        {/* List */}
        <div className={`${mobileShowDetail ? 'hidden lg:flex' : 'flex'} flex-col w-full lg:w-[46%] xl:w-[42%] border-r border-[var(--space-border-default)] bg-[var(--space-surface-card)]`}>
          <div className="px-4 py-3 border-b border-[var(--space-border-default)] space-y-2.5">
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--space-surface-muted)] border border-[var(--space-border-default)]">
              <Search className="w-3.5 h-3.5 text-[var(--space-text-muted)] flex-shrink-0" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search name, company, title…"
                className="flex-1 text-sm bg-transparent border-none outline-none text-[var(--space-text-primary)] placeholder:text-[var(--space-text-muted)]"
              />
            </div>
            <div className="flex items-center gap-1.5 flex-wrap">
              <Filter className="w-3.5 h-3.5 text-[var(--space-text-muted)]" />
              {(['all', 'follow_up_due', ...OUTREACH_STATUSES] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilterStatus(f)}
                  className={`px-2.5 py-1 rounded-full text-xs font-medium transition-all ${
                    filterStatus === f
                      ? f === 'follow_up_due' ? 'bg-amber-500 text-black font-semibold' : tw.button.primary
                      : tw.button.secondary
                  }`}
                >
                  {f === 'all' ? 'All' : f === 'follow_up_due' ? `Follow up due${metrics.due > 0 ? ` (${metrics.due})` : ''}` : STATUS_LABELS[f as OutreachStatus]}
                </button>
              ))}
            </div>
          </div>

          <div className="hidden sm:grid grid-cols-[1.3fr_1.1fr_1.1fr_0.9fr_0.8fr] gap-3 px-4 py-2 border-b border-[var(--space-border-default)] bg-[var(--space-surface-muted)]">
            {['Name', 'Company', 'Title', 'Status', 'Last activity'].map((h) => (
              <p key={h} className="text-[10px] font-semibold uppercase tracking-wider text-[var(--space-text-muted)]">{h}</p>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="text-center py-16">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--space-brand-primary)] mx-auto" />
                <p className="text-sm text-[var(--space-text-muted)] mt-3">Loading prospects…</p>
              </div>
            ) : error ? (
              <div className="text-center py-16 text-red-400 text-sm px-4">Error: {error.message}</div>
            ) : filtered.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center px-4">
                <User className="w-8 h-8 text-[var(--space-text-muted)] mb-2" />
                <p className="text-sm text-[var(--space-text-secondary)]">
                  {contacts.length === 0 ? 'No prospects yet — add your first contact to start tracking outreach.' : 'No contacts match your filters.'}
                </p>
              </div>
            ) : (
              filtered.map((c) => (
                <ContactRow key={c.id} c={c} selected={selectedId === c.id} onSelect={() => handleSelect(c.id)} />
              ))
            )}
          </div>

          <div className="px-4 py-2.5 border-t border-[var(--space-border-default)] bg-[var(--space-surface-muted)]">
            <p className="text-[10px] text-[var(--space-text-muted)]">
              {filtered.length} of {contacts.length} prospects · drafting + tracking only — no automated LinkedIn sending
            </p>
          </div>
        </div>

        {/* Detail */}
        <div className={`${mobileShowDetail ? 'flex' : 'hidden lg:flex'} flex-col flex-1 min-w-0 bg-[var(--space-surface-muted)]`}>
          {selected ? (
            <ContactDetail c={selected} onBack={() => setMobileShowDetail(false)} onChanged={refresh} />
          ) : (
            <div className="flex-1 flex items-center justify-center text-center p-8">
              <div>
                <Building2 className="w-8 h-8 text-[var(--space-text-muted)] mx-auto mb-2" />
                <p className="text-sm text-[var(--space-text-secondary)]">Select a prospect to draft messages and log activity.</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
