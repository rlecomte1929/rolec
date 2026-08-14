/**
 * CaseFeasibilityPanel — warns HR when a case cannot make its target start date.
 *
 * Employment-permit corridors invert the usual model: the permit and entry visa
 * must both be granted BEFORE the employee can travel, so an ES_IE case opened
 * six weeks out is unrecoverable no matter how diligently it is run. The backend
 * measures each corridor's pre-arrival runway from its step graph and returns a
 * verdict on GET /api/hr/cases/{caseId}/overview; this renders it.
 *
 * Free-movement corridors reach this component too and always resolve to 'ok' —
 * their step graphs root at arrival, so there is no runway to run out of. No
 * corridor allowlist is involved on either side.
 *
 * Renders NOTHING for 'ok', for a null feasibility block, or while loading. An
 * absent opinion must never render as reassurance.
 *
 * All date arithmetic is server-side. `derivation` is displayed verbatim.
 */
import React, { useEffect, useState } from 'react';
import { AlertTriangle, Clock } from 'lucide-react';
import { Alert } from '../antigravity';
import { fetchCaseOverview } from '../../api/cases';
import type { CaseFeasibility } from '../../api/cases';

interface CaseFeasibilityPanelProps {
  /**
   * The relocation_cases UUID — `detail.caseId`, NOT `detail.id`.
   * See fetchCaseOverview for why the distinction matters.
   */
  caseId?: string | null;
}

function dayLabel(days: number): string {
  const n = Math.abs(days);
  return `${n} day${n === 1 ? '' : 's'}`;
}

export const CaseFeasibilityPanel: React.FC<CaseFeasibilityPanelProps> = ({ caseId }) => {
  const [feasibility, setFeasibility] = useState<CaseFeasibility | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!caseId) { setFeasibility(null); return; }
    void fetchCaseOverview(caseId).then((overview) => {
      if (!cancelled) setFeasibility(overview?.feasibility ?? null);
    });
    return () => { cancelled = true; };
  }, [caseId]);

  // 'ok' and null both mean "nothing to say" — render no container at all.
  if (!feasibility || feasibility.verdict === 'ok') return null;

  const isCritical = feasibility.verdict === 'critical';
  const shortfall = feasibility.required_days - feasibility.available_days;

  return (
    <Alert
      variant={isCritical ? 'error' : 'warning'}
      title={
        isCritical
          ? 'This start date is unlikely to be achievable'
          : 'This start date leaves no room for delay'
      }
      className="flex gap-3 items-start"
    >
      <span className="sr-only">
        {isCritical ? 'Critical timeline warning' : 'Timeline warning'}
      </span>
      {isCritical
        ? <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" aria-hidden="true" />
        : <Clock className="w-5 h-5 shrink-0 mt-0.5" aria-hidden="true" />}
      <div className="space-y-2">
        <p>
          This corridor needs <strong>{dayLabel(feasibility.required_days)}</strong> of
          steps completed before the employee can start.{' '}
          {feasibility.available_days < 0
            ? <>The target start date has already passed.</>
            : <>Only <strong>{dayLabel(feasibility.available_days)}</strong> remain
                {isCritical && <> — a shortfall of <strong>{dayLabel(shortfall)}</strong></>}.</>}
        </p>
        <p className="opacity-80">{feasibility.derivation}</p>
        <p className="opacity-80">
          Timelines depend on authority processing times we do not control. Confirm the
          plan with the immigration adviser handling this case before committing to the
          start date.
        </p>
      </div>
    </Alert>
  );
};

export default CaseFeasibilityPanel;
