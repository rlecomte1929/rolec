/**
 * CaseGate — Tier 0 → Tier 1 paywall for Case Command corridor checks,
 * wired to the relopass-* server hooks:
 *   - creates the case row via relopass-create-case (when none is known yet)
 *   - reads access state via relopass-access (through useCaseAccess)
 *   - starts Stripe Checkout via relopass-checkout ({ caseId, tier })
 *
 * accessTier 'free'              → teaser gate: 2–3 real non-obvious
 *   requirements shown verbatim, the rest blurred, €800 unlock CTA
 * accessTier 'roadmap' or higher → children render normally
 *
 * Payment truth lives SERVER-SIDE only: pricing is fixed inside the
 * relopass-checkout hook and the unlock is written by server-side Stripe
 * verification (relopass-webhook + lazy verification in relopass-access).
 * This component never flips access state itself — after the Stripe redirect
 * it simply re-reads the server state until it says paid.
 */

import { useState, useEffect, useRef, type ReactNode } from 'react';
import {
  Lock, Sparkles, ShieldCheck, Receipt, ArrowRight, Loader2,
  CheckCircle2, AlertTriangle,
} from 'lucide-react';
import { PRICE_ROADMAP_CENTS, PRICE_ESSENTIALS_CENTS, formatEur, tierAtLeast } from '../../lib/pricing';
import { createCase, startCheckout, useCaseAccess } from './hooks/useCaseAccess';

export interface PreviewRequirement {
  id: string;
  title: string;
  description: string;
  offsetLabel: string;
  actionByDate: string;
  owner: string;
}

interface CaseGateProps {
  /** Corridor key for the case row, e.g. 'france-norway'. */
  corridor: string;
  /** The submitted check inputs — used to create the case row server-side. */
  employeeType: string;
  moveDate: string;
  /** Session scope stored on the case row (optional). */
  sessionId?: string | null;
  /** Known caseId (from localStorage or the post-payment ?caseId= param). */
  initialCaseId?: number | null;
  /** True when the page landed from a Stripe success redirect. */
  paymentSuccess?: boolean;
  /** Total requirement count for the teaser headline. */
  totalRequirements: number;
  /** Count of non-obvious ("didn't know to look for") requirements. */
  nonObviousCount: number;
  /** 2–3 real non-obvious requirements shown verbatim in the teaser. */
  previewRequirements: PreviewRequirement[];
  /** Called when the server-side case row is known/created. */
  onCaseId?: (caseId: number) => void;
  /** The full roadmap. Blurred while locked, rendered normally when unlocked. */
  children: ReactNode;
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

export default function CaseGate({
  corridor,
  employeeType,
  moveDate,
  sessionId = null,
  initialCaseId = null,
  paymentSuccess = false,
  totalRequirements,
  nonObviousCount,
  previewRequirements,
  onCaseId,
  children,
}: CaseGateProps) {
  const [caseId, setCaseId] = useState<number | null>(initialCaseId);
  const [createError, setCreateError] = useState(false);
  const [checkoutBusy, setCheckoutBusy] = useState(false);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const creatingRef = useRef<string | null>(null);
  const pollCountRef = useRef(0);
  const onCaseIdRef = useRef(onCaseId);
  onCaseIdRef.current = onCaseId;

  const { access, loading, error: accessError, refetch } = useCaseAccess(caseId);
  const unlocked = tierAtLeast(access?.accessTier, 'roadmap');

  // Keep in sync when the parent learns the caseId (e.g. post-payment URL).
  useEffect(() => {
    if (initialCaseId && initialCaseId !== caseId) setCaseId(initialCaseId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialCaseId]);

  // No case row known for these inputs yet → create one server-side.
  useEffect(() => {
    if (caseId || !employeeType || !moveDate) return;
    const signature = `${corridor}|${employeeType}|${moveDate}`;
    if (creatingRef.current === signature) return;
    creatingRef.current = signature;
    setCreateError(false);
    createCase({ corridor, employeeType, moveDate, sessionId }).then((id) => {
      if (creatingRef.current !== signature) return;
      if (id) {
        setCaseId(id);
        onCaseIdRef.current?.(id);
      } else {
        setCreateError(true);
        creatingRef.current = null;
      }
    });
  }, [caseId, corridor, employeeType, moveDate, sessionId]);

  // After a Stripe success redirect the server-side confirmation can lag a
  // few seconds — poll the access state (max ~30s) until it reports paid.
  useEffect(() => {
    if (!paymentSuccess || unlocked || loading || !caseId) return;
    if (pollCountRef.current >= 12) return;
    const timer = setTimeout(() => {
      pollCountRef.current += 1;
      refetch();
    }, 2500);
    return () => clearTimeout(timer);
  }, [paymentSuccess, unlocked, loading, caseId, access, refetch]);

  const handleCheckout = async () => {
    if (!caseId || checkoutBusy) return;
    setCheckoutBusy(true);
    setCheckoutError(null);
    try {
      const base = window.location.origin + window.location.pathname;
      const result = await startCheckout(
        caseId,
        'roadmap',
        `${base}?app=case-command&payment=success&caseId=${caseId}`,
        `${base}?app=case-command`,
      );
      if (result?.checkoutUrl) {
        redirectToCheckout(result.checkoutUrl);
        return;
      }
      setCheckoutError('Could not start checkout. Please try again.');
    } catch {
      setCheckoutError('Could not start checkout. Please try again.');
    } finally {
      setCheckoutBusy(false);
    }
  };

  if (loading || (!caseId && !createError)) {
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

  // ── Locked: teaser gate ────────────────────────────────────────────────
  const waitingOnPayment = paymentSuccess && !unlocked && Boolean(access);

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

      <div className="mb-4 p-4 rounded-xl border border-[var(--space-border-default)] bg-[var(--space-surface-card)]">
        <h4 className="text-sm font-semibold text-[var(--space-text-primary)] mb-1">
          Why not just ask ChatGPT?
        </h4>
        <p className="text-xs text-[var(--space-text-secondary)] leading-relaxed">
          Chat tools generate plausible checklists. ReloPass looks up requirements a lawyer
          has confirmed against primary sources. The D-number window is a lookup, not a guess.
        </p>
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

      {/* Unlock CTA — email, company and VAT are collected on the Stripe page */}
      <div className="p-5 rounded-2xl border border-[var(--space-border-strong)] bg-[var(--space-surface-panel)]">
        <div className="text-center">
          <button
            type="button"
            onClick={handleCheckout}
            disabled={checkoutBusy || !caseId}
            className="inline-flex items-center gap-2 px-5 py-3 rounded-xl bg-[var(--space-brand-primary)] text-[var(--space-text-on-primary)] text-sm font-bold shadow-md hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {checkoutBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            {checkoutBusy
              ? 'Opening secure checkout…'
              : `Unlock your full roadmap + vendor shortlist — ${formatEur(PRICE_ROADMAP_CENTS)}`}
            {!checkoutBusy && <ArrowRight className="w-4 h-4" />}
          </button>
          <p className="text-[11px] text-[var(--space-text-muted)] mt-2.5 flex items-center justify-center gap-1.5">
            <Receipt className="w-3.5 h-3.5" /> Receipt issued — expensable as a professional service
          </p>
          {checkoutError && (
            <p className="text-xs text-red-400 mt-2.5 flex items-center justify-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" /> {checkoutError}
            </p>
          )}
        </div>

        {(createError || (accessError && !access)) && (
          <p className="text-xs text-red-400 mt-3 text-center">
            Couldn't reach the case service —{' '}
            <button
              type="button"
              onClick={() => { creatingRef.current = null; setCreateError(false); if (caseId) refetch(); }}
              className="underline"
            >
              retry
            </button>
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
