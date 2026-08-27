/**
 * AssignmentExceptionsPanel — GAP 7 (enriched)
 *
 * Displays assignment-level policy exception requests from the new
 * GET /api/assignments/{id}/exceptions endpoint. Unlike the older
 * ExceptionFlagsPanel (which shows immigration-service blockers), this
 * panel shows benefit-level exceptions with:
 *  - Benefit key and type label
 *  - Current vs requested value comparison
 *  - AI insight (if populated by the backend)
 *  - Full audit trail of HR actions
 *  - Inline Approve / Reject with an optional note
 *
 * Renders nothing when there are no exceptions (fail-open).
 */

import React, { useCallback, useEffect, useState } from 'react';
import { Button } from '../antigravity/Button';
import {
  listAssignmentExceptions,
  resolveAssignmentException,
  type AssignmentExceptionRead,
} from '../../api/assignmentExceptions';

interface Props {
  assignmentId: string;
}

const STATUS_STYLES: Record<string, string> = {
  pending:  'bg-[#fef9c3] border-[#fde68a] text-[#854d0e]',
  approved: 'bg-[#dcfce7] border-[#86efac] text-[#166534]',
  rejected: 'bg-[#fee2e2] border-[#fca5a5] text-[#991b1b]',
  escalated:'bg-[#e0f2fe] border-[#7dd3fc] text-[#0369a1]',
};

function fmtVal(v: unknown): string {
  if (v == null) return '—';
  if (typeof v === 'object') return JSON.stringify(v, null, 0);
  return String(v as string | number | boolean | bigint);
}

function fmtTs(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
}

export const AssignmentExceptionsPanel: React.FC<Props> = ({ assignmentId }) => {
  const [rows, setRows] = useState<AssignmentExceptionRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [longWait, setLongWait] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [activeNote, setActiveNote] = useState<Record<string, string>>({});
  const [savingId, setSavingId] = useState<string | null>(null);
  const [expandedAudit, setExpandedAudit] = useState<Record<string, boolean>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await listAssignmentExceptions(assignmentId);
      setRows(data);
    } catch {
      setLoadError("We can't load exceptions right now. Hit refresh, or try again in a moment.");
    } finally {
      setLoading(false);
    }
  }, [assignmentId]);

  useEffect(() => { void load(); }, [load]);

  // Surface a softer "still checking" state if a load runs past 3s.
  useEffect(() => {
    if (!loading) { setLongWait(false); return; }
    const t = window.setTimeout(() => setLongWait(true), 3000);
    return () => window.clearTimeout(t);
  }, [loading]);

  const resolve = async (row: AssignmentExceptionRead, status: 'approved' | 'rejected') => {
    setSavingId(row.id);
    setActionError(null);
    try {
      await resolveAssignmentException(assignmentId, row.id, {
        status,
        hr_note: activeNote[row.id]?.trim() || undefined,
      });
      await load();
      setActiveNote((prev) => {
        const next = { ...prev };
        delete next[row.id];
        return next;
      });
    } catch {
      setActionError('Could not save decision.');
    } finally {
      setSavingId(null);
    }
  };

  return (
    <div className="rounded-xl border border-[#e2e8f0] bg-white overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-[#f1f5f9]">
        <div>
          <div className="text-sm font-semibold text-[#0b2b43]">
            Policy exceptions
            {rows.filter((r) => r.status === 'pending').length > 0 && (
              <span className="ml-2 inline-flex items-center justify-center rounded-full bg-[#fef3c7] border border-[#fbbf24] px-2 py-0.5 text-xs font-medium text-[#92400e]">
                {rows.filter((r) => r.status === 'pending').length} pending
              </span>
            )}
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Benefit-level exceptions flagged for this assignment
          </p>
        </div>
        <Button unstyled
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className="text-xs text-[#0b2b43] hover:underline disabled:opacity-50"
        >
          {loading ? 'Refreshing…' : 'Refresh'}
        </Button>
      </div>

      {/* Action-level error (e.g. a failed Approve/Reject) — shown above the list, never replaces it. */}
      {actionError && rows.length > 0 && (
        <div className="px-5 py-3 text-sm text-[#991b1b] bg-[#fef2f2]">{actionError}</div>
      )}

      {loadError ? (
        <div className="px-5 py-8 text-center">
          <p className="text-sm text-[#475569]">{loadError}</p>
          <Button unstyled
            type="button"
            onClick={() => void load()}
            className="mt-3 rounded-lg bg-[#0b2b43] px-4 py-2 text-xs font-medium text-white hover:bg-[#0f3858] transition-colors"
          >
            Refresh exceptions
          </Button>
        </div>
      ) : loading && rows.length === 0 ? (
        longWait ? (
          <div className="px-5 py-8 text-center">
            <p className="text-sm text-[#475569]">Still checking — this case has a lot of policy rules.</p>
          </div>
        ) : (
          <div className="divide-y divide-[#f1f5f9]" aria-busy="true" aria-label="Loading policy exceptions">
            {[1, 2].map((i) => (
              <div key={i} className="px-5 py-4 animate-pulse">
                <div className="h-3 bg-[#f1f5f9] rounded w-40 mb-2" />
                <div className="h-3 bg-[#f1f5f9] rounded w-72" />
              </div>
            ))}
          </div>
        )
      ) : rows.length === 0 ? (
        <div className="px-5 py-8 text-center">
          <p className="text-sm text-[#475569]">No exceptions flagged for this assignment.</p>
        </div>
      ) : (
        <ul className="divide-y divide-[#f1f5f9]">
          {rows.map((row) => {
            const isPending = row.status === 'pending';
            const isSaving = savingId === row.id;
            const statusStyle = STATUS_STYLES[row.status] ?? STATUS_STYLES.pending;
            const showAudit = expandedAudit[row.id] ?? false;

            return (
              <li key={row.id} className="px-5 py-4 space-y-3">
                {/* Title row */}
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-[#0b2b43] capitalize">
                        {row.type_label || row.benefit_key || '—'}
                      </span>
                      <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${statusStyle}`}>
                        {row.status.charAt(0).toUpperCase() + row.status.slice(1)}
                      </span>
                    </div>
                    <div className="text-xs text-[#6b7280] mt-0.5">
                      Requested {row.created_at ? fmtTs(row.created_at) : '—'}
                    </div>
                  </div>
                </div>

                {/* Current vs requested */}
                {(row.current_value || row.requested_value) && (
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-lg bg-[#f8fafc] px-3 py-2 border border-[#e2e8f0]">
                      <div className="text-xs font-medium text-slate-500 mb-1">Current</div>
                      <div className="text-xs text-[#334155] font-mono break-all">
                        {fmtVal(row.current_value)}
                      </div>
                    </div>
                    <div className="rounded-lg bg-[#eff6ff] px-3 py-2 border border-[#bfdbfe]">
                      <div className="text-xs font-medium text-[#1d4ed8] mb-1">Requested</div>
                      <div className="text-xs text-[#1e40af] font-mono break-all">
                        {fmtVal(row.requested_value)}
                      </div>
                    </div>
                  </div>
                )}

                {/* Reason */}
                {row.reason && (
                  <p className="whitespace-pre-line rounded-md bg-[#f8fafc] px-3 py-2 text-xs text-[#334155]">
                    {row.reason}
                  </p>
                )}

                {/* AI insight */}
                {row.ai_insight && (
                  <div className="flex items-start gap-2 rounded-lg bg-[#fafafa] border border-[#e2e8f0] px-3 py-2">
                    <span className="text-base leading-none mt-0.5">✦</span>
                    <p className="text-xs text-[#475569] leading-relaxed">{row.ai_insight}</p>
                  </div>
                )}

                {/* HR action area (only for pending) */}
                {isPending && (
                  <div className="space-y-2">
                    <label className="block text-xs font-medium text-[#475569]" htmlFor={`note-${row.id}`}>
                      Note for the employee (optional)
                    </label>
                    <textarea
                      id={`note-${row.id}`}
                      value={activeNote[row.id] ?? ''}
                      onChange={(e) =>
                        setActiveNote((prev) => ({ ...prev, [row.id]: e.target.value }))
                      }
                      rows={2}
                      maxLength={2000}
                      disabled={isSaving}
                      placeholder="Adds context to the decision."
                      className="w-full rounded-md border border-[#cbd5e1] bg-white px-3 py-2 text-xs text-[#0b2b43] focus:border-[#0b2b43] focus:outline-none focus:ring-1 focus:ring-[#0b2b43]"
                    />
                    <div className="flex gap-2 justify-end">
                      <Button unstyled
                        type="button"
                        onClick={() => void resolve(row, 'rejected')}
                        disabled={isSaving}
                        className="rounded-lg border border-[#e2e8f0] bg-white px-3 py-1.5 text-xs font-medium text-[#374151] hover:bg-[#f8fafc] disabled:opacity-50 transition-colors"
                      >
                        Reject
                      </Button>
                      <Button unstyled
                        type="button"
                        onClick={() => void resolve(row, 'approved')}
                        disabled={isSaving}
                        className="rounded-lg bg-[#0b2b43] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#0f3858] disabled:opacity-50 transition-colors"
                      >
                        {isSaving ? 'Saving…' : 'Approve'}
                      </Button>
                    </div>
                  </div>
                )}

                {/* Audit trail toggle */}
                {Array.isArray(row.audit_events) && row.audit_events.length > 0 && (
                  <div>
                    <Button unstyled
                      type="button"
                      onClick={() =>
                        setExpandedAudit((prev) => ({ ...prev, [row.id]: !prev[row.id] }))
                      }
                      className="text-xs text-[#6b7280] hover:text-[#0b2b43] transition-colors"
                    >
                      {showAudit ? '▲ Hide' : '▼ Show'} audit trail ({row.audit_events.length})
                    </Button>
                    {showAudit && (
                      <ol className="mt-2 space-y-1 pl-3 border-l-2 border-[#e2e8f0]">
                        {row.audit_events.map((ev, i) => (
                          <li key={i} className="text-xs text-[#6b7280]">
                            <span className="font-medium text-[#334155]">{ev.action}</span>
                            {ev.actor && <span> by {ev.actor}</span>}
                            {ev.note && <span> — {ev.note}</span>}
                            <span className="ml-2 text-slate-500">{fmtTs(ev.ts)}</span>
                          </li>
                        ))}
                      </ol>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};
