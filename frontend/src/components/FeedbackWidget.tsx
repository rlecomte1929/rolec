/**
 * FeedbackWidget — floating feedback button for authenticated users.
 *
 * Fixed bottom-right on all product pages.
 * Submits to the `feedback` Supabase table via direct insert.
 *
 * Features:
 * - Category: Bug / Idea / Other
 * - Optional screenshot capture (html2canvas, widget hidden during capture)
 * - Auto-generated human-readable report ID (e.g. BUG-260617-A1B2)
 * - Page URL automatically attached
 */

import { useState, useRef, useEffect } from 'react';
import { submitProductFeedback, getMyReports, type ScreenshotStorage } from '../api/productFeedback';
import type { MyReport } from '../api/productFeedback';
import { collectDiagnostics } from '../lib/diagnostics';
import { startBugReportRecording, getAnalyticsConsent } from '../analytics';
import { ScreenshotCapture } from './feedback/ScreenshotCapture';
import { AnnotationModal } from './feedback/AnnotationModal';
import { Button } from './antigravity/Button';
import { Badge } from './antigravity/Badge';

type Category    = 'bug' | 'idea' | 'other';
type WidgetState = 'idle' | 'open' | 'capturing' | 'submitting' | 'success' | 'error' | 'reports';

const CATEGORY_LABELS: Record<Category, string> = {
  bug:   'Bug',
  idea:  'Idea',
  other: 'Other',
};

const TYPE_PREFIX: Record<Category, string> = {
  bug:   'BUG',
  idea:  'IDR',
  other: 'OTH',
};

function makeReportId(category: Category): string {
  const d    = new Date();
  const date = `${String(d.getFullYear()).slice(2)}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;
  const rand = Math.random().toString(16).slice(2, 6).toUpperCase();
  return `${TYPE_PREFIX[category]}-${date}-${rand}`;
}

/** TD-9 (AIQ-1544): the test-drive provision flow stashes the run's campaign slice in
 *  localStorage (key `relopass_test_drive`). Read it so in-session feedback is attributed to
 *  the tester's campaign + corridor + segment instead of landing unattributed. Best-effort —
 *  returns {} when there's no session, storage is unavailable, or the value is malformed. */
function readTestDriveSlice(): { campaign?: string; corridor_id?: string; tester_segment?: string } {
  try {
    const raw = window.localStorage.getItem('relopass_test_drive');
    if (!raw) return {};
    const p = JSON.parse(raw) as Record<string, unknown>;
    const out: { campaign?: string; corridor_id?: string; tester_segment?: string } = {};
    if (typeof p.campaign === 'string' && p.campaign) out.campaign = p.campaign.slice(0, 64);
    if (typeof p.corridor_id === 'string' && p.corridor_id) out.corridor_id = p.corridor_id.slice(0, 64);
    if (typeof p.tester_segment === 'string' && p.tester_segment) out.tester_segment = p.tester_segment.slice(0, 32);
    return out;
  } catch {
    return {};
  }
}

export function FeedbackWidget({ userId }: { userId: string | null }) {
  const [state, setState]         = useState<WidgetState>('idle');
  const [category, setCategory]   = useState<Category>('bug');
  const [message, setMessage]     = useState('');
  const [screenshot, setScreenshot] = useState<string | null>(null);
  const [reportId, setReportId]   = useState<string | null>(null);
  // [AIQ-1480] screenshot capture + markup flow.
  const [shotStep, setShotStep]   = useState<'none' | 'capture' | 'annotate'>('none');
  const [rawCapture, setRawCapture] = useState<string | null>(null);
  const [storageNote, setStorageNote] = useState<ScreenshotStorage | null>(null);
  // My reports view state.
  const [reports, setReports]           = useState<MyReport[] | null>(null);
  const [reportsLoading, setReportsLoading] = useState(false);
  const [reportsError, setReportsError] = useState(false);

  const textareaRef  = useRef<HTMLTextAreaElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Focus textarea when popover opens, and start a consent-gated session replay so a
  // reported bug carries a watchable recording (no-op without analytics consent). The
  // session id + replay url are picked up by collectDiagnostics() at submit time.
  useEffect(() => {
    if (state === 'open') {
      setTimeout(() => textareaRef.current?.focus(), 50);
      startBugReportRecording();
    }
  }, [state]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && (state === 'open' || state === 'error' || state === 'reports')) close();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [state]);

  // Fetch the caller's reports when entering the My-reports view.
  useEffect(() => {
    if (state !== 'reports') return;
    setReportsLoading(true);
    setReportsError(false);
    getMyReports()
      .then((res) => setReports(res.reports))
      .catch(() => setReportsError(true))
      .finally(() => setReportsLoading(false));
  }, [state]);

  function close() {
    setState('idle');
    setMessage('');
    setCategory('bug');
    setScreenshot(null);
    setReportId(null);
    setShotStep('none');
    setRawCapture(null);
    setStorageNote(null);
  }

  // [AIQ-1480] Capture (full page / region / upload) → annotate → attach.
  const onCaptured = (dataUrl: string) => {
    setRawCapture(dataUrl);
    setShotStep('annotate');
    // If we were hidden during a delayed capture, reopen the widget popover.
    setState((s) => s === 'capturing' ? 'open' : s);
  };

  // The AnnotationModal calls onSave(dataUrl) with the already-annotated URL.
  const attachAnnotated = (dataUrl: string) => {
    setScreenshot(dataUrl);
    setRawCapture(null);
    setShotStep('none');
  };

  const onFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    // Reset the input so the same file can be re-selected after cancel.
    e.target.value = '';
    const reader = new FileReader();
    reader.onload = (ev) => {
      const dataUrl = ev.target?.result;
      if (typeof dataUrl === 'string') onCaptured(dataUrl);
    };
    reader.readAsDataURL(file);
  };

  async function submit() {
    const trimmed = message.trim();
    if (!trimmed) return;

    setState('submitting');
    const rid = reportId ?? makeReportId(category);
    setReportId(rid);
    void userId; // kept for future analytics; the backend sets user_id from the session.

    try {
      // POST /api/feedback (backend writes via the service role + uploads the screenshot to
      // the private Storage bucket). Direct Supabase inserts fail for ReloPass-session users.
      const res = await submitProductFeedback({
        category,
        message: trimmed.slice(0, 2000),
        page_url: window.location.pathname,
        report_id: rid,
        screenshot_data: screenshot ?? null,
        client_context: collectDiagnostics(),
        // TD-9 (AIQ-1544): attribute the feedback to the test-drive run when one is active.
        ...readTestDriveSlice(),
      });
      setStorageNote(res.screenshot_storage ?? null);
      setState('success');
      // Keep the success panel up a little longer when there's a storage note to read.
      setTimeout(() => close(), res.screenshot_storage ? 6000 : 3500);
    } catch {
      setState('error');
      setTimeout(() => setState('open'), 2500);
    }
  }

  const isVisible = state !== 'idle' && state !== 'capturing';

  // Status badge variant + label for the My-reports list.
  function statusVariant(status: string | null): 'neutral' | 'info' | 'success' {
    if (status === 'triaged') return 'info';
    if (status === 'dispatched' || status === 'resolved') return 'success';
    return 'neutral';
  }
  function statusLabel(status: string | null): string {
    return status ?? 'submitted';
  }

  return (
    // onMouseDown stopPropagation prevents the widget's clicks from closing
    // page-level dropdowns that use document mousedown to detect "click outside".
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions -- non-interactive wrapper; the handler only stops event propagation
    <div
      ref={containerRef}
      data-html2canvas-ignore
      onMouseDown={(e) => e.stopPropagation()}
      className="fixed bottom-4 right-4 z-50 flex flex-col items-end gap-2"
    >
      {/* Annotation modal — fullscreen via portal, shown when a capture/upload is ready */}
      {shotStep === 'annotate' && rawCapture && (
        <AnnotationModal
          imageSrc={rawCapture}
          onSave={attachAnnotated}
          onCancel={() => { setRawCapture(null); setShotStep('none'); }}
        />
      )}

      {/* Hidden file input for "Upload image" */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={onFileUpload}
      />

      {isVisible && (
        <div className="w-80 rounded-xl border border-gray-200 bg-white shadow-xl overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <div className="flex items-center gap-3">
              <p className="text-sm font-semibold text-gray-900">
                {state === 'reports' ? 'My reports' : 'Share feedback'}
              </p>
              {(state === 'open' || state === 'error' || state === 'submitting') && (
                <Button unstyled onClick={() => setState('reports')}
                  className="text-xs text-gray-400 hover:text-gray-700 underline underline-offset-2 transition-colors"
                  aria-label="My reports">
                  My reports
                </Button>
              )}
              {state === 'reports' && (
                <Button unstyled onClick={() => setState('open')}
                  className="text-xs text-gray-400 hover:text-gray-700 underline underline-offset-2 transition-colors">
                  ← Write feedback
                </Button>
              )}
            </div>
            <Button unstyled onClick={close}
              className="text-gray-400 hover:text-gray-600 transition-colors" aria-label="Close">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </Button>
          </div>

          {/* Success */}
          {state === 'success' && (
            <div className="flex flex-col items-center justify-center px-4 py-8 gap-2 text-center">
              <svg className="w-8 h-8 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-sm font-medium text-gray-900">Received — thank you!</p>
              {reportId && (
                <p className="text-xs text-gray-400">
                  Reference: <span className="font-mono font-semibold text-gray-600">{reportId}</span>
                </p>
              )}
              <p className="text-xs text-gray-400">We&apos;ll look into it.</p>
              {storageNote && (
                <p className="mt-1 text-[11px] text-gray-500 leading-snug">
                  Screenshot saved. Image storage: <span className="font-semibold">{storageNote.remaining_mb} MB</span> left
                  of {storageNote.budget_mb} MB ({storageNote.used_mb} MB used).
                </p>
              )}
              <button
                type="button"
                onClick={() => setState('reports')}
                className="mt-1 text-xs text-gray-400 underline underline-offset-2 hover:text-gray-600 transition-colors"
              >
                View my reports
              </button>
            </div>
          )}

          {/* My reports */}
          {state === 'reports' && (
            <div className="px-4 py-4 max-h-72 overflow-y-auto">
              {reportsLoading && (
                <p className="text-xs text-gray-400 text-center py-4">Loading…</p>
              )}
              {reportsError && !reportsLoading && (
                <p className="text-xs text-red-500 text-center py-4">
                  Could not load your reports — please try again.
                </p>
              )}
              {!reportsLoading && !reportsError && reports !== null && reports.length === 0 && (
                <p className="text-xs text-gray-400 text-center py-4">No reports yet.</p>
              )}
              {!reportsLoading && !reportsError && reports !== null && reports.length > 0 && (
                <ul className="space-y-2">
                  {reports.map((r) => (
                    <li key={r.report_id} className="rounded-lg border border-gray-100 px-3 py-2 space-y-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono text-[10.5px] text-gray-500 truncate">{r.report_id}</span>
                        <Badge variant={statusVariant(r.status)} size="sm">
                          {statusLabel(r.status)}
                        </Badge>
                      </div>
                      {r.message_excerpt && (
                        <p className="text-xs text-gray-600 truncate">{r.message_excerpt}</p>
                      )}
                      {(r.severity || r.area) && (
                        <div className="flex flex-wrap gap-1">
                          {r.severity && <Badge variant="neutral" size="sm">{r.severity}</Badge>}
                          {r.area && <Badge variant="neutral" size="sm">{r.area}</Badge>}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {/* Form */}
          {(state === 'open' || state === 'submitting' || state === 'error') && (
            <div className="px-4 py-4 space-y-3">
              {/* Category tabs */}
              <div className="flex gap-2">
                {(Object.keys(CATEGORY_LABELS) as Category[]).map((c) => (
                  <Button unstyled key={c} onClick={() => setCategory(c)}
                    className={`flex-1 text-xs py-1.5 rounded border font-medium transition-colors ${
                      category === c
                        ? 'bg-gray-900 text-white border-gray-900'
                        : 'border-gray-200 text-gray-500 hover:border-gray-300 hover:text-gray-700'
                    }`}>
                    {CATEGORY_LABELS[c]}
                  </Button>
                ))}
              </div>

              {/* Textarea */}
              <textarea
                ref={textareaRef}
                rows={3}
                placeholder={
                  category === 'bug'  ? 'What happened? What did you expect?' :
                  category === 'idea' ? 'What would make this more useful?' :
                  "What's on your mind?"
                }
                className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2.5 text-gray-800 placeholder-gray-300 resize-none focus:outline-none focus:ring-1 focus:ring-gray-400"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) void submit(); }}
                disabled={state === 'submitting'}
              />

              {/* Transparency: only shown when we are actually recording (bug + consent). */}
              {category === 'bug' && getAnalyticsConsent() === 'granted' && (
                <p className="text-[10.5px] text-gray-400">
                  To help us debug, we capture a short screen replay of this session.
                </p>
              )}

              {/* Attach image — screenshot or upload */}
              <div className="space-y-2">
                {shotStep === 'capture' ? (
                  <ScreenshotCapture
                    onCapture={onCaptured}
                    onCancel={() => setShotStep('none')}
                    onDelayStart={() => setState('capturing')}
                  />
                ) : screenshot ? (
                  <div className="relative rounded-lg overflow-hidden border border-gray-200">
                    <img src={screenshot} alt="Attachment preview" className="w-full object-cover max-h-28" />
                    <button
                      type="button"
                      onClick={() => setScreenshot(null)}
                      className="absolute top-1 right-1 w-5 h-5 rounded-full bg-gray-900/70 text-white text-[10px] flex items-center justify-center hover:bg-gray-900"
                      title="Remove image"
                    >
                      ✕
                    </button>
                    <div className="absolute bottom-1 left-1 text-[9px] font-mono bg-gray-900/60 text-white rounded px-1.5 py-0.5">
                      image attached
                    </div>
                  </div>
                ) : (
                  <div className="flex gap-2">
                    {/* Take screenshot */}
                    <Button unstyled
                      onClick={() => setShotStep('capture')}
                      disabled={state === 'submitting'}
                      className="flex-1 flex items-center justify-center gap-1.5 text-xs py-1.5 px-3 rounded-lg border border-dashed border-gray-300 text-gray-500 hover:border-gray-400 hover:text-gray-700 transition-colors disabled:opacity-40"
                    >
                      <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round"
                          d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z" />
                        <path strokeLinecap="round" strokeLinejoin="round"
                          d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0zM18.75 10.5h.008v.008h-.008V10.5z" />
                      </svg>
                      Screenshot
                    </Button>
                    {/* Upload from disk */}
                    <Button unstyled
                      onClick={() => fileInputRef.current?.click()}
                      disabled={state === 'submitting'}
                      className="flex-1 flex items-center justify-center gap-1.5 text-xs py-1.5 px-3 rounded-lg border border-dashed border-gray-300 text-gray-500 hover:border-gray-400 hover:text-gray-700 transition-colors disabled:opacity-40"
                    >
                      <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round"
                          d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                      </svg>
                      Upload
                    </Button>
                  </div>
                )}
              </div>

              {/* Page context badge */}
              <div className="flex items-center gap-1.5 text-[10.5px] text-gray-400">
                <svg className="w-3 h-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244" />
                </svg>
                <span className="truncate font-mono">{window.location.pathname}</span>
              </div>

              {state === 'error' && (
                <p className="text-xs text-red-500">Failed to send — please try again.</p>
              )}

              {/* Footer */}
              <div className="flex items-center justify-between pt-0.5">
                <p className="text-xs text-gray-300">⌘ Enter to send</p>
                <Button unstyled
                  onClick={submit}
                  disabled={!message.trim() || state === 'submitting'}
                  className="text-xs font-semibold px-4 py-2 rounded-lg bg-gray-900 text-white hover:bg-gray-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {state === 'submitting' ? 'Sending…' : 'Send'}
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Trigger button */}
      <Button unstyled
        onClick={() => state === 'idle' ? setState('open') : close()}
        className="flex items-center gap-2 px-4 py-2.5 rounded-full bg-gray-900 text-white text-xs font-semibold shadow-md hover:bg-gray-700 transition-colors"
        aria-label="Give feedback"
      >
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round"
            d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
        </svg>
        Feedback
      </Button>
    </div>
  );
}
