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
 * platform (visible in the platform's session/users view — NOT the CRM
 * contact count). Company/role are OPTIONAL and passed as registration
 * metadata when provided (internal only — never rendered). After
 * verification the visitor gets a plain link to
 * https://relopass.com/test-drive — no PII or query params in the URL.
 *
 * NO payment/Stripe elements. NO marketing emails (the only outbound email
 * is the transactional OTP code). NO external database connections.
 * NO immigration, tax, or legal logic.
 */

import { useState } from 'react';
import { CheckCircle2, ArrowRight, Loader2, AlertCircle } from 'lucide-react';

const WORKSPACE_ID = 'd0c29613-9cb5-4652-9c6a-494eeed352e5';

// IMPORTANT: the register endpoint wants the SPACE id ("workspace-776786").
// window.__APP_ID__ is the per-app registry id ("fr-no-pilot-landing") and
// must NOT be used as the spaceId — that was the previous bug here.
const SPACE_ID: string =
  (typeof window !== 'undefined' && (window as any).__SPACE_ID__) || 'workspace-776786';

const SOURCE_TAG = 'relopass-test-drive'; // internal tracking tag — never rendered
const SESSION_STORAGE_KEY = `space_session_${SPACE_ID}`;

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

function track(event: string, data?: Record<string, unknown>) {
  try {
    const fn = (window as any).trackFunnelEvent;
    if (typeof fn === 'function') fn(event, { source: SOURCE_TAG, ...data });
  } catch { /* analytics must never break the page */ }
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
          metadata: {
            source: SOURCE_TAG, // internal tracking field — never rendered
            ...(trimmedCompany ? { company: trimmedCompany } : {}),
            ...(trimmedRole ? { role: trimmedRole } : {}),
          },
        }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data?.success || !data?.workspaceSessionId) {
        throw new Error(data?.error || 'Something went wrong. Please try again.');
      }
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

  const inputClass =
    'w-full px-4 py-3 rounded-xl border border-[var(--space-border-default)] bg-[var(--space-surface-card)] text-sm text-[var(--space-text-primary)] placeholder:text-[var(--space-text-muted)] outline-none focus:ring-2 focus:ring-[var(--space-brand-primary)] focus:border-transparent transition-all';

  return (
    <div className="min-h-full w-full flex flex-col bg-[linear-gradient(150deg,var(--space-surface-gradient-from),var(--space-surface-gradient-via),var(--space-surface-gradient-to))] text-[var(--space-text-primary)]">
      <main className="flex-1 flex items-center justify-center px-5 sm:px-8 py-12 sm:py-16">
        <div className="w-full max-w-md">
          {/* Brand header */}
          <div className="text-center mb-8">
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
              We'll only email you your verification code. We never sell your data.
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
