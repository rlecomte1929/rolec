/**
 * FeedbackTab — unified admin view for all feedback streams.
 *
 * Reads from /api/admin/feedback (normalized UNION of product/ai_answers/helpfulness).
 * Triage (status/owner/resolution) goes through PATCH — never mutates ML source tables.
 */

import { useEffect, useState, useCallback } from 'react';
import { Button } from '../antigravity/Button';
import {
  listFeedback,
  triageFeedback,
  type UnifiedFeedbackItem,
  type FeedbackStream,
  type TriageStatus,
} from '../../api/adminFeedback';

type FilterStatus = TriageStatus | 'all';

const STATUS_CHIP: Record<TriageStatus, string> = {
  new:      'bg-blue-100 text-blue-700 border-blue-200',
  reviewed: 'bg-amber-100 text-amber-700 border-amber-200',
  acted_on: 'bg-green-100 text-green-700 border-green-200',
  closed:   'bg-gray-100 text-gray-500 border-gray-200',
};

const STATUS_LABEL: Record<TriageStatus, string> = {
  new:      'New',
  reviewed: 'Reviewed',
  acted_on: 'Acted on',
  closed:   'Closed',
};

const STREAM_LABEL: Record<FeedbackStream, string> = {
  product:     'Product',
  ai_answers:  'AI Answers',
  helpfulness: 'Helpfulness',
};

function fmtRelative(iso: string): string {
  const diff  = Date.now() - new Date(iso).getTime();
  const hours = Math.floor(diff / 3_600_000);
  const days  = Math.floor(diff / 86_400_000);
  if (hours < 1)  return 'Just now';
  if (hours < 24) return `${hours}h ago`;
  return `${days}d ago`;
}

function fmtDate(iso: string): string {
  const d = new Date(iso);
  return (
    d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) +
    ' · ' +
    d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
  );
}

const STREAMS: FeedbackStream[] = ['product', 'ai_answers', 'helpfulness'];

export function FeedbackTab() {
  const [rows, setRows]                   = useState<UnifiedFeedbackItem[]>([]);
  const [loading, setLoading]             = useState(true);
  const [error, setError]                 = useState<string | null>(null);
  const [activeStream, setActiveStream]   = useState<FeedbackStream | 'all'>('all');
  const [filterStatus, setFilterStatus]   = useState<FilterStatus>('all');
  const [savingId, setSavingId]           = useState<string | null>(null);
  const [expanded, setExpanded]           = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await listFeedback(
        activeStream !== 'all' ? { stream: activeStream } : undefined
      );
      setRows(items);
    } catch {
      setError('Failed to load feedback.');
    } finally {
      setLoading(false);
    }
  }, [activeStream]);

  useEffect(() => { void load(); }, [load]);

  const updateStatus = async (row: UnifiedFeedbackItem, newStatus: TriageStatus) => {
    setSavingId(row.id);
    try {
      await triageFeedback(row.stream, row.id, { status: newStatus });
      setRows((prev) => prev.map((r) => r.id === row.id ? { ...r, status: newStatus } : r));
    } catch {
      // silently fail — user can retry via Refresh
    }
    setSavingId(null);
  };

  const displayed = rows.filter((r) => {
    if (filterStatus !== 'all' && r.status !== filterStatus) return false;
    return true;
  });

  const counts = {
    all:      rows.length,
    new:      rows.filter((r) => r.status === 'new' || r.status === null).length,
    reviewed: rows.filter((r) => r.status === 'reviewed').length,
    acted_on: rows.filter((r) => r.status === 'acted_on').length,
    closed:   rows.filter((r) => r.status === 'closed').length,
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-sm text-gray-400">Loading…</p>
      </div>
    );
  }
  if (error) {
    return (
      <div className="flex flex-col items-center gap-3 py-20">
        <p className="text-sm text-red-600">{error}</p>
        <Button unstyled onClick={load} className="text-sm text-gray-500 underline">Retry</Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Stream tabs */}
      <div className="flex gap-1 rounded-lg border border-gray-200 p-0.5 bg-gray-50 w-fit">
        {(['all', ...STREAMS] as const).map((s) => (
          <Button
            unstyled
            key={s}
            onClick={() => { setActiveStream(s); setExpanded(null); }}
            className={`text-xs px-3 py-1 rounded-md font-medium transition-colors ${
              activeStream === s
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {s === 'all' ? 'All streams' : STREAM_LABEL[s]}
          </Button>
        ))}
      </div>

      {/* Summary bar */}
      <div className="grid grid-cols-4 gap-3">
        {([
          { label: 'Total',    value: counts.all,      color: 'text-gray-900' },
          { label: 'New',      value: counts.new,      color: 'text-blue-600' },
          { label: 'Reviewed', value: counts.reviewed, color: 'text-amber-600' },
          { label: 'Acted on', value: counts.acted_on, color: 'text-green-600' },
        ] as const).map(({ label, value, color }) => (
          <div key={label} className="rounded-lg border border-gray-200 px-4 py-3 bg-white">
            <p className={`text-xl font-bold ${color}`}>{value}</p>
            <p className="text-xs text-gray-400 mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      {/* Status filter */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex gap-1 rounded-lg border border-gray-200 p-0.5 bg-gray-50">
          {(['all', 'new', 'reviewed', 'acted_on', 'closed'] as const).map((f) => (
            <Button
              unstyled
              key={f}
              onClick={() => setFilterStatus(f)}
              className={`text-xs px-3 py-1 rounded-md font-medium transition-colors ${
                filterStatus === f
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {f === 'all' ? 'All status' : STATUS_LABEL[f]}
              {' '}
              <span className="opacity-50">
                {f === 'all' ? counts.all : counts[f as TriageStatus]}
              </span>
            </Button>
          ))}
        </div>
        <div className="flex-1" />
        <Button unstyled onClick={load} className="text-xs text-gray-400 hover:text-gray-600 underline">
          Refresh
        </Button>
      </div>

      {/* Empty state */}
      {displayed.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center rounded-lg border border-gray-200 bg-white">
          <p className="text-sm font-medium text-gray-600">No items match the current filter.</p>
          <p className="text-xs text-gray-400 mt-1">Try a different stream or status filter.</p>
        </div>
      )}

      {/* Table */}
      {displayed.length > 0 && (
        <div className="rounded-lg border border-gray-200 overflow-hidden">
          <div className="grid grid-cols-[100px_110px_1fr_120px_120px_140px] bg-gray-50 border-b border-gray-200 text-[11px] font-semibold text-gray-400 uppercase tracking-wide">
            <div className="px-3 py-2.5">ID</div>
            <div className="px-3 py-2.5">Stream</div>
            <div className="px-3 py-2.5">Text</div>
            <div className="px-3 py-2.5">Verdict</div>
            <div className="px-3 py-2.5">Date</div>
            <div className="px-3 py-2.5">Status</div>
          </div>
          <div className="divide-y divide-gray-100 bg-white">
            {displayed.map((row) => {
              const isExpanded = expanded === row.id;
              const effectiveStatus: TriageStatus = row.status ?? 'new';
              return (
                <div key={row.id}>
                  <div
                    className="grid grid-cols-[100px_110px_1fr_120px_120px_140px] items-center hover:bg-gray-50 transition-colors cursor-pointer"
                    onClick={() => setExpanded(isExpanded ? null : row.id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setExpanded(isExpanded ? null : row.id);
                      }
                    }}
                    role="button"
                    tabIndex={0}
                    aria-expanded={isExpanded}
                  >
                    <div className="px-3 py-2.5">
                      <span className="font-mono text-[10.5px] text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">
                        {(row.source_ref ?? row.id).slice(0, 8)}
                      </span>
                    </div>
                    <div className="px-3 py-2.5">
                      <span className="text-[11px] font-medium text-gray-600">
                        {STREAM_LABEL[row.stream]}
                      </span>
                    </div>
                    <div className="px-3 py-2.5">
                      <p className="text-[12px] text-gray-700 truncate">{row.text ?? '—'}</p>
                    </div>
                    <div className="px-3 py-2.5">
                      <span className="text-[11px] text-gray-500">{row.verdict ?? '—'}</span>
                    </div>
                    <div className="px-3 py-2.5">
                      <span className="text-[11px] text-gray-400" title={fmtDate(row.created_at)}>
                        {fmtRelative(row.created_at)}
                      </span>
                    </div>
                    <div className="px-3 py-2.5">
                      <select
                        onClick={(e) => e.stopPropagation()}
                        value={effectiveStatus}
                        disabled={savingId === row.id}
                        onChange={(e) => updateStatus(row, e.target.value as TriageStatus)}
                        className={`text-[11px] font-medium px-2 py-0.5 rounded border cursor-pointer focus:outline-none disabled:opacity-50 ${STATUS_CHIP[effectiveStatus]}`}
                      >
                        {(['new', 'reviewed', 'acted_on', 'closed'] as TriageStatus[]).map((s) => (
                          <option key={s} value={s}>{STATUS_LABEL[s]}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="bg-gray-50 border-t border-gray-100 px-4 py-4 space-y-2">
                      <div className="flex items-center gap-2 flex-wrap text-[10.5px]">
                        <span className="font-semibold text-gray-600">{STREAM_LABEL[row.stream]}</span>
                        <span className="font-mono text-gray-400">{row.source_ref}</span>
                        <span className="text-gray-400">{fmtDate(row.created_at)}</span>
                        {row.user_id && (
                          <span className="font-mono text-gray-400">user: {row.user_id.slice(0, 12)}…</span>
                        )}
                        {row.company_id && (
                          <span className="font-mono text-gray-400">co: {row.company_id}</span>
                        )}
                      </div>
                      <p className="text-sm text-gray-800 whitespace-pre-wrap">{row.text ?? '—'}</p>
                      {row.owner && (
                        <p className="text-[10.5px] text-gray-400">Owner: {row.owner}</p>
                      )}
                      {row.resolution && (
                        <p className="text-[10.5px] text-gray-400">Resolution: {row.resolution}</p>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
