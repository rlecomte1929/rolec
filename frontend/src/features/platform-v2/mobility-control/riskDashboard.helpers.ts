/**
 * AIQ-1416 — pure helpers for the HR risk dashboard. No runtime imports (types only),
 * so unit tests can exercise them without pulling in the api/supabase client chain.
 */
import type { CommandCenterCaseRow } from '../../../api/client';
import type { ComplianceAlert } from '../../../api/compliance';

const RISK_RANK: Record<string, number> = { red: 0, yellow: 1 };

/** The "risk feed": non-green cases, red-first, then soonest move first. */
export function deriveRiskItems(cases: CommandCenterCaseRow[]): CommandCenterCaseRow[] {
  return cases
    .filter((c) => c.riskStatus === 'red' || c.riskStatus === 'yellow')
    .sort((a, b) => {
      const rank = (RISK_RANK[a.riskStatus] ?? 2) - (RISK_RANK[b.riskStatus] ?? 2);
      if (rank !== 0) return rank;
      const da = a.daysUntilMove ?? Number.POSITIVE_INFINITY;
      const db = b.daysUntilMove ?? Number.POSITIVE_INFINITY;
      return da - db;
    });
}

/** True when a compliance alert is about a visa/permit/residence expiry. */
export function isVisaAlert(a: ComplianceAlert): boolean {
  return /visa|permit|residence|expir/i.test(`${a.category} ${a.description ?? ''}`);
}

/** days_until from an alert's detail blob, or +Infinity when absent. */
export function daysUntil(a: ComplianceAlert): number {
  const v = a.detail?.days_until;
  return typeof v === 'number' ? v : Number.POSITIVE_INFINITY;
}
