/**
 * FeedbackTab — admin view for pilot feedback submissions.
 *
 * Notion-style triage table: report ID · type · page · message · screenshot · date · status.
 * Inline status update (new → reviewed → acted_on).
 */

import { useEffect, useState, useCallback } from 'react';
import { Button } from '../antigravity/Button';
import { supabase } from '../../api/supabase';

type FeedbackStatus   = 'new' | 'reviewed' | 'acted_on';
type FeedbackCategory = 'bug' | 'idea' | 'other';
type FilterStatus     = FeedbackStatus | 'all';
type FilterCategory   = FeedbackCategory | 'all';

interface FeedbackRow {
  id:              string;
  user_id:         string | null;
  page_url:        string;
  category:        FeedbackCategory;
  message:         string;
  status:          FeedbackStatus;
  created_at:      string;
  report_id:       string | null;
  screenshot_data: string | null;
}

// ── Style maps ────────────────────────────────────────────────────────────────

const STATUS_CHIP: Record<FeedbackStatus, string> = {
  new:      'bg-blue-100 text-blue-700 border-blue-200',
  reviewed: 'bg-amber-100 text-amber-700 border-amber-200',
  acted_on: 'bg-green-100 text-green-700 border-green-200',
};

const STATUS_LABEL: Record<FeedbackStatus, string> = {
  new:      'New',
  reviewed: 'Reviewed',
  acted_on: 'Acted on',
};

const CAT_CHIP: Record<FeedbackCategory, string> = {
  bug:   'bg-red-50 text-red-600 border-red-200',
  idea:  'bg-teal-50 text-teal-600 border-teal-200',
  other: 'bg-gray-100 text-gray-500 border-gray-200',
};

const CAT_ICON: Record<FeedbackCategory, string> = {
  bug:   '🐛',
  idea:  '💡',
  other: '💬',
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) +
         ' · ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
}

function fmtRelative(iso: string): string {
  const diff  = Date.now() - new Date(iso).getTime();
  const hours = Math.floor(diff / 3_600_000);
  const days  = Math.floor(diff / 86_400_000);
  if (hours < 1)  return 'Just now';
  if (hours < 24) return `${hours}h ago`;
  return `${days}d ago`;
}

// ── Screenshot lightbox ───────────────────────────────────────────────────────

function ScreenshotLightbox({ src, onClose }: { src: string; onClose: () => void }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-[200] bg-black/75 flex items-center justify-center p-6"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      onKeyDown={(e) => { if (e.key === 'Escape') onClose(); }}
      role="button"
      tabIndex={-1}
      aria-label="Close screenshot preview"
    >
      <div className="relative max-w-4xl max-h-[85vh] rounded-xl overflow-hidden shadow-2xl">
        <img src={src} alt="Feedback screenshot" className="max-w-full max-h-[85vh] object-contain" />
        <button
          onClick={onClose}
          className="absolute top-3 right-3 w-7 h-7 rounded-full bg-black/60 text-white flex items-center justify-center text-sm hover:bg-black"
        >✕</button>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function FeedbackTab() {
  const [rows, setRows]           = useState<FeedbackRow[]>([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<string | null>(null);
  const [filterStatus, setFilterStatus]   = useState<FilterStatus>('all');
  const [filterCategory, setFilterCategory] = useState<FilterCategory>('all');
  const [savingId, setSavingId]   = useState<string | null>(null);
  const [expanded, setExpanded]   = useState<string | null>(null);
  const [lightbox, setLightbox]   = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const { data, error: err } = await supabase
      .from('feedback')
      .select('id, user_id, page_url, category, message, status, created_at, report_id, screenshot_data')
      .order('created_at', { ascending: false })
      .limit(500);

    if (err) setError('Failed to load feedback.');
    else setRows((data) ?? []);
    setLoading(false);
  }, []);

  useEffect(() => { void load(); }, [load]);

  const updateStatus = async (row: FeedbackRow, newStatus: FeedbackStatus) => {
    setSavingId(row.id);
    const { error: err } = await supabase
      .from('feedback')
      .update({ status: newStatus })
      .eq('id', row.id);
    if (!err) setRows((prev) => prev.map((r) => r.id === row.id ? { ...r, status: newStatus } : r));
    setSavingId(null);
  };

  const displayed = rows.filter((r) => {
    if (filterStatus   !== 'all' && r.status   !== filterStatus)   return false;
    if (filterCategory !== 'all' && r.category !== filterCategory) return false;
    return true;
  });

  const counts = {
    all:      rows.length,
    new:      rows.filter((r) => r.status === 'new').length,
    reviewed: rows.filter((r) => r.status === 'reviewed').length,
    acted_on: rows.filter((r) => r.status === 'acted_on').length,
    bug:      rows.filter((r) => r.category === 'bug').length,
    idea:     rows.filter((r) => r.category === 'idea').length,
    other:    rows.filter((r) => r.category === 'other').length,
  };

  if (loading) {
    return <div className="flex items-center justify-center py-20"><p className="text-sm text-gray-400">Loading…</p></div>;
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
    <>
      {lightbox && <ScreenshotLightbox src={lightbox} onClose={() => setLightbox(null)} />}

      <div className="space-y-4">
        {/* Summary bar */}
        <div className="grid grid-cols-4 gap-3">
          {([
            { label: 'Total',     value: counts.all,      color: 'text-gray-900' },
            { label: 'New',       value: counts.new,      color: 'text-blue-600' },
            { label: 'Reviewed',  value: counts.reviewed, color: 'text-amber-600' },
            { label: 'Acted on',  value: counts.acted_on, color: 'text-green-600' },
          ] as const).map(({ label, value, color }) => (
            <div key={label} className="rounded-lg border border-gray-200 px-4 py-3 bg-white">
              <p className={`text-xl font-bold ${color}`}>{value}</p>
              <p className="text-xs text-gray-400 mt-0.5">{label}</p>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="flex items-center gap-4 flex-wrap">
          {/* Status filter */}
          <div className="flex gap-1 rounded-lg border border-gray-200 p-0.5 bg-gray-50">
            {(['all', 'new', 'reviewed', 'acted_on'] as const).map((f) => (
              <Button unstyled key={f} onClick={() => setFilterStatus(f)}
                className={`text-xs px-3 py-1 rounded-md font-medium transition-colors ${
                  filterStatus === f ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                }`}>
                {f === 'all' ? 'All status' : STATUS_LABEL[f]}
                {' '}<span className="opacity-50">{f === 'all' ? counts.all : counts[f]}</span>
              </Button>
            ))}
          </div>

          {/* Category filter */}
          <div className="flex gap-1 rounded-lg border border-gray-200 p-0.5 bg-gray-50">
            {(['all', 'bug', 'idea', 'other'] as const).map((f) => (
              <Button unstyled key={f} onClick={() => setFilterCategory(f)}
                className={`text-xs px-3 py-1 rounded-md font-medium transition-colors ${
                  filterCategory === f ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                }`}>
                {f === 'all' ? 'All types' : `${CAT_ICON[f]} ${f}`}
                {f !== 'all' && <span className="opacity-50 ml-1">{counts[f]}</span>}
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
            <p className="text-xs text-gray-400 mt-1">Try changing the status or type filter above.</p>
          </div>
        )}

        {/* Notion-style table */}
        {displayed.length > 0 && (
          <div className="rounded-lg border border-gray-200 overflow-hidden">
            {/* Table header */}
            <div className="grid grid-cols-[120px_80px_160px_1fr_80px_120px_160px] gap-0 bg-gray-50 border-b border-gray-200 text-[11px] font-semibold text-gray-400 uppercase tracking-wide">
              <div className="px-3 py-2.5">ID</div>
              <div className="px-3 py-2.5">Type</div>
              <div className="px-3 py-2.5">Page</div>
              <div className="px-3 py-2.5">Message</div>
              <div className="px-3 py-2.5">Shot</div>
              <div className="px-3 py-2.5">Date</div>
              <div className="px-3 py-2.5">Status</div>
            </div>

            {/* Rows */}
            <div className="divide-y divide-gray-100 bg-white">
              {displayed.map((row) => {
                const isExpanded = expanded === row.id;
                return (
                  <div key={row.id}>
                    {/* Compact row */}
                    <div
                      className="grid grid-cols-[120px_80px_160px_1fr_80px_120px_160px] gap-0 items-center hover:bg-gray-50 transition-colors cursor-pointer"
                      onClick={() => setExpanded(isExpanded ? null : row.id)}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setExpanded(isExpanded ? null : row.id); } }}
                      role="button"
                      tabIndex={0}
                      aria-expanded={isExpanded}
                    >
                      {/* Report ID */}
                      <div className="px-3 py-2.5">
                        <span className="font-mono text-[10.5px] text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">
                          {row.report_id ?? row.id.slice(0, 8)}
                        </span>
                      </div>

                      {/* Category */}
                      <div className="px-3 py-2.5">
                        <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10.5px] font-medium ${CAT_CHIP[row.category]}`}>
                          {CAT_ICON[row.category]} {row.category}
                        </span>
                      </div>

                      {/* Page */}
                      <div className="px-3 py-2.5">
                        <span className="text-[11px] font-mono text-gray-400 truncate block max-w-[140px]" title={row.page_url}>
                          {row.page_url}
                        </span>
                      </div>

                      {/* Message preview */}
                      <div className="px-3 py-2.5">
                        <p className="text-[12px] text-gray-700 truncate">{row.message}</p>
                      </div>

                      {/* Screenshot thumbnail */}
                      <div className="px-3 py-2.5">
                        {row.screenshot_data ? (
                          <button
                            className="w-12 h-8 rounded border border-gray-200 overflow-hidden hover:ring-2 ring-blue-400 transition-all"
                            onClick={(e) => { e.stopPropagation(); setLightbox(row.screenshot_data); }}
                            title="View screenshot"
                          >
                            <img src={row.screenshot_data} alt="" className="w-full h-full object-cover" />
                          </button>
                        ) : (
                          <span className="text-[10px] text-gray-300">—</span>
                        )}
                      </div>

                      {/* Date */}
                      <div className="px-3 py-2.5">
                        <span className="text-[11px] text-gray-400" title={fmtDate(row.created_at)}>
                          {fmtRelative(row.created_at)}
                        </span>
                      </div>

                      {/* Status inline editor */}
                      <div className="px-3 py-2.5">
                        <select
                          onClick={(e) => e.stopPropagation()}
                          value={row.status}
                          disabled={savingId === row.id}
                          onChange={(e) => updateStatus(row, e.target.value as FeedbackStatus)}
                          className={`text-[11px] font-medium px-2 py-0.5 rounded border cursor-pointer focus:outline-none disabled:opacity-50 ${STATUS_CHIP[row.status]}`}
                        >
                          {(['new', 'reviewed', 'acted_on'] as FeedbackStatus[]).map((s) => (
                            <option key={s} value={s}>{STATUS_LABEL[s]}</option>
                          ))}
                        </select>
                      </div>
                    </div>

                    {/* Expanded detail */}
                    {isExpanded && (
                      <div className="bg-gray-50 border-t border-gray-100 px-4 py-4 grid grid-cols-[1fr_auto] gap-6">
                        <div className="space-y-2">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className={`text-[10.5px] font-semibold px-2 py-0.5 rounded border ${CAT_CHIP[row.category]}`}>
                              {CAT_ICON[row.category]} {row.category}
                            </span>
                            <span className="font-mono text-[10.5px] text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                              {row.report_id ?? row.id.slice(0, 8)}
                            </span>
                            <span className="text-[10.5px] text-gray-400">{fmtDate(row.created_at)}</span>
                            <span className="font-mono text-[10.5px] text-gray-400">{row.page_url}</span>
                          </div>
                          <p className="text-sm text-gray-800 whitespace-pre-wrap">{row.message}</p>
                          {row.user_id && (
                            <p className="text-[10.5px] font-mono text-gray-400">user: {row.user_id.slice(0, 12)}…</p>
                          )}
                        </div>
                        {row.screenshot_data && (
                          <button
                            onClick={() => setLightbox(row.screenshot_data)}
                            className="shrink-0 w-40 rounded-lg overflow-hidden border border-gray-200 hover:ring-2 ring-blue-400 transition-all"
                            title="View full screenshot"
                          >
                            <img src={row.screenshot_data} alt="Screenshot" className="w-full object-cover" />
                          </button>
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
    </>
  );
}
