/**
 * [P2-6] PolicyReviewQueuePage.tsx
 *
 * HR validation gate — the mandatory human-in-the-loop review step before
 * any AI-extracted policy value enters the knowledge base.
 *
 * Route: /hr/policy-builder/review
 *
 * Per-row actions: Approve · Edit (inline) · Reject (with optional note)
 * Rules:
 *   - No bulk-approve — every row requires an explicit HR decision
 *   - Cannot publish until conflicts = 0 and all rows are actioned
 *   - Confidence badge: green ≥ 0.90, amber 0.70–0.89, red < 0.70
 *   - Conflict flag (red ⚠) blocks the category until resolved
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Input } from '../../../components/antigravity/Input';
import { Button } from '../../../components/antigravity/Button';
import { AppShell } from '../../../components/AppShell';
import {
  policyBuilderPipelineAPI,
  type ReviewQueueItem,
  type ReviewQueueResponse,
} from '../../../api/policyBuilderPipeline';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function confidenceBadgeStyle(score: number | null): { bg: string; text: string; label: string } {
  if (score === null) return { bg: 'bg-slate-100', text: 'text-slate-500', label: '—' };
  const pct = Math.round(score * 100);
  if (score >= 0.90) return { bg: 'bg-emerald-100', text: 'text-emerald-700', label: `${pct}%` };
  if (score >= 0.70) return { bg: 'bg-amber-100', text: 'text-amber-700', label: `${pct}%` };
  return { bg: 'bg-rose-100', text: 'text-rose-700', label: `${pct}%` };
}

// N11-FU2 (AIQ-851 follow-up): per-field confidence below this threshold maps to
// the "absent/guessed" tier of the extraction's 3-tier scale (1.0 / 0.5 / 0.1) —
// HR should verify these manually before approving. The badge already colours
// anything < 0.70 rose; this adds an explicit warning icon at the < 0.5 line so
// the "verify manually" tier is unmistakable.
export const LOW_CONFIDENCE_THRESHOLD = 0.5;

export function isLowConfidence(score: number | null): boolean {
  return score !== null && score < LOW_CONFIDENCE_THRESHOLD;
}

function statusBadge(item: ReviewQueueItem) {
  if (item.status === 'validated') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-700">
        ✓ Approved
      </span>
    );
  }
  if (item.status === 'rejected') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-700">
        ✗ Rejected
      </span>
    );
  }
  if (item.status === 'edited') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-700">
        ✎ Edited
      </span>
    );
  }
  return null;
}

function formatValue(item: ReviewQueueItem): string {
  const v = item.hr_override_value ?? item.value;
  if (v == null) return '—';
  const parts = [String(v)];
  if (item.currency) parts.unshift(item.currency);
  if (item.unit) parts.push(`/ ${item.unit}`);
  return parts.join(' ');
}

// ---------------------------------------------------------------------------
// Row component
// ---------------------------------------------------------------------------

interface ReviewRowProps {
  item: ReviewQueueItem;
  onApprove: (id: string) => void;
  onEdit: (id: string, value: string) => void;
  onReject: (id: string, note: string) => void;
  loading: boolean;
}

export const ReviewRow: React.FC<ReviewRowProps> = ({ item, onApprove, onEdit, onReject, loading }) => {
  const [editMode, setEditMode] = useState(false);
  const [editValue, setEditValue] = useState(String(item.hr_override_value ?? item.value ?? ''));
  const [rejectMode, setRejectMode] = useState(false);
  const [rejectNote, setRejectNote] = useState('');

  const badge = confidenceBadgeStyle(item.confidence_score);
  const hasConflicts = item.conflicts.length > 0;
  const isActioned = item.status !== 'pending';

  const handleSaveEdit = () => {
    onEdit(item.id, editValue);
    setEditMode(false);
  };

  const handleReject = () => {
    onReject(item.id, rejectNote);
    setRejectMode(false);
    setRejectNote('');
  };

  return (
    <tr
      className={[
        'border-b border-slate-100 transition-colors',
        isActioned ? 'opacity-60' : 'hover:bg-slate-50',
        hasConflicts && !isActioned ? 'bg-rose-50/40' : '',
      ].join(' ')}
    >
      {/* Category */}
      <td className="py-3 px-4 align-top">
        <div className="flex flex-col gap-0.5">
          <span className="text-xs font-mono text-slate-400">{item.category_code}</span>
          <span className="text-sm font-medium text-slate-900">{item.category_display_name}</span>
          {item.tier && (
            <span className="text-xs text-slate-500">{item.tier}</span>
          )}
        </div>
      </td>

      {/* Value */}
      <td className="py-3 px-4 align-top w-48">
        {editMode ? (
          <div className="flex items-center gap-1.5">
            <Input unstyled
              type="text"
              value={editValue}
              onChange={(v) => setEditValue(v)}
              className="w-24 rounded border border-blue-300 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-200"
              autoFocus
            />
            <Button unstyled
              type="button"
              onClick={handleSaveEdit}
              disabled={loading || !editValue.trim()}
              className="px-2 py-1 rounded text-xs font-semibold bg-navy-800 text-white hover:bg-navy-900 disabled:opacity-50"
            >
              Save
            </Button>
            <Button unstyled
              type="button"
              onClick={() => setEditMode(false)}
              className="px-2 py-1 rounded text-xs text-slate-500 hover:text-slate-700"
            >
              Cancel
            </Button>
          </div>
        ) : (
          <span className="text-sm text-slate-900 font-medium">{formatValue(item)}</span>
        )}
        {item.hr_override_value && !editMode && (
          <div className="text-[10px] text-blue-500 mt-0.5">HR edited</div>
        )}
      </td>

      {/* Source */}
      <td className="py-3 px-4 align-top max-w-[180px]">
        <div className="text-xs text-slate-700 truncate" title={item.source_doc}>
          {item.source_doc}
        </div>
        {item.source_page != null && (
          <div className="text-[10px] text-slate-400">p. {item.source_page}</div>
        )}
      </td>

      {/* Confidence */}
      <td className="py-3 px-4 align-top text-center">
        <span
          className={`inline-block px-2 py-0.5 rounded text-xs font-bold ${badge.bg} ${badge.text}`}
          title={item.ambiguity_flag ? 'Ambiguity flag set by classifier' : undefined}
        >
          {badge.label}
          {item.ambiguity_flag && ' ⚠'}
        </span>
        {isLowConfidence(item.confidence_score) && (
          <span
            role="img"
            aria-label="Low confidence — verify manually"
            title="Low confidence (below 50%) — verify this value against the source document before approving."
            className="ml-1 align-middle text-rose-600 font-bold cursor-help"
          >
            ⚠
          </span>
        )}
      </td>

      {/* Conflicts */}
      <td className="py-3 px-4 align-top text-center">
        {hasConflicts ? (
          <div className="flex flex-col items-center gap-1">
            {item.conflicts.map((c) => (
              <div key={c.conflict_id} className="flex items-center gap-1">
                <span
                  className={`text-xs font-bold px-1.5 py-0.5 rounded ${
                    c.severity === 'high'
                      ? 'bg-rose-100 text-rose-700'
                      : 'bg-amber-100 text-amber-700'
                  }`}
                  title={`Conflicts with ${c.other_source_doc}${c.other_page != null ? ` p.${c.other_page}` : ''}: value ${c.other_value}`}
                >
                  {c.severity === 'high' ? '⚠ High' : '~ Med'}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <span className="text-slate-300 text-sm">—</span>
        )}
      </td>

      {/* Status */}
      <td className="py-3 px-4 align-top text-center">
        {statusBadge(item)}
      </td>

      {/* Actions */}
      <td className="py-3 px-4 align-top">
        {isActioned ? null : (
          <div className="flex flex-col gap-1.5">
            {rejectMode ? (
              <div className="flex flex-col gap-1">
                <textarea
                  value={rejectNote}
                  onChange={(e) => setRejectNote(e.target.value)}
                  placeholder="Optional reason…"
                  rows={2}
                  className="w-full rounded border border-rose-200 px-2 py-1 text-xs resize-none focus:outline-none focus:ring-2 focus:ring-rose-200"
                />
                <div className="flex gap-1">
                  <Button unstyled
                    type="button"
                    onClick={handleReject}
                    disabled={loading}
                    className="px-2 py-1 rounded text-xs font-semibold bg-rose-600 text-white hover:bg-rose-700 disabled:opacity-50"
                  >
                    Confirm reject
                  </Button>
                  <Button unstyled
                    type="button"
                    onClick={() => setRejectMode(false)}
                    className="px-2 py-1 rounded text-xs text-slate-500 hover:text-slate-700"
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex gap-1.5 flex-wrap">
                <Button unstyled
                  type="button"
                  onClick={() => onApprove(item.id)}
                  disabled={loading || hasConflicts}
                  title={hasConflicts ? 'Resolve conflicts before approving' : undefined}
                  className="px-2.5 py-1 rounded text-xs font-semibold bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  Approve
                </Button>
                <Button unstyled
                  type="button"
                  onClick={() => setEditMode(true)}
                  disabled={loading}
                  className="px-2.5 py-1 rounded text-xs font-semibold border border-blue-300 text-blue-700 hover:bg-blue-50 disabled:opacity-40 transition-colors"
                >
                  Edit
                </Button>
                <Button unstyled
                  type="button"
                  onClick={() => setRejectMode(true)}
                  disabled={loading}
                  className="px-2.5 py-1 rounded text-xs font-semibold border border-rose-200 text-rose-600 hover:bg-rose-50 disabled:opacity-40 transition-colors"
                >
                  Reject
                </Button>
              </div>
            )}
          </div>
        )}
      </td>
    </tr>
  );
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function PolicyReviewQueuePage() {
  const [queue, setQueue] = useState<ReviewQueueResponse | null>(null);
  const [items, setItems] = useState<ReviewQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null); // factId

  useEffect(() => {
    setLoading(true);
    policyBuilderPipelineAPI
      .getReviewQueue()
      .then((data) => {
        setQueue(data);
        setItems(data.items);
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : 'Failed to load review queue');
      })
      .finally(() => setLoading(false));
  }, []);

  const handleApprove = useCallback(async (factId: string) => {
    setActionLoading(factId);
    try {
      const res = await policyBuilderPipelineAPI.actionReviewItem(factId, { action: 'approve' });
      setItems((prev) => prev.map((i) => (i.id === factId ? res.item : i)));
    } catch {
      // silent — optimistic update already applied
    } finally {
      setActionLoading(null);
    }
  }, []);

  const handleEdit = useCallback(async (factId: string, value: string) => {
    setActionLoading(factId);
    // Optimistic update
    setItems((prev) =>
      prev.map((i) =>
        i.id === factId ? { ...i, status: 'edited', hr_override_value: value } : i
      )
    );
    try {
      const res = await policyBuilderPipelineAPI.actionReviewItem(factId, {
        action: 'edit',
        hr_override_value: value,
      });
      setItems((prev) => prev.map((i) => (i.id === factId ? res.item : i)));
    } catch {
      // Revert optimistic update on failure
      setItems((prev) =>
        prev.map((i) =>
          i.id === factId ? { ...i, status: 'pending', hr_override_value: null } : i
        )
      );
    } finally {
      setActionLoading(null);
    }
  }, []);

  const handleReject = useCallback(async (factId: string, note: string) => {
    setActionLoading(factId);
    // Optimistic: remove from pending view
    setItems((prev) =>
      prev.map((i) =>
        i.id === factId ? { ...i, status: 'rejected', rejection_note: note || null } : i
      )
    );
    try {
      const res = await policyBuilderPipelineAPI.actionReviewItem(factId, {
        action: 'reject',
        rejection_note: note || null,
      });
      setItems((prev) => prev.map((i) => (i.id === factId ? res.item : i)));
    } catch {
      setItems((prev) =>
        prev.map((i) =>
          i.id === factId ? { ...i, status: 'pending', rejection_note: null } : i
        )
      );
    } finally {
      setActionLoading(null);
    }
  }, []);

  // Derived counts
  const pendingCount = items.filter((i) => i.status === 'pending').length;
  const approvedCount = items.filter(
    (i) => i.status === 'validated' || i.status === 'edited'
  ).length;
  const conflictCount = items.filter(
    (i) => i.status === 'pending' && i.conflicts.some((c) => c.severity === 'high')
  ).length;
  const total = items.length;
  const progressPct = total > 0 ? Math.round((approvedCount / total) * 100) : 0;
  const allActioned = total > 0 && pendingCount === 0;
  const canPublish = allActioned && conflictCount === 0;

  return (
    <AppShell>
      <div className="min-h-screen bg-[#f8fafc]">
        <div className="max-w-7xl mx-auto px-6 py-8">
          {/* Page header */}
          <div className="mb-6">
            <h1 className="text-2xl font-bold text-[#0b2b43]">Policy Review Queue</h1>
            <p className="text-[#64748b] mt-1">
              Review and validate AI-extracted policy values before they enter the knowledge base.
              {queue?.document_name && (
                <span className="font-medium text-[#0b2b43]"> · {queue.document_name}</span>
              )}
            </p>
          </div>

          {/* Progress header */}
          {!loading && !error && total > 0 && (
            <div className="mb-6 rounded-2xl border border-[#e2e8f0] bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between mb-3 flex-wrap gap-3">
                <div className="flex items-center gap-6">
                  <span className="text-sm font-semibold text-[#0b2b43]">
                    Review progress: {approvedCount} of {total} actioned
                  </span>
                  <div className="flex items-center gap-3 text-sm text-slate-500">
                    <span>
                      <span className="font-semibold text-amber-600">{pendingCount}</span> pending
                    </span>
                    <span>
                      <span className="font-semibold text-emerald-600">{approvedCount}</span> approved/edited
                    </span>
                    {conflictCount > 0 && (
                      <span className="font-semibold text-rose-600">
                        {conflictCount} conflict{conflictCount !== 1 ? 's' : ''} remaining
                      </span>
                    )}
                  </div>
                </div>
                <Button unstyled
                  type="button"
                  disabled={!canPublish}
                  title={
                    !canPublish
                      ? conflictCount > 0
                        ? 'Resolve all conflicts before publishing'
                        : 'All rows must be actioned before publishing'
                      : undefined
                  }
                  className={[
                    'px-5 py-2 rounded-xl text-sm font-semibold transition-all',
                    canPublish
                      ? 'bg-[#0b2b43] text-white hover:bg-[#0e3a5c]'
                      : 'bg-slate-200 text-slate-400 cursor-not-allowed',
                  ].join(' ')}
                >
                  Publish to knowledge base
                </Button>
              </div>
              {/* Progress bar */}
              <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all bg-emerald-500"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
              <div className="text-right text-xs text-slate-400 mt-1">{progressPct}%</div>
            </div>
          )}

          {/* Loading */}
          {loading && (
            <div className="flex justify-center py-20 text-slate-400 text-sm">
              Loading review queue…
            </div>
          )}

          {/* Error */}
          {error && !loading && (
            <div className="rounded-xl bg-rose-50 border border-rose-200 px-5 py-4 text-sm text-rose-700">
              {error}
            </div>
          )}

          {/* Empty state */}
          {!loading && !error && total === 0 && (
            <div className="rounded-2xl border border-[#e2e8f0] bg-white p-12 text-center shadow-sm">
              <div className="text-4xl mb-3">✓</div>
              <h3 className="text-lg font-semibold text-[#0b2b43]">All items reviewed</h3>
              <p className="text-slate-500 mt-1 text-sm">
                No pending items — the review queue is empty.
              </p>
            </div>
          )}

          {/* Review table */}
          {!loading && !error && total > 0 && (
            <div className="rounded-2xl border border-[#e2e8f0] bg-white shadow-sm overflow-hidden">
              <table className="w-full border-collapse text-left">
                <thead>
                  <tr className="bg-[#f8fafc] border-b border-[#e2e8f0]">
                    {['Category', 'Value', 'Source', 'Confidence', 'Conflicts', 'Status', 'Actions'].map((h) => (
                      <th
                        key={h}
                        className="py-3 px-4 text-xs font-semibold text-slate-500 uppercase tracking-wide"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <ReviewRow
                      key={item.id}
                      item={item}
                      onApprove={handleApprove}
                      onEdit={handleEdit}
                      onReject={handleReject}
                      loading={actionLoading === item.id}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
