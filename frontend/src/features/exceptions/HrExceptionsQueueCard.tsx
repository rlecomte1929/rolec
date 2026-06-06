/**
 * HR-side card for the Command Center: lists pending exception requests
 * across the HR's whole company and lets HR approve/reject each row with
 * an optional note. T1.3 part 3.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { Card, Button } from '../../components/antigravity';
import {
  listExceptionRequestsForCompany,
  resolveExceptionRequest,
  type ExceptionRequest,
} from '../../api/exceptions';

function fmtAmount(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency: currency || 'USD',
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `${amount} ${currency}`;
  }
}

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

export const HrExceptionsQueueCard: React.FC = () => {
  const [rows, setRows] = useState<ExceptionRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeNote, setActiveNote] = useState<Record<string, string>>({});
  const [savingId, setSavingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listExceptionRequestsForCompany('pending');
      setRows(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Could not load exception queue.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const resolve = async (row: ExceptionRequest, status: 'approved' | 'rejected') => {
    setSavingId(row.id);
    try {
      await resolveExceptionRequest(row.id, {
        status,
        hr_note: activeNote[row.id]?.trim() || undefined,
      });
      // Drop from the pending list locally; HR can refresh to see resolved set.
      setRows((prev) => prev.filter((r) => r.id !== row.id));
      setActiveNote((prev) => {
        const next = { ...prev };
        delete next[row.id];
        return next;
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Could not resolve.';
      setError(msg);
    } finally {
      setSavingId(null);
    }
  };

  return (
    <Card padding="lg">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-[#0b2b43]">Exception requests</h2>
          <p className="text-sm text-[#6b7280] mt-1">
            Employees asking to exceed a policy cap. Approve or reject; the decision shows on
            their Estimate Review page.
          </p>
        </div>
        <Button unstyled
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className="text-sm text-[#0b2b43] hover:underline disabled:opacity-50"
        >
          {loading ? 'Refreshing…' : 'Refresh'}
        </Button>
      </div>

      {error && (
        <div role="alert" className="mb-4 rounded-lg border border-[#fecaca] bg-[#fef2f2] px-3 py-2 text-sm text-[#991b1b]">
          {error}
        </div>
      )}

      {loading && rows.length === 0 ? (
        <div className="space-y-2 py-4">
          {[...Array(2)].map((_, i) => (
            <div key={i} className="h-16 rounded-lg bg-[#f1f5f9] animate-pulse" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-lg border border-dashed border-[#cbd5e1] py-8 text-center text-sm text-[#6b7280]">
          No pending exception requests.
        </div>
      ) : (
        <ul className="space-y-3">
          {rows.map((row) => {
            const note = activeNote[row.id] ?? '';
            const isSaving = savingId === row.id;
            const overage = row.requested_amount - row.cap_amount;
            return (
              <li key={row.id} className="rounded-lg border border-[#e2e8f0] bg-white p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-[#0b2b43] capitalize">{row.category}</span>
                      <span className="inline-flex items-center rounded-full border border-[#fde68a] bg-[#fef9c3] px-2 py-0.5 text-xs font-medium text-[#854d0e]">
                        Pending
                      </span>
                    </div>
                    <div className="mt-1 text-sm text-[#0b2b43]">
                      Requested <strong>{fmtAmount(row.requested_amount, row.currency)}</strong> vs cap{' '}
                      <strong>{fmtAmount(row.cap_amount, row.currency)}</strong>
                      {overage > 0 && (
                        <span className="ml-2 text-[#9a3412]">
                          (+{fmtAmount(overage, row.currency)} over)
                        </span>
                      )}
                    </div>
                    <div className="mt-1 text-xs text-[#6b7280]">
                      Submitted {fmtDate(row.created_at)} · case <span className="font-mono">{row.case_id.slice(0, 8)}</span>
                    </div>
                  </div>
                </div>
                <p className="mt-3 whitespace-pre-line rounded-md bg-[#f8fafc] px-3 py-2 text-sm text-[#334155]">
                  {row.reason}
                </p>
                <label className="mt-3 block text-xs font-medium text-[#475569]" htmlFor={`note-${row.id}`}>
                  Note for the employee (optional)
                </label>
                <textarea
                  id={`note-${row.id}`}
                  value={note}
                  onChange={(e) =>
                    setActiveNote((prev) => ({ ...prev, [row.id]: e.target.value }))
                  }
                  rows={2}
                  maxLength={2000}
                  disabled={isSaving}
                  placeholder="Adds context to the approval / rejection."
                  className="mt-1 w-full rounded-md border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#0b2b43] focus:border-[#0b2b43] focus:outline-none focus:ring-1 focus:ring-[#0b2b43]"
                />
                <div className="mt-3 flex flex-wrap items-center justify-end gap-2">
                  <Button
                    variant="outline"
                    onClick={() => void resolve(row, 'rejected')}
                    disabled={isSaving}
                  >
                    Reject
                  </Button>
                  <Button onClick={() => void resolve(row, 'approved')} disabled={isSaving}>
                    {isSaving ? 'Saving…' : 'Approve'}
                  </Button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
};
