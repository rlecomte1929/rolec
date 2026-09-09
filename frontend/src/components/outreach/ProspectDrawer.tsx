import React, { useEffect, useRef, useState, useCallback } from 'react';
import { X, ExternalLink, Clipboard, Check, RefreshCw } from 'lucide-react';
import { Textarea, Alert } from '../antigravity';
import { useMessages } from '../../hooks/useMessages';
import { useReplies } from '../../hooks/useReplies';
import { isFollowUpDue, daysSinceSent } from '../../hooks/useFollowUpQueue';
import { personaliseMessage, pickBestTemplate } from '../../utils/messagePersonaliser';
import { isOverLinkedInLimit, linkedInCharCount } from '../../utils/linkedInFormatter';
import type { LinkedInProspect, MessageTemplate, OutreachMessage, ProspectReply, ProspectStatus } from '../../types/outreach';
import { ReplyLogModal } from './ReplyLogModal';

// ── Local flash-toast helper ──────────────────────────────────────────────────
function useCopyFlash() {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const flash = useCallback(() => {
    setCopied(true);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setCopied(false), 2000);
  }, []);
  return { copied, flash };
}

// ── Status timeline ───────────────────────────────────────────────────────────
const STATUS_STEPS: { key: ProspectStatus; label: string }[] = [
  { key: 'flagged',         label: 'Flagged' },
  { key: 'message_drafted', label: 'Drafted' },
  { key: 'message_sent',    label: 'Sent' },
  { key: 'replied',         label: 'Replied' },
  { key: 'converted',       label: 'Converted' },
];

const STATUS_ORDER: ProspectStatus[] = [
  'flagged', 'message_drafted', 'message_sent',
  'replied', 'follow_up_sent', 'converted', 'not_interested', 'archived',
];

function statusIndex(s: ProspectStatus): number {
  return STATUS_ORDER.indexOf(s);
}

// ── Props ─────────────────────────────────────────────────────────────────────
export interface ProspectDrawerProps {
  prospect: LinkedInProspect | null;
  templates: MessageTemplate[];
  onClose: () => void;
  onUpdateProspect: (id: string, patch: Partial<LinkedInProspect>) => Promise<void>;
  onUpdateStatus: (id: string, status: ProspectStatus, extra?: Partial<LinkedInProspect>) => Promise<void>;
}

export function ProspectDrawer({
  prospect,
  templates,
  onClose,
  onUpdateProspect,
  onUpdateStatus,
}: ProspectDrawerProps): React.ReactElement {
  const isOpen = prospect !== null;

  // Hooks
  const { getDraftForProspect, getMessagesForProspect, createMessage, updateMessage, markSent, markCopied } = useMessages();
  const { logReply, getRepliesForProspect } = useReplies();

  // Local state
  const [draft, setDraft] = useState<OutreachMessage | null>(null);
  const [draftBody, setDraftBody] = useState('');
  const [replies, setReplies] = useState<ProspectReply[]>([]);
  const [notes, setNotes] = useState('');
  const [loadingDraft, setLoadingDraft] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showReplyModal, setShowReplyModal] = useState(false);
  const [savingNotes, setSavingNotes] = useState(false);
  const [markingSent, setMarkingSent] = useState(false);
  const [markingFollowUp, setMarkingFollowUp] = useState(false);
  const [followUpDraft, setFollowUpDraft] = useState<OutreachMessage | null>(null);
  const [followUpBody, setFollowUpBody] = useState('');
  const { copied: copiedDraft, flash: flashDraft } = useCopyFlash();
  const { copied: copiedFollowUp, flash: flashFollowUp } = useCopyFlash();

  // Escape key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  // Load data when prospect changes
  useEffect(() => {
    if (!prospect) return;
    setNotes(prospect.notes ?? '');
    setError(null);
    setDraft(null);
    setDraftBody('');
    setReplies([]);
    setFollowUpDraft(null);
    setFollowUpBody('');

    setLoadingDraft(true);
    Promise.all([
      getDraftForProspect(prospect.id),
      getRepliesForProspect(prospect.id),
      getMessagesForProspect(prospect.id),
    ]).then(([d, r, allMsgs]) => {
      setDraft(d);
      setDraftBody(d?.body ?? '');
      setReplies(r);
      // Find an existing follow-up draft
      const fu = allMsgs.find((m) => m.message_type === 'follow_up' && m.status === 'draft') ?? null;
      setFollowUpDraft(fu);
      setFollowUpBody(fu?.body ?? '');
    }).catch((e: unknown) => setError(e instanceof Error ? e.message : 'Failed to load prospect data')).finally(() => setLoadingDraft(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prospect?.id]);

  // ── Actions ──────────────────────────────────────────────────────────────────

  const handleSaveNotes = async () => {
    if (!prospect) return;
    setSavingNotes(true);
    await onUpdateProspect(prospect.id, { notes: notes.trim() || null });
    setSavingNotes(false);
  };

  const handleSaveDraftBody = async () => {
    if (!draft) return;
    await updateMessage(draft.id, { body: draftBody });
    setDraft((d) => d ? { ...d, body: draftBody } : d);
  };

  const handleCopyDraft = async () => {
    if (!draft) return;
    await navigator.clipboard.writeText(draftBody);
    flashDraft();
    await markCopied(draft.id);
  };

  const handleMarkSent = async () => {
    if (!prospect || !draft) return;
    setMarkingSent(true);
    try {
      await markSent(draft.id);
      await onUpdateStatus(prospect.id, 'message_sent', { message_sent_at: new Date().toISOString() });
      setDraft((d) => d ? { ...d, status: 'sent', sent_at: new Date().toISOString() } : d);
    } finally {
      setMarkingSent(false);
    }
  };

  const handleRegenerateDraft = async (type: 'initial' | 'follow_up') => {
    if (!prospect) return;
    const template = pickBestTemplate(templates, type);
    if (!template) { setError('No active template found for this message type.'); return; }
    const body = personaliseMessage(template.body_template, prospect);
    if (type === 'initial') {
      if (draft) {
        await updateMessage(draft.id, { body });
        setDraftBody(body);
        setDraft((d) => d ? { ...d, body } : d);
      } else {
        const msg = await createMessage({
          prospect_id: prospect.id, message_type: 'initial', body, status: 'draft',
          subject_line: null, personalisation_notes: `Generated from template: ${template.name}`,
          approved_at: null, sent_at: null, copied_to_clipboard_at: null,
        });
        setDraft(msg);
        setDraftBody(body);
      }
    } else {
      if (followUpDraft) {
        await updateMessage(followUpDraft.id, { body });
        setFollowUpBody(body);
        setFollowUpDraft((d) => d ? { ...d, body } : d);
      } else {
        const msg = await createMessage({
          prospect_id: prospect.id, message_type: 'follow_up', body, status: 'draft',
          subject_line: null, personalisation_notes: `Generated from template: ${template.name}`,
          approved_at: null, sent_at: null, copied_to_clipboard_at: null,
        });
        setFollowUpDraft(msg);
        setFollowUpBody(body);
      }
    }
  };

  const handleCopyFollowUp = async () => {
    if (!followUpDraft) return;
    await navigator.clipboard.writeText(followUpBody);
    flashFollowUp();
    await markCopied(followUpDraft.id);
  };

  const handleMarkFollowUpSent = async () => {
    if (!prospect || !followUpDraft) return;
    setMarkingFollowUp(true);
    try {
      await markSent(followUpDraft.id);
      await onUpdateStatus(prospect.id, 'follow_up_sent', { follow_up_sent_at: new Date().toISOString() });
      setFollowUpDraft((d) => d ? { ...d, status: 'sent' } : d);
    } finally {
      setMarkingFollowUp(false);
    }
  };

  const handleLogReply = async (data: Parameters<typeof logReply>[0]) => {
    if (!prospect) return;
    const reply = await logReply(data);
    setReplies((prev) => [reply, ...prev]);
    await onUpdateStatus(prospect.id, 'replied', { last_reply_at: new Date().toISOString() });
  };

  const handleStatusAction = async (next: ProspectStatus) => {
    if (!prospect) return;
    const extra: Partial<LinkedInProspect> = {};
    if (next === 'converted') extra.converted_at = new Date().toISOString();
    await onUpdateStatus(prospect.id, next, extra);
  };

  // ── Computed ─────────────────────────────────────────────────────────────────
  const followUpDue = prospect ? isFollowUpDue(prospect) : false;
  const daysSince = prospect ? daysSinceSent(prospect) : null;
  const currentStatusIdx = prospect ? statusIndex(prospect.status) : -1;
  const draftSent = draft?.status === 'sent';

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <button
          type="button"
          aria-label="Close panel"
          className="fixed inset-0 z-40 bg-black/20 cursor-default border-0 p-0"
          onClick={onClose}
        />
      )}

      {/* Panel */}
      <div
        className={`fixed top-0 right-0 bottom-0 z-50 flex flex-col w-full max-w-xl bg-white shadow-2xl border-l border-slate-200 transition-transform duration-300 ease-in-out ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {prospect && (
          <>
            {/* Header */}
            <div className="flex items-start justify-between px-6 py-4 border-b border-gray-100">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <h2 className="text-base font-semibold text-navy-900 truncate">{prospect.full_name}</h2>
                  <a
                    href={prospect.linkedin_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-gray-500 hover:text-navy-600 flex-shrink-0"
                    title="Open LinkedIn profile"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </a>
                </div>
                <p className="text-sm text-gray-500 truncate">{prospect.job_title} · {prospect.company_name}</p>
                <div className="flex items-center gap-2 mt-1.5">
                  {prospect.corridor_relevance && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-teal-50 text-teal-700">
                      {prospect.corridor_relevance}
                    </span>
                  )}
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_MAP[prospect.status]}`}>
                    {STATUS_LABELS[prospect.status] ?? prospect.status}
                  </span>
                </div>
              </div>
              <button
                onClick={onClose}
                className="ml-4 p-1.5 text-gray-500 hover:text-gray-600 rounded hover:bg-gray-100 transition-colors flex-shrink-0"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Status action footer */}
            <StatusActionBar prospect={prospect} onAction={handleStatusAction} />

            {/* Scrollable body */}
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
              {error && <Alert variant="error">{error}</Alert>}

              {/* Status timeline */}
              <section>
                <div className="flex items-center gap-0">
                  {STATUS_STEPS.map((step, i) => {
                    const done = statusIndex(step.key) <= currentStatusIdx;
                    const isLast = i === STATUS_STEPS.length - 1;
                    const nextKey = !isLast ? STATUS_STEPS[i + 1]?.key : undefined;
                    const connectorDone = nextKey !== undefined && statusIndex(nextKey) <= currentStatusIdx;
                    return (
                      <React.Fragment key={step.key}>
                        <div className="flex flex-col items-center">
                          <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold border-2 ${
                            done
                              ? 'bg-navy-700 border-navy-700 text-white'
                              : 'bg-white border-gray-300 text-gray-500'
                          }`}>
                            {done ? '✓' : i + 1}
                          </div>
                          <span className={`text-xs mt-1 whitespace-nowrap ${done ? 'text-navy-700 font-medium' : 'text-gray-500'}`}>
                            {step.label}
                          </span>
                        </div>
                        {!isLast && (
                          <div className={`flex-1 h-0.5 mb-4 mx-1 ${connectorDone ? 'bg-navy-700' : 'bg-gray-200'}`} />
                        )}
                      </React.Fragment>
                    );
                  })}
                </div>
              </section>

              {/* Notes */}
              <section>
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Notes</h3>
                <Textarea
                  value={notes}
                  onChange={setNotes}
                  onBlur={handleSaveNotes}
                  placeholder="Add context about this prospect…"
                  rows={2}
                />
                {savingNotes && <p className="text-xs text-gray-500 mt-1">Saving…</p>}
              </section>

              {/* Message draft */}
              <section>
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                  {draftSent ? 'Message sent' : 'Current draft'}
                </h3>
                {loadingDraft ? (
                  <p className="text-sm text-gray-500">Loading draft…</p>
                ) : (
                  <>
                    <Textarea
                      value={draftBody}
                      onChange={setDraftBody}
                      onBlur={handleSaveDraftBody}
                      placeholder="No draft yet — click Regenerate to create one."
                      rows={8}
                      disabled={draftSent}
                    />
                    {draftBody && isOverLinkedInLimit(draftBody) && (
                      <p className="text-xs text-amber-600 mt-1">
                        ⚠ {linkedInCharCount(draftBody)} chars — LinkedIn DM limit is ~300. Consider trimming.
                      </p>
                    )}
                    <div className="flex items-center gap-2 mt-2">
                      <button
                        onClick={() => handleRegenerateDraft('initial')}
                        className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-navy-700 border border-gray-200 rounded px-2 py-1.5 transition-colors"
                        disabled={draftSent}
                      >
                        <RefreshCw className="w-3 h-3" /> Regenerate
                      </button>
                      <button
                        onClick={handleCopyDraft}
                        disabled={!draftBody}
                        className="flex items-center gap-1.5 text-xs font-medium text-navy-700 hover:text-navy-900 border border-navy-200 bg-navy-50 rounded px-2 py-1.5 transition-colors disabled:opacity-40"
                      >
                        {copiedDraft ? <><Check className="w-3 h-3 text-green-500" /> Copied!</> : <><Clipboard className="w-3 h-3" /> Copy to clipboard</>}
                      </button>
                      {!draftSent && (
                        <button
                          onClick={handleMarkSent}
                          disabled={markingSent || !draft}
                          className="flex items-center gap-1.5 text-xs font-medium text-white bg-navy-700 hover:bg-navy-800 rounded px-2 py-1.5 transition-colors disabled:opacity-50 ml-auto"
                        >
                          {markingSent ? 'Marking…' : '✓ Mark as sent'}
                        </button>
                      )}
                    </div>
                    {draftSent && prospect.message_sent_at && (
                      <p className="text-xs text-gray-500 mt-1">
                        Sent {new Date(prospect.message_sent_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
                      </p>
                    )}
                  </>
                )}
              </section>

              {/* Follow-up section */}
              {(followUpDue || followUpDraft) && (
                <section className={`rounded-lg p-4 border ${followUpDue ? 'bg-amber-50 border-amber-200' : 'bg-gray-50 border-gray-200'}`}>
                  <h3 className="text-xs font-semibold uppercase tracking-wide mb-2 text-amber-700">
                    {followUpDue
                      ? `Follow-up overdue · ${daysSince}d since sent`
                      : 'Follow-up'}
                  </h3>
                  <Textarea
                    value={followUpBody}
                    onChange={setFollowUpBody}
                    onBlur={async () => {
                      if (followUpDraft) await updateMessage(followUpDraft.id, { body: followUpBody });
                    }}
                    placeholder="No follow-up draft yet."
                    rows={6}
                    disabled={followUpDraft?.status === 'sent'}
                  />
                  {followUpBody && isOverLinkedInLimit(followUpBody) && (
                    <p className="text-xs text-amber-600 mt-1">
                      ⚠ {linkedInCharCount(followUpBody)} chars — LinkedIn DM limit is ~300.
                    </p>
                  )}
                  <div className="flex items-center gap-2 mt-2">
                    <button
                      onClick={() => handleRegenerateDraft('follow_up')}
                      className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-navy-700 border border-gray-200 rounded px-2 py-1.5 bg-white transition-colors"
                      disabled={followUpDraft?.status === 'sent'}
                    >
                      <RefreshCw className="w-3 h-3" /> {followUpDraft ? 'Regenerate' : 'Generate draft'}
                    </button>
                    <button
                      onClick={handleCopyFollowUp}
                      disabled={!followUpBody}
                      className="flex items-center gap-1.5 text-xs font-medium text-navy-700 hover:text-navy-900 border border-navy-200 bg-white rounded px-2 py-1.5 transition-colors disabled:opacity-40"
                    >
                      {copiedFollowUp ? <><Check className="w-3 h-3 text-green-500" /> Copied!</> : <><Clipboard className="w-3 h-3" /> Copy</>}
                    </button>
                    {followUpDraft?.status !== 'sent' && (
                      <button
                        onClick={handleMarkFollowUpSent}
                        disabled={markingFollowUp || !followUpDraft}
                        className="flex items-center gap-1.5 text-xs font-medium text-white bg-navy-700 hover:bg-navy-800 rounded px-2 py-1.5 transition-colors disabled:opacity-50 ml-auto"
                      >
                        {markingFollowUp ? 'Marking…' : '✓ Mark follow-up sent'}
                      </button>
                    )}
                  </div>
                </section>
              )}

              {/* Generate follow-up draft when not yet due but user wants it */}
              {!followUpDue && !followUpDraft && prospect.status === 'message_sent' && (
                <section>
                  <button
                    onClick={() => handleRegenerateDraft('follow_up')}
                    className="text-xs text-gray-500 hover:text-navy-700 underline"
                  >
                    Generate follow-up draft early
                  </button>
                </section>
              )}

              {/* Reply thread */}
              <section>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    Reply thread ({replies.length})
                  </h3>
                  <button
                    onClick={() => setShowReplyModal(true)}
                    className="text-xs text-navy-600 hover:text-navy-800 font-medium"
                  >
                    + Log a reply
                  </button>
                </div>
                {replies.length === 0 ? (
                  <p className="text-sm text-gray-500">No replies logged yet.</p>
                ) : (
                  <div className="space-y-3">
                    {replies.map((r) => (
                      <div key={r.id} className="bg-gray-50 rounded-lg p-3 text-sm">
                        <div className="flex items-center justify-between mb-1">
                          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${SENTIMENT_MAP[r.sentiment]}`}>
                            {SENTIMENT_LABELS[r.sentiment]}
                          </span>
                          <span className="text-xs text-gray-500">
                            {new Date(r.replied_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                          </span>
                        </div>
                        {r.reply_text && <p className="text-gray-700 text-xs whitespace-pre-wrap">{r.reply_text}</p>}
                        {r.next_action && (
                          <p className="mt-1.5 text-xs text-navy-700 font-medium">
                            → {r.next_action}
                            {r.next_action_due && (
                              <span className="text-gray-500 font-normal ml-1">
                                by {new Date(r.next_action_due).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                              </span>
                            )}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </div>
          </>
        )}
      </div>

      {prospect && (
        <ReplyLogModal
          open={showReplyModal}
          onClose={() => setShowReplyModal(false)}
          prospectId={prospect.id}
          messageId={draft?.id ?? null}
          onSave={handleLogReply}
        />
      )}
    </>
  );
}

// ── Status action bar ─────────────────────────────────────────────────────────

const TERMINAL_STATUSES: ProspectStatus[] = ['converted', 'not_interested', 'archived'];
const ACTIONABLE_STATUSES: ProspectStatus[] = ['message_sent', 'replied', 'follow_up_sent'];

function StatusActionBar({
  prospect,
  onAction,
}: {
  prospect: LinkedInProspect;
  onAction: (status: ProspectStatus) => Promise<void>;
}): React.ReactElement | null {
  const [acting, setActing] = useState<ProspectStatus | null>(null);

  const act = async (next: ProspectStatus) => {
    setActing(next);
    try { await onAction(next); } finally { setActing(null); }
  };

  if (ACTIONABLE_STATUSES.includes(prospect.status)) {
    return (
      <div className="flex items-center gap-2 px-6 py-3 border-b border-gray-100 bg-gray-50">
        <span className="text-xs text-gray-500 mr-auto">Move to:</span>
        <button
          onClick={() => act('converted')}
          disabled={acting !== null}
          className="text-xs font-medium px-3 py-1.5 rounded-lg bg-teal-600 text-white hover:bg-teal-700 disabled:opacity-50 transition-colors"
        >
          {acting === 'converted' ? '…' : '✓ Converted'}
        </button>
        <button
          onClick={() => act('not_interested')}
          disabled={acting !== null}
          className="text-xs font-medium px-3 py-1.5 rounded-lg border border-red-200 text-red-600 hover:bg-red-50 disabled:opacity-50 transition-colors"
        >
          {acting === 'not_interested' ? '…' : '✗ Not interested'}
        </button>
        <button
          onClick={() => act('archived')}
          disabled={acting !== null}
          className="text-xs font-medium px-3 py-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-100 disabled:opacity-50 transition-colors"
        >
          {acting === 'archived' ? '…' : 'Archive'}
        </button>
      </div>
    );
  }

  if (TERMINAL_STATUSES.includes(prospect.status)) {
    return (
      <div className="flex items-center gap-2 px-6 py-3 border-b border-gray-100 bg-gray-50">
        <span className="text-xs text-gray-500 mr-auto">This prospect is {prospect.status.replace('_', ' ')}.</span>
        <button
          onClick={() => act('flagged')}
          disabled={acting !== null}
          className="text-xs font-medium px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 hover:bg-white disabled:opacity-50 transition-colors"
        >
          {acting === 'flagged' ? '…' : '↩ Restore to active'}
        </button>
      </div>
    );
  }

  return null;
}

// ── Style maps ────────────────────────────────────────────────────────────────
const STATUS_LABELS: Record<ProspectStatus, string> = {
  flagged:         'Flagged',
  message_drafted: 'Drafted',
  message_sent:    'Sent',
  replied:         'Replied',
  follow_up_sent:  'Follow-up sent',
  converted:       'Converted',
  not_interested:  'Not interested',
  archived:        'Archived',
};

export const STATUS_MAP: Record<ProspectStatus, string> = {
  flagged:         'bg-gray-100 text-gray-600',
  message_drafted: 'bg-blue-50 text-blue-700',
  message_sent:    'bg-navy-50 text-navy-800',
  replied:         'bg-green-50 text-green-700',
  follow_up_sent:  'bg-yellow-50 text-yellow-700',
  converted:       'bg-teal-50 text-teal-700',
  not_interested:  'bg-red-50 text-red-600',
  archived:        'bg-gray-100 text-gray-500',
};

const SENTIMENT_LABELS: Record<string, string> = {
  positive: 'Positive', neutral: 'Neutral', negative: 'Negative', not_set: 'Not sure',
};

const SENTIMENT_MAP: Record<string, string> = {
  positive: 'bg-green-100 text-green-700',
  neutral:  'bg-gray-100 text-gray-600',
  negative: 'bg-red-100 text-red-700',
  not_set:  'bg-gray-50 text-gray-500',
};
