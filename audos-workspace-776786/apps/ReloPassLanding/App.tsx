/**
 * ReloPass FR→NO Landing + Waitlist
 * ---------------------------------
 * Standalone marketing + registration page for the France → Norway corridor.
 * THIN CAPTURE LAYER ONLY:
 *   - The form performs a real Audos space registration + email OTP
 *     verification so each verified email becomes a counted unique signed-in
 *     user on the platform:
 *       1. POST /api/space/{spaceId}/register  → workspaceSessionId
 *       2. POST /api/auth/otp/space/send       (transactional OTP email only)
 *       3. POST /api/auth/otp/space/verify
 *     Company/role are OPTIONAL and stored on the CRM contact when provided,
 *     tagged with source "fr-no-landing". After verification the visitor gets
 *     a plain link to https://relopass.com/test-drive — no PII in the URL.
 *   - The €150 refundable deposit uses the built-in Audos Stripe integration
 *     (POST /api/payments/checkout).
 *   - NO external/production database connections. NO Supabase. NO
 *     immigration, tax, or legal logic of any kind.
 *
 * COPY ASSETS (reserved for ad campaigns — DO NOT render on this page):
 *   Ad-hook copy (B): "Stop Googling Norwegian red tape. We handle your
 *   employee's first week."
 */

import { useState, useEffect, useRef } from 'react';
import {
  Shield, CheckCircle2, ArrowRight, Loader2, Lock, Calendar, Users,
  FileText, Sparkles, AlertCircle, Plane,
} from 'lucide-react';

const WORKSPACE_ID = 'd0c29613-9cb5-4652-9c6a-494eeed352e5';
const SPACE_ID: string =
  (typeof window !== 'undefined' && ((window as any).__APP_ID__ || (window as any).__SPACE_ID__)) ||
  'workspace-776786';

const SOURCE_TAG = 'fr-no-landing'; // hidden tracking field — applied to every captured lead
const DEPOSIT_SESSION_KEY = 'relopass_frno_deposit_session_v1';
const DEPOSIT_AMOUNT_CENTS = 15000; // €150.00

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

type OfferVariant = 'standard' | 'pioneer';

const OFFERS: Array<{
  variant: OfferVariant;
  label: string;
  name: string;
  price: string;
  priceNote?: string;
  highlighted: boolean;
}> = [
  {
    variant: 'standard',
    label: 'Standard',
    name: 'FR→NO Relocation Starter',
    price: '€1,490',
    highlighted: false,
  },
  {
    variant: 'pioneer',
    label: 'Pioneer rate',
    name: 'FR→NO Relocation Starter — Pioneer Rate',
    price: '€890',
    priceNote: 'Early-adopter pricing — limited spots',
    highlighted: true,
  },
];

const OFFER_DESCRIPTION =
  'Done-for-you first-week setup for your relocating employee — D-number, EEA registration, tax card (skattekort), and folkeregister handled before their start date.';

const STEPS = [
  {
    icon: Users,
    title: 'Share the move details',
    body: 'Employee type, start date, 5 minutes of your time.',
  },
  {
    icon: FileText,
    title: 'We build the setup plan',
    body: 'Every first-week requirement mapped to a date and an owner, with the non-obvious ones flagged.',
  },
  {
    icon: CheckCircle2,
    title: 'Your employee lands ready',
    body: 'D-number, tax card, EEA registration, and folkeregister sorted before their first day.',
  },
];

function track(event: string, data?: Record<string, unknown>) {
  try {
    const fn = (window as any).trackFunnelEvent;
    if (typeof fn === 'function') fn(event, { source: SOURCE_TAG, ...data });
  } catch { /* analytics must never break the page */ }
}

/** Best-effort CRM tagging — the lead is already stored even if this fails. */
async function tagContact(contactId: string) {
  try {
    const listRes = await fetch(`/api/workspace-tags/${WORKSPACE_ID}`);
    const listData = await listRes.json().catch(() => null);
    let tag = (listData?.tags || []).find((t: any) => t?.name === SOURCE_TAG);
    if (!tag) {
      const createRes = await fetch(`/api/workspace-tags/${WORKSPACE_ID}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: SOURCE_TAG, color: '#2a93e0' }),
      });
      const created = await createRes.json().catch(() => null);
      tag = created?.tag;
    }
    if (tag?.id) {
      await fetch(`/api/entity-tags/contacts/${contactId}/tags?workspaceId=${WORKSPACE_ID}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tagId: tag.id, propagateToSessions: true }),
      });
    }
  } catch { /* non-blocking */ }
}

function redirectToCheckout(checkoutUrl: string) {
  try {
    if (window.top && window.top !== window) {
      window.top.location.href = checkoutUrl;
      return;
    }
  } catch { /* cross-origin iframe — fall through */ }
  window.location.href = checkoutUrl;
}

export default function ReloPassLanding() {
  const formRef = useRef<HTMLDivElement>(null);

  // Lead form / OTP verification state
  const [email, setEmail] = useState('');
  const [company, setCompany] = useState('');
  const [role, setRole] = useState('');
  const [formError, setFormError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [gateStep, setGateStep] = useState<'email' | 'code' | 'verified'>('email');
  const [workspaceSessionId, setWorkspaceSessionId] = useState<string | null>(null);
  const [otpCode, setOtpCode] = useState('');
  const [otpError, setOtpError] = useState('');
  const [verifying, setVerifying] = useState(false);

  // Deposit state
  const [depositLoading, setDepositLoading] = useState<OfferVariant | null>(null);
  const [depositError, setDepositError] = useState('');
  const [depositConfirmed, setDepositConfirmed] = useState(false);

  // On return from Stripe: verify the stored checkout session server-side and
  // show the inline confirmation only when the payment is actually paid.
  useEffect(() => {
    let cancelled = false;
    const raw = localStorage.getItem(DEPOSIT_SESSION_KEY);
    if (!raw) return;
    let stored: { sessionId?: string } | null = null;
    try { stored = JSON.parse(raw); } catch { /* ignore */ }
    if (!stored?.sessionId) {
      localStorage.removeItem(DEPOSIT_SESSION_KEY);
      return;
    }
    fetch(`/api/payments/status/${stored.sessionId}`, { headers: { 'X-App-Id': SPACE_ID } })
      .then((r) => r.json())
      .then((d) => {
        if (cancelled) return;
        if (d?.paymentStatus === 'paid') {
          setDepositConfirmed(true);
          localStorage.removeItem(DEPOSIT_SESSION_KEY);
          track('deposit_paid');
        } else if (d?.status === 'expired') {
          localStorage.removeItem(DEPOSIT_SESSION_KEY);
        }
        // still open → keep the stored session; we re-check on next visit
      })
      .catch(() => { /* leave stored session for a later re-check */ });
    return () => { cancelled = true; };
  }, []);

  const scrollToForm = () => {
    formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  // Step 1 — register a real Audos space session (stores the CRM contact,
  // with company/role when provided), then send the transactional OTP code.
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');

    const trimmedEmail = email.trim().toLowerCase();
    const trimmedCompany = company.trim();
    const trimmedRole = role.trim();

    if (!EMAIL_RE.test(trimmedEmail)) {
      setFormError('Please enter a valid work email address.');
      return;
    }

    setSubmitting(true);
    try {
      const res = await fetch(`/api/space/${SPACE_ID}/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: trimmedEmail,
          workspaceId: WORKSPACE_ID,
          visitorId: crypto.randomUUID(),
          attribution: { source: SOURCE_TAG },
          metadata: {
            source: SOURCE_TAG, // hidden tracking field
            ...(trimmedCompany ? { company: trimmedCompany } : {}),
            ...(trimmedRole ? { role: trimmedRole } : {}),
          },
        }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data?.success || !data?.workspaceSessionId) {
        throw new Error(data?.error || 'Something went wrong. Please try again.');
      }
      if (data.contactId) void tagContact(data.contactId);
      track('lead_captured', { company: trimmedCompany });
      setWorkspaceSessionId(data.workspaceSessionId);

      // The ONLY outbound email in this flow: the transactional OTP code.
      const otpRes = await fetch('/api/auth/otp/space/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: trimmedEmail,
          workspaceId: WORKSPACE_ID,
          sessionUuid: data.workspaceSessionId,
        }),
      });
      const otpData = await otpRes.json().catch(() => null);
      if (!otpRes.ok || otpData?.success === false) {
        throw new Error(otpData?.error || 'Could not send the verification code. Please try again.');
      }

      setOtpCode('');
      setOtpError('');
      setGateStep('code');
    } catch (err: any) {
      setFormError(err?.message || 'Something went wrong. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  // Step 2 — verify the 4-digit code against the registered session.
  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setOtpError('');

    const trimmedCode = otpCode.trim();
    if (!/^\d{4}$/.test(trimmedCode)) {
      setOtpError('Please enter the 4-digit code from your inbox.');
      return;
    }
    if (!workspaceSessionId) {
      setOtpError('Your session expired — please re-enter your email.');
      setGateStep('email');
      return;
    }

    setVerifying(true);
    try {
      const res = await fetch('/api/auth/otp/space/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          code: trimmedCode,
          workspaceId: WORKSPACE_ID,
          sessionUuid: workspaceSessionId,
        }),
      });
      const data = await res.json().catch(() => null);
      if (data?.success && data?.verified) {
        track('email_verified');
        setGateStep('verified');
      } else {
        setOtpError("That code didn't match — please try again.");
      }
    } catch {
      setOtpError("That code didn't match — please try again.");
    } finally {
      setVerifying(false);
    }
  };

  const handleDeposit = async (variant: OfferVariant) => {
    setDepositError('');
    setDepositLoading(variant);
    track('deposit_checkout_started', { variant });
    try {
      const trimmedEmail = email.trim().toLowerCase();
      const res = await fetch('/api/payments/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-App-Id': SPACE_ID },
        body: JSON.stringify({
          amount: DEPOSIT_AMOUNT_CENTS,
          currency: 'eur',
          productName: 'ReloPass FR→NO Pilot — €150 Refundable Deposit',
          productDescription:
            'Fully refundable design-partner deposit — applied to your package price if you proceed',
          customerEmail: EMAIL_RE.test(trimmedEmail) ? trimmedEmail : undefined,
          successUrl: window.location.href,
          cancelUrl: window.location.href,
          metadata: {
            source: SOURCE_TAG,
            offerVariant: variant,
            creditProgram: 'AVL',
            refundable: 'true',
          },
        }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data?.checkoutUrl) {
        throw new Error(data?.error || 'Could not start checkout. Please try again.');
      }
      try {
        localStorage.setItem(
          DEPOSIT_SESSION_KEY,
          JSON.stringify({ sessionId: data.sessionId, variant, at: Date.now() }),
        );
      } catch { /* ignore storage failures */ }
      redirectToCheckout(data.checkoutUrl);
    } catch (err: any) {
      setDepositError(err?.message || 'Could not start checkout. Please try again.');
      setDepositLoading(null);
    }
  };

  return (
    <div className="min-h-full w-full bg-[var(--space-surface-page)] text-[var(--space-text-primary)]">
      {/* Deposit confirmation banner */}
      {depositConfirmed && (
        <div className="sticky top-0 z-20 px-4 py-3 bg-green-600 text-white text-sm font-medium flex items-center justify-center gap-2 shadow-lg">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          Deposit received — we'll be in touch within 24 hours to confirm your pilot.
        </div>
      )}

      {/* ── 1. Hero ─────────────────────────────────────────────────────── */}
      <section className="relative px-5 sm:px-8 pt-14 sm:pt-20 pb-14 sm:pb-16 bg-[linear-gradient(150deg,var(--space-surface-gradient-from),var(--space-surface-gradient-via),var(--space-surface-gradient-to))] overflow-hidden">
        <div className="absolute -top-24 -right-24 w-80 h-80 rounded-full bg-[var(--space-brand-primary)] opacity-10 blur-3xl pointer-events-none" />
        <div className="absolute -bottom-32 -left-16 w-96 h-96 rounded-full bg-[var(--space-brand-highlight)] opacity-10 blur-3xl pointer-events-none" />
        <div className="max-w-3xl mx-auto relative">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-[var(--space-border-strong)] bg-[var(--space-surface-panel)] mb-6">
            <Plane className="w-3.5 h-3.5 text-[var(--space-text-accent)]" />
            <span className="text-xs font-semibold tracking-wide text-[var(--space-text-secondary)]">
              France → Norway relocations · ReloPass
            </span>
          </div>
          <h1 className="text-3xl sm:text-5xl font-bold text-white leading-tight mb-5">
            Norway compliance, handled before day one.
          </h1>
          <p className="text-base sm:text-lg text-[var(--space-text-secondary)] leading-relaxed mb-8 max-w-2xl">
            D-number, EEA registration, tax card, and folkeregister — sorted for your relocating
            employee before their first day. No Googling. No missed deadlines.
          </p>
          <button
            type="button"
            onClick={scrollToForm}
            className="inline-flex items-center gap-2 px-6 py-3.5 rounded-xl bg-[var(--space-brand-primary)] text-[var(--space-text-on-primary)] text-base font-semibold hover:brightness-110 transition-all shadow-[0_10px_30px_var(--space-shell-shadow-strong)]"
          >
            Book a pilot <ArrowRight className="w-4 h-4" />
          </button>
          <div className="flex flex-wrap gap-x-5 gap-y-2 mt-7 text-xs text-[var(--space-text-muted)]">
            <span className="flex items-center gap-1.5"><Shield className="w-3.5 h-3.5 text-[var(--space-text-accent)]" /> Built for HR teams, not lawyers</span>
            <span className="flex items-center gap-1.5"><Calendar className="w-3.5 h-3.5 text-[var(--space-text-accent)]" /> Every deadline mapped to a date</span>
            <span className="flex items-center gap-1.5"><CheckCircle2 className="w-3.5 h-3.5 text-[var(--space-text-accent)]" /> Done before the start date</span>
          </div>
        </div>
      </section>

      {/* ── 2. Offer cards (A/B price split) ────────────────────────────── */}
      <section className="px-5 sm:px-8 py-12 sm:py-14">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-xl sm:text-2xl font-bold text-[var(--space-text-primary)] mb-2 text-center">
            One package. Everything your employee needs in week one.
          </h2>
          <p className="text-sm text-[var(--space-text-secondary)] text-center mb-8 max-w-xl mx-auto">
            Fixed price per relocating employee. Choose the rate that fits — the scope is identical.
          </p>

          {depositError && (
            <div className="max-w-xl mx-auto mb-5 px-4 py-3 rounded-xl border border-red-500/40 bg-red-500/10 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
              <p className="text-xs text-red-300">{depositError}</p>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {OFFERS.map((offer) => (
              <div
                key={offer.variant}
                className={`relative flex flex-col rounded-2xl bg-white text-slate-900 p-6 sm:p-7 shadow-xl ${
                  offer.highlighted
                    ? 'ring-2 ring-[var(--space-brand-highlight)]'
                    : 'ring-1 ring-slate-200'
                }`}
              >
                <span
                  className={`absolute -top-3 left-6 px-3 py-1 rounded-full text-[11px] font-bold uppercase tracking-wider ${
                    offer.highlighted
                      ? 'bg-[var(--space-brand-highlight)] text-[#062028]'
                      : 'bg-slate-800 text-white'
                  }`}
                >
                  {offer.label}
                </span>

                <h3 className="text-base font-bold mt-3 mb-1 leading-snug">{offer.name}</h3>
                <div className="flex items-baseline gap-2 mb-1">
                  <span className="text-4xl font-extrabold tracking-tight">{offer.price}</span>
                  <span className="text-xs text-slate-500 font-medium">per relocating employee</span>
                </div>
                {offer.priceNote && (
                  <p className="text-xs font-semibold text-[var(--space-brand-highlight-700)] mb-1 flex items-center gap-1">
                    <Sparkles className="w-3.5 h-3.5" /> {offer.priceNote}
                  </p>
                )}
                <p className="text-sm text-slate-600 leading-relaxed mt-2 mb-6 flex-1">
                  {OFFER_DESCRIPTION}
                </p>

                <button
                  type="button"
                  onClick={scrollToForm}
                  className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-[var(--space-brand-primary)] text-white text-sm font-semibold hover:brightness-110 transition-all mb-2.5"
                >
                  Book a pilot <ArrowRight className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => handleDeposit(offer.variant)}
                  disabled={depositLoading !== null}
                  className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-xl border-2 border-slate-300 text-slate-800 text-sm font-semibold hover:border-[var(--space-brand-primary)] hover:text-[var(--space-brand-primary-700)] transition-all disabled:opacity-60"
                >
                  {depositLoading === offer.variant ? (
                    <><Loader2 className="w-4 h-4 animate-spin" /> Opening secure checkout…</>
                  ) : (
                    <><Lock className="w-3.5 h-3.5" /> Reserve your spot — €150 refundable deposit</>
                  )}
                </button>
                <p className="text-[11px] text-slate-500 text-center mt-2.5">
                  Fully refundable design-partner deposit — applied to your package price if you proceed.
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── 3. How it works ─────────────────────────────────────────────── */}
      <section className="px-5 sm:px-8 py-12 sm:py-14 bg-[var(--space-surface-page-alt)] border-y border-[var(--space-border-default)]">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-xl sm:text-2xl font-bold text-[var(--space-text-primary)] mb-8 text-center">
            How it works
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
            {STEPS.map((step, i) => (
              <div
                key={step.title}
                className="p-5 rounded-2xl border border-[var(--space-border-default)] bg-[var(--space-surface-card)]"
              >
                <div className="flex items-center gap-3 mb-3">
                  <span className="w-8 h-8 rounded-full bg-[var(--space-brand-primary)] text-[var(--space-text-on-primary)] flex items-center justify-center text-sm font-bold flex-shrink-0">
                    {i + 1}
                  </span>
                  <step.icon className="w-5 h-5 text-[var(--space-text-accent)]" />
                </div>
                <h3 className="text-sm font-bold text-[var(--space-text-primary)] mb-1.5">{step.title}</h3>
                <p className="text-xs text-[var(--space-text-secondary)] leading-relaxed">{step.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── 4. Lead-capture form ────────────────────────────────────────── */}
      <section ref={formRef} className="px-5 sm:px-8 py-12 sm:py-16 scroll-mt-4">
        <div className="max-w-lg mx-auto">
          <h2 className="text-xl sm:text-2xl font-bold text-[var(--space-text-primary)] mb-2 text-center">
            Get early access
          </h2>
          <p className="text-sm text-[var(--space-text-secondary)] text-center mb-7">
            Tell us who you are — we'll reach out to set up your FR→NO pilot.
          </p>

          {gateStep === 'verified' ? (
            /* ── Step 3: verified ───────────────────────────────── */
            <div className="px-5 py-6 rounded-2xl border border-green-500/40 bg-green-500/10 text-center">
              <CheckCircle2 className="w-8 h-8 text-green-400 mx-auto mb-2" />
              <p className="text-sm font-semibold text-green-300 mb-4">✓ You're verified.</p>
              <a
                href="https://relopass.com/test-drive"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl bg-[var(--space-brand-primary)] text-[var(--space-text-on-primary)] text-sm font-semibold hover:brightness-110 transition-all"
              >
                Continue to your test drive <ArrowRight className="w-4 h-4" />
              </a>
            </div>
          ) : gateStep === 'code' ? (
            /* ── Step 2: OTP entry ──────────────────────────────── */
            <form onSubmit={handleVerifyOtp} className="space-y-4" noValidate>
              <div className="px-4 py-3 rounded-xl border border-[var(--space-border-strong)] bg-[var(--space-surface-panel)]">
                <p className="text-xs text-[var(--space-text-secondary)]">
                  We've emailed you a 4-digit code — check your inbox.
                </p>
                <p className="text-[11px] text-[var(--space-text-muted)] mt-1">
                  Sent to {email.trim().toLowerCase()}
                </p>
              </div>
              <div>
                <label htmlFor="frno-otp" className="block text-xs font-semibold text-[var(--space-text-secondary)] mb-1.5">
                  4-digit code <span className="text-red-400">*</span>
                </label>
                <input
                  id="frno-otp"
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={4}
                  autoComplete="one-time-code"
                  required
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, '').slice(0, 4))}
                  placeholder="••••"
                  className="w-full px-4 py-3 rounded-xl border border-[var(--space-border-default)] bg-[var(--space-surface-card)] text-base tracking-[0.5em] text-center text-[var(--space-text-primary)] placeholder:text-[var(--space-text-muted)] outline-none focus:ring-2 focus:ring-[var(--space-brand-primary)] focus:border-transparent transition-all"
                />
              </div>

              {otpError && (
                <div className="px-3.5 py-2.5 rounded-xl border border-red-500/40 bg-red-500/10 flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                  <p className="text-xs text-red-300">{otpError}</p>
                </div>
              )}

              <button
                type="submit"
                disabled={verifying}
                className="w-full inline-flex items-center justify-center gap-2 px-5 py-3.5 rounded-xl bg-[var(--space-brand-primary)] text-[var(--space-text-on-primary)] text-sm font-semibold hover:brightness-110 transition-all disabled:opacity-60"
              >
                {verifying ? 'Verifying…' : (<>Verify <ArrowRight className="w-4 h-4" /></>)}
              </button>
              <button
                type="button"
                onClick={() => { setGateStep('email'); setOtpCode(''); setOtpError(''); }}
                className="w-full text-[11px] text-[var(--space-text-muted)] hover:text-[var(--space-text-secondary)] transition-colors"
              >
                Use a different email
              </button>
            </form>
          ) : (
            /* ── Step 1: email entry ────────────────────────────── */
            <form onSubmit={handleSubmit} className="space-y-4" noValidate>
              <div>
                <label htmlFor="frno-email" className="block text-xs font-semibold text-[var(--space-text-secondary)] mb-1.5">
                  Work email <span className="text-red-400">*</span>
                </label>
                <input
                  id="frno-email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  className="w-full px-4 py-3 rounded-xl border border-[var(--space-border-default)] bg-[var(--space-surface-card)] text-sm text-[var(--space-text-primary)] placeholder:text-[var(--space-text-muted)] outline-none focus:ring-2 focus:ring-[var(--space-brand-primary)] focus:border-transparent transition-all"
                />
              </div>
              <div>
                <label htmlFor="frno-company" className="block text-xs font-semibold text-[var(--space-text-secondary)] mb-1.5">
                  Company name <span className="text-[var(--space-text-muted)] font-normal">(optional)</span>
                </label>
                <input
                  id="frno-company"
                  type="text"
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  placeholder="Your company"
                  className="w-full px-4 py-3 rounded-xl border border-[var(--space-border-default)] bg-[var(--space-surface-card)] text-sm text-[var(--space-text-primary)] placeholder:text-[var(--space-text-muted)] outline-none focus:ring-2 focus:ring-[var(--space-brand-primary)] focus:border-transparent transition-all"
                />
              </div>
              <div>
                <label htmlFor="frno-role" className="block text-xs font-semibold text-[var(--space-text-secondary)] mb-1.5">
                  Your role <span className="text-[var(--space-text-muted)] font-normal">(optional)</span>
                </label>
                <input
                  id="frno-role"
                  type="text"
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  placeholder="e.g. HR Manager, Office Manager"
                  className="w-full px-4 py-3 rounded-xl border border-[var(--space-border-default)] bg-[var(--space-surface-card)] text-sm text-[var(--space-text-primary)] placeholder:text-[var(--space-text-muted)] outline-none focus:ring-2 focus:ring-[var(--space-brand-primary)] focus:border-transparent transition-all"
                />
              </div>

              {/* Hidden tracking field */}
              <input type="hidden" name="source" value={SOURCE_TAG} />

              {formError && (
                <div className="px-3.5 py-2.5 rounded-xl border border-red-500/40 bg-red-500/10 flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                  <p className="text-xs text-red-300">{formError}</p>
                </div>
              )}

              <button
                type="submit"
                disabled={submitting}
                className="w-full inline-flex items-center justify-center gap-2 px-5 py-3.5 rounded-xl bg-[var(--space-brand-primary)] text-[var(--space-text-on-primary)] text-sm font-semibold hover:brightness-110 transition-all disabled:opacity-60"
              >
                {submitting ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> Sending…</>
                ) : (
                  <>Get early access <ArrowRight className="w-4 h-4" /></>
                )}
              </button>
            </form>
          )}

          {/* ── 6. Privacy / opt-in notice ──────────────────────────────── */}
          <p className="text-[11px] text-[var(--space-text-muted)] text-center mt-4 leading-relaxed">
            By submitting, you agree to be contacted about ReloPass services. We never sell your data.
          </p>
        </div>
      </section>

      {/* Footer */}
      <footer className="px-5 sm:px-8 py-6 border-t border-[var(--space-border-default)] text-center">
        <p className="text-[11px] text-[var(--space-text-muted)]">
          ReloPass · France → Norway employee relocation compliance, done for you.
        </p>
      </footer>
    </div>
  );
}
