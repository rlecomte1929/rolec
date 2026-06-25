import { useCallback, useEffect, useMemo, useState } from 'react';
import { Button } from '../../../components/antigravity/Button';
import { AppShell } from '../../../components/AppShell';
import { Breadcrumb } from '../../../components/Breadcrumb';
import { AIRecommendationCard } from '../../ai-oversight/AIRecommendationCard';
import { getCountryName } from '../../../utils/countries';
import {
  getExceptionAuditTrail,
  listExceptionRequestsForCompany,
  resolveExceptionRequest,
} from '../../../api/exceptions';
import type {
  ExceptionAuditEvent,
  ExceptionRequest,
} from '../../../api/exceptions';

/**
 * HR Policy Exceptions — V2.
 *
 * Two-pane inbox: left = filterable exception request list; right = detail
 * pane with approve/reject decision flow + audit trail.
 *
 * Backend: live, real data only. On mount the page fetches
 * `GET /api/exception-requests` (listExceptionRequestsForCompany) and renders
 * exactly what exists for the caller's company — no fabricated/demo rows. An
 * honest empty state shows when there are none. Approve/reject decisions
 * persist via `PATCH /api/exception-requests/:id` (resolveExceptionRequest).
 */

// ── Types ─────────────────────────────────────────────────────────────────────

type AuditKind = 'submit' | 'ai' | 'approve' | 'reject' | 'note';

interface AuditEvent {
  kind: AuditKind;
  who: string;
  what: string;
  quote?: string;
  when: string;
}

interface ExcEmployee {
  name: string;
  initials: string;
  role: string;
  caseId: string;
}

type ExcStatus = 'pending' | 'approved' | 'rejected';
type ExcType = 'new_category' | 'cap_override' | 'timeline_extension' | 'additional_coverage';

interface ExcRequest {
  id: string;
  type: ExcType;
  typeLabel: string;
  benefit: string;
  employee: ExcEmployee;
  current: { value: string; sub: string };
  requested: { value: string; sub: string };
  justification: string;
  submittedAgo: string;
  status: ExcStatus;
  hrNote: string | null;
  decidedBy: string | null;
  aiInsight?: string;
  unread: boolean;
  audit: AuditEvent[];
}

// ── Mock data (swap for API call when backend endpoint ships) ─────────────────


// ── Sub-components ────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: ExcStatus }) {
  const cfg: Record<ExcStatus, { label: string; dot: string; pill: string }> = {
    pending:  { label: 'Pending review', dot: 'bg-amber-400', pill: 'bg-amber-50 text-amber-700 ring-1 ring-amber-200' },
    approved: { label: 'Approved',       dot: 'bg-emerald-500', pill: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200' },
    rejected: { label: 'Not approved',  dot: 'bg-rose-500', pill: 'bg-rose-50 text-rose-700 ring-1 ring-rose-200' },
  };
  const { label, dot, pill } = cfg[status];
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${pill}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
      {label}
    </span>
  );
}

const TYPE_BADGE_COLORS: Record<ExcType, string> = {
  cap_override:        'bg-blue-50 text-blue-700 ring-1 ring-blue-200',
  new_category:        'bg-teal-50 text-teal-700 ring-1 ring-teal-200',
  timeline_extension:  'bg-amber-50 text-amber-700 ring-1 ring-amber-200',
  additional_coverage: 'bg-blue-50 text-blue-700 ring-1 ring-blue-200',
};

function AuditDot({ kind }: { kind: AuditKind }) {
  const cls: Record<AuditKind, string> = {
    submit:  'bg-slate-400',
    ai:      'bg-accent-400',
    approve: 'bg-emerald-500',
    reject:  'bg-rose-500',
    note:    'bg-slate-400',
  };
  return <span className={`w-2 h-2 rounded-full shrink-0 mt-1 ${cls[kind]}`} />;
}

// ── List row ──────────────────────────────────────────────────────────────────

function ExcRow({ r, active, onClick }: { r: ExcRequest; active: boolean; onClick: () => void }) {
  return (
    <Button unstyled
      onClick={onClick}
      className={`w-full text-left px-4 py-3.5 flex gap-3 transition-colors border-b border-slate-100 last:border-b-0 ${
        active ? 'bg-slate-50' : 'hover:bg-slate-50/60'
      } ${r.unread ? 'font-medium' : ''}`}
    >
      {/* Avatar */}
      <div className="w-8 h-8 rounded-full bg-slate-200 text-slate-600 text-xs font-semibold flex items-center justify-center shrink-0 mt-0.5">
        {r.employee.initials}
      </div>

      {/* Body */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-sm text-slate-900 truncate">{r.employee.name}</span>
          <span className={`px-1.5 py-px rounded text-[10px] font-semibold uppercase tracking-wide ${TYPE_BADGE_COLORS[r.type]}`}>
            {r.typeLabel}
          </span>
        </div>
        <div className="text-sm text-slate-800 truncate">
          <strong>{r.benefit}</strong>
          <span className="text-slate-400"> · </span>
          <span className="text-slate-500">{r.requested.value}</span>
        </div>
        <div className="mt-1 text-xs text-slate-400 truncate leading-relaxed">{r.justification}</div>
      </div>

      {/* Right meta */}
      <div className="flex flex-col items-end gap-1.5 shrink-0">
        <span className="text-xs text-slate-400">{r.submittedAgo}</span>
        <StatusBadge status={r.status} />
      </div>
    </Button>
  );
}

// ── Detail pane ───────────────────────────────────────────────────────────────

function ExcDetail({
  r,
  onDecide,
}: {
  r: ExcRequest | null;
  onDecide: (id: string, intent: 'approve' | 'reject', note: string) => void;
}) {
  const [intent, setIntent] = useState<'approve' | 'reject' | null>(null);
  const [note, setNote] = useState('');
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    setIntent(null);
    setNote('');
    setSubmitted(false);
  }, [r?.id]);

  if (!r) {
    return (
      <div className="flex-1 flex items-center justify-center text-center p-8">
        <div>
          <div className="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center mx-auto mb-3">
            <svg className="w-6 h-6 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <p className="text-sm font-medium text-slate-700">Select a request</p>
          {/* RTL: change 'on the left' to 'on the right' for Arabic/Hebrew locales */}
          <p className="text-xs text-slate-400 mt-1 max-w-[260px]">Choose a request on the left to see the full context, justification, and decision history.</p>
        </div>
      </div>
    );
  }

  const decided = r.status === 'approved' || r.status === 'rejected';
  const firstName = r.employee.name.split(' ')[0];

  const handleConfirm = () => {
    if (!intent) return;
    onDecide(r.id, intent, note);
    setSubmitted(true);
  };

  return (
    <div className="flex-1 overflow-y-auto">
      {/* Header */}
      <div className="px-6 pt-5 pb-4 border-b border-slate-100 flex items-start gap-3">
        <div className="w-10 h-10 rounded-full bg-slate-200 text-slate-600 text-sm font-semibold flex items-center justify-center shrink-0">
          {r.employee.initials}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-slate-900">{r.employee.name}</p>
          <p className="text-xs text-slate-400 mt-0.5">{r.employee.role}</p>
        </div>
        <div className="text-right shrink-0">
          <StatusBadge status={r.status} />
          <p className="text-[10px] text-slate-400 mt-1.5">{r.id} · case {r.employee.caseId}</p>
        </div>
      </div>

      <div className="px-6 py-5 space-y-6">
        {/* Requested change */}
        <section>
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Requested change</h3>
          <div className="flex items-stretch gap-3">
            <div className="flex-1 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
              <p className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider mb-1">Current policy</p>
              <p className="text-sm font-semibold text-slate-800">{r.current.value}</p>
              {r.current.sub && (
                <p className="text-xs text-slate-400 mt-0.5">{r.current.sub}</p>
              )}
            </div>
            <div className="flex items-center text-slate-300">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </div>
            <div className="flex-1 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3">
              <p className="text-[10px] text-blue-500 font-semibold uppercase tracking-wider mb-1">{r.typeLabel}</p>
              <p className="text-sm font-semibold text-blue-800">{r.requested.value}</p>
              {r.requested.sub && (
                <p className="text-xs text-blue-500 mt-0.5">{r.requested.sub}</p>
              )}
            </div>
          </div>
        </section>

        {/* Justification */}
        <section>
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Employee justification</h3>
          <div className="rounded-lg border border-slate-200 bg-white px-4 py-3">
            <p className="text-xs text-slate-400 mb-1.5">{firstName} wrote:</p>
            <p className="text-sm text-slate-700 leading-relaxed">{r.justification}</p>
          </div>
        </section>

        {/* AI precedent insight (AI-002 wire-in, AI-005 payload upgrade) — Art. 14
            oversight wrapper. The backend `precedent_insight_service` produces a
            structured payload (rationale, approval rate, sample size, similar
            case ids) when this page is wired to real /api/exception-requests
            data. Today the page still ships mock requests for demo purposes, so
            the rationale below comes from `r.aiInsight` (mock string); when the
            swap to live data lands, the backend response's `precedent_insight`
            field flows through here as `aiOutput`. The recommendation_id uses the
            deterministic `precedent_v1:<id>` form so re-running the same insight
            against the same DB state produces the same id — `ai_decisions` can
            then dedupe / replay against a stable source version. */}
        {r.aiInsight && !decided && !submitted && (
          <AIRecommendationCard
            recommendationId={`precedent_v1:${r.id}`}
            feature="exception_insight"
            title="AI precedent insight"
            rationale={<><strong>Precedent · </strong>{r.aiInsight}</>}
            aiOutput={{
              exception_request_id: r.id,
              exception_type: r.type,
              benefit: r.benefit,
              insight: r.aiInsight,
              source_version: 'precedent_v1',
            }}
          />
        )}

        {/* Decision panel */}
        {!decided && !submitted && (
          <section>
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Your decision</h3>
            <div className="flex gap-3 mb-4">
              <Button unstyled
                onClick={() => setIntent('approve')}
                className={`flex-1 flex items-center gap-3 px-4 py-3 rounded-lg border-2 transition-all text-left ${
                  intent === 'approve'
                    ? 'border-emerald-400 bg-emerald-50'
                    : 'border-slate-200 bg-white hover:border-slate-300'
                }`}
              >
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${intent === 'approve' ? 'bg-emerald-500' : 'bg-slate-100'}`}>
                  <svg className={`w-4 h-4 ${intent === 'approve' ? 'text-white' : 'text-slate-400'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <div>
                  <p className={`text-sm font-semibold ${intent === 'approve' ? 'text-emerald-800' : 'text-slate-700'}`}>Approve</p>
                  <p className="text-xs text-slate-400">Grant the requested change</p>
                </div>
              </Button>

              <Button unstyled
                onClick={() => setIntent('reject')}
                className={`flex-1 flex items-center gap-3 px-4 py-3 rounded-lg border-2 transition-all text-left ${
                  intent === 'reject'
                    ? 'border-rose-400 bg-rose-50'
                    : 'border-slate-200 bg-white hover:border-slate-300'
                }`}
              >
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${intent === 'reject' ? 'bg-rose-500' : 'bg-slate-100'}`}>
                  <svg className={`w-4 h-4 ${intent === 'reject' ? 'text-white' : 'text-slate-400'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </div>
                <div>
                  <p className={`text-sm font-semibold ${intent === 'reject' ? 'text-rose-800' : 'text-slate-700'}`}>Reject</p>
                  <p className="text-xs text-slate-400">Keep current policy as-is</p>
                </div>
              </Button>
            </div>

            {intent && (
              <div className="space-y-3">
                <label className="block">
                  <span className="text-xs font-medium text-slate-600">
                    Comment to {firstName}
                    {intent === 'reject'
                      ? <span className="text-rose-500 ml-1">*</span>
                      : <span className="text-slate-400 ml-1">(optional — but recommended)</span>}
                  </span>
                  <textarea
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    rows={3}
                    placeholder={
                      intent === 'approve'
                        ? 'e.g. Approved. The new cap is effective for your case only — your roadmap will update automatically.'
                        : 'Explain why this can\'t be approved and propose an alternative if possible. This text is sent back to the employee.'
                    }
                    className="mt-1.5 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 placeholder:text-slate-300 focus:outline-none focus:ring-2 focus:ring-slate-200 resize-none"
                  />
                </label>
                <div className="flex items-center gap-3">
                  <p className="text-xs text-slate-400 flex-1">{firstName} will be notified via in-app + email.</p>
                  <Button unstyled
                    onClick={() => { setIntent(null); setNote(''); }}
                    className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 transition-colors"
                  >
                    Cancel
                  </Button>
                  <Button unstyled
                    onClick={handleConfirm}
                    disabled={intent === 'reject' && !note.trim()}
                    className={`px-4 py-2 text-sm font-medium rounded-lg text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                      intent === 'approve' ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-rose-600 hover:bg-rose-700'
                    }`}
                  >
                    {intent === 'approve' ? 'Confirm approval' : 'Confirm rejection'}
                  </Button>
                </div>
              </div>
            )}
          </section>
        )}

        {/* Decision result */}
        {(decided || submitted) && (
          <section>
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Decision</h3>
            <div className={`rounded-lg border px-4 py-3 ${
              (r.status === 'approved' || (submitted && intent === 'approve'))
                ? 'border-emerald-200 bg-emerald-50'
                : 'border-rose-200 bg-rose-50'
            }`}>
              <p className={`text-sm font-semibold ${
                (r.status === 'approved' || (submitted && intent === 'approve')) ? 'text-emerald-800' : 'text-rose-800'
              }`}>
                {submitted
                  ? (intent === 'approve' ? 'Request approved' : 'Request rejected')
                  : (r.status === 'approved' ? 'Request approved' : 'Request not approved')}
              </p>
              <p className="text-xs text-slate-500 mt-0.5">
                Decided by {submitted ? 'you' : r.decidedBy} · {submitted ? 'just now' : ''}
              </p>
              {(r.hrNote || (submitted && note)) && (
                <p className="mt-2 text-sm text-slate-700 leading-relaxed border-t border-slate-200/60 pt-2">
                  {r.hrNote || note}
                </p>
              )}
            </div>
          </section>
        )}

        {/* Audit trail */}
        <section>
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Audit trail</h3>
          <div className="space-y-3">
            {[
              ...r.audit,
              ...(submitted && intent
                ? [{
                    kind: intent === 'approve' ? 'approve' : 'reject' as AuditKind,
                    who: 'You',
                    what: intent === 'approve' ? 'Approved with note.' : 'Rejected with note.',
                    quote: note || undefined,
                    when: 'Just now',
                  }]
                : []),
            ].map((event, i) => (
              <div key={i} className="flex gap-3">
                <AuditDot kind={event.kind} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-2 flex-wrap">
                    <span className="text-xs font-semibold text-slate-700">{event.who}</span>
                    <span className="text-xs text-slate-400">{event.when}</span>
                  </div>
                  <p className="text-xs text-slate-600 mt-0.5 leading-relaxed">{event.what}</p>
                  {event.quote && (
                    <p className="text-xs text-slate-500 italic mt-1 leading-relaxed">"{event.quote}"</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

// ── Server → UI mapping helpers (AI-005 follow-up) ───────────────────────────
//
// The live exception inbox renders the same ExcRequest shape that the mock
// fixtures produce. The mapping below fills the gaps the server doesn't
// currently provide (avatar initials, formatted relative times, formatted
// currency amounts) and uses the joined employee / corridor fields when the
// backend returns them.

const CATEGORY_TO_TYPE: Record<string, ExcType> = {
  new_category: 'new_category',
  cap_override: 'cap_override',
  timeline_extension: 'timeline_extension',
  additional_coverage: 'additional_coverage',
};

const TYPE_LABEL: Record<ExcType, string> = {
  new_category: 'Add benefit',
  cap_override: 'Cap override',
  timeline_extension: 'Timeline',
  additional_coverage: 'More coverage',
};

function initialsFrom(name: string | null | undefined): string {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/);
  const first = parts[0];
  if (!first) return '?';
  if (parts.length === 1) return first.slice(0, 2).toUpperCase();
  const last = parts[parts.length - 1] ?? first;
  return (first.charAt(0) + last.charAt(0)).toUpperCase();
}

function relativeTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return '—';
  const diffMs = Date.now() - t;
  const mins = Math.floor(diffMs / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h`;
  const days = Math.floor(hrs / 24);
  return `${days}d`;
}

function formatMoney(amount: number | null | undefined, currency: string | null | undefined): string {
  if (amount == null || !Number.isFinite(amount)) return '—';
  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency: (currency || 'EUR').toUpperCase(),
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `${amount} ${currency || ''}`.trim();
  }
}

function roleSubtitle(req: ExceptionRequest): string {
  const role = (req.requested_by_role || '').toLowerCase();
  const roleLabel = role === 'hr' ? 'HR' : role === 'admin' ? 'Admin' : role === 'employee' ? 'Employee' : '';
  const corridor =
    req.origin_country && req.destination_country
      ? `${getCountryName(req.origin_country)} → ${getCountryName(req.destination_country)}`
      : '';
  return [roleLabel, corridor].filter(Boolean).join(' · ');
}

/** Convert a live ExceptionRequest into the ExcRequest shape the existing
 * inbox UI expects. Mock-only fields (justification, audit array, aiInsight
 * mock string) are filled with sensible derivations or left empty. */
function mapServerToUi(req: ExceptionRequest): ExcRequest {
  // Q3-A: prefer the dedicated `exception_type` column when present. Falls back
  // to the legacy client-side category→type mapping for rows written before the
  // 20260528 migration landed (these have exception_type=NULL).
  const fromServer =
    req.exception_type && (CATEGORY_TO_TYPE[req.exception_type] as ExcType | undefined);
  const type: ExcType =
    fromServer ?? (CATEGORY_TO_TYPE[req.category] as ExcType | undefined) ?? 'cap_override';
  return {
    id: req.id,
    type,
    typeLabel: TYPE_LABEL[type],
    benefit: req.requested_by_role || type, // server has no `benefit` column today; fallback
    employee: {
      name: req.requested_by_name || 'Employee',
      initials: initialsFrom(req.requested_by_name),
      role: roleSubtitle(req) || 'Employee',
      caseId: req.case_id,
    },
    current: { value: formatMoney(req.cap_amount, req.currency), sub: '' },
    requested: { value: formatMoney(req.requested_amount, req.currency), sub: '' },
    justification: req.reason || '—',
    submittedAgo: relativeTime(req.created_at),
    status: req.status,
    hrNote: req.hr_note,
    decidedBy: req.resolved_by_user_id ? (req.resolved_by_user_id) : null,
    // No live aiInsight yet — the precedent_insight pipeline (AI-005 on PR #152)
    // provides the structured payload; this swap can light it up later.
    aiInsight: undefined,
    unread: req.status === 'pending',
    audit: [], // populated on selection via getExceptionAuditTrail
  };
}

/** Convert a server audit event into the AuditEvent shape used by the inbox. */
function mapAuditEventToUi(ev: ExceptionAuditEvent): AuditEvent {
  const kind: AuditKind =
    ev.action_type === 'insert'
      ? 'submit'
      : ev.action_type === 'update'
        ? // distinguish approve vs reject by new_value.status when available
          ev.new_value && (ev.new_value as { status?: string }).status === 'approved'
          ? 'approve'
          : ev.new_value && (ev.new_value as { status?: string }).status === 'rejected'
            ? 'reject'
            : 'note'
        : 'note';
  const note = ev.new_value && (ev.new_value as { hr_note?: string }).hr_note;
  return {
    kind,
    who: ev.actor_name || (ev.actor_type === 'system' ? 'System' : 'Unknown'),
    what:
      kind === 'submit'
        ? 'Submitted exception request.'
        : kind === 'approve'
          ? 'Approved.'
          : kind === 'reject'
            ? 'Rejected.'
            : 'Updated.',
    quote: typeof note === 'string' && note ? note : undefined,
    when: relativeTime(ev.created_at) + ' ago',
  };
}

// ── Main page ─────────────────────────────────────────────────────────────────

type FilterTab = 'pending' | 'approved' | 'rejected' | 'all';

export function HrExceptionsPage({ embedded = false }: { embedded?: boolean } = {}) {
  const [requests, setRequests] = useState<ExcRequest[]>([]);
  const [filter, setFilter] = useState<FilterTab>('pending');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  // True once the live fetch attempt has resolved — drives whether the
  // selected row is eligible for a real audit-trail fetch.
  const [isLiveData, setIsLiveData] = useState(false);
  // 'loading' until the first fetch resolves; 'error' if it failed. The inbox
  // shows only real backend data — no fabricated rows — so HR sees exactly
  // what exists for their company, and an honest empty state when nothing does.
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'error'>('loading');

  useEffect(() => {
    let cancelled = false;
    listExceptionRequestsForCompany()
      .then((live) => {
        if (cancelled) return;
        const mapped = (live ?? []).map(mapServerToUi);
        setRequests(mapped);
        setSelectedId(mapped[0]?.id ?? null);
        setIsLiveData(true);
        setLoadState('ready');
      })
      .catch(() => {
        if (cancelled) return;
        setLoadState('error');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // When the selected row is live data, fetch its audit trail from the
  // backend and merge into the request shape. Mock rows already carry
  // their own audit array.
  useEffect(() => {
    if (!isLiveData || !selectedId) return;
    let cancelled = false;
    getExceptionAuditTrail(selectedId)
      .then((events) => {
        if (cancelled) return;
        const ui = events.map(mapAuditEventToUi);
        setRequests((rs) => rs.map((r) => (r.id === selectedId ? { ...r, audit: ui } : r)));
      })
      .catch(() => {
        // Leave audit array empty if the trail fetch fails. Non-blocking.
      });
    return () => {
      cancelled = true;
    };
  }, [isLiveData, selectedId]);

  const counts = useMemo(
    () => ({
      all:      requests.length,
      pending:  requests.filter((r) => r.status === 'pending').length,
      approved: requests.filter((r) => r.status === 'approved').length,
      rejected: requests.filter((r) => r.status === 'rejected').length,
    }),
    [requests]
  );

  const filtered = useMemo(
    () => (filter === 'all' ? requests : requests.filter((r) => r.status === filter)),
    [filter, requests]
  );

  const selected = filtered.find((r) => r.id === selectedId) ?? filtered[0] ?? null;

  // Mark row as read on selection
  useEffect(() => {
    if (!selectedId) return;
    setRequests((rs) => rs.map((r) => (r.id === selectedId ? { ...r, unread: false } : r)));
  }, [selectedId]);

  const handleDecide = useCallback(
    (id: string, intent: 'approve' | 'reject', note: string) => {
      const nextStatus = intent === 'approve' ? 'approved' : 'rejected';
      // Optimistic update — reflect the decision immediately in the inbox.
      const prev = requests;
      setRequests((rs) =>
        rs.map((r) =>
          r.id === id
            ? { ...r, status: nextStatus, hrNote: note, decidedBy: 'You', unread: false }
            : r
        )
      );
      // For live backend rows, persist the decision. Mock rows (demo fallback,
      // not live data) stay client-only. On failure, roll back the optimistic
      // change so the inbox doesn't claim a decision the server never recorded.
      if (isLiveData) {
        resolveExceptionRequest(id, { status: nextStatus, hr_note: note || undefined }).catch(
          () => {
            setRequests(prev);
          }
        );
      }
    },
    [isLiveData, requests]
  );

  const TABS: { key: FilterTab; label: string }[] = [
    { key: 'pending',  label: 'Pending' },
    { key: 'approved', label: 'Approved' },
    { key: 'rejected', label: 'Rejected' },
    { key: 'all',      label: 'All' },
  ];

  // AIQ-1112: when embedded under the Policy tab, skip the AppShell wrapper
  // (HrPolicy provides the shell + tab chrome). Standalone route still wraps it.
  const body = (
    <>
      {/* Page header */}
      <div className="px-6 py-5 border-b border-slate-100">
        <Breadcrumb section="HR Operations" title="Policy exceptions" className="mb-2" />
        <div className="flex items-end gap-3">
          <h1 className="text-xl font-semibold text-slate-900">Policy exceptions</h1>
          <div className="flex-1" />
          {counts.pending > 0 && (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-700 ring-1 ring-amber-200">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
              {counts.pending} pending
            </span>
          )}
          <Button unstyled className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-xs font-medium text-slate-600 hover:bg-slate-50 transition-colors">
            <svg className="w-3.5 h-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Export
          </Button>
        </div>
        <p className="mt-1 text-sm text-slate-500 leading-relaxed">
          Employees requested deviations from their assigned policy. Review each request, approve or reject with a note, and the decision flows back to their relocation plan.
        </p>
      </div>

      {/* Two-pane inbox */}
      <div className="flex h-[calc(100vh-160px)] overflow-hidden">
        {/* Left list pane */}
        <div className="w-[380px] shrink-0 flex flex-col border-r border-slate-100 overflow-hidden">
          {/* List header + filter tabs */}
          <div className="px-4 pt-4 pb-0 border-b border-slate-100">
            <div className="flex items-baseline gap-2 mb-3">
              <p className="text-sm font-semibold text-slate-800">Exception requests</p>
              {counts.pending > 0 && (
                <span className="w-5 h-5 rounded-full bg-amber-100 text-amber-700 text-[10px] font-bold flex items-center justify-center">
                  {counts.pending}
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400 mb-3">Across {counts.all} cases · live</p>
            <div className="flex gap-1 -mb-px">
              {TABS.map((tab) => (
                <Button unstyled
                  key={tab.key}
                  onClick={() => setFilter(tab.key)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-t-md border-b-2 transition-colors ${
                    filter === tab.key
                      ? 'border-slate-900 text-slate-900'
                      : 'border-transparent text-slate-400 hover:text-slate-600'
                  }`}
                >
                  {tab.label}
                  <span className={`ml-1.5 text-[10px] ${filter === tab.key ? 'text-slate-500' : 'text-slate-300'}`}>
                    {counts[tab.key]}
                  </span>
                </Button>
              ))}
            </div>
          </div>

          {/* List body */}
          <div className="flex-1 overflow-y-auto">
            {loadState === 'loading' ? (
              <div className="flex flex-col items-center justify-center h-full text-center px-6 py-10">
                <p className="text-sm text-slate-400">Loading exception requests…</p>
              </div>
            ) : loadState === 'error' ? (
              <div className="flex flex-col items-center justify-center h-full text-center px-6 py-10">
                <svg className="w-8 h-8 text-amber-400 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <p className="text-sm text-slate-500">Couldn't load exception requests.</p>
                <p className="text-xs text-slate-400 mt-0.5">Refresh to try again.</p>
              </div>
            ) : filtered.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center px-6 py-10">
                <svg className="w-8 h-8 text-emerald-400 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <p className="text-sm text-slate-500">No {filter} requests.</p>
                <p className="text-xs text-slate-400 mt-0.5">Exception requests from employees will appear here.</p>
              </div>
            ) : (
              filtered.map((r) => (
                <ExcRow
                  key={r.id}
                  r={r}
                  active={selected?.id === r.id}
                  onClick={() => setSelectedId(r.id)}
                />
              ))
            )}
          </div>
        </div>

        {/* Right detail pane */}
        <ExcDetail r={selected} onDecide={handleDecide} />
      </div>
    </>
  );

  return embedded ? body : <AppShell wide>{body}</AppShell>;
}
