/**
 * ReloPass Registration Gate
 * --------------------------
 * Corridor-neutral registration page. Its ONLY job:
 *   land → enter email → OTP code → verify → "Continue to your test drive →".
 * All corridor selection and relocation content lives on
 * https://relopass.com/test-drive — this page stays generic on purpose.
 *
 * Registration flow (platform built-in endpoints — no server-hook
 * intermediary; the platform owns every database write):
 *   1. POST /api/space/{spaceId}/register  → workspaceSessionId
 *   2. POST /api/auth/otp/space/send       (transactional OTP email only)
 *   3. POST /api/auth/otp/space/verify
 * Each verified email becomes a counted unique signed-in user on the
 * platform. Company/role are OPTIONAL and stored on the CRM contact when
 * provided, tagged with source "fr-no-landing" (internal tracking tag only —
 * never rendered). After verification the visitor gets a plain link to
 * https://relopass.com/test-drive — no PII or params in the URL.
 *
 * The €150 refundable deposit button uses the built-in Audos Stripe
 * integration (POST /api/payments/checkout) and is intentionally unchanged.
 *
 * NO external database connections. NO immigration, tax, or legal logic.
 */

import { useState, useEffect } from 'react';
import {
  CheckCircle2, ArrowRight, Loader2, Lock, AlertCircle, ShieldCheck,
} from 'lucide-react';

const WORKSPACE_ID = 'd0c29613-9cb5-4652-9c6a-494eeed352e5';

// IMPORTANT: the register endpoint wants the SPACE id ("workspace-776786").
// window.__APP_ID__ is the per-app registry id ("fr-no-pilot-landing") and
// must NOT be used as the spaceId — that was the previous bug here.
const SPACE_ID: string =
  (typeof window !== 'undefined' && (window as any).__SPACE_ID__) || 'workspace-776786';

const SOURCE_TAG = 'fr-no-landing'; // hidden tracking tag — applied to every captured lead
const SESSION_STORAGE_KEY = `space_session_${SPACE_ID}`;
const DEPOSIT_SESSION_KEY = 'relopass_frno_deposit_session_v1';
const DEPOSIT_AMOUNT_CENTS = 15000; // €150.00

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

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
  // Registration / OTP state
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

  // Deposit state (Stripe flow intentionally unchanged)
  const [depositLoading, setDepositLoading] = useState(false);
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

  // Step 1 — register a real Audos space session (the PLATFORM endpoint owns
  // the database write; no custom hook in between), then send the OTP code.
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
        // Persist the verified session so the platform counts this visitor
        // as a unique signed-in user across reloads.
        try {
          localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({
            id: workspaceSessionId,
            workspaceSessionId,
            email: email.trim().toLowerCase(),
            verified: true,
            timestamp: Date.now(),
          }));
        } catch { /* storage failures must not block verification */ }
        track('email_verified');
        setGateStep('verified');
      } else {
        setOtpError(data?.error || "That code didn't match — please try again.");
      }
    } catch {
      setOtpError("That code didn't match — please try again.");
    } finally {
      setVerifying(false);
    }
  };

  // Stripe deposit — flow and payload intentionally unchanged (hard rule).
  const handleDeposit = async () => {
    setDepositError('');
    setDepositLoading(true);
    track('deposit_checkout_started', { variant: 'standard' });
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
            offerVariant: 'standard',
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
          JSON.stringify({ sessionId: data.sessionId, variant: 'standard', at: Date.now() }),
        );
      } catch { /* ignore storage failures */ }
      redirectToCheckout(data.checkoutUrl);
    } catch (err: any) {
      setDepositError(err?.message || 'Could not start checkout. Please try again.');
      setDepositLoading(false);
    }
  };

  const inputClass =
    'w-full px-4 py-3 rounded-xl border border-[var(--space-border-default)] bg-[var(--space-surface-card)] text-sm text-[var(--space-text-primary)] placeholder:text-[var(--space-text-muted)] outline-none focus:ring-2 focus:ring-[var(--space-brand-primary)] focus:border-transparent transition-all';

  return (
    <div className="min-h-full w-full flex flex-col bg-[linear-gradient(150deg,var(--space-surface-gradient-from),var(--space-surface-gradient-via),var(--space-surface-gradient-to))] text-[var(--space-text-primary)]">
      {/* Deposit confirmation banner */}
      {depositConfirmed && (
        <div className="sticky top-0 z-20 px-4 py-3 bg-green-600 text-white text-sm font-medium flex items-center justify-center gap-2 shadow-lg">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          Deposit received — we'll be in touch within 24 hours.
        </div>
      )}

      <main className="flex-1 flex items-center justify-center px-5 sm:px-8 py-12 sm:py-16">
        <div className="w-full max-w-md">
          {/* Brand header */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-[var(--space-border-strong)] bg-[var(--space-surface-panel)] mb-5">
              <ShieldCheck className="w-3.5 h-3.5 text-[var(--space-text-accent)]" />
              <span className="text-xs font-semibold tracking-wide text-[var(--space-text-secondary)]">ReloPass</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold text-white leading-tight mb-2">
              Register to access your ReloPass test drive
            </h1>
            <p className="text-sm text-[var(--space-text-secondary)]">
              Enter your work email and we'll send you a 4-digit verification code.
            </p>
          </div>

          {/* Registration card */}
          <div className="rounded-2xl border border-[var(--space-border-default)] bg-[var(--space-surface-panel)] p-6 sm:p-7 shadow-[0_10px_30px_var(--space-shell-shadow-strong)]">
            {gateStep === 'verified' ? (
              /* ── Step 3: verified ───────────────────────────────── */
              <div className="px-2 py-4 text-center">
                <CheckCircle2 className="w-10 h-10 text-green-400 mx-auto mb-3" />
                <p className="text-sm font-semibold text-green-300 mb-5">✓ You're verified.</p>
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
                <div className="px-4 py-3 rounded-xl border border-[var(--space-border-strong)] bg-[var(--space-surface-card)]">
                  <p className="text-xs text-[var(--space-text-secondary)]">
                    We've emailed you a 4-digit code — check your inbox.
                  </p>
                  <p className="text-[11px] text-[var(--space-text-muted)] mt-1">
                    Sent to {email.trim().toLowerCase()}
                  </p>
                </div>
                <div>
                  <label htmlFor="relopass-otp" className="block text-xs font-semibold text-[var(--space-text-secondary)] mb-1.5">
                    4-digit code <span className="text-red-400">*</span>
                  </label>
                  <input
                    id="relopass-otp"
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
                  <label htmlFor="relopass-email" className="block text-xs font-semibold text-[var(--space-text-secondary)] mb-1.5">
                    Work email <span className="text-red-400">*</span>
                  </label>
                  <input
                    id="relopass-email"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@company.com"
                    className={inputClass}
                  />
                </div>
                <div>
                  <label htmlFor="relopass-company" className="block text-xs font-semibold text-[var(--space-text-secondary)] mb-1.5">
                    Company name <span className="text-[var(--space-text-muted)] font-normal">(optional)</span>
                  </label>
                  <input
                    id="relopass-company"
                    type="text"
                    value={company}
                    onChange={(e) => setCompany(e.target.value)}
                    placeholder="Your company"
                    className={inputClass}
                  />
                </div>
                <div>
                  <label htmlFor="relopass-role" className="block text-xs font-semibold text-[var(--space-text-secondary)] mb-1.5">
                    Your role <span className="text-[var(--space-text-muted)] font-normal">(optional)</span>
                  </label>
                  <input
                    id="relopass-role"
                    type="text"
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    placeholder="e.g. HR Manager, Office Manager"
                    className={inputClass}
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
                    <>Send my verification code <ArrowRight className="w-4 h-4" /></>
                  )}
                </button>
              </form>
            )}

            <p className="text-[11px] text-[var(--space-text-muted)] text-center mt-4 leading-relaxed">
              By submitting, you agree to be contacted about ReloPass services. We never sell your data.
            </p>
          </div>

          {/* Deposit block — Stripe button intentionally unchanged */}
          <div className="mt-6 rounded-2xl border border-[var(--space-border-default)] bg-[var(--space-surface-card)] p-5">
            {depositError && (
              <div className="mb-3 px-3.5 py-2.5 rounded-xl border border-red-500/40 bg-red-500/10 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-red-300">{depositError}</p>
              </div>
            )}
            <button
              type="button"
              onClick={handleDeposit}
              disabled={depositLoading}
              className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-xl border-2 border-[var(--space-border-strong)] text-[var(--space-text-primary)] text-sm font-semibold hover:border-[var(--space-brand-primary)] hover:text-[var(--space-text-accent)] transition-all disabled:opacity-60"
            >
              {depositLoading ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Opening secure checkout…</>
              ) : (
                <><Lock className="w-3.5 h-3.5" /> Reserve your spot — €150 refundable deposit</>
              )}
            </button>
            <p className="text-[11px] text-[var(--space-text-muted)] text-center mt-2.5">
              Fully refundable design-partner deposit — applied to your package price if you proceed.
            </p>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="px-5 sm:px-8 py-6 border-t border-[var(--space-border-default)] text-center">
        <p className="text-[11px] text-[var(--space-text-muted)]">© ReloPass</p>
      </footer>
    </div>
  );
}
