// SNAPSHOT (2026-07-18) of components/CaseGate.tsx — the live workspace file is authoritative.
// Import paths reflect the file's real location under components/.

/**
 * CaseGate — Tier 0 → Tier 1 paywall for Case Command corridor checks.
 *
 * Wraps the full requirement roadmap for one submitted case. On mount it asks
 * the `case-access` server function for the case's access state:
 *   - accessTier 'free'              → teaser gate: 2–3 real non-obvious
 *     requirements shown verbatim, the rest blurred, €800 unlock CTA
 *   - accessTier 'roadmap' or higher → children render normally
 *
 * Payment truth lives SERVER-SIDE only: the CTA creates a Stripe Checkout
 * session via the `case-checkout` server function, and the unlock is written
 * by server-side Stripe verification (case-access / stripe-case-webhook
 * hooks). This component never flips access state itself — after the Stripe
 * redirect it simply re-reads the server state until it says paid.
 */

import { useState, useEffect, useCallback, useRef, type ReactNode } from 'react';
import {
  Lock, Sparkles, ShieldCheck, Receipt, ArrowRight, Loader2,
  CheckCircle2, AlertTriangle, Building2, Mail, Hash,
} from 'lucide-react';
import { PRICE_ROADMAP_CENTS, PRICE_ESSENTIALS_CENTS, formatEur, tierAtLeast } from '../lib/pricing';

const SPACE_ID: string =
  (typeof window !== 'undefined' && ((window as any).__APP_ID__ || (window as any).__SPACE_ID__)) ||
  'workspace-776786';

const HOOK_BASE = `/api/workspaces/${SPACE_ID}/hooks`;

export interface CaseAccessState {
  caseId: number;
  accessTier: string;
  paymentStatus: string;
  unlockedAt: string | null;
  employeeType?: string | null;
  moveDate?: string | null;
}

export interface PreviewRequirement {
  id: string;
  title: string;
  description: string;
  offsetLabel: string;
  actionByDate: string;
  owner: string;
}

interface CaseGateProps {
  /** Deterministic case identity, e.g. 'frno|<sessionId>|<employeeType>|<moveDate>'. */
  caseKey: string;
  /** Row payload used when the caseKey has no case_access row yet. */
  createPayload: { employeeType: string; moveDate: string; sessionId?: string | null };
  /** Known case_access.id (e.g. from the post-payment ?caseId= param). */
  initialCaseId?: number | null;
  /** True when the page landed from a Stripe success redirect. */
  paymentSuccess?: boolean;
  /** Total requirement count for the teaser headline. */
  totalRequirements: number;
  /** Count of non-obvious ("didn't know to look for") requirements. */
  nonObviousCount: number;
  /** 2–3 real non-obvious requirements shown verbatim in the teaser. */
  previewRequirements: PreviewRequirement[];
  /** Called whenever the server reports an access state (incl. caseId). */
  onAccess?: (access: CaseAccessState) => void;
  /** The full roadmap. Blurred while locked, rendered normally when unlocked. */
  children: ReactNode;
}

function getSessionEmail(): string {
  try {
    const stored = localStorage.getItem(`space_session_${SPACE_ID}`);
    if (stored) {
      const session = JSON.parse(stored);
      if (session && typeof session.email === 'string') return session.email;
    }
  } catch { /* ignore */ }
  return '';
}

function redirectToCheckout(url: string) {
  try {
    if (window.top && window.top !== window) {
      window.top.location.href = url;
      return;
    }
  } catch { /* cross-origin iframe */ }
  window.location.href = url;
}

async function fetchAccess(body: Record<string, unknown>): Promise<CaseAccessState | null> {
  const res = await fetch(`${HOOK_BASE}/case-access/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) return null;
  const data = await res.json();
  if (typeof data?.caseId !== 'number') return null;
  return data as CaseAccessState;
}

export default function CaseGate({
  caseKey,
  createPayload,
  initialCaseId = null,
  paymentSuccess = false,
  totalRequirements,
  nonObviousCount,
  previewRequirements,
  onAccess,
  children,
}: CaseGateProps) {
  const [access, setAccess] = useState<CaseAccessState | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [email, setEmail] = useState(getSessionEmail);
  const [company, setCompany] = useState('');
  const [vat, setVat] = useState('');
  const [checkoutBusy, setCheckoutBusy] = useState(false);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const pollCountRef = useRef(0);
  const onAccessRef = useRef(onAccess);
  onAccessRef.current = onAccess;

  const unlocked = tierAtLeast(access?.accessTier, 'roadmap');

  const loadAccess = useCallback(async () => {
    try {
      const state = await fetchAccess({
        caseId: initialCaseId || undefined,
        caseKey,
        create: createPayload,
      });
      if (state) {
        setAccess(state);
        setLoadError(false);
        onAccessRef.current?.(state);
        return state;
      }
      setLoadError(true);
      return null;
    } catch {
      setLoadError(true);
      return null;
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseKey, initialCaseId, createPayload.employeeType, createPayload.moveDate]);

  useEffect(() => {
    setLoading(true);
    setAccess(null);
    pollCountRef.current = 0;
    loadAccess();
  }, [loadAccess]);

  // After a Stripe success redirect the server-side confirmation can lag a
  // few seconds — poll the access state (max ~30s) until it reports paid.
  useEffect(() => {
    if (!paymentSuccess || unlocked || loading) return;
    if (pollCountRef.current >= 12) return;
    const timer = setTimeout(() => {
      pollCountRef.current += 1;
      loadAccess();
    }, 2500);
    return () => clearTimeout(timer);
  }, [paymentSuccess, unlocked, loading, access, loadAccess]);

  const startCheckout = async () => {
    if (!access || checkoutBusy) return;
    const trimmedEmail = email.trim();
    if (!trimmedEmail || !trimmedEmail.includes('@')) {
      setCheckoutError('Enter the email address the receipt should go to.');
      return;
    }
    setCheckoutBusy(true);
    setCheckoutError(null);
    try {
      const base = window.location.origin + window.location.pathname;
      const res = await fetch(`${HOOK_BASE}/case-checkout/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          caseId: access.caseId,
          customerEmail: trimmedEmail,
          company: company.trim(),
          vat: vat.trim(),
          successUrl: `${base}?app=case-command&payment=success&caseId=${access.caseId}`,
          cancelUrl: `${base}?app=case-command`,
        }),
      });
      const data = await res.json();
      if (res.ok && data?.url) {
        redirectToCheckout(data.url);
        return;
      }
      setCheckoutError('Could not start checkout. Please try again.');
    } catch {
      setCheckoutError('Could not start checkout. Please try again.');
    } finally {
      setCheckoutBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Loader2 className="w-6 h-6 animate-spin text-[var(--space-brand-primary)] mb-3" />
        <p className="text-sm text-[var(--space-text-secondary)]">Checking case access…</p>
      </div>
    );
  }

  if (unlocked) {
    return (
      <div>
        {paymentSuccess && (
          <div className="mb-4 px-4 py-3 rounded-xl border border-green-500/30 bg-green-500/10 flex items-start gap-2.5">
            <CheckCircle2 className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-green-300">Roadmap unlocked — your full requirements are below</p>
              <p className="text-xs text-[var(--space-text-secondary)] mt-0.5">
                A confirmation email with your expensable receipt is on its way. This case stays unlocked — reload anytime.
              </p>
            </div>
          </div>
        )}
        {children}
      </div>
    );
  }

  // ── Locked: teaser gate ──────────────────────────────────────────────────
  const waitingOnPayment = paymentSuccess && access?.paymentStatus === 'pending';

  return (
    <div>
      {waitingOnPayment && (
        <div className="mb-4 px-4 py-3 rounded-xl border border-amber-500/30 bg-amber-500/10 flex items-center gap-2.5">
          <Loader2 className="w-4 h-4 animate-spin text-amber-400 flex-shrink-0" />
          <p className="text-xs text-amber-200">Confirming your payment with Stripe — this usually takes a few seconds…</p>
        </div>
      )}

      {/* Teaser headline */}
      <div className="px-5 py-5 rounded-2xl border border-[var(--space-border-strong)] bg-gradient-to-br from-[var(--space-brand-primary-50)] via-[var(--space-surface-card)] to-[var(--space-brand-highlight-50)] mb-4">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-[var(--space-brand-primary)] flex items-center justify-center flex-shrink-0 shadow-md">
            <Sparkles className="w-5 h-5 text-[var(--space-text-on-primary)]" />
          </div>
          <div>
            <h3 className="text-base sm:text-lg font-bold text-[var(--space-text-primary)] leading-snug">
              Your move has {totalRequirements} requirements — including {nonObviousCount} you may not have known to look for
            </h3>
            <p className="text-xs text-[var(--space-text-secondary)] mt-1">
              Here are {previewRequirements.length} of them. The full time-anchored sequence — every deadline, owner and feasibility flag — is one unlock away.
            </p>
          </div>
        </div>
      </div>

      {/* Preview: real non-obvious requirements, verbatim */}
      <div className="space-y-2.5 mb-4">
        {previewRequirements.map((req) => (
          <div key={req.id} className="p-3.5 rounded-xl border border-amber-500/30 bg-amber-500/10">
            <div className="flex items-start justify-between gap-2 mb-1">
              <h4 className="text-sm font-semibold text-[var(--space-text-primary)] leading-snug">{req.title}</h4>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/20 text-amber-200 flex-shrink-0">
                Easy to miss
              </span>
            </div>
            <p className="text-xs text-[var(--space-text-secondary)] leading-relaxed mb-1.5">{req.description}</p>
            <p className="text-[10px] text-[var(--space-text-muted)]">
              {req.offsetLabel} · act by {req.actionByDate} · owner: {req.owner}
            </p>
          </div>
        ))}
      </div>

      {/* Blurred remainder of the roadmap */}
      <div className="relative rounded-2xl overflow-hidden border border-[var(--space-border-default)] mb-4" aria-hidden="true">
        <div className="max-h-72 overflow-hidden blur-[6px] select-none pointer-events-none opacity-70">
          {children}
        </div>
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-[var(--space-surface-page)]" />
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="flex items-center gap-2 px-3.5 py-2 rounded-full bg-[var(--space-surface-panel-strong)] border border-[var(--space-border-strong)] text-xs font-semibold text-[var(--space-text-primary)] shadow-lg">
            <Lock className="w-3.5 h-3.5 text-[var(--space-text-accent)]" />
            {Math.max(totalRequirements - previewRequirements.length, 0)} more requirements locked
          </span>
        </div>
      </div>

      {/* Unlock CTA */}
      <div className="p-5 rounded-2xl border border-[var(--space-border-strong)] bg-[var(--space-surface-panel)]">
        {!showForm ? (
          <div className="text-center">
            <button
              type="button"
              onClick={() => { setShowForm(true); setCheckoutError(null); }}
              className="inline-flex items-center gap-2 px-5 py-3 rounded-xl bg-[var(--space-brand-primary)] text-[var(--space-text-on-primary)] text-sm font-bold shadow-md hover:opacity-90 transition-opacity"
            >
              Unlock your full roadmap + vendor shortlist — {formatEur(PRICE_ROADMAP_CENTS)}
              <ArrowRight className="w-4 h-4" />
            </button>
            <p className="text-[11px] text-[var(--space-text-muted)] mt-2.5 flex items-center justify-center gap-1.5">
              <Receipt className="w-3.5 h-3.5" /> Receipt issued — expensable as a professional service
            </p>
          </div>
        ) : (
          <div className="max-w-md mx-auto">
            <p className="text-sm font-semibold text-[var(--space-text-primary)] mb-1">
              Unlock this case — {formatEur(PRICE_ROADMAP_CENTS)} one-time
            </p>
            <p className="text-xs text-[var(--space-text-secondary)] mb-3.5">
              Company name and VAT number go on your receipt so it's expensable as a professional service.
            </p>
            <div className="space-y-2.5">
              <label className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--space-surface-muted)] border border-[var(--space-border-default)]">
                <Mail className="w-3.5 h-3.5 text-[var(--space-text-muted)] flex-shrink-0" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Work email (for receipt + confirmation)"
                  className="flex-1 text-sm bg-transparent border-none outline-none text-[var(--space-text-primary)] placeholder:text-[var(--space-text-muted)]"
                />
              </label>
              <label className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--space-surface-muted)] border border-[var(--space-border-default)]">
                <Building2 className="w-3.5 h-3.5 text-[var(--space-text-muted)] flex-shrink-0" />
                <input
                  type="text"
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  placeholder="Company name (for the receipt)"
                  className="flex-1 text-sm bg-transparent border-none outline-none text-[var(--space-text-primary)] placeholder:text-[var(--space-text-muted)]"
                />
              </label>
              <label className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--space-surface-muted)] border border-[var(--space-border-default)]">
                <Hash className="w-3.5 h-3.5 text-[var(--space-text-muted)] flex-shrink-0" />
                <input
                  type="text"
                  value={vat}
                  onChange={(e) => setVat(e.target.value)}
                  placeholder="VAT number (optional)"
                  className="flex-1 text-sm bg-transparent border-none outline-none text-[var(--space-text-primary)] placeholder:text-[var(--space-text-muted)]"
                />
              </label>
            </div>
            {checkoutError && (
              <p className="text-xs text-red-400 mt-2.5 flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" /> {checkoutError}
              </p>
            )}
            <button
              type="button"
              onClick={startCheckout}
              disabled={checkoutBusy || !email.trim()}
              className="w-full mt-3.5 inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-[var(--space-brand-primary)] text-[var(--space-text-on-primary)] text-sm font-bold shadow-md hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {checkoutBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Lock className="w-4 h-4" />}
              {checkoutBusy ? 'Opening secure checkout…' : `Continue to secure checkout — ${formatEur(PRICE_ROADMAP_CENTS)}`}
            </button>
            <p className="text-[11px] text-[var(--space-text-muted)] mt-2 text-center flex items-center justify-center gap-1.5">
              <Receipt className="w-3.5 h-3.5" /> Receipt issued — expensable as a professional service
            </p>
          </div>
        )}

        {loadError && !access && (
          <p className="text-xs text-red-400 mt-3 text-center">
            Couldn't reach the access service — <button type="button" onClick={loadAccess} className="underline">retry</button>
          </p>
        )}

        {/* Tier 2 scaffold — greyed out, not clickable */}
        <div className="mt-4 pt-4 border-t border-[var(--space-border-default)]">
          <div className="flex items-center justify-between gap-3 opacity-50 cursor-not-allowed select-none" aria-disabled="true">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-8 h-8 rounded-lg bg-[var(--space-surface-muted)] flex items-center justify-center flex-shrink-0">
                <ShieldCheck className="w-4 h-4 text-[var(--space-text-muted)]" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-[var(--space-text-secondary)]">Immigration assurance — coming soon</p>
                <p className="text-[11px] text-[var(--space-text-muted)] truncate">
                  Lawyer-assured corridor guidance · {formatEur(PRICE_ESSENTIALS_CENTS)}
                </p>
              </div>
            </div>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-[var(--space-surface-muted)] text-[var(--space-text-muted)] flex-shrink-0">
              Coming soon
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
