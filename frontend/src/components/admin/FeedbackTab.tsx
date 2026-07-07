/**
 * FeedbackTab — unified admin view for all feedback streams.
 *
 * Reads from /api/admin/feedback (normalized UNION of product/ai_answers/helpfulness).
 * Triage (status/owner/resolution) goes through PATCH — never mutates ML source tables.
 * Dispatch: the admin adds context, /dispatch/preview engineers a task (reviewed inline),
 * then /dispatch/create writes it to the Notion AI Work Queue and links back.
 */

import { useEffect, useState, useCallback } from 'react';
import { Button } from '../antigravity/Button';
import { Badge } from '../antigravity/Badge';
import { ProgressStrip } from './ProgressStrip';
import {
  listFeedback,
  triageFeedback,
  getFeedbackScreenshot,
  saveDispatchContext,
  dispatchPreview,
  dispatchCreate,
  dismissFeedback,
  deleteFeedback,
  triggerFix,
  autoAttempt,
  advanceState,
  type UnifiedFeedbackItem,
  type FeedbackStream,
  type TriageStatus,
  type DispatchStatus,
  type EngineeredTask,
  type FixTriggerResult,
} from '../../api/adminFeedback';
import { isTriggerFixEnabled } from '../../featureFlags';
import type { ClientContext } from '../../lib/diagnostics';

type FilterStatus = TriageStatus | 'all';
type ActiveMode = FeedbackStream | 'all' | 'dispatched';

/** client_context normally arrives as an object (jsonb); tolerate a string just in case. */
function parseCtx(raw: ClientContext | string | null | undefined): ClientContext | null {
  if (!raw) return null;
  if (typeof raw === 'string') {
    try {
      return JSON.parse(raw) as ClientContext;
    } catch {
      return null;
    }
  }
  return raw;
}

/** Highlighted callout naming the exact skill + command to run in Claude Code. */
function FixSkillCallout({ result }: { result: FixTriggerResult }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(result.command);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch { /* clipboard unavailable — the text is selectable */ }
  };
  return (
    <div className="rounded-lg border border-[#6ec0bd] bg-[#ebf7f6] px-3 py-2 space-y-1.5">
      <p className="text-[10.5px] font-semibold text-[#105d5b] uppercase tracking-wide">Run in Claude Code</p>
      <div className="flex items-center gap-2">
        <code className="flex-1 text-[12px] font-mono text-[#0b2b43] bg-white border border-[#a4d8d6] rounded px-2 py-1 truncate">
          {result.command}
        </code>
        <Button
          unstyled
          onClick={() => void copy()}
          className="shrink-0 text-[11px] font-medium px-2 py-1 rounded border border-[#6ec0bd] text-[#105d5b] hover:bg-[#d2eceb]"
        >
          {copied ? 'Copied ✓' : 'Copy'}
        </Button>
      </div>
      <p className="text-[10px] text-gray-500">Routes to {result.routes_to}</p>
    </div>
  );
}

/** Diagnostics panel — the page + function that failed, for the triager. */
function DiagnosticsPanel({ ctx }: { ctx: ClientContext }) {
  return (
    <div className="pt-2 mt-1 border-t border-gray-200 space-y-1.5">
      <p className="text-[10.5px] font-semibold text-gray-500">Diagnostics</p>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-gray-600">
        {ctx.route && (
          <span><span className="text-gray-400">Page</span> <span className="font-mono">{ctx.route}</span></span>
        )}
        {ctx.appVersion && (
          <span><span className="text-gray-400">App</span> <span className="font-mono">{ctx.appVersion}</span></span>
        )}
        {ctx.viewport && (
          <span><span className="text-gray-400">Viewport</span> {ctx.viewport}</span>
        )}
        {ctx.interactionId && (
          <span><span className="text-gray-400">Interaction</span> <span className="font-mono">{ctx.interactionId}</span></span>
        )}
      </div>
      {ctx.recentFailedRequests?.length > 0 && (
        <div className="text-[11px]">
          <p className="text-gray-400 mb-0.5">Failed requests</p>
          <ul className="space-y-0.5">
            {ctx.recentFailedRequests.map((r, i) => (
              <li key={i} className="font-mono text-gray-700">
                {r.method} {r.path} →{' '}
                <span className={r.status >= 500 || r.status === 0 ? 'text-red-600' : 'text-amber-600'}>
                  {r.status || 'network error'}
                </span>
                {r.requestId && <span className="text-gray-400"> · req {r.requestId}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
      {ctx.recentErrors?.length > 0 && (
        <div className="text-[11px]">
          <p className="text-gray-400 mb-0.5">Errors — function that failed</p>
          <ul className="space-y-1">
            {ctx.recentErrors.map((e, i) => (
              <li key={i} className="text-gray-700">
                <span className="text-red-600">{e.message}</span>
                {e.failingFrame && (
                  <span className="block font-mono text-[10px] text-gray-500">{e.failingFrame}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      {ctx.breadcrumbs?.length > 0 && (
        <details className="text-[11px]">
          <summary className="text-gray-400 cursor-pointer">Recent activity ({ctx.breadcrumbs.length})</summary>
          <ol className="mt-0.5 space-y-0.5 text-gray-500">
            {ctx.breadcrumbs.map((b, i) => (
              <li key={i} className="font-mono text-[10px]">{b.type}: {b.message}</li>
            ))}
          </ol>
        </details>
      )}
    </div>
  );
}

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
  product:       'Product',
  ai_answers:    'AI Answers',
  helpfulness:   'Helpfulness',
  hr_assignment: 'HR → Employee',
  hr_case:       'HR Case Notes',
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

const STREAMS: FeedbackStream[] = ['product', 'ai_answers', 'helpfulness', 'hr_assignment', 'hr_case'];

export function FeedbackTab() {
  const [rows, setRows]                   = useState<UnifiedFeedbackItem[]>([]);
  const [loading, setLoading]             = useState(true);
  const [error, setError]                 = useState<string | null>(null);
  const [activeStream, setActiveStream]   = useState<ActiveMode>('all');
  const [filterStatus, setFilterStatus]   = useState<FilterStatus>('all');
  const [reporterFilter, setReporterFilter] = useState('');
  const [messageFilter, setMessageFilter] = useState('');
  const [savingId, setSavingId]           = useState<string | null>(null);
  const [expanded, setExpanded]           = useState<string | null>(null);
  const [showDismissed, setShowDismissed] = useState(false);
  const [managingId, setManagingId]       = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  // Lazily-fetched screenshots, cached by row id (a null entry = fetched, none available).
  const [shots, setShots]                 = useState<Record<string, string | null>>({});
  const [shotLoadingId, setShotLoadingId] = useState<string | null>(null);

  // Dispatch → AI Work Queue
  const [contextDrafts, setContextDrafts]       = useState<Record<string, string>>({});
  const [savingContextId, setSavingContextId]   = useState<string | null>(null);
  const [previewFor, setPreviewFor]             = useState<string | null>(null);
  const [previewTask, setPreviewTask]           = useState<EngineeredTask | null>(null);
  const [previewLoadingId, setPreviewLoadingId] = useState<string | null>(null);
  const [creatingId, setCreatingId]             = useState<string | null>(null);
  const [dispatchErrors, setDispatchErrors]     = useState<Record<string, string>>({});
  // Trigger fix / Auto-attempt (on dispatched rows).
  const [triggerResults, setTriggerResults]     = useState<Record<string, FixTriggerResult>>({});
  const [fixBusyId, setFixBusyId]               = useState<string | null>(null);
  const fixEnabled = isTriggerFixEnabled();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await listFeedback({
        ...(activeStream === 'dispatched'
          ? { dispatched: true }
          : activeStream !== 'all' ? { stream: activeStream } : {}),
        ...(showDismissed ? { includeDismissed: true } : {}),
      });
      setRows(items);
    } catch {
      setError('Failed to load feedback.');
    } finally {
      setLoading(false);
    }
  }, [activeStream, showDismissed]);

  useEffect(() => { void load(); }, [load]);

  // When a product row with a screenshot is expanded, fetch the image once (lazy).
  useEffect(() => {
    if (!expanded || expanded in shots) return;
    const row = rows.find((r) => r.id === expanded);
    if (!row || row.stream !== 'product' || !row.has_screenshot) return;
    let cancelled = false;
    setShotLoadingId(expanded);
    getFeedbackScreenshot(row.stream, row.id)
      .then((data) => { if (!cancelled) setShots((prev) => ({ ...prev, [row.id]: data })); })
      .catch(() => { if (!cancelled) setShots((prev) => ({ ...prev, [row.id]: null })); })
      .finally(() => { if (!cancelled) setShotLoadingId((cur) => (cur === row.id ? null : cur)); });
    return () => { cancelled = true; };
  }, [expanded, rows, shots]);

  const updateStatus = async (row: UnifiedFeedbackItem, newStatus: TriageStatus) => {
    setSavingId(row.id);
    setDispatchErrors((prev) => ({ ...prev, [row.id]: '' }));
    try {
      await triageFeedback(row.stream, row.id, { status: newStatus });
      setRows((prev) => prev.map((r) => r.id === row.id ? { ...r, status: newStatus } : r));
    } catch {
      // Surface the failure per-row (reusing the dispatch-error display) instead of
      // failing silently — otherwise a failed save looks successful.
      setDispatchErrors((prev) => ({ ...prev, [row.id]: 'Could not update status — please retry.' }));
    }
    setSavingId(null);
  };

  /** Manually advance (or reject) a row's pipeline `dispatch_status` via the ProgressStrip. */
  const handleAdvance = useCallback(async (row: UnifiedFeedbackItem, target: string) => {
    setSavingId(row.id);
    setDispatchErrors((prev) => ({ ...prev, [row.id]: '' }));
    try {
      const res = await advanceState(row.stream, row.id, target as DispatchStatus);
      setRows((prev) => prev.map((r) => r.id === row.id ? { ...r, dispatch_status: res.dispatch_status } : r));
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Could not update the pipeline state.';
      setDispatchErrors((prev) => ({ ...prev, [row.id]: msg }));
    } finally {
      setSavingId(null);
    }
  }, []);

  const ctxValue = (row: UnifiedFeedbackItem) =>
    contextDrafts[row.id] ?? row.dispatch_context ?? '';

  /** Persist the admin's per-item context (on blur). */
  const saveContext = useCallback(async (row: UnifiedFeedbackItem, value: string) => {
    if ((row.dispatch_context ?? '') === value) return; // no change
    setSavingContextId(row.id);
    try {
      await saveDispatchContext(row.stream, row.id, value);
      setRows((prev) => prev.map((r) => r.id === row.id ? { ...r, dispatch_context: value } : r));
    } catch { /* keep the draft; error surfaced on dispatch */ }
    finally { setSavingContextId(null); }
  }, []);

  /** Generate the engineered task for review (no side effects). */
  const openPreview = useCallback(async (row: UnifiedFeedbackItem) => {
    setDispatchErrors((prev) => ({ ...prev, [row.id]: '' }));
    setPreviewLoadingId(row.id);
    setPreviewFor(row.id);
    setPreviewTask(null);
    try {
      const task = await dispatchPreview(row.stream, row.id, { text: row.text, category: row.verdict ?? 'bug' });
      setPreviewTask(task);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Could not generate the task.';
      setDispatchErrors((prev) => ({ ...prev, [row.id]: msg }));
      setPreviewFor(null);
    } finally {
      setPreviewLoadingId(null);
    }
  }, []);

  /** Create the Notion Work Queue page from the reviewed task. */
  const createTask = useCallback(async (row: UnifiedFeedbackItem) => {
    if (!previewTask) return;
    setCreatingId(row.id);
    setDispatchErrors((prev) => ({ ...prev, [row.id]: '' }));
    try {
      const res = await dispatchCreate(row.stream, row.id, previewTask);
      setRows((prev) => prev.map((r) => r.id === row.id
        ? { ...r, dispatch_status: 'dispatched', dispatch_ref: res.url } : r));
      setPreviewFor(null);
      setPreviewTask(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Could not create the Notion task.';
      setDispatchErrors((prev) => ({ ...prev, [row.id]: msg }));
    } finally {
      setCreatingId(null);
    }
  }, [previewTask]);

  /** Trigger fix — flip the dispatched task to "Ready for AI" + surface the skill command. */
  const runTriggerFix = useCallback(async (row: UnifiedFeedbackItem) => {
    setFixBusyId(`${row.id}:fix`);
    setDispatchErrors((prev) => ({ ...prev, [row.id]: '' }));
    try {
      const res = await triggerFix(row.stream, row.id);
      setTriggerResults((prev) => ({ ...prev, [row.id]: res }));
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Could not trigger the fix.';
      setDispatchErrors((prev) => ({ ...prev, [row.id]: msg }));
    } finally {
      setFixBusyId(null);
    }
  }, []);

  /** Auto-attempt — fire the autofix pipeline for this task (Trivial/Low, non-Red only). */
  const runAutoAttempt = useCallback(async (row: UnifiedFeedbackItem) => {
    setFixBusyId(`${row.id}:auto`);
    setDispatchErrors((prev) => ({ ...prev, [row.id]: '' }));
    try {
      await autoAttempt(row.stream, row.id);
      setDispatchErrors((prev) => ({ ...prev, [row.id]: 'Auto-attempt dispatched — a draft PR will appear shortly.' }));
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Could not start the auto-attempt.';
      setDispatchErrors((prev) => ({ ...prev, [row.id]: msg }));
    } finally {
      setFixBusyId(null);
    }
  }, []);

  /** Soft-dismiss (hide) or restore a row. */
  const doDismiss = useCallback(async (row: UnifiedFeedbackItem, dismissed: boolean) => {
    setManagingId(row.id);
    try {
      await dismissFeedback(row.stream, row.id, dismissed);
      if (dismissed && !showDismissed) {
        setRows((prev) => prev.filter((r) => r.id !== row.id));
        setExpanded(null);
      } else {
        setRows((prev) => prev.map((r) => r.id === row.id ? { ...r, dismissed } : r));
      }
    } catch { /* keep the row; admin can retry */ }
    finally { setManagingId(null); }
  }, [showDismissed]);

  /** Permanently delete a product row. */
  const doDelete = useCallback(async (row: UnifiedFeedbackItem) => {
    setManagingId(row.id);
    try {
      await deleteFeedback(row.id);
      setRows((prev) => prev.filter((r) => r.id !== row.id));
      setConfirmDeleteId(null);
      setExpanded(null);
    } catch { /* keep the row; admin can retry */ }
    finally { setManagingId(null); }
  }, []);

  const reporterQuery = reporterFilter.trim().toLowerCase();
  const messageQuery = messageFilter.trim().toLowerCase();
  const displayed = rows.filter((r) => {
    if (activeStream !== 'dispatched' && filterStatus !== 'all' && r.status !== filterStatus) return false;
    if (reporterQuery) {
      const hay = `${r.reporter_name ?? ''} ${r.reporter_email ?? ''}`.toLowerCase();
      if (!hay.includes(reporterQuery)) return false;
    }
    if (messageQuery) {
      const hay = `${r.text ?? ''} ${r.client_context?.route ?? ''}`.toLowerCase();
      if (!hay.includes(messageQuery)) return false;
    }
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
        {(['all', ...STREAMS, 'dispatched'] as ActiveMode[]).map((s) => (
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
            {s === 'all' ? 'All streams' : s === 'dispatched' ? 'Dispatched' : STREAM_LABEL[s]}
          </Button>
        ))}
      </div>

      {/* ── Dispatched view ── */}
      {activeStream === 'dispatched' && (
        <>
          <div className="flex justify-end">
            <Button unstyled onClick={load} className="text-xs text-gray-400 hover:text-gray-600 underline">
              Refresh
            </Button>
          </div>

          {displayed.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 text-center rounded-lg border border-gray-200 bg-white">
              <p className="text-sm font-medium text-gray-600">No dispatched tickets</p>
              <p className="text-xs text-gray-400 mt-1">Dispatched tickets will appear here once tickets are routed to engineering.</p>
            </div>
          )}

          {displayed.length > 0 && (
            <div className="rounded-lg border border-gray-200 overflow-hidden">
              <div className="grid grid-cols-[110px_140px_140px_110px_100px_100px_120px] bg-gray-50 border-b border-gray-200 text-[11px] font-semibold text-gray-400 uppercase tracking-wide">
                <div className="px-3 py-2.5">Source ref</div>
                <div className="px-3 py-2.5">Stream</div>
                <div className="px-3 py-2.5">Dispatch ref</div>
                <div className="px-3 py-2.5">Dispatch status</div>
                <div className="px-3 py-2.5">Severity</div>
                <div className="px-3 py-2.5">Area</div>
                <div className="px-3 py-2.5">Date</div>
              </div>
              <div className="divide-y divide-gray-100 bg-white">
                {displayed.map((row) => (
                  <div
                    key={row.id}
                    className="grid grid-cols-[110px_140px_140px_110px_100px_100px_120px] items-center py-2.5"
                  >
                    <div className="px-3">
                      <span className="font-mono text-[10.5px] text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">
                        {(row.source_ref ?? row.id).slice(0, 10)}
                      </span>
                    </div>
                    <div className="px-3">
                      <span className="text-[11px] font-medium text-gray-600">
                        {STREAM_LABEL[row.stream]}
                      </span>
                    </div>
                    <div className="px-3">
                      {row.dispatch_ref ? (
                        <span className="font-mono text-[10.5px] text-[#0b2b43] bg-blue-50 px-1.5 py-0.5 rounded">
                          {row.dispatch_ref}
                        </span>
                      ) : (
                        <span className="text-[11px] text-gray-400">—</span>
                      )}
                    </div>
                    <div className="px-3">
                      <Badge variant="success" size="sm">
                        {row.dispatch_status ?? 'dispatched'}
                      </Badge>
                    </div>
                    <div className="px-3">
                      {row.severity ? (
                        <Badge
                          variant={row.severity === 'critical' ? 'error' : 'neutral'}
                          size="sm"
                        >
                          {row.severity}
                        </Badge>
                      ) : (
                        <span className="text-[11px] text-gray-400">—</span>
                      )}
                    </div>
                    <div className="px-3">
                      {row.area ? (
                        <Badge
                          variant={row.area === 'isolation' ? 'error' : 'info'}
                          size="sm"
                        >
                          {row.area}
                        </Badge>
                      ) : (
                        <span className="text-[11px] text-gray-400">—</span>
                      )}
                    </div>
                    <div className="px-3">
                      <span className="text-[11px] text-gray-400" title={fmtDate(row.created_at)}>
                        {fmtRelative(row.created_at)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* ── Normal (non-dispatched) view ── */}
      {activeStream !== 'dispatched' && (
        <>
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
                {f === 'all' ? counts.all : counts[f]}
              </span>
            </Button>
          ))}
        </div>
        <input
          type="text"
          value={reporterFilter}
          onChange={(e) => setReporterFilter(e.target.value)}
          placeholder="Filter by reporter…"
          aria-label="Filter by reporter name or email"
          className="text-xs px-2.5 py-1.5 rounded-md border border-gray-200 bg-white text-gray-700 placeholder:text-gray-400 focus:outline-none focus:ring-1 focus:ring-[#1f8e8b] w-48"
        />
        <input
          type="search"
          value={messageFilter}
          onChange={(e) => setMessageFilter(e.target.value)}
          placeholder="Search message or page…"
          aria-label="Search feedback message or page route"
          className="text-xs px-2.5 py-1.5 rounded-md border border-gray-200 bg-white text-gray-700 placeholder:text-gray-400 focus:outline-none focus:ring-1 focus:ring-[#1f8e8b] w-52"
        />
        {(reporterQuery || messageQuery) && (
          <span className="text-[11px] text-gray-400">
            {displayed.length} match{displayed.length === 1 ? '' : 'es'}
          </span>
        )}
        <div className="flex-1" />
        <label className="flex items-center gap-1.5 text-[11px] text-gray-500 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={showDismissed}
            onChange={(e) => setShowDismissed(e.target.checked)}
            className="accent-[#1f8e8b]"
          />
          Show dismissed
        </label>
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
        </>
      )}

      {/* Table — normal (non-dispatched) mode */}
      {activeStream !== 'dispatched' && displayed.length > 0 && (
        <div className="rounded-lg border border-gray-200 overflow-hidden">
          <div className="grid grid-cols-[100px_110px_minmax(0,1fr)_140px_120px_120px_140px_110px] bg-gray-50 border-b border-gray-200 text-[11px] font-semibold text-gray-400 uppercase tracking-wide">
            <div className="px-3 py-2.5">ID</div>
            <div className="px-3 py-2.5">Stream</div>
            <div className="px-3 py-2.5">Text</div>
            <div className="px-3 py-2.5">Tags</div>
            <div className="px-3 py-2.5">Verdict</div>
            <div className="px-3 py-2.5">Date</div>
            <div className="px-3 py-2.5">Status</div>
            <div className="px-3 py-2.5">Dispatch</div>
          </div>
          <div className="divide-y divide-gray-100 bg-white">
            {displayed.map((row) => {
              const isExpanded = expanded === row.id;
              const effectiveStatus: TriageStatus = row.status ?? 'new';
              const dispatchErr = dispatchErrors[row.id];
              const alreadyDispatched = row.dispatch_status === 'dispatched';
              const triggerResult = triggerResults[row.id];
              return (
                <div key={row.id}>
                  <div
                    className="grid grid-cols-[100px_110px_minmax(0,1fr)_140px_120px_120px_140px_110px] items-center hover:bg-gray-50 transition-colors cursor-pointer"
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
                    <div className="px-3 py-2.5 flex items-center gap-1">
                      <span className="font-mono text-[10.5px] text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">
                        {(row.source_ref ?? row.id).slice(0, 8)}
                      </span>
                      {row.has_screenshot && (
                        <span title="Screenshot attached" aria-label="Screenshot attached" className="text-[11px] leading-none">📷</span>
                      )}
                    </div>
                    <div className="px-3 py-2.5">
                      <span className="text-[11px] font-medium text-gray-600">
                        {STREAM_LABEL[row.stream]}
                      </span>
                    </div>
                    <div className="px-3 py-2.5 min-w-0">
                      <p className="text-[12px] text-gray-700 truncate">{row.text ?? '—'}</p>
                    </div>
                    {/* Tags: severity + area badges */}
                    <div className="px-3 py-2.5 flex flex-wrap gap-1">
                      {row.severity && (
                        <Badge
                          variant={row.severity === 'critical' ? 'error' : 'neutral'}
                          size="sm"
                        >
                          {row.severity}
                        </Badge>
                      )}
                      {row.area && (
                        <Badge
                          variant={row.area === 'isolation' ? 'error' : 'info'}
                          size="sm"
                        >
                          {row.area}
                        </Badge>
                      )}
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
                    {/* Dispatch column — dispatched rows link to Notion; otherwise the
                        row is clickable to open the dispatch panel (no separate button). */}
                    <div className="px-3 py-2.5">
                      {alreadyDispatched && row.dispatch_ref && /^https?:\/\//.test(row.dispatch_ref) ? (
                        <a
                          href={row.dispatch_ref}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="text-[11px] font-medium text-[#1f8e8b] hover:underline"
                        >
                          Notion ↗
                        </a>
                      ) : alreadyDispatched ? (
                        <Badge variant="success" size="sm">dispatched</Badge>
                      ) : (
                        <span className="text-[11px] text-gray-300">—</span>
                      )}
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="bg-gray-50 border-t border-gray-100 px-4 py-4 space-y-2">
                      <div className="flex items-center gap-2 flex-wrap text-[10.5px]">
                        <span className="font-semibold text-gray-600">{STREAM_LABEL[row.stream]}</span>
                        <span className="font-mono text-gray-400">{row.source_ref}</span>
                        {row.company_id && (
                          <span className="font-mono text-gray-400">co: {row.company_id}</span>
                        )}
                      </div>
                      {/* Reporter attribution — who reported this, and exactly when */}
                      <div className="flex items-center gap-2 flex-wrap text-[11px]">
                        <span className="text-gray-400">Reported by</span>
                        {(row.reporter_name || row.reporter_email) ? (
                          <>
                            {row.reporter_name && (
                              <span className="font-medium text-gray-700">{row.reporter_name}</span>
                            )}
                            {row.reporter_email && (
                              <a
                                href={`mailto:${row.reporter_email}`}
                                onClick={(e) => e.stopPropagation()}
                                className="text-[#1f8e8b] hover:underline"
                              >
                                {row.reporter_email}
                              </a>
                            )}
                            {row.reporter_role && (
                              <span className="text-[10px] uppercase px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 border border-gray-200 font-medium">
                                {row.reporter_role}
                              </span>
                            )}
                          </>
                        ) : (
                          <span className="italic text-gray-400">Unknown reporter</span>
                        )}
                        <span className="text-gray-300">·</span>
                        <span className="text-gray-500" title={new Date(row.created_at).toLocaleString()}>
                          {fmtDate(row.created_at)}
                        </span>
                      </div>
                      <p className="text-sm text-gray-800 whitespace-pre-wrap">{row.text ?? '—'}</p>
                      {row.stream === 'product' && row.has_screenshot && (
                        <div className="pt-1">
                          <p className="text-[10.5px] font-semibold text-gray-500 mb-1">Screenshot</p>
                          {shots[row.id] ? (
                            <img
                              src={shots[row.id]!}
                              alt="Feedback screenshot"
                              className="max-w-full max-h-[520px] rounded border border-gray-200 shadow-sm object-contain bg-white"
                            />
                          ) : shotLoadingId === row.id ? (
                            <p className="text-[11px] text-gray-400">Loading screenshot…</p>
                          ) : row.id in shots ? (
                            <p className="text-[11px] text-gray-400">Screenshot unavailable.</p>
                          ) : (
                            <p className="text-[11px] text-gray-400">Loading screenshot…</p>
                          )}
                        </div>
                      )}
                      {row.stream === 'product' && parseCtx(row.client_context) && (
                        <DiagnosticsPanel ctx={parseCtx(row.client_context)!} />
                      )}
                      {row.owner && (
                        <p className="text-[10.5px] text-gray-400">Owner: {row.owner}</p>
                      )}
                      {row.resolution && (
                        <p className="text-[10.5px] text-gray-400">Resolution: {row.resolution}</p>
                      )}

                      {/* Pipeline state — stepper + valid next-action button(s). Shows its
                          own error (e.g. a 409 illegal transition) since the shared
                          dispatchErr slot below isn't always rendered (only inside the
                          fix-enabled / not-yet-dispatched branches). */}
                      <div className="pt-2 mt-1 border-t border-gray-200 space-y-1">
                        <ProgressStrip
                          status={row.dispatch_status ?? 'new'}
                          tier={row.autonomy_tier}
                          busy={savingId === row.id}
                          onAdvance={(t) => void handleAdvance(row, t)}
                        />
                        {dispatchErr && <p className="text-[11px] text-red-600">{dispatchErr}</p>}
                      </div>

                      {/* Dispatch → AI Work Queue */}
                      <div className="pt-2 mt-1 border-t border-gray-200">
                        {alreadyDispatched && row.dispatch_ref && /^https?:\/\//.test(row.dispatch_ref) ? (
                          <div className="space-y-2">
                            <p className="text-[11px] text-gray-600">
                              Dispatched to the AI Work Queue ·{' '}
                              <a
                                href={row.dispatch_ref}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-[#1f8e8b] hover:underline font-medium"
                              >
                                open task in Notion ↗
                              </a>
                            </p>

                            {/* Launch a fix — manual, per-task */}
                            {fixEnabled && (
                              <>
                                <div className="flex items-center gap-2 flex-wrap">
                                  <Button
                                    unstyled
                                    disabled={fixBusyId === `${row.id}:fix`}
                                    onClick={() => void runTriggerFix(row)}
                                    className="text-[11px] font-medium px-3 py-1 rounded bg-[#0b2b43] text-white hover:bg-[#0b3b5c] disabled:opacity-50"
                                  >
                                    {fixBusyId === `${row.id}:fix` ? 'Triggering…' : 'Trigger fix'}
                                  </Button>
                                  <Button
                                    unstyled
                                    disabled={fixBusyId === `${row.id}:auto`}
                                    onClick={() => void runAutoAttempt(row)}
                                    title="Fires the autofix pipeline — Trivial/Low, non-Red tasks only"
                                    className="text-[11px] font-medium px-3 py-1 rounded border border-[#0b2b43] text-[#0b2b43] hover:bg-[#0b2b43] hover:text-white transition-colors disabled:opacity-40"
                                  >
                                    {fixBusyId === `${row.id}:auto` ? 'Dispatching…' : 'Auto-attempt'}
                                  </Button>
                                </div>
                                {triggerResult && <FixSkillCallout result={triggerResult} />}
                                {dispatchErr && <p className="text-[11px] text-gray-600">{dispatchErr}</p>}
                              </>
                            )}
                          </div>
                        ) : (
                          <div className="space-y-2">
                            <p className="text-[10.5px] font-semibold text-gray-500">Dispatch to AI Work Queue</p>
                            <span className="block text-[10.5px] text-gray-400">
                              Context (required — repro steps, expected behaviour, constraints)
                            </span>
                            <textarea
                              value={ctxValue(row)}
                              onChange={(e) => setContextDrafts((p) => ({ ...p, [row.id]: e.target.value }))}
                              onBlur={(e) => void saveContext(row, e.target.value)}
                              placeholder="Add the detail an engineer needs to fix this…"
                              rows={3}
                              className="w-full text-[12px] rounded border border-gray-200 px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-[#1f8e8b]"
                            />
                            {savingContextId === row.id && <p className="text-[10px] text-gray-400">Saving…</p>}
                            {dispatchErr && <p className="text-[11px] text-red-600">{dispatchErr}</p>}

                            {previewFor === row.id && previewTask ? (
                              <div className="rounded border border-gray-200 bg-white p-3 space-y-2">
                                <p className="text-[10.5px] font-semibold text-gray-500">Review the engineered task</p>
                                {([
                                  ['Title', 'title'],
                                  ['Goal (strategic objective)', 'strategic_objective'],
                                  ['Plan / execution prompt', 'execution_prompt'],
                                  ['Expected output', 'expected_output'],
                                  ['Validation criteria (success)', 'validation_criteria'],
                                  ['Verify (test command)', 'test_command'],
                                ] as const).map(([label, key]) => (
                                  <div key={key}>
                                    <span className="block text-[10px] uppercase tracking-wide text-gray-400">{label}</span>
                                    <textarea
                                      value={(previewTask[key]) ?? ''}
                                      onChange={(e) => setPreviewTask((t) => (t ? { ...t, [key]: e.target.value } : t))}
                                      rows={key === 'title' ? 1 : 2}
                                      className="w-full text-[12px] rounded border border-gray-200 px-2 py-1 focus:outline-none focus:ring-1 focus:ring-[#1f8e8b]"
                                    />
                                  </div>
                                ))}
                                <div className="flex items-center gap-1.5 flex-wrap text-[10px]">
                                  <span className="px-1.5 py-0.5 rounded bg-gray-100 border border-gray-200">Priority: {previewTask.priority}</span>
                                  <span className="px-1.5 py-0.5 rounded bg-gray-100 border border-gray-200">Complexity: {previewTask.complexity}</span>
                                  <span className="px-1.5 py-0.5 rounded bg-gray-100 border border-gray-200">{previewTask.task_type}</span>
                                  <span className="px-1.5 py-0.5 rounded bg-gray-100 border border-gray-200">{previewTask.layer}</span>
                                  <span className="px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">{previewTask.status}</span>
                                </div>
                                <div className="flex gap-2">
                                  <Button
                                    unstyled
                                    disabled={creatingId === row.id}
                                    onClick={() => void createTask(row)}
                                    className="text-[11px] font-medium px-3 py-1 rounded bg-[#0b2b43] text-white hover:bg-[#0b3b5c] disabled:opacity-50"
                                  >
                                    {creatingId === row.id ? 'Creating…' : 'Create task in Notion'}
                                  </Button>
                                  <Button
                                    unstyled
                                    onClick={() => { setPreviewFor(null); setPreviewTask(null); }}
                                    className="text-[11px] font-medium px-3 py-1 rounded border border-gray-300 text-gray-600 hover:bg-gray-100"
                                  >
                                    Cancel
                                  </Button>
                                </div>
                              </div>
                            ) : (
                              <Button
                                unstyled
                                disabled={!ctxValue(row).trim() || previewLoadingId === row.id}
                                onClick={() => void openPreview(row)}
                                className="text-[11px] font-medium px-3 py-1 rounded border border-[#0b2b43] text-[#0b2b43] hover:bg-[#0b2b43] hover:text-white transition-colors disabled:opacity-40"
                              >
                                {previewLoadingId === row.id ? 'Drafting task…' : 'Draft task with AI'}
                              </Button>
                            )}
                          </div>
                        )}
                      </div>

                      {/* Admin actions — dismiss (all streams, reversible) + delete (product only) */}
                      <div className="pt-2 mt-1 border-t border-gray-200 flex items-center gap-3 text-[11px]">
                        {row.dismissed ? (
                          <Button
                            unstyled
                            disabled={managingId === row.id}
                            onClick={() => void doDismiss(row, false)}
                            className="text-gray-500 hover:text-gray-700 underline disabled:opacity-50"
                          >
                            Restore
                          </Button>
                        ) : (
                          <Button
                            unstyled
                            disabled={managingId === row.id}
                            onClick={() => void doDismiss(row, true)}
                            className="text-gray-500 hover:text-gray-700 underline disabled:opacity-50"
                          >
                            Dismiss (hide)
                          </Button>
                        )}
                        {row.stream === 'product' && (
                          confirmDeleteId === row.id ? (
                            <span className="flex items-center gap-2">
                              <span className="text-red-700 font-medium">Delete permanently?</span>
                              <Button
                                unstyled
                                disabled={managingId === row.id}
                                onClick={() => void doDelete(row)}
                                className="text-red-700 font-semibold hover:underline disabled:opacity-50"
                              >
                                Yes, delete
                              </Button>
                              <Button unstyled onClick={() => setConfirmDeleteId(null)} className="text-gray-500 hover:underline">
                                Cancel
                              </Button>
                            </span>
                          ) : (
                            <Button unstyled onClick={() => setConfirmDeleteId(row.id)} className="text-red-600 hover:underline">
                              Delete
                            </Button>
                          )
                        )}
                        {managingId === row.id && <span className="text-gray-400">…</span>}
                      </div>
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
