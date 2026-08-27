import { useCallback, useEffect, useState } from 'react';
import { Badge, Button } from '../antigravity';
import {
  getCaseAuditTrail,
  amendCaseAuditEvent,
  reverseCaseAuditEvent,
  type CaseAuditEvent,
  type CaseAuditFilters,
} from '../../api/caseAudit';

/**
 * [NAV-HR-3 / AIQ-1122 + NAV-HR-3-FU / AIQ-1137] Chronological audit trail for a
 * case, sourced from the canonical public.audit_logs and aggregated across all
 * of the case's bridged ids. Supports action-type + date filters and append-only
 * amend/reverse annotations (the original row is never mutated).
 */

const ANNOTATION_EVENTS = new Set(['AUDIT_AMENDED', 'AUDIT_REVERSED']);

function formatTs(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('en-GB', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function actionTone(action: string): 'success' | 'warning' | 'error' | 'neutral' {
  if (action === 'insert') return 'success';
  if (action === 'delete') return 'error';
  if (action === 'update') return 'warning';
  return 'neutral';
}

function verbLabel(e: CaseAuditEvent): string {
  return (e.event || e.action_type || 'event').replace(/_/g, ' ');
}

function reasonOf(e: CaseAuditEvent): string | null {
  const nv = e.new_value;
  const r = nv && typeof nv === 'object' ? (nv).reason : null;
  return typeof r === 'string' && r.trim() ? r : null;
}

function isAnnotation(e: CaseAuditEvent): boolean {
  return !!e.event && ANNOTATION_EVENTS.has(e.event);
}

/** An event already reversed by a later annotation row can't be reversed again. */
function reversedIds(events: CaseAuditEvent[]): Set<string> {
  const ids = new Set<string>();
  for (const e of events) {
    if (e.event === 'AUDIT_REVERSED' && e.new_value && typeof e.new_value === 'object') {
      const ref = (e.new_value).reverses;
      if (typeof ref === 'string') ids.add(ref);
    }
  }
  return ids;
}

type AnnotationKind = 'amend' | 'reverse';

export function CaseAuditTimeline({ caseId }: { caseId: string }) {
  const [events, setEvents] = useState<CaseAuditEvent[] | null>(null);
  const [error, setError] = useState(false);
  const [filters, setFilters] = useState<CaseAuditFilters>({});

  // Inline annotation editor state: which row + which kind is open.
  const [target, setTarget] = useState<{ id: string; kind: AnnotationKind } | null>(null);
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(() => {
    setEvents(null);
    setError(false);
    let cancelled = false;
    getCaseAuditTrail(caseId, filters)
      .then((e) => { if (!cancelled) setEvents(e); })
      .catch(() => { if (!cancelled) { setEvents([]); setError(true); } });
    return () => { cancelled = true; };
  }, [caseId, filters]);

  useEffect(() => load(), [load]);

  const openEditor = (id: string, kind: AnnotationKind) => {
    setTarget({ id, kind });
    setReason('');
    setActionError(null);
  };

  const submitAnnotation = async () => {
    if (!target) return;
    if (!reason.trim()) {
      setActionError('A reason is required.');
      return;
    }
    setSubmitting(true);
    setActionError(null);
    try {
      if (target.kind === 'amend') {
        await amendCaseAuditEvent(caseId, target.id, reason.trim());
      } else {
        await reverseCaseAuditEvent(caseId, target.id, reason.trim());
      }
      setTarget(null);
      setReason('');
      load();
    } catch {
      setActionError(`Could not ${target.kind} this entry. Please try again.`);
    } finally {
      setSubmitting(false);
    }
  };

  const alreadyReversed = events ? reversedIds(events) : new Set<string>();

  return (
    <details className="rounded-xl border border-[#e2e8f0] bg-white shadow-sm">
      <summary className="cursor-pointer list-none px-5 py-4 [&::-webkit-details-marker]:hidden">
        <div className="flex items-center justify-between gap-3">
          <span className="text-base font-semibold text-[#0b2b43]">▸ Audit trail</span>
          <span className="text-xs text-[#64748b]">
            {events === null ? 'Loading…' : `${events.length} event${events.length === 1 ? '' : 's'} · who changed what, when`}
          </span>
        </div>
      </summary>
      <div className="px-5 pb-5">
        {/* ── AIQ-1137: filters ── */}
        <div className="mb-4 flex flex-wrap items-end gap-3 border-b border-[#f1f5f9] pb-4">
          <label className="flex flex-col gap-1">
            <span className="text-[11px] font-medium text-[#64748b]">Action</span>
            <select
              value={filters.action_type ?? ''}
              onChange={(e) =>
                setFilters((f) => ({ ...f, action_type: (e.target.value || undefined) as CaseAuditFilters['action_type'] }))
              }
              className="rounded-md border border-[#cbd5e1] bg-white px-2 py-1 text-xs text-[#0b2b43] focus:border-[#0b2b43] focus:outline-none"
            >
              <option value="">All</option>
              <option value="insert">Insert</option>
              <option value="update">Update</option>
              <option value="delete">Delete</option>
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[11px] font-medium text-[#64748b]">From</span>
            <input
              type="date"
              value={filters.date_from ? filters.date_from.slice(0, 10) : ''}
              onChange={(e) => setFilters((f) => ({ ...f, date_from: e.target.value ? `${e.target.value}T00:00:00Z` : undefined }))}
              className="rounded-md border border-[#cbd5e1] bg-white px-2 py-1 text-xs text-[#0b2b43] focus:border-[#0b2b43] focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[11px] font-medium text-[#64748b]">To</span>
            <input
              type="date"
              value={filters.date_to ? filters.date_to.slice(0, 10) : ''}
              onChange={(e) => setFilters((f) => ({ ...f, date_to: e.target.value ? `${e.target.value}T23:59:59Z` : undefined }))}
              className="rounded-md border border-[#cbd5e1] bg-white px-2 py-1 text-xs text-[#0b2b43] focus:border-[#0b2b43] focus:outline-none"
            />
          </label>
          {(filters.action_type || filters.date_from || filters.date_to) && (
            <Button variant="ghost" onClick={() => setFilters({})} className="text-xs">
              Clear
            </Button>
          )}
        </div>

        {events === null ? (
          <div className="py-3 text-sm text-[#64748b]">Loading audit trail…</div>
        ) : error ? (
          <div className="py-3 text-sm text-[#64748b]">Couldn&apos;t load the audit trail.</div>
        ) : events.length === 0 ? (
          <div className="py-3 text-sm text-[#64748b]">No recorded actions on this case yet.</div>
        ) : (
          <ol className="space-y-3">
            {events.map((e) => {
              const rowReason = reasonOf(e);
              const annotation = isAnnotation(e);
              const canAnnotate = !annotation && e.action_type !== 'delete';
              const canReverse = canAnnotate && !alreadyReversed.has(e.id);
              const editing = target?.id === e.id;
              return (
                <li key={e.id} className="flex gap-3">
                  <div
                    className={`mt-1.5 h-2 w-2 flex-shrink-0 rounded-full ${annotation ? 'bg-amber-400' : 'bg-slate-300'}`}
                    aria-hidden="true"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium capitalize text-[#0b2b43]">{verbLabel(e)}</span>
                      <Badge variant={actionTone(e.action_type)} size="sm">{e.action_type}</Badge>
                      <span className="text-[11px] text-slate-500">{e.entity_type}</span>
                    </div>
                    <div className="text-xs text-slate-500">
                      {e.actor_name || e.actor_id || 'system'} · {formatTs(e.created_at)}
                    </div>
                    {rowReason && <div className="mt-0.5 text-xs text-slate-600">“{rowReason}”</div>}

                    {/* amend/reverse actions on original events */}
                    {canAnnotate && !editing && (
                      <div className="mt-1 flex gap-3">
                        <Button unstyled onClick={() => openEditor(e.id, 'amend')} className="text-[11px] font-medium text-accent-600 hover:text-accent-800 hover:underline">
                          Amend
                        </Button>
                        {canReverse && (
                          <Button unstyled onClick={() => openEditor(e.id, 'reverse')} className="text-[11px] font-medium text-accent-600 hover:text-accent-800 hover:underline">
                            Reverse
                          </Button>
                        )}
                        {!canReverse && <span className="text-[11px] text-slate-500">Reversed</span>}
                      </div>
                    )}

                    {editing && (
                      <div className="mt-2 space-y-2 rounded-md border border-[#e2e8f0] bg-[#f8fafc] p-2">
                        <div className="text-[11px] font-medium text-[#0b2b43] capitalize">{target.kind} this entry</div>
                        <textarea
                          value={reason}
                          onChange={(ev) => setReason(ev.target.value)}
                          rows={2}
                          maxLength={1000}
                          placeholder={target.kind === 'amend' ? 'What is being corrected?' : 'Why is this being reversed?'}
                          className="w-full rounded-md border border-[#cbd5e1] bg-white px-2 py-1 text-xs text-[#0b2b43] focus:border-[#0b2b43] focus:outline-none"
                          disabled={submitting}
                        />
                        {actionError && <p className="text-[11px] text-rose-600">{actionError}</p>}
                        <div className="flex items-center gap-2">
                          <Button variant="outline" onClick={() => setTarget(null)} disabled={submitting} className="text-xs">
                            Cancel
                          </Button>
                          <Button onClick={submitAnnotation} disabled={submitting} className="text-xs">
                            {submitting ? 'Saving…' : `Confirm ${target.kind}`}
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </details>
  );
}
