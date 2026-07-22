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
import { AlertTriangle, CheckCircle2, FlaskConical, Lock, Shield } from 'lucide-react';
import api from '../../api/client';
import { getAuthItem } from '../../utils/demo';
import { looksLikeTestEmail } from '../../utils/testAccount';

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

  // Test-drive (synthetic @probe.test/@testco.com) users are on Stripe TEST mode — show
  // the test-card instructions so there are no surprises and it's clear no real money moves.
  // Real customers never see this. Mirrors profiles.is_test via looksLikeTestEmail.
  const isTestDrive = looksLikeTestEmail(getAuthItem('relopass_email'));

  const destination = [destCity, destCountry].filter(Boolean).join(', ') || 'your destination';

  const handleUnlock = async () => {
    setLoading(true);
    setError(null);
    try {
      // Route through the shared API client, NOT a relative fetch. In production the app
      // is a static site at relopass.com; a relative fetch('/api/payment/checkout') hits
      // that host (→ 200 with an empty body → "Unexpected end of JSON input"), not the
      // backend. The api client prepends VITE_API_URL (api.relopass.com) and adds the
      // Authorization header via its request interceptor (require_assignment_visibility).
      const res = await api.post<{ checkoutUrl?: string }>('/api/payment/checkout', {
        assignmentId,
        tier: 'roadmap',
      });
      const checkoutUrl = res.data?.checkoutUrl;
      if (!checkoutUrl) throw new Error('No checkout URL returned from server.');
      window.location.href = checkoutUrl;
    } catch (err) {
      // Surface the backend's {error} message when present (axios puts it on response.data).
      const backendError = (err as { response?: { data?: { error?: string } } })?.response?.data?.error;
      setError(backendError ?? (err instanceof Error ? err.message : 'Something went wrong. Please try again.'));
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

      {/* Test-mode instructions — test-drive users only. No real charge is possible. */}
      {isTestDrive ? (
        <div className="mb-4 px-4 py-3 rounded-lg bg-amber-50 border border-amber-200">
          <div className="flex items-start gap-2">
            <FlaskConical className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" aria-hidden />
            <div className="text-sm text-amber-800">
              <p className="font-semibold">Test mode — you will not be charged.</p>
              <p className="mt-0.5">
                This is a demo checkout. On the Stripe page, pay with test card{' '}
                <span className="font-mono font-medium">4242&nbsp;4242&nbsp;4242&nbsp;4242</span>,
                any future expiry date, and any 3-digit CVC. No real payment is taken.
              </p>
            </div>
          </div>
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
