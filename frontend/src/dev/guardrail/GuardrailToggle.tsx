/**
 * GuardrailToggle
 *
 * Admin settings widget that reads/writes the AI spend guardrail flag.
 * Drop this into any admin page — no props required.
 *
 * Example:
 *   <GuardrailToggle />
 */
import { useAiGuardrail } from './useAiGuardrail';

export function GuardrailToggle() {
  const { enabled, loading, saving, error, toggle } = useAiGuardrail();

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-400">
        <span className="inline-block w-4 h-4 rounded-full border-2 border-slate-200 border-t-accent-500 animate-spin" />
        Loading guardrail status…
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white px-5 py-4 max-w-lg">
      <div className="flex items-center gap-3">
        {/* Shield icon */}
        <div className="w-8 h-8 rounded-lg bg-accent-50 flex items-center justify-center shrink-0">
          <svg className="w-4 h-4 text-accent-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
        </div>

        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-slate-900">AI Spend Guardrail</p>
          <p className="text-xs text-slate-500 mt-0.5">
            {enabled
              ? 'Every AI call requires your approval before running.'
              : 'AI calls execute without interruption (production mode).'}
          </p>
        </div>

        {/* Toggle */}
        <button
          role="switch"
          aria-checked={enabled}
          aria-label={enabled ? 'Disable guardrail' : 'Enable guardrail'}
          disabled={saving}
          onClick={() => toggle(!enabled)}
          className={`relative flex-shrink-0 w-11 h-6 rounded-full border-0 transition-colors duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer ${enabled ? 'bg-accent-500' : 'bg-slate-200'}`}
        >
          <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all duration-200 ${enabled ? 'left-[calc(100%-22px)]' : 'left-0.5'}`} />
        </button>
      </div>

      {/* Dev mode badge */}
      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-slate-100">
        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold tracking-wider bg-amber-50 text-amber-600 border border-amber-200 uppercase">
          Dev mode
        </span>
        <span className="text-xs text-slate-400">Remove this toggle before demo / launch.</span>
      </div>

      {saving && (
        <p className="text-xs text-slate-400 mt-2 flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded-full border border-slate-300 border-t-accent-400 animate-spin" />
          Saving…
        </p>
      )}
      {error && (
        <p className="text-xs text-red-500 mt-2" role="alert">⚠️ {error}</p>
      )}
    </div>
  );
}
