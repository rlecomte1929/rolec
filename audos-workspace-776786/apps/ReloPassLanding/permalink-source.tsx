/**
 * SOURCE OF RECORD for the standalone public permalink page
 * "test-drive-access" (permalink page id: dbbfb360-8b41-442e-be23-9736f51aa475).
 *
 * The live copy is stored platform-side via the permalink-pages integration.
 * To update the page, PATCH this source to:
 *   PATCH /api/workspaces/776786/permalink-pages/dbbfb360-8b41-442e-be23-9736f51aa475
 *   body: { "tsxSource": "<this file>" }
 * To make it PUBLIC after founder approval:
 *   body: { "isPublic": true, "accessToken": null }
 * Canonical public URL (once public):
 *   https://audos.com/p/d0c29613-9cb5-4652-9c6a-494eeed352e5/test-drive-access
 *
 * NOTE: this file is NOT registered in config.json and is NOT compiled into
 * the space bundle — it exists so agents can find and edit the permalink
 * page source. The in-space app remains apps/ReloPassLanding/App.tsx.
 */

/**
 * ReloPass Registration Gate — standalone public permalink page.
 * Same flow as apps/ReloPassLanding/App.tsx, restyled with concrete brand
 * colors (permalink pages don't receive the space's --space-* CSS variables).
 *
 * Flow: land → enter email → OTP code → verify → "Continue to your test drive →".
 *   1. POST /api/space/workspace-776786/register  → workspaceSessionId
 *   2. POST /api/auth/otp/space/send              (transactional OTP email only)
 *   3. POST /api/auth/otp/space/verify
 * After verify: plain link to https://relopass.com/test-drive — no params.
 */

import { useState, useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import {
  CheckCircle2, ArrowRight, Loader2, Lock, AlertCircle, ShieldCheck,
} from 'lucide-react';

const WORKSPACE_ID = 'd0c29613-9cb5-4652-9c6a-494eeed352e5';
const SPACE_ID = 'workspace-776786';
const SOURCE_TAG = 'fr-no-landing'; // hidden tracking tag — never rendered
const SESSION_STORAGE_KEY = `space_session_${SPACE_ID}`;
const DEPOSIT_SESSION_KEY = 'relopass_frno_deposit_session_v1';
const DEPOSIT_AMOUNT_CENTS = 15000; // €150.00

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

// Brand palette (mirrors workspace-branding.json / config.json themeTokens)
const C = {
  pageFrom: '#0b1620', pageVia: '#10212e', pageTo: '#0a2733',
  card: '#142430', panel: '#172935',
  border: '#24384a', borderStrong: '#33506a',
  textPrimary: '#eaf2f8', textSecondary: '#a7c2d3', textMuted: '#7f9bad',
  accent: '#38c6de', primary: '#2a93e0', onPrimary: '#111827',
};

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

function App() {
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
        } else if (d?.status === 'expired') {
          localStorage.removeItem(DEPOSIT_SESSION_KEY);
        }
      })
      .catch(() => { /* re-check next visit */ });
    return () => { cancelled = true; };
  }, []);

  // Step 1 — register via the platform endpoint (the platform owns the DB
  // write; no server-hook intermediary), then send the OTP code.
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
            source: SOURCE_TAG,
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
        try {
          localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({
            id: workspaceSessionId,
            workspaceSessionId,
            email: email.trim().toLowerCase(),
            verified: true,
            timestamp: Date.now(),
          }));
        } catch { /* storage failures must not block verification */ }
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
      window.location.href = data.checkoutUrl;
    } catch (err: any) {
      setDepositError(err?.message || 'Could not start checkout. Please try again.');
      setDepositLoading(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    backgroundColor: C.card,
    borderColor: C.border,
    color: C.textPrimary,
  };
  const inputClass =
    'w-full px-4 py-3 rounded-xl border text-sm outline-none focus:ring-2 transition-all placeholder-gray-500';

  return (
    <div
      className="min-h-screen w-full flex flex-col"
      style={{
        background: `linear-gradient(150deg, ${C.pageFrom}, ${C.pageVia}, ${C.pageTo})`,
        color: C.textPrimary,
        fontFamily: '"Inter", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      }}
    >
      {depositConfirmed && (
        <div className="sticky top-0 z-20 px-4 py-3 bg-green-600 text-white text-sm font-medium flex items-center justify-center gap-2 shadow-lg">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          Deposit received — we'll be in touch within 24 hours.
        </div>
      )}

      <main className="flex-1 flex items-center justify-center px-5 sm:px-8 py-12 sm:py-16">
        <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <div
              className="inline-flex items-center gap-2 px-3 py-1 rounded-full border mb-5"
              style={{ borderColor: C.borderStrong, backgroundColor: C.panel }}
            >
              <ShieldCheck className="w-3.5 h-3.5" style={{ color: C.accent }} />
              <span className="text-xs font-semibold tracking-wide" style={{ color: C.textSecondary }}>ReloPass</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold text-white leading-tight mb-2">
              Register to access your ReloPass test drive
            </h1>
            <p className="text-sm" style={{ color: C.textSecondary }}>
              Enter your work email and we'll send you a 4-digit verification code.
            </p>
          </div>

          <div
            className="rounded-2xl border p-6 sm:p-7"
            style={{ borderColor: C.border, backgroundColor: C.panel, boxShadow: '0 10px 30px #041a26' }}
          >
            {gateStep === 'verified' ? (
              <div className="px-2 py-4 text-center">
                <CheckCircle2 className="w-10 h-10 text-green-400 mx-auto mb-3" />
                <p className="text-sm font-semibold text-green-300 mb-5">✓ You're verified.</p>
                <a
                  href="https://relopass.com/test-drive"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl text-sm font-semibold hover:brightness-110 transition-all"
                  style={{ backgroundColor: C.primary, color: C.onPrimary }}
                >
                  Continue to your test drive <ArrowRight className="w-4 h-4" />
                </a>
              </div>
            ) : gateStep === 'code' ? (
              <form onSubmit={handleVerifyOtp} className="space-y-4" noValidate>
                <div
                  className="px-4 py-3 rounded-xl border"
                  style={{ borderColor: C.borderStrong, backgroundColor: C.card }}
                >
                  <p className="text-xs" style={{ color: C.textSecondary }}>
                    We've emailed you a 4-digit code — check your inbox.
                  </p>
                  <p className="text-[11px] mt-1" style={{ color: C.textMuted }}>
                    Sent to {email.trim().toLowerCase()}
                  </p>
                </div>
                <div>
                  <label htmlFor="relopass-otp" className="block text-xs font-semibold mb-1.5" style={{ color: C.textSecondary }}>
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
                    className="w-full px-4 py-3 rounded-xl border text-base tracking-[0.5em] text-center outline-none focus:ring-2 transition-all placeholder-gray-500"
                    style={inputStyle}
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
                  className="w-full inline-flex items-center justify-center gap-2 px-5 py-3.5 rounded-xl text-sm font-semibold hover:brightness-110 transition-all disabled:opacity-60"
                  style={{ backgroundColor: C.primary, color: C.onPrimary }}
                >
                  {verifying ? 'Verifying…' : (<>Verify <ArrowRight className="w-4 h-4" /></>)}
                </button>
                <button
                  type="button"
                  onClick={() => { setGateStep('email'); setOtpCode(''); setOtpError(''); }}
                  className="w-full text-[11px] transition-colors hover:opacity-80"
                  style={{ color: C.textMuted }}
                >
                  Use a different email
                </button>
              </form>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4" noValidate>
                <div>
                  <label htmlFor="relopass-email" className="block text-xs font-semibold mb-1.5" style={{ color: C.textSecondary }}>
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
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label htmlFor="relopass-company" className="block text-xs font-semibold mb-1.5" style={{ color: C.textSecondary }}>
                    Company name <span className="font-normal" style={{ color: C.textMuted }}>(optional)</span>
                  </label>
                  <input
                    id="relopass-company"
                    type="text"
                    value={company}
                    onChange={(e) => setCompany(e.target.value)}
                    placeholder="Your company"
                    className={inputClass}
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label htmlFor="relopass-role" className="block text-xs font-semibold mb-1.5" style={{ color: C.textSecondary }}>
                    Your role <span className="font-normal" style={{ color: C.textMuted }}>(optional)</span>
                  </label>
                  <input
                    id="relopass-role"
                    type="text"
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    placeholder="e.g. HR Manager, Office Manager"
                    className={inputClass}
                    style={inputStyle}
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
                  className="w-full inline-flex items-center justify-center gap-2 px-5 py-3.5 rounded-xl text-sm font-semibold hover:brightness-110 transition-all disabled:opacity-60"
                  style={{ backgroundColor: C.primary, color: C.onPrimary }}
                >
                  {submitting ? (
                    <><Loader2 className="w-4 h-4 animate-spin" /> Sending…</>
                  ) : (
                    <>Send my verification code <ArrowRight className="w-4 h-4" /></>
                  )}
                </button>
              </form>
            )}

            <p className="text-[11px] text-center mt-4 leading-relaxed" style={{ color: C.textMuted }}>
              By submitting, you agree to be contacted about ReloPass services. We never sell your data.
            </p>
          </div>

          {/* Deposit block — Stripe button intentionally unchanged */}
          <div className="mt-6 rounded-2xl border p-5" style={{ borderColor: C.border, backgroundColor: C.card }}>
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
              className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-xl border-2 text-sm font-semibold transition-all disabled:opacity-60 hover:brightness-110"
              style={{ borderColor: C.borderStrong, color: C.textPrimary }}
            >
              {depositLoading ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Opening secure checkout…</>
              ) : (
                <><Lock className="w-3.5 h-3.5" /> Reserve your spot — €150 refundable deposit</>
              )}
            </button>
            <p className="text-[11px] text-center mt-2.5" style={{ color: C.textMuted }}>
              Fully refundable design-partner deposit — applied to your package price if you proceed.
            </p>
          </div>
        </div>
      </main>

      <footer className="px-5 sm:px-8 py-6 border-t text-center" style={{ borderColor: C.border }}>
        <p className="text-[11px]" style={{ color: C.textMuted }}>© ReloPass</p>
      </footer>
    </div>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
