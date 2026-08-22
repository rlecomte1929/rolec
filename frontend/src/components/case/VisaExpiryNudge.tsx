/**
 * VisaExpiryNudge — [AIQ-1860] ambient "next best action" card for a nearing
 * visa/permit expiry, shown above the shared relocation plan on the HR case page.
 *
 * Ambient, not modal: it renders inline, is dismissible, and returns null when
 * there is nothing to say. A failed fetch shows nothing rather than blocking the
 * page — the same non-critical contract RuleUpdateBanner uses.
 *
 * NOT AN AI DECISION, deliberately. The number shown is arithmetic on a stored
 * date (compliance_evaluator's `date_threshold` rule computes `detail.days_until`
 * against a seeded 60-day window). No model is consulted, so this is advisory UI
 * chrome and needs no `ai_decisions` log — the alternative the task raised, and
 * the cheaper, more honest reading of it.
 *
 * WHAT THE CONFIDENCE BADGE MEANS. It is the provenance of the expiry DATE, not a
 * model score — there is no model here and inventing a percentage would be a
 * fabricated number. HIGH = an HR-maintained immigration record; MEDIUM = a
 * self-declared or OCR-extracted profile field; UNKNOWN = we cannot tell which
 * field fired. Low-trust levels are visually muted, per the task's UX constraint.
 *
 * Data source: GET /api/compliance/alerts (HR-scoped, company-wide) filtered to
 * this case. The alert row is also the dismissal record — PATCH .../{id} with
 * status='dismissed' persists server-side, so a dismissal survives a reload and
 * follows the user across devices.
 */
import React, { useEffect, useState } from 'react';
import {
  listComplianceAlerts,
  resolveComplianceAlert,
  type ComplianceAlert,
} from '../../api/compliance';
import {
  isVisaAlert,
  daysUntil,
} from '../../features/platform-v2/mobility-control/riskDashboard.helpers';
import { ConfidenceBadge } from '../../features/platform-v2/roadmap/ConfidenceBadge';
import type { ConfidenceLevel } from '../../features/platform-v2/roadmap/confidence.tokens';

/** Below this many days the nudge reads as urgent rather than advisory. */
export const URGENT_WITHIN_DAYS = 14;

/**
 * Provenance of the expiry date behind an alert, expressed on the shared
 * 4-level confidence scale. Driven by `detail.field`, which compliance_evaluator
 * stamps onto every `date_threshold` hit.
 */
export function confidenceForAlert(alert: ComplianceAlert): ConfidenceLevel {
  const field = typeof alert.detail?.field === 'string' ? alert.detail.field : '';
  // Maintained by HR on the immigration case record — the authoritative one.
  if (field === 'permit_expiry_date') return 'HIGH';
  // Self-declared at intake or OCR-extracted from a passport: real, but unverified.
  if (field === 'existing_visa_expiry' || field === 'passport_expiry') return 'MEDIUM';
  return 'UNKNOWN';
}

/**
 * The one alert worth nudging about: open, about a visa/permit expiry, on this
 * case, and soonest first. Exported so the threshold logic is unit-testable
 * without rendering.
 */
export function selectNudgeAlert(
  alerts: ComplianceAlert[],
  caseId: string,
): ComplianceAlert | null {
  const candidates = alerts
    .filter((a) => a.case_id === caseId)
    .filter((a) => a.status === 'open')
    .filter(isVisaAlert)
    // An expiry already in the past is a different problem (and a different
    // message); the evaluator only fires 0 <= days_until <= threshold, but the
    // guard keeps this honest if that ever changes.
    .filter((a) => Number.isFinite(daysUntil(a)) && daysUntil(a) >= 0)
    .sort((a, b) => daysUntil(a) - daysUntil(b));
  return candidates[0] ?? null;
}

export interface VisaExpiryNudgeProps {
  /** Canonical relocation-case id — must match ComplianceAlert.case_id. */
  caseId: string;
  /** Invoked by the CTA. Kept a prop because no renewal flow exists yet. */
  onStartRenewal: () => void;
}

export const VisaExpiryNudge: React.FC<VisaExpiryNudgeProps> = ({ caseId, onStartRenewal }) => {
  const [alert, setAlert] = useState<ComplianceAlert | null>(null);
  const [dismissing, setDismissing] = useState(false);

  useEffect(() => {
    if (!caseId) return;
    let cancelled = false;
    listComplianceAlerts()
      .then((r) => {
        if (!cancelled) setAlert(selectNudgeAlert(r.alerts ?? [], caseId));
      })
      .catch(() => {
        // Non-critical: never block the case page on this card's failure.
        if (!cancelled) setAlert(null);
      });
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  if (!alert) return null;

  const days = daysUntil(alert);
  const level = confidenceForAlert(alert);
  // "Low-confidence suggestions muted/labeled" — the whole card recedes rather
  // than the badge alone, so an unverified date never reads as urgent.
  const muted = level === 'LOW' || level === 'UNKNOWN';
  const urgent = !muted && days <= URGENT_WITHIN_DAYS;

  const handleDismiss = async () => {
    setDismissing(true);
    const previous = alert;
    setAlert(null); // optimistic — the card is ambient, so it should go at once
    try {
      await resolveComplianceAlert(previous.id, 'dismissed');
    } catch {
      // Put it back so the dismissal is not silently lost; the user can retry.
      setAlert(previous);
    } finally {
      setDismissing(false);
    }
  };

  const tone = muted
    ? 'border-slate-200 bg-slate-50'
    : urgent
      ? 'border-red-300 bg-red-50'
      : 'border-amber-300 bg-amber-50';
  const headingTone = muted ? 'text-slate-700' : urgent ? 'text-red-900' : 'text-amber-900';
  const bodyTone = muted ? 'text-slate-600' : urgent ? 'text-red-800' : 'text-amber-800';

  const dayLabel = days === 0 ? 'today' : days === 1 ? 'in 1 day' : `in ${days} days`;

  return (
    <div
      // status, not alert: this is ambient and must not interrupt a screen
      // reader mid-task. Urgency is carried by the text, not by assertiveness.
      role="status"
      aria-live="polite"
      data-testid="visa-expiry-nudge"
      className={`mb-3 rounded-xl border p-4 ${tone}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className={`font-semibold ${headingTone}`}>
          {alert.category === 'immigration' ? 'Visa' : 'Permit'} expires {dayLabel}
        </span>
        <ConfidenceBadge level={level} size="sm" />
      </div>

      <p className={`mt-1 text-sm ${bodyTone}`}>
        {muted
          ? 'We could not confirm where this expiry date came from — check the immigration record before acting on it.'
          : 'Renewals typically need to start well before the expiry date. Start the renewal?'}
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={onStartRenewal}
          className="rounded-md bg-[#0b2b43] px-3 py-1.5 text-sm font-medium text-white hover:bg-[#0b2b43]/90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#1f8e8b]"
        >
          Start renewal
        </button>
        <button
          type="button"
          aria-label="Dismiss visa expiry suggestion"
          disabled={dismissing}
          onClick={handleDismiss}
          className={`rounded-md px-2 py-1 text-sm hover:bg-black/5 disabled:opacity-50 ${bodyTone}`}
        >
          Dismiss
        </button>
      </div>
    </div>
  );
};

export default VisaExpiryNudge;
