import React, { useEffect, useState } from 'react';
import { Button } from '../../../components/antigravity/Button';
import { getRequirements } from '../../../api/cases';
import { RequirementList } from '../../../components/requirements/RequirementList';
import { RequirementsCoverageNotice } from '../../../components/requirements/RequirementsCoverageNotice';
import { ImmigrationDisclaimer } from '../../../components/requirements/ImmigrationDisclaimer';
import type { CaseRequirementsDTO, RequirementItemDTO } from '../../../types';

/**
 * What the destination actually requires of this employee.
 *
 * The dossier page lists the FORMS — the documents that satisfy requirements —
 * but never said what is required, or why. This is the missing half: the
 * requirement_items dossier across the IDENTITY / RESIDENCE / EMPLOYMENT /
 * HOUSING / HEALTHCARE pillars, nationality-gated, with the stated "nothing
 * required" confirmations.
 *
 * THE ONE RULE HERE: an empty section must never assert anything. On this screen
 * an empty list reads as "nothing is required of you" — a claim about someone's
 * legal obligations. So loading / failed / not-covered / empty are four distinct
 * states, and a fetch failure is never allowed to impersonate an answer.
 */
export const DestinationRequirements: React.FC<{ caseId: string }> = ({ caseId }) => {
  const [data, setData] = useState<CaseRequirementsDTO | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'failed'>('loading');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!caseId) return;
    let cancelled = false;
    setState('loading');
    getRequirements(caseId)
      .then((res) => {
        if (cancelled) return;
        setData(res);
        setState('ready');
      })
      .catch(() => {
        if (cancelled) return;
        // Deliberately NOT "render nothing". A backend hiccup must not quietly
        // tell someone they have no legal obligations.
        setData(null);
        setState('failed');
      });
    return () => {
      cancelled = true;
    };
  }, [caseId, reloadKey]);

  const grouped = (data?.requirements ?? []).reduce<Record<string, RequirementItemDTO[]>>(
    (acc, item) => {
      const list = acc[item.pillar] ?? [];
      list.push(item);
      acc[item.pillar] = list;
      return acc;
    },
    {},
  );

  const nationalityWaived = data?.nationalityWaived ?? [];
  // NOT symmetric: for a THIRD_COUNTRY national this array holds the *EU* items, so
  // rendering it verbatim would tell an Indian employee "Justificatif de domicile
  // doesn't apply to you" — confusing, and false. Their list didn't shrink.
  const showNationalityWaived =
    (data?.nationalityClass === 'OWN_NATIONAL' || data?.nationalityClass === 'EU_EEA') &&
    nationalityWaived.length > 0;

  return (
    <section data-testid="destination-requirements" className="mb-6">
      <div className="mb-3">
        <h2 className="text-lg font-semibold text-[#0b2b43]">What your destination requires</h2>
        <p className="text-xs text-[#64748b] mt-0.5">
          Based on where you’re moving and your nationality. Your forms below are how you satisfy
          these.
        </p>
      </div>

      {state === 'loading' && (
        <div className="text-sm text-[#6b7280]">Loading your destination requirements…</div>
      )}

      {state === 'failed' && (
        <div
          data-testid="requirements-error"
          className="rounded-xl border border-[#fecaca] bg-[#fff5f5] px-4 py-3 text-sm text-[#7a2a2a]"
        >
          <div className="font-semibold mb-1">We couldn’t load your destination requirements</div>
          <div className="mb-2">
            This is a problem on our side — it does <strong>not</strong> mean nothing is required of
            you. Please retry before relying on this page.
          </div>
          <Button variant="outline" size="sm" onClick={() => setReloadKey((k) => k + 1)}>
            Retry
          </Button>
        </div>
      )}

      {state === 'ready' && (
        <>
          <RequirementsCoverageNotice covered={data?.covered} destCountry={data?.destCountry} />

          {data?.staWaived && data.staWaived.length > 0 && (
            <div className="mt-4 rounded-xl border border-[#e2e8f0] bg-[#f8fafc] px-4 py-3 text-sm text-[#4b5563]">
              <div className="text-sm font-semibold text-[#0b2b43] mb-1">
                Waived for this short-term assignment
              </div>
              <div className="mb-2">
                Because this is a short-term assignment (under 12 months), these long-term
                requirements don’t apply:
              </div>
              <ul className="list-disc list-inside space-y-1">
                {data.staWaived.map((title) => (
                  <li key={title}>{title}</li>
                ))}
              </ul>
            </div>
          )}

          {showNationalityWaived && (
            <div
              data-testid="nationality-waived"
              className="mt-4 rounded-xl border border-[#e2e8f0] bg-[#f8fafc] px-4 py-3 text-sm text-[#4b5563]"
            >
              <div className="text-sm font-semibold text-[#0b2b43] mb-1">
                Not required for your nationality
              </div>
              <div className="mb-2">
                {data?.nationalityClass === 'OWN_NATIONAL'
                  ? 'Because you are a national of the destination country, these immigration requirements don’t apply:'
                  : 'Because you have EU/EEA freedom of movement, these immigration requirements don’t apply:'}
              </div>
              <ul className="list-disc list-inside space-y-1">
                {nationalityWaived.map((title) => (
                  <li key={title}>{title}</li>
                ))}
              </ul>
            </div>
          )}

          {/* An empty list must NEVER claim. The backend returns covered=false for a
              catalog gap, so the notice above speaks. This is only a fallback, and it
              does not assert. */}
          {Object.keys(grouped).length === 0 && data?.covered !== false && (
            <div className="mt-4 rounded-xl border border-[#e2e8f0] bg-[#f8fafc] px-4 py-3 text-sm text-[#4b5563]">
              We don’t have destination requirements for your case yet. This does{' '}
              <strong>not</strong> mean nothing is required of you — please confirm with your HR
              contact.
            </div>
          )}

          <div className="mt-4 space-y-6">
            {/* AIQ-1658: the immigration disclaimer belongs to the requirements as a
                whole, so render it ONCE above the first pillar — it used to live inside
                RequirementList and repeated for every pillar section. */}
            {Object.keys(grouped).length > 0 && <ImmigrationDisclaimer />}
            {Object.entries(grouped).map(([pillar, items]) => (
              <div key={pillar}>
                <div className="text-sm font-semibold text-[#0b2b43] mb-3">{pillar}</div>
                <RequirementList items={items} />
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
};
