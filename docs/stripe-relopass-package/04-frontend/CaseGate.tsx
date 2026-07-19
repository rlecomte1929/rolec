// CaseGate.tsx
// ReloPass — Stripe Integration v1.0
//
// Tier 0 → Tier 1 paywall for Case Command. Renders the full roadmap
// (children) when the case is unlocked; otherwise renders the free teaser
// with an €800 unlock CTA. Payment truth lives SERVER-SIDE only — this
// component never flips access state itself.

import { useState, type ReactNode } from 'react';
import { useCaseAccess } from './hooks/useCaseAccess';

export interface PreviewRequirement {
  id: string;
  title: string;
  description: string;
}

export interface CaseGateProps {
  caseId: string;
  /** Total requirement count for the teaser headline. */
  totalRequirements: number;
  /** Count of non-obvious ("didn't know to look for") requirements. */
  nonObviousCount: number;
  /** Feasibility badge computed by the rule engine. */
  feasibility: 'clear' | 'amber' | 'red';
  /** 2–3 real non-obvious requirements shown verbatim in the teaser. */
  previewRequirements: PreviewRequirement[];
  /** The full roadmap — rendered only when unlocked. */
  children: ReactNode;
}

const FEASIBILITY_LABEL: Record<CaseGateProps['feasibility'], string> = {
  clear: 'Feasible on your timeline',
  amber: 'Tight — some deadlines at risk',
  red: 'At risk — act now',
};

/** Redirect that also works when the app is embedded in an iframe. */
function redirectToCheckout(url: string) {
  try {
    if (window.top && window.top !== window) {
      window.top.location.href = url;
      return;
    }
  } catch {
    /* cross-origin iframe — fall through */
  }
  window.location.href = url;
}

export default function CaseGate({
  caseId,
  totalRequirements,
  nonObviousCount,
  feasibility,
  previewRequirements,
  children,
}: CaseGateProps) {
  const { access, loading, error, refetch, hasFullAccess } = useCaseAccess(caseId);
  const [checkoutBusy, setCheckoutBusy] = useState(false);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);

  const startCheckout = async () => {
    if (checkoutBusy) return;
    setCheckoutBusy(true);
    setCheckoutError(null);
    try {
      const res = await fetch(`/api/relopass/cases/${encodeURIComponent(caseId)}/checkout`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tier: 'roadmap' }),
      });
      const data = await res.json();
      if (res.ok && data?.checkoutUrl) {
        redirectToCheckout(data.checkoutUrl);
        return;
      }
      setCheckoutError(data?.error ?? 'Could not start checkout. Please try again.');
    } catch {
      setCheckoutError('Could not start checkout. Please try again.');
    } finally {
      setCheckoutBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="case-gate case-gate--loading" role="status">
        Checking case access…
      </div>
    );
  }

  // Unlocked (per case, or via a starter/growth retainer account).
  if (hasFullAccess) return <>{children}</>;

  const lockedCount = Math.max(totalRequirements - previewRequirements.length, 0);

  return (
    <div className="case-gate" data-testid="case-gate">
      {/* Teaser headline */}
      <div className="case-gate__teaser">
        <h3>
          Your move has {totalRequirements} requirements — including {nonObviousCount} you may
          not have known to look for
        </h3>
        <span className={`case-gate__feasibility case-gate__feasibility--${feasibility}`}>
          {FEASIBILITY_LABEL[feasibility]}
        </span>
      </div>

      {/* Real non-obvious requirements, verbatim */}
      <ul className="case-gate__previews">
        {previewRequirements.map((req) => (
          <li key={req.id} className="case-gate__preview">
            <strong>{req.title}</strong>
            <p>{req.description}</p>
          </li>
        ))}
        <li className="case-gate__locked-row" aria-hidden="true">
          + {lockedCount} more requirements locked
        </li>
      </ul>

      {/* Primary CTA — Tier 1 */}
      <button
        type="button"
        className="case-gate__cta"
        onClick={startCheckout}
        disabled={checkoutBusy}
      >
        {checkoutBusy ? 'Opening secure checkout…' : 'Unlock full roadmap + vendor list — €800'}
      </button>
      <p className="case-gate__receipt-note">
        Receipt with company name + VAT number issued automatically — expensable as a
        professional service.
      </p>

      {/* Secondary CTA — Tier 2 stub, always disabled until lawyer sign-off */}
      <button type="button" className="case-gate__cta case-gate__cta--disabled" disabled>
        Essentials (immigration assurance) — €2,000 · coming soon
      </button>

      {checkoutError && <p className="case-gate__error">{checkoutError}</p>}
      {error && !access && (
        <p className="case-gate__error">
          Couldn't check access —{' '}
          <button type="button" onClick={() => refetch()}>
            retry
          </button>
        </p>
      )}
    </div>
  );
}
