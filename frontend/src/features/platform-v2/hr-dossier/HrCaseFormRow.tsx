/**
 * [P4-2] HrCaseFormRow — one row in the HR Dossier panel.
 *
 * Collapsed: code badge | name | progress bar | status badge | flag indicator | chevron
 * Expanded:  status banner → History log → Comment thread → [Status dropdown] [Flag button]
 *
 * Patterned on CaseFormCard.tsx but with HR-specific actions.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Checkbox } from '../../../components/antigravity/Checkbox';
import { FileInput } from '../../../components/antigravity/FileInput';
import { Input } from '../../../components/antigravity/Input';
import { Button } from '../../../components/antigravity/Button';
import { Badge, Card } from '../../../components/antigravity';
import type {
  CaseFormStatus,
  CaseFormSummary,
  FormComment,
  FormEvent,
} from '../../../api/dossier';
import { adhocFormsAPI, commentsAPI, eventsAPI, flagAPI } from '../../../api/dossier';

// ── Status display helpers (shared with CaseFormCard) ────────────────────────

type DisplayStatus = CaseFormStatus | 'blocked';

function displayStatus(form: CaseFormSummary): DisplayStatus {
  if (
    form.blocker_form_id &&
    form.status !== 'submitted' &&
    form.status !== 'approved' &&
    form.status !== 'rejected'
  ) {
    return 'blocked';
  }
  return form.status;
}

const STATUS_LABEL: Record<DisplayStatus, string> = {
  not_started: 'Not started',
  auto_filled: 'AI-prefilled',
  in_progress: 'In progress',
  pending_doc: 'Waiting on doc',
  ready: 'Ready to submit',
  blocked: 'Blocked',
  submitted: 'Submitted',
  approved: 'Approved',
  rejected: 'Rejected',
};

const STATUS_BADGE_VARIANT: Record<DisplayStatus, 'success' | 'warning' | 'error' | 'info' | 'neutral'> = {
  not_started: 'neutral',
  auto_filled: 'warning',
  in_progress: 'info',
  pending_doc: 'neutral',
  ready: 'success',
  blocked: 'error',
  submitted: 'info',
  approved: 'success',
  rejected: 'error',
};

function statusBannerTone(s: DisplayStatus): string {
  if (s === 'approved') return 'bg-emerald-50 border-emerald-200 text-emerald-900';
  if (s === 'rejected') return 'bg-rose-50 border-rose-200 text-rose-900';
  if (s === 'ready')    return 'bg-emerald-50 border-emerald-200 text-emerald-900';
  if (s === 'blocked')  return 'bg-rose-50 border-rose-200 text-rose-900';
  if (s === 'submitted') return 'bg-blue-50 border-blue-200 text-blue-900';
  if (s === 'in_progress' || s === 'auto_filled') return 'bg-amber-50 border-amber-200 text-amber-900';
  return 'bg-slate-50 border-slate-200 text-slate-700';
}

function statusBannerText(form: CaseFormSummary): string {
  const s = displayStatus(form);
  if (s === 'blocked')   return form.blocker_form_code ? `Blocked — awaiting ${form.blocker_form_code}` : 'Blocked — awaiting upstream form';
  if (s === 'auto_filled') return `AI pre-filled ${form.fields_summary.filled_by_ai} fields · ${form.fields_summary.missing_required} still need input`;
  if (s === 'in_progress') return `In progress — ${form.completion_pct}% complete`;
  if (s === 'ready')     return 'Ready for submission';
  if (s === 'submitted') return form.receipt_ref ? `Submitted · ref ${form.receipt_ref}` : 'Submitted — awaiting authority response';
  if (s === 'approved')  return 'Approved';
  if (s === 'rejected')  return 'Rejected — return to employee for corrections';
  return STATUS_LABEL[s];
}

function deadlineChip(deadline: string | null): { tone: string; text: string } | null {
  if (!deadline) return null;
  const due = new Date(deadline);
  if (Number.isNaN(due.getTime())) return null;
  const diffDays = Math.ceil((due.getTime() - Date.now()) / 86400000);
  const label = due.toLocaleDateString();
  if (diffDays < 0)  return { tone: 'bg-rose-100 text-rose-700 border-rose-200',   text: `Overdue · ${label}` };
  if (diffDays <= 7) return { tone: 'bg-amber-100 text-amber-700 border-amber-200', text: `${diffDays}d · ${label}` };
  return { tone: 'bg-slate-100 text-slate-600 border-slate-200', text: label };
}

// ── HR-specific status transitions ────────────────────────────────────────────
// 'submitted' and 'rejected' are handled by dedicated modals, not direct clicks.

const HR_STATUS_OPTIONS: Array<{ value: CaseFormStatus; label: string; needsModal?: boolean }> = [
  { value: 'not_started', label: 'Reset to Not started' },
  { value: 'ready',       label: 'Mark Ready' },
  { value: 'submitted',   label: 'Mark Submitted', needsModal: true },
  { value: 'approved',    label: 'Approve' },
  { value: 'rejected',    label: 'Reject',          needsModal: true },
];

// ── Component ────────────────────────────────────────────────────────────────

export interface HrCaseFormRowProps {
  form: CaseFormSummary;
  /** Called by parent to refresh the form list after a status/flag change */
  onRefresh: () => void;
}

export const HrCaseFormRow: React.FC<HrCaseFormRowProps> = ({ form, onRefresh }) => {
  const [expanded, setExpanded]         = useState(false);
  const [comments, setComments]         = useState<FormComment[]>([]);
  const [events, setEvents]             = useState<FormEvent[]>([]);
  const [loadingData, setLoadingData]   = useState(false);
  const [commentText, setCommentText]   = useState('');
  const [submittingComment, setSubmittingComment] = useState(false);
  const [commentError, setCommentError] = useState<string | null>(null);
  const [statusNote, setStatusNote]     = useState('');
  const [statusError, setStatusError]   = useState<string | null>(null);
  const [flagInput, setFlagInput]       = useState('');
  const [showFlagInput, setShowFlagInput] = useState(false);
  const [flagError, setFlagError]       = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  // [P4-5] Submit modal state
  const [showSubmitModal, setShowSubmitModal]     = useState(false);
  const [submitReceiptRef, setSubmitReceiptRef]   = useState('');
  const [submitNote, setSubmitNote]               = useState('');
  const [submitError, setSubmitError]             = useState<string | null>(null);

  // [P4-5] Reject modal state
  const [showRejectModal, setShowRejectModal]     = useState(false);
  const [rejectReason, setRejectReason]           = useState('');
  const [reopenForCorrection, setReopenForCorrection] = useState(true);
  const [rejectError, setRejectError]             = useState<string | null>(null);

  const isFlagged = !!(form as CaseFormSummary & { flag_note?: string }).flag_note;
  const isAdhoc = !!form.is_adhoc;

  // [P4-3] Replace-PDF state for ad-hoc forms
  const [replacingPdf, setReplacingPdf] = useState(false);
  const [replacePdfError, setReplacePdfError] = useState<string | null>(null);

  const loadExpandedData = useCallback(async () => {
    setLoadingData(true);
    try {
      const [c, e] = await Promise.all([
        commentsAPI.list(form.case_id, form.id),
        eventsAPI.list(form.case_id, form.id),
      ]);
      setComments(c);
      setEvents(e);
    } catch {
      // non-blocking — just show empty
    } finally {
      setLoadingData(false);
    }
  }, [form.case_id, form.id]);

  useEffect(() => {
    if (expanded) void loadExpandedData();
  }, [expanded, loadExpandedData]);

  // ── Actions ──────────────────────────────────────────────────────────────

  const handlePostComment = async () => {
    if (!commentText.trim()) return;
    setSubmittingComment(true);
    setCommentError(null);
    try {
      const created = await commentsAPI.create(form.case_id, form.id, commentText.trim());
      setComments((prev) => [...prev, created]);
      setCommentText('');
    } catch {
      setCommentError('Failed to post comment.');
    } finally {
      setSubmittingComment(false);
    }
  };

  const handleStatusChange = async (newStatus: string) => {
    setActionLoading(true);
    setStatusError(null);
    try {
      const resp = await fetch(`/api/cases/${form.case_id}/forms/${form.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ status: newStatus, note: statusNote.trim() || undefined }),
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail?.error || body.detail || `Status ${resp.status}`);
      }
      setStatusNote('');
      onRefresh();
      void loadExpandedData();
    } catch (e) {
      setStatusError(e instanceof Error ? e.message : 'Failed to update status.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleFlag = async () => {
    setActionLoading(true);
    setFlagError(null);
    try {
      await flagAPI.patch(form.case_id, form.id, flagInput.trim() || null);
      setShowFlagInput(false);
      setFlagInput('');
      onRefresh();
      void loadExpandedData();
    } catch {
      setFlagError('Failed to update flag.');
    } finally {
      setActionLoading(false);
    }
  };

  // ── [P4-3] Replace PDF (ad-hoc forms only) ────────────────────────────────

  const handleReplacePdf = async (file: File | null | undefined) => {
    if (!file) return;
    setReplacingPdf(true);
    setReplacePdfError(null);
    try {
      await adhocFormsAPI.replacePdf(form.case_id, form.id, file);
      onRefresh();
      void loadExpandedData();
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      setReplacePdfError(err.response?.data?.detail || err.message || 'Failed to replace PDF.');
    } finally {
      setReplacingPdf(false);
    }
  };

  // ── [P4-5] Submit modal confirm ───────────────────────────────────────────

  const handleSubmitConfirm = async () => {
    if (!submitReceiptRef.trim()) {
      setSubmitError('Receipt reference is required.');
      return;
    }
    setActionLoading(true);
    setSubmitError(null);
    try {
      const resp = await fetch(`/api/cases/${form.case_id}/forms/${form.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          status: 'submitted',
          receipt_ref: submitReceiptRef.trim(),
          note: submitNote.trim() || undefined,
        }),
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail?.error || body.detail || `Status ${resp.status}`);
      }
      setShowSubmitModal(false);
      setSubmitReceiptRef('');
      setSubmitNote('');
      onRefresh();
      void loadExpandedData();
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : 'Failed to mark as submitted.');
    } finally {
      setActionLoading(false);
    }
  };

  // ── [P4-5] Reject modal confirm ───────────────────────────────────────────

  const handleRejectConfirm = async () => {
    if (!rejectReason.trim()) {
      setRejectError('Rejection reason is required.');
      return;
    }
    setActionLoading(true);
    setRejectError(null);
    try {
      const resp = await fetch(`/api/cases/${form.case_id}/forms/${form.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          status: 'rejected',
          rejection_reason: rejectReason.trim(),
          note: rejectReason.trim(),
        }),
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail?.error || body.detail || `Status ${resp.status}`);
      }
      // If re-open: immediately transition to in_progress so the employee can correct
      if (reopenForCorrection) {
        await fetch(`/api/cases/${form.case_id}/forms/${form.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ status: 'not_started', note: 'Re-opened for employee correction' }),
        });
      }
      setShowRejectModal(false);
      setRejectReason('');
      setReopenForCorrection(true);
      onRefresh();
      void loadExpandedData();
    } catch (e) {
      setRejectError(e instanceof Error ? e.message : 'Failed to reject form.');
    } finally {
      setActionLoading(false);
    }
  };

  // ── Derived display values ────────────────────────────────────────────────

  const dStatus    = displayStatus(form);
  const chip       = deadlineChip(form.deadline);
  const bannerTone = statusBannerTone(dStatus);
  const bannerText = statusBannerText(form);
  const total      = form.fields_summary.total;
  const filled     = form.fields_summary.filled_by_ai + form.fields_summary.filled_by_human;
  const pct        = total > 0 ? Math.round((filled / total) * 100) : form.completion_pct;

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <Card padding="lg" className={`transition-shadow hover:shadow-sm ${isFlagged ? 'ring-1 ring-amber-300' : ''}`}>
      {/* ── Collapsed header row ─────────────────────────────────────────── */}
      <Button unstyled
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="w-full text-left grid grid-cols-12 items-center gap-3"
      >
        {/* Code + name */}
        <div className="col-span-5 flex items-start gap-2 min-w-0">
          {isAdhoc ? (
            <span className="shrink-0">
              <Badge variant="info" size="sm">Custom</Badge>
            </span>
          ) : (
            <span className="shrink-0 inline-flex items-center px-2 py-0.5 rounded font-mono text-[11px] font-semibold bg-slate-100 text-slate-700 border border-slate-200">
              {form.template.code}
            </span>
          )}
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium text-slate-900 truncate">{form.template.name}</div>
            <div className="text-xs text-slate-500 truncate">
              {isAdhoc
                ? (form.template.authority_name || 'Ad-hoc document')
                : <>{form.template.authority_code && `${form.template.authority_code} · `}v{form.template.version}</>}
            </div>
          </div>
        </div>

        {/* Progress bar — ad-hoc forms have no fields, so show the doc state instead */}
        <div className="col-span-4">
          {isAdhoc ? (
            <span className="text-xs text-slate-500">
              {form.original_file_url ? 'PDF attached' : 'No PDF attached'}
            </span>
          ) : (
            <>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-slate-500">{filled}/{total} fields</span>
                <span className="text-xs font-medium text-slate-700">{pct}%</span>
              </div>
              <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    dStatus === 'blocked'
                      ? 'bg-rose-400'
                      : dStatus === 'ready' || dStatus === 'approved'
                        ? 'bg-emerald-500'
                        : 'bg-blue-500'
                  }`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </>
          )}
        </div>

        {/* Status badge + flag indicator + deadline chip + chevron */}
        <div className="col-span-3 flex items-center justify-end gap-2">
          {isFlagged && (
            <span title="Flagged" className="text-amber-500 shrink-0">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M3 6a1 1 0 011-1h10a1 1 0 01.832 1.555L11.5 11l3.332 4.445A1 1 0 0114 17H4a1 1 0 01-1-1V6z" clipRule="evenodd"/>
              </svg>
            </span>
          )}
          {chip && (
            <span className={`hidden md:inline-flex items-center px-2 py-0.5 rounded border text-[11px] font-medium ${chip.tone}`}>
              {chip.text}
            </span>
          )}
          <Badge variant={STATUS_BADGE_VARIANT[dStatus]}>{STATUS_LABEL[dStatus]}</Badge>
          <svg
            className={`w-4 h-4 text-slate-400 transition-transform shrink-0 ${expanded ? 'rotate-180' : ''}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </Button>

      {/* ── Expanded panel ──────────────────────────────────────────────── */}
      {expanded && (
        <div className="mt-4 space-y-4">
          {/* Status banner */}
          <div className={`rounded border px-3 py-2 text-sm ${bannerTone}`}>{bannerText}</div>

          {/* [WS1] Content-honesty notice — representative scaffolding until an
              authorised human verifies it against the issuing authority. HR sees
              this too so they don't relay unverified requirements to employees. */}
          {form.template.verification_status !== 'verified' && !isAdhoc && (
            <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 flex items-start gap-2">
              <svg className="w-3.5 h-3.5 mt-0.5 shrink-0 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
              </svg>
              <span>
                Indicative guidance — verify the current requirements with{' '}
                <span className="font-medium">
                  {form.template.authority_name ?? 'the issuing authority'}
                </span>{' '}
                before advising the employee.
              </span>
            </div>
          )}

          {/* [P4-3] Ad-hoc notes */}
          {isAdhoc && form.notes && (
            <div className="rounded border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Notes</span>
              <p className="mt-0.5 whitespace-pre-wrap">{form.notes}</p>
            </div>
          )}

          {/* Loading indicator for comments + events */}
          {loadingData && (
            <p className="text-xs text-slate-400">Loading history…</p>
          )}

          {/* ── History timeline ──────────────────────────────────────── */}
          {!loadingData && events.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">History</h3>
              <ol className="space-y-2">
                {events.map((ev) => (
                  <li key={ev.id} className="flex items-start gap-2 text-xs text-slate-600">
                    <span className="mt-0.5 w-2 h-2 rounded-full bg-slate-300 shrink-0" />
                    <div>
                      <span className="text-slate-400">
                        {new Date(ev.created_at).toLocaleString()} ·{' '}
                      </span>
                      {ev.event_type === 'status_change' ? (
                        <>
                          <span className="font-medium text-slate-700">
                            {ev.from_status} → {ev.to_status}
                          </span>
                          {ev.actor_name && <span className="text-slate-400"> by {ev.actor_name}</span>}
                          {ev.note && <span className="ml-1 italic text-slate-500">&quot;{ev.note}&quot;</span>}
                        </>
                      ) : ev.event_type === 'flagged' ? (
                        <>
                          <span className="font-medium text-amber-600">Flagged</span>
                          {ev.actor_name && <span className="text-slate-400"> by {ev.actor_name}</span>}
                          {ev.note && <span className="ml-1 italic text-slate-500">&quot;{ev.note}&quot;</span>}
                        </>
                      ) : ev.event_type === 'unflagged' ? (
                        <>
                          <span className="font-medium text-slate-600">Flag cleared</span>
                          {ev.actor_name && <span className="text-slate-400"> by {ev.actor_name}</span>}
                        </>
                      ) : (
                        <span className="font-medium text-slate-700">{ev.event_type}</span>
                      )}
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          )}

          {/* ── Comment thread ────────────────────────────────────────── */}
          <div>
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Comments</h3>
            {!loadingData && comments.length === 0 && (
              <p className="text-xs text-slate-400 mb-2">No comments yet.</p>
            )}
            {!loadingData && comments.map((c) => (
              <div key={c.id} className="mb-2 rounded bg-slate-50 border border-slate-100 px-3 py-2">
                <div className="flex items-center justify-between mb-0.5">
                  <span className="text-xs font-medium text-slate-700">{c.author_name ?? 'Unknown'}</span>
                  <span className="text-[10px] text-slate-400">
                    {new Date(c.created_at).toLocaleString()}
                  </span>
                </div>
                <p className="text-xs text-slate-600">{c.content}</p>
              </div>
            ))}

            {/* New comment input */}
            <div className="flex gap-2 mt-1">
              <Input unstyled
                type="text"
                value={commentText}
                onChange={(v) => setCommentText(v)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && void handlePostComment()}
                placeholder="Add a comment…"
                className="flex-1 rounded border border-slate-200 px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-[#0b2b43]"
              />
              <Button unstyled
                type="button"
                onClick={() => void handlePostComment()}
                disabled={submittingComment || !commentText.trim()}
                className="px-3 py-1 rounded text-xs font-medium bg-[#0b2b43] text-white disabled:opacity-40"
              >
                Post
              </Button>
            </div>
            {commentError && <p className="mt-1 text-xs text-rose-600">{commentError}</p>}
          </div>

          {/* ── HR Actions ───────────────────────────────────────────── */}
          <div className="border-t border-slate-100 pt-3 space-y-2">
            {/* [P4-3] Replace PDF — ad-hoc forms only */}
            {isAdhoc && (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium text-slate-600 shrink-0">Document:</span>
                {form.original_file_url ? (
                  <a
                    href={form.original_file_url}
                    target="_blank"
                    rel="noreferrer"
                    className="px-2.5 py-1 rounded text-xs font-medium border border-slate-200 text-slate-700 hover:bg-slate-50"
                  >
                    View PDF
                  </a>
                ) : (
                  <span className="text-xs text-slate-400">No PDF attached</span>
                )}
                <label
                  className={`px-2.5 py-1 rounded text-xs font-medium border cursor-pointer transition-colors
                    ${replacingPdf
                      ? 'bg-slate-100 text-slate-400 border-slate-200 cursor-wait'
                      : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'}`}
                >
                  {replacingPdf ? 'Uploading…' : 'Replace PDF'}
                  <FileInput
                    accept="application/pdf"
                    className="hidden"
                    disabled={replacingPdf}
                    onChange={(e) => {
                      void handleReplacePdf(e.target.files?.[0]);
                      e.target.value = '';
                    }}
                  />
                </label>
                {replacePdfError && <span className="text-xs text-rose-600">{replacePdfError}</span>}
              </div>
            )}

            {/* Status change */}
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-medium text-slate-600 shrink-0">Change status:</span>
              <div className="flex flex-wrap gap-1.5">
                {HR_STATUS_OPTIONS.map((opt) => (
                  <Button unstyled
                    key={opt.value}
                    type="button"
                    disabled={actionLoading || opt.value === form.status}
                    onClick={() => {
                      if (opt.value === 'submitted') { setShowSubmitModal(true); return; }
                      if (opt.value === 'rejected')  { setShowRejectModal(true);  return; }
                      void handleStatusChange(opt.value);
                    }}
                    className={`px-2.5 py-1 rounded text-xs font-medium border transition-colors
                      ${opt.value === form.status
                        ? 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed'
                        : opt.value === 'approved'
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100'
                          : opt.value === 'rejected'
                            ? 'bg-rose-50 text-rose-700 border-rose-200 hover:bg-rose-100'
                            : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
                      }`}
                  >
                    {opt.label}
                  </Button>
                ))}
              </div>
            </div>

            {/* Optional status note (for non-modal transitions only) */}
            <Input unstyled
              type="text"
              value={statusNote}
              onChange={(v) => setStatusNote(v)}
              placeholder="Note for status change (optional)"
              className="w-full rounded border border-slate-200 px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-[#0b2b43]"
            />
            {statusError && <p className="text-xs text-rose-600">{statusError}</p>}

            {/* Flag toggle */}
            <div className="flex items-center gap-2 flex-wrap">
              <Button unstyled
                type="button"
                onClick={() => {
                  setShowFlagInput((v) => !v);
                  setFlagInput(isFlagged ? '' : '');
                }}
                className={`flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium border transition-colors
                  ${isFlagged
                    ? 'bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100'
                    : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                  }`}
              >
                <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M3 6a1 1 0 011-1h10a1 1 0 01.832 1.555L11.5 11l3.332 4.445A1 1 0 0114 17H4a1 1 0 01-1-1V6z" clipRule="evenodd"/>
                </svg>
                {isFlagged ? 'Clear flag' : 'Flag'}
              </Button>

              {showFlagInput && !isFlagged && (
                <>
                  <Input unstyled
                    type="text"
                    value={flagInput}
                    onChange={(v) => setFlagInput(v)}
                    placeholder="Flag reason…"
                    className="flex-1 min-w-[160px] rounded border border-slate-200 px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-amber-400"
                  />
                  <Button unstyled
                    type="button"
                    disabled={actionLoading || !flagInput.trim()}
                    onClick={() => void handleFlag()}
                    className="px-2.5 py-1 rounded text-xs font-medium bg-amber-500 text-white disabled:opacity-40"
                  >
                    Set flag
                  </Button>
                </>
              )}

              {isFlagged && showFlagInput && (
                <Button unstyled
                  type="button"
                  disabled={actionLoading}
                  onClick={() => void handleFlag()}
                  className="px-2.5 py-1 rounded text-xs font-medium bg-rose-500 text-white disabled:opacity-40"
                >
                  Confirm clear
                </Button>
              )}
            </div>
            {flagError && <p className="text-xs text-rose-600">{flagError}</p>}
          </div>
        </div>
      )}

      {/* ── [P4-5] Submit modal ──────────────────────────────────────────── */}
      {showSubmitModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6 space-y-4">
            <h2 className="text-base font-semibold text-slate-900">Mark as Submitted</h2>
            <p className="text-sm text-slate-600">
              Enter the receipt or reference number from{' '}
              <strong>{form.template.authority_name ?? form.template.authority_code ?? 'the authority'}</strong>.
            </p>
            <div className="space-y-2">
              <label htmlFor="hcf-receipt-reference" className="block text-xs font-medium text-slate-700">
                Receipt / Reference <span className="text-rose-500">*</span>
              </label>
              {/* eslint-disable jsx-a11y/no-autofocus */}{/* modal dialog: focus first field for keyboard users */}
              <Input id="hcf-receipt-reference" unstyled
                type="text"
                value={submitReceiptRef}
                onChange={(v) => setSubmitReceiptRef(v)}
                placeholder="e.g. UDI-2026-00123"
                autoFocus
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0b2b43]"
              />
              {/* eslint-enable jsx-a11y/no-autofocus */}
              <label htmlFor="hcf-note-optional" className="block text-xs font-medium text-slate-700 mt-2">Note (optional)</label>
              <Input id="hcf-note-optional" unstyled
                type="text"
                value={submitNote}
                onChange={(v) => setSubmitNote(v)}
                placeholder="Internal note…"
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0b2b43]"
              />
            </div>
            {submitError && <p className="text-xs text-rose-600">{submitError}</p>}
            <div className="flex justify-end gap-2 pt-2">
              <Button unstyled
                type="button"
                onClick={() => { setShowSubmitModal(false); setSubmitReceiptRef(''); setSubmitNote(''); setSubmitError(null); }}
                className="px-4 py-2 rounded text-sm border border-slate-200 text-slate-600 hover:bg-slate-50"
              >
                Cancel
              </Button>
              <Button unstyled
                type="button"
                disabled={actionLoading || !submitReceiptRef.trim()}
                onClick={() => void handleSubmitConfirm()}
                className="px-4 py-2 rounded text-sm font-medium bg-[#0b2b43] text-white disabled:opacity-40 hover:bg-[#0e3a5c]"
              >
                {actionLoading ? 'Saving…' : 'Confirm Submission'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ── [P4-5] Reject modal ──────────────────────────────────────────── */}
      {showRejectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6 space-y-4">
            <h2 className="text-base font-semibold text-rose-700">Reject Form</h2>
            <p className="text-sm text-slate-600">
              The employee will see this reason in their dossier view. Be specific about what needs to be corrected.
            </p>
            <div className="space-y-2">
              <label htmlFor="hcf-rejection-reason" className="block text-xs font-medium text-slate-700">
                Rejection reason <span className="text-rose-500">*</span>
              </label>
              <textarea id="hcf-rejection-reason"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="e.g. Missing apostille on birth certificate."
                rows={3}
                // eslint-disable-next-line jsx-a11y/no-autofocus -- modal dialog: focus first field for keyboard users
                autoFocus
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-400 resize-none"
              />
            </div>
            <label htmlFor="hcf-reopen-for-employee-correcti" className="flex items-center gap-2 cursor-pointer select-none">
              <Checkbox id="hcf-reopen-for-employee-correcti"
                checked={reopenForCorrection}
                onChange={(e) => setReopenForCorrection(e.target.checked)}
                className="rounded border-slate-300 text-[#0b2b43] focus:ring-[#0b2b43]"
              />
              <span className="text-sm text-slate-700">Re-open for employee correction</span>
            </label>
            {rejectError && <p className="text-xs text-rose-600">{rejectError}</p>}
            <div className="flex justify-end gap-2 pt-2">
              <Button unstyled
                type="button"
                onClick={() => { setShowRejectModal(false); setRejectReason(''); setReopenForCorrection(true); setRejectError(null); }}
                className="px-4 py-2 rounded text-sm border border-slate-200 text-slate-600 hover:bg-slate-50"
              >
                Cancel
              </Button>
              <Button unstyled
                type="button"
                disabled={actionLoading || !rejectReason.trim()}
                onClick={() => void handleRejectConfirm()}
                className="px-4 py-2 rounded text-sm font-medium bg-rose-600 text-white disabled:opacity-40 hover:bg-rose-700"
              >
                {actionLoading ? 'Saving…' : 'Reject Form'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
};
