/**
 * FeedbackTab — admin view for pilot feedback submissions.
 * Sorted by created_at desc. Inline status update (new → reviewed → acted_on).
 */

import { useEffect, useState, useCallback } from 'react';
import { Button } from '../antigravity/Button';
import { supabase } from '../../api/supabase';

type FeedbackStatus   = 'new' | 'reviewed' | 'acted_on';
type FeedbackCategory = 'bug' | 'idea' | 'other';

interface FeedbackRow {
  id:         string;
  user_id:    string | null;
  page_url:   string;
  category:   FeedbackCategory;
  message:    string;
  status:     FeedbackStatus;
  created_at: string;
}

const STATUS_STYLES: Record<FeedbackStatus, string> = {
  new:       'bg-blue-100 text-blue-700',
  reviewed:  'bg-amber-100 text-amber-700',
  acted_on:  'bg-green-100 text-green-700',
};

const STATUS_LABELS: Record<FeedbackStatus, string> = {
  new:       'New',
  reviewed:  'Reviewed',
  acted_on:  'Acted on',
};

const CATEGORY_STYLES: Record<FeedbackCategory, string> = {
  bug:   'bg-red-50 text-red-600',
  idea:  'bg-accent-50 text-accent-600',
  other: 'bg-gray-100 text-gray-500',
};

function fmtDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) +
    ' ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
}

function fmtRelative(iso: string): string {
  const diff  = Date.now() - new Date(iso).getTime();
  const hours = Math.floor(diff / 3_600_000);
  const days  = Math.floor(diff / 86_400_000);
  if (hours < 1)   return 'Just now';
  if (hours < 24)  return `${hours}h ago`;
  return `${days}d ago`;
}

export function FeedbackTab() {
  const [rows, setRows]       = useState<FeedbackRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [filter, setFilter]   = useState<FeedbackStatus | 'all'>('all');
  const [savingId, setSavingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const { data, error: err } = await supabase
      .from('feedback')
      .select('id, user_id, page_url, category, message, status, created_at')
      .order('created_at', { ascending: false })
      .limit(500);

    if (err) setError('Failed to load feedback.');
    else setRows((data as FeedbackRow[]) ?? []);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const updateStatus = async (row: FeedbackRow, newStatus: FeedbackStatus) => {
    setSavingId(row.id);
    const { error: err } = await supabase
      .from('feedback')
      .update({ status: newStatus })
      .eq('id', row.id);

    if (!err) {
      setRows((prev) => prev.map((r) => r.id === row.id ? { ...r, status: newStatus } : r));
    }
    setSavingId(null);
  };

  const displayed = filter === 'all' ? rows : rows.filter((r) => r.status === filter);

  const counts = {
    all:       rows.length,
    new:       rows.filter((r) => r.status === 'new').length,
    reviewed:  rows.filter((r) => r.status === 'reviewed').length,
    acted_on:  rows.filter((r) => r.status === 'acted_on').length,
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-sm text-gray-400">Loading feedback...</p>
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
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-gray-900">Pilot Feedback</h2>
          <p className="text-sm text-gray-500">
            {counts.new} unreviewed — {counts.acted_on} acted on
          </p>
        </div>
        <Button unstyled onClick={load} className="text-xs text-gray-400 hover:text-gray-600 underline">
          Refresh
        </Button>
      </div>

      {/* Filter bar */}
      <div className="flex gap-2 border-b border-gray-200 pb-2">
        {(['all', 'new', 'reviewed', 'acted_on'] as const).map((f) => (
          <Button unstyled
            key={f}
            onClick={() => setFilter(f)}
            className={`text-xs px-3 py-1.5 rounded font-medium transition-colors ${
              filter === f
                ? 'bg-gray-900 text-white'
                : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
            }`}
          >
            {f === 'all' ? 'All' : STATUS_LABELS[f as FeedbackStatus]}
            <span className="ml-1.5 opacity-60">{counts[f]}</span>
          </Button>
        ))}
      </div>

      {/* Empty state */}
      {displayed.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <p className="text-sm font-medium text-gray-600 mb-1">
            {filter === 'all' ? 'No feedback submitted yet.' : `No ${STATUS_LABELS[filter as FeedbackStatus].toLowerCase()} items.`}
          </p>
          <p className="text-xs text-gray-400">
            {filter === 'all' ? 'The widget is live — feedback will appear here when pilot users submit.' : ''}
          </p>
        </div>
      )}

      {/* Rows */}
      {displayed.length > 0 && (
        <div className="divide-y divide-gray-100 rounded-lg border border-gray-200 overflow-hidden">
          {displayed.map((row) => (
            <div key={row.id} className="bg-white px-4 py-4 space-y-2.5">
              {/* Meta row */}
              <div className="flex items-center flex-wrap gap-2 text-xs text-gray-400">
                <span
                  className={`inline-flex items-center px-2 py-0.5 rounded font-medium ${CATEGORY_STYLES[row.category]}`}
                >
                  {row.category}
                </span>
                <span title={fmtDate(row.created_at)}>{fmtRelative(row.created_at)}</span>
                <span className="text-gray-300">{row.page_url}</span>
              </div>

              {/* Message */}
              <p className="text-sm text-gray-800 whitespace-pre-wrap break-words">
                {row.message}
              </p>

              {/* Status controls */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-gray-400">Status:</span>
                {(['new', 'reviewed', 'acted_on'] as FeedbackStatus[]).map((s) => (
                  <Button unstyled
                    key={s}
                    onClick={() => updateStatus(row, s)}
                    disabled={row.status === s || savingId === row.id}
                    className={`text-xs px-2 py-0.5 rounded border transition-colors ${
                      row.status === s
                        ? `${STATUS_STYLES[s]} border-transparent cursor-default`
                        : 'border-gray-200 text-gray-400 hover:text-gray-600 hover:border-gray-300'
                    }`}
                  >
                    {STATUS_LABELS[s]}
                  </Button>
                ))}
                {savingId === row.id && (
                  <span className="text-xs text-gray-300">Saving...</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
