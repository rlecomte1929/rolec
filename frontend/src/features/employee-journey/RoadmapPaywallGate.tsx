/**
 * RoadmapPaywallGate — rendered on the roadmap page when the employee
 * has not yet paid for their relocation roadmap (access_tier = 'free').
 *
 * Design mirrors the Audos CaseGate.tsx proof-of-concept but uses the
 * ReloPass platform design system (navy/accent tokens, AppShell spacing).
 *
 * Checkout flow:
 *   POST /api/payment/checkout  { assignmentId, tier: 'roadmap' }
 *   → { checkoutUrl: string }   (Stripe-hosted checkout)
 *   → redirect to Stripe
 *   → success_url points back to /employee/dashboard?payment=success&session_id=…
 *
 * ⚠️  The /api/payment/checkout endpoint must be implemented in the backend.
 *     It should create a Stripe Checkout Session (same contract as the
 *     relopass-checkout Audos hook) and return { checkoutUrl }.
 *     See docs/stripe-relopass-package/ for the full spec.
 */
import React, { useState } from 'react';
import { AlertTriangle, CheckCircle2, Lock, Shield } from 'lucide-react';
import { getAuthItem } from '../../utils/demo';

interface RoadmapPaywallGateProps {
  /** Assignment UUID — passed as the checkout `assignmentId` payload. */
  assignmentId: string;
  /** Destination city label, e.g. "Amsterdam". */
  destCity?: string | null;
  /** Destination country, e.g. "Netherlands". */
  destCountry?: string | null;
}

const FEATURES = [
  'All requirements in chronological order, anchored to your move date',
  'Feasibility flags — see immediately if any windows are tight or already missed',
  'Recommended vendors per category: movers, immigration lawyers, tax advisors, schools',
  'Responsible-party tagging on every item (HR / you / both)',
] as const;

export const RoadmapPaywallGate: React.FC<RoadmapPaywallGateProps> = ({
  assignmentId,
  destCity,
  destCountry,
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const destination = [destCity, destCountry].filter(Boolean).join(', ') || 'your destination';

  const handleUnlock = async () => {
    setLoading(true);
    setError(null);
    try {
      // /api/payment/checkout requires the caller to be able to see this
      // assignment (require_assignment_visibility), so send the ReloPass token.
      const token = getAuthItem('relopass_token');
      const res = await fetch('/api/payment/checkout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ assignmentId, tier: 'roadmap' }),
      });
      if (!res.ok) {
        const err = (await res.json().catch(() => ({ error: 'Unknown error' }))) as {
          error?: string;
        };
        throw new Error(err.error ?? `Checkout failed (${res.status})`);
      }
      const { checkoutUrl } = (await res.json()) as { checkoutUrl?: string };
      if (!checkoutUrl) throw new Error('No checkout URL returned from server.');
      window.location.href = checkoutUrl;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.');
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl px-6 py-12">
      {/* Lock icon + headline */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-navy-50 border border-navy-100 mb-4">
          <Lock className="w-7 h-7 text-navy-700" aria-hidden />
        </div>
        <h2 className="text-2xl font-semibold text-navy-800 mb-2">Your roadmap is ready to unlock</h2>
        <p className="text-base text-slate-600 max-w-md mx-auto">
          Get your full, personalised step-by-step plan for moving to {destination}.
        </p>
      </div>

      {/* Feature list card */}
      <div className="rounded-xl border border-accent-200 bg-accent-50 p-5 mb-6">
        <div className="flex items-center gap-3 mb-4">
          <Shield className="w-5 h-5 text-accent-600 flex-shrink-0" aria-hidden />
          <h3 className="font-semibold text-navy-800">Full roadmap + vendor recommendations</h3>
        </div>
        <ul className="space-y-2">
          {FEATURES.map((line) => (
            <li key={line} className="flex items-start gap-2 text-sm text-slate-700">
              <CheckCircle2
                className="w-4 h-4 text-accent-500 flex-shrink-0 mt-0.5"
                aria-hidden
              />
              <span>{line}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Error state */}
      {error ? (
        <div className="mb-4 px-4 py-3 rounded-lg bg-red-50 border border-red-200 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" aria-hidden />
          <p className="text-sm text-red-700">{error}</p>
        </div>
      ) : null}

      {/* Primary CTA */}
      <button
        type="button"
        onClick={() => void handleUnlock()}
        disabled={loading}
        className="w-full flex items-center justify-center gap-2 py-3.5 px-5 rounded-xl font-semibold text-white bg-navy-700 hover:bg-navy-800 disabled:opacity-60 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600 focus-visible:ring-offset-2"
      >
        {loading ? (
          <>
            <span
              className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin"
              aria-hidden
            />
            Opening checkout…
          </>
        ) : (
          'Unlock full roadmap — €800'
        )}
      </button>
      <p className="text-center text-xs text-slate-500 mt-3">
        Secure checkout via Stripe · Your card details never touch ReloPass
      </p>
    </div>
  );
};
