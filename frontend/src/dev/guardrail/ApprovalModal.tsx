/**
 * ApprovalModal
 *
 * Global modal that listens for pending AI spend requests via Supabase
 * Realtime and prompts the admin to approve or reject each one.
 *
 * Mount ONCE at the app root (App.tsx), outside the Routes tree:
 *
 *   import { ApprovalModal } from './dev/guardrail/ApprovalModal';
 *   // inside App():
 *   <ApprovalModal />
 *
 * How it works:
 *   1. On mount, fetches any pre-existing pending requests
 *   2. Subscribes to INSERT events on ai_spend_requests (status = pending)
 *   3. Renders a blocking modal for each — FIFO
 *   4. Calls POST /functions/v1/approve-ai-request with { request_id, approved }
 *   5. Removes the modal on success; shows error inline on failure
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Button } from '../../components/antigravity/Button';
import { supabase } from '../../api/supabase';

const APPROVE_URL = `${import.meta.env.VITE_SUPABASE_URL}/functions/v1/approve-ai-request`;
const ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY;

interface SpendRequest {
  id: string;
  function_name: string;
  description: string;
  estimated_cost_cents: number;
  created_at: string;
}

export function ApprovalModal() {
  const [queue, setQueue] = useState<SpendRequest[]>([]);
  const [processing, setProcessing] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const channelRef = useRef<ReturnType<typeof supabase.channel> | null>(null);

  const addToQueue = useCallback((req: SpendRequest) => {
    setQueue((prev) => {
      if (prev.some((r) => r.id === req.id)) return prev;
      return [...prev, req];
    });
  }, []);

  const removeFromQueue = useCallback((id: string) => {
    setQueue((prev) => prev.filter((r) => r.id !== id));
    setActionError(null);
  }, []);

  // Initial fetch + Realtime subscription
  useEffect(() => {
    (async () => {
      const { data } = await supabase
        .from('ai_spend_requests')
        .select('id, function_name, description, estimated_cost_cents, created_at')
        .eq('status', 'pending')
        .order('created_at', { ascending: true });
      (data ?? []).forEach(addToQueue);
    })();

    const channel = supabase
      .channel('ai_spend_requests_pending')
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'ai_spend_requests', filter: 'status=eq.pending' },
        (payload) => addToQueue(payload.new as SpendRequest)
      )
      .subscribe();

    channelRef.current = channel;
    return () => { supabase.removeChannel(channel); };
  }, [addToQueue]);

  const handleDecision = useCallback(async (approved: boolean) => {
    const current = queue[0];
    if (!current || processing) return;
    setProcessing(true);
    setActionError(null);

    try {
      const res = await fetch(APPROVE_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', apikey: ANON_KEY },
        body: JSON.stringify({ request_id: current.id, approved }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error((data as { error?: string })?.error ?? `HTTP ${res.status}`);
      }
      removeFromQueue(current.id);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setProcessing(false);
    }
  }, [queue, processing, removeFromQueue]);

  const current = queue[0] ?? null;
  if (!current) return null;

  const costLabel = current.estimated_cost_cents > 0
    ? `~$${(current.estimated_cost_cents / 100).toFixed(2)}`
    : '< $0.01';

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[9998]" aria-hidden="true" />

      {/* Modal */}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="guardrail-title"
        aria-describedby="guardrail-desc"
        className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-[9999] w-full max-w-md bg-white rounded-2xl shadow-2xl border border-slate-200 p-6"
      >
        {/* Header */}
        <div className="flex items-start gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-accent-50 border border-accent-100 flex items-center justify-center shrink-0">
            <svg className="w-5 h-5 text-accent-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6z" />
            </svg>
          </div>
          <div className="flex-1">
            <h2 id="guardrail-title" className="text-base font-semibold text-slate-900">AI Spend Request</h2>
            <p className="text-xs text-slate-400 font-mono mt-0.5">{current.function_name}</p>
          </div>
          {queue.length > 1 && (
            <span className="text-xs font-semibold px-2 py-1 rounded-full bg-amber-50 text-amber-600 border border-amber-200">
              +{queue.length - 1} more
            </span>
          )}
        </div>

        {/* Description */}
        <p id="guardrail-desc" className="text-sm text-slate-700 leading-relaxed mb-4">
          {current.description}
        </p>

        {/* Cost */}
        <div className="flex items-center justify-between px-4 py-2.5 bg-slate-50 rounded-xl border border-slate-100 mb-4">
          <span className="text-xs text-slate-500">Estimated cost</span>
          <span className="text-sm font-bold text-slate-900 tabular-nums">{costLabel}</span>
        </div>

        {/* Error */}
        {actionError && (
          <div className="px-4 py-3 rounded-xl bg-red-50 border border-red-200 text-sm text-red-600 mb-4" role="alert">
            ⚠️ {actionError}
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3">
          <Button unstyled
            onClick={() => handleDecision(false)}
            disabled={processing}
            className="flex-1 px-4 py-2.5 rounded-xl border border-slate-200 bg-white text-sm font-medium text-slate-600 hover:bg-red-50 hover:text-red-600 hover:border-red-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Reject
          </Button>
          <Button unstyled
            onClick={() => handleDecision(true)}
            disabled={processing}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-accent-500 hover:bg-accent-600 text-white text-sm font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {processing ? (
              <>
                <span className="w-3.5 h-3.5 rounded-full border-2 border-white/30 border-t-white animate-spin" aria-hidden="true" />
                Running…
              </>
            ) : 'Approve & Run'}
          </Button>
        </div>

        <p className="text-center text-xs text-slate-400 mt-3">
          Guardrail active · disable in Admin → Overview
        </p>
      </div>
    </>
  );
}
