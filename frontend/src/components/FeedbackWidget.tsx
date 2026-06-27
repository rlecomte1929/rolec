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

import { useState, useRef, useEffect, useCallback } from 'react';
import { supabase } from '../api/supabase';
import { Button } from './antigravity/Button';

type Category    = 'bug' | 'idea' | 'other';
type WidgetState = 'idle' | 'open' | 'capturing' | 'submitting' | 'success' | 'error';

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

export function FeedbackWidget({ userId }: { userId: string | null }) {
  const [state, setState]         = useState<WidgetState>('idle');
  const [category, setCategory]   = useState<Category>('bug');
  const [message, setMessage]     = useState('');
  const [screenshot, setScreenshot] = useState<string | null>(null);
  const [reportId, setReportId]   = useState<string | null>(null);

  const textareaRef  = useRef<HTMLTextAreaElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Focus textarea when popover opens
  useEffect(() => {
    if (state === 'open') setTimeout(() => textareaRef.current?.focus(), 50);
  }, [state]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && (state === 'open' || state === 'error')) close();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [state]);

  // Close on click outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if ((state === 'open' || state === 'error') && containerRef.current &&
          !containerRef.current.contains(e.target as Node)) close();
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [state]);

  function close() {
    setState('idle');
    setMessage('');
    setCategory('bug');
    setScreenshot(null);
    setReportId(null);
  }

  const captureScreenshot = useCallback(async () => {
    setState('capturing');
    // Hide widget during capture so it doesn't appear in the screenshot
    const widgetEl = containerRef.current;
    if (widgetEl) widgetEl.style.visibility = 'hidden';

    try {
      // Lazy-import html2canvas so it doesn't affect initial bundle
      const { default: html2canvas } = await import('html2canvas');
      const canvas = await html2canvas(document.body, {
        useCORS:        true,
        allowTaint:     true,
        logging:        false,
        scale:          0.4,          // reduce resolution → smaller payload
        ignoreElements: (el) => el === widgetEl,
      });
      const dataUrl = canvas.toDataURL('image/jpeg', 0.65);
      setScreenshot(dataUrl);
    } catch {
      // Screenshot failed silently — user can still submit without it
    } finally {
      if (widgetEl) widgetEl.style.visibility = '';
      setState('open');
    }
  }, []);

  async function submit() {
    const trimmed = message.trim();
    if (!trimmed) return;

    setState('submitting');
    const rid = reportId ?? makeReportId(category);
    setReportId(rid);

    void userId; // kept for future analytics; DB uses auth.uid() default
    const { error } = await supabase.from('feedback').insert({
      page_url:        window.location.pathname,
      category,
      message:         trimmed.slice(0, 2000),
      report_id:       rid,
      screenshot_data: screenshot ?? null,
    });

    if (error) {
      setState('error');
      setTimeout(() => setState('open'), 2500);
    } else {
      setState('success');
      setTimeout(() => close(), 3500);
    }
  }

  const isVisible = state !== 'idle' && state !== 'capturing';

  return (
    <div ref={containerRef} className="fixed bottom-4 right-4 z-50 flex flex-col items-end gap-2">
      {isVisible && (
        <div className="w-80 rounded-xl border border-gray-200 bg-white shadow-xl overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <p className="text-sm font-semibold text-gray-900">Share feedback</p>
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

              {/* Screenshot area */}
              <div className="space-y-2">
                {screenshot ? (
                  <div className="relative rounded-lg overflow-hidden border border-gray-200">
                    <img src={screenshot} alt="Page screenshot" className="w-full object-cover max-h-28" />
                    <button
                      onClick={() => setScreenshot(null)}
                      className="absolute top-1 right-1 w-5 h-5 rounded-full bg-gray-900/70 text-white text-[10px] flex items-center justify-center hover:bg-gray-900"
                      title="Remove screenshot"
                    >
                      ✕
                    </button>
                    <div className="absolute bottom-1 left-1 text-[9px] font-mono bg-gray-900/60 text-white rounded px-1.5 py-0.5">
                      screenshot attached
                    </div>
                  </div>
                ) : (
                  <Button unstyled
                    onClick={captureScreenshot}
                    disabled={state === 'submitting'}
                    className="w-full flex items-center justify-center gap-1.5 text-xs py-1.5 px-3 rounded-lg border border-dashed border-gray-300 text-gray-500 hover:border-gray-400 hover:text-gray-700 transition-colors disabled:opacity-40"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round"
                        d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z" />
                      <path strokeLinecap="round" strokeLinejoin="round"
                        d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0zM18.75 10.5h.008v.008h-.008V10.5z" />
                    </svg>
                    Capture screenshot
                  </Button>
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
