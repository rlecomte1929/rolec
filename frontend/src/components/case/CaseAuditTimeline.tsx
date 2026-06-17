import { useEffect, useState } from 'react';
import { Badge } from '../antigravity';
import { getCaseAuditTrail, type CaseAuditEvent } from '../../api/caseAudit';

/**
 * [NAV-HR-3 / AIQ-1122] Read-only chronological audit trail for a case, sourced
 * from the canonical public.audit_logs. Shows who did what, when, and (where
 * present) the reason. Append-only amend/reverse is a tracked follow-up.
 */

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
  const r = nv && typeof nv === 'object' ? (nv as Record<string, unknown>).reason : null;
  return typeof r === 'string' && r.trim() ? r : null;
}

export function CaseAuditTimeline({ caseId }: { caseId: string }) {
  const [events, setEvents] = useState<CaseAuditEvent[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setEvents(null);
    setError(false);
    getCaseAuditTrail(caseId)
      .then((e) => { if (!cancelled) setEvents(e); })
      .catch(() => { if (!cancelled) { setEvents([]); setError(true); } });
    return () => { cancelled = true; };
  }, [caseId]);

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
        {events === null ? (
          <div className="py-3 text-sm text-[#64748b]">Loading audit trail…</div>
        ) : error ? (
          <div className="py-3 text-sm text-[#64748b]">Couldn't load the audit trail.</div>
        ) : events.length === 0 ? (
          <div className="py-3 text-sm text-[#64748b]">No recorded actions on this case yet.</div>
        ) : (
          <ol className="space-y-3">
            {events.map((e) => {
              const reason = reasonOf(e);
              return (
                <li key={e.id} className="flex gap-3">
                  <div className="mt-1.5 h-2 w-2 flex-shrink-0 rounded-full bg-slate-300" aria-hidden="true" />
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium capitalize text-[#0b2b43]">{verbLabel(e)}</span>
                      <Badge variant={actionTone(e.action_type)} size="sm">{e.action_type}</Badge>
                      <span className="text-[11px] text-slate-400">{e.entity_type}</span>
                    </div>
                    <div className="text-xs text-slate-500">
                      {e.actor_name || e.actor_id || 'system'} · {formatTs(e.created_at)}
                    </div>
                    {reason && <div className="mt-0.5 text-xs text-slate-600">“{reason}”</div>}
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
