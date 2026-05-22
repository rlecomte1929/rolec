/**
 * FeedbackWidget — floating feedback button for authenticated users.
 *
 * Fixed bottom-right on all product pages.
 * Submits to the `feedback` Supabase table via direct insert.
 */

import { useState, useRef, useEffect } from 'react';
import { supabase } from '../api/supabase';

type Category = 'bug' | 'idea' | 'other';

const CATEGORY_LABELS: Record<Category, string> = {
  bug:   'Bug',
  idea:  'Idea',
  other: 'Other',
};

type WidgetState = 'idle' | 'open' | 'submitting' | 'success' | 'error';

export function FeedbackWidget({ userId }: { userId: string | null }) {
  const [state, setState]       = useState<WidgetState>('idle');
  const [category, setCategory] = useState<Category>('other');
  const [message, setMessage]   = useState('');
  const textareaRef             = useRef<HTMLTextAreaElement>(null);
  const containerRef            = useRef<HTMLDivElement>(null);

  // Focus textarea when popover opens
  useEffect(() => {
    if (state === 'open') {
      setTimeout(() => textareaRef.current?.focus(), 50);
    }
  }, [state]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && state === 'open') close();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [state]);

  // Close on click outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (state === 'open' && containerRef.current &&
          !containerRef.current.contains(e.target as Node)) {
        close();
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [state]);

  function close() {
    setState('idle');
    setMessage('');
    setCategory('other');
  }

  async function submit() {
    const trimmed = message.trim();
    if (!trimmed) return;

    setState('submitting');

    // user_id is intentionally omitted — the DB default `auth.uid()` fills it
    // from the JWT, which guarantees it matches the RLS WITH CHECK rule.
    // The `userId` prop is kept for forward compatibility / future analytics.
    void userId;
    const { error } = await supabase.from('feedback').insert({
      page_url: window.location.pathname,
      category,
      message:  trimmed.slice(0, 2000),
    });

    if (error) {
      setState('error');
      setTimeout(() => setState('open'), 2500);
    } else {
      setState('success');
      setTimeout(() => close(), 2000);
    }
  }

  return (
    <div ref={containerRef} className="fixed bottom-4 right-4 z-50 flex flex-col items-end gap-2">
      {(state === 'open' || state === 'submitting' || state === 'success' || state === 'error') && (
        <div className="w-80 rounded-xl border border-gray-200 bg-white shadow-lg overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <p className="text-sm font-semibold text-gray-900">Share feedback</p>
            <button
              onClick={close}
              className="text-gray-400 hover:text-gray-600 transition-colors"
              aria-label="Close"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {state === 'success' && (
            <div className="flex flex-col items-center justify-center px-4 py-8 gap-2 text-center">
              <svg className="w-8 h-8 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-sm font-medium text-gray-900">Received.</p>
              <p className="text-xs text-gray-400">Thanks for the input.</p>
            </div>
          )}

          {(state === 'open' || state === 'submitting' || state === 'error') && (
            <div className="px-4 py-4 space-y-3">
              <div className="flex gap-2">
                {(Object.keys(CATEGORY_LABELS) as Category[]).map((c) => (
                  <button
                    key={c}
                    onClick={() => setCategory(c)}
                    className={`flex-1 text-xs py-1.5 rounded border font-medium transition-colors ${
                      category === c
                        ? 'bg-gray-900 text-white border-gray-900'
                        : 'border-gray-200 text-gray-500 hover:border-gray-300 hover:text-gray-700'
                    }`}
                  >
                    {CATEGORY_LABELS[c]}
                  </button>
                ))}
              </div>

              <textarea
                ref={textareaRef}
                rows={4}
                placeholder={
                  category === 'bug'  ? 'What happened? What did you expect?' :
                  category === 'idea' ? 'What would make this more useful?' :
                  'What\'s on your mind?'
                }
                className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2.5 text-gray-800 placeholder-gray-300 resize-none focus:outline-none focus:ring-1 focus:ring-gray-400"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submit();
                }}
                disabled={state === 'submitting'}
              />

              {state === 'error' && (
                <p className="text-xs text-red-500">Failed to send — try again.</p>
              )}

              <div className="flex items-center justify-between">
                <p className="text-xs text-gray-300">⌘ Enter to send</p>
                <button
                  onClick={submit}
                  disabled={!message.trim() || state === 'submitting'}
                  className="text-xs font-semibold px-4 py-2 rounded-lg bg-gray-900 text-white hover:bg-gray-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {state === 'submitting' ? 'Sending...' : 'Send'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      <button
        onClick={() => state === 'idle' ? setState('open') : close()}
        className="flex items-center gap-2 px-4 py-2.5 rounded-full bg-gray-900 text-white text-xs font-semibold shadow-md hover:bg-gray-700 transition-colors"
        aria-label="Give feedback"
      >
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round"
            d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
        </svg>
        Feedback
      </button>
    </div>
  );
}
