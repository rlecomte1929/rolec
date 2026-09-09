import React, { useEffect, useRef, useState } from 'react';
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
 *
 * TWO AUDIENCES, ONE COMPONENT. HR is the persona accountable for the move and was the
 * only one who could not see any of this — /hr/requirements reads a different table and
 * the roadmap overlay carries only a couple of titles. Rather than fork the component for
 * HR, the strings are keyed on `audience`: the four-state discipline above is the valuable
 * part and must not exist in two copies that can drift apart. Only the pronouns change —
 * an employee is told what is required of *them*, HR what is required of *the employee*.
 */
export type RequirementsAudience = 'employee' | 'hr';

interface CopyPack {
  heading: string;
  subheading: string;
  loading: string;
  failedTitle: string;
  failedBody: React.ReactNode;
  waivedNationalityTitle: string;
  waivedOwnNational: string;
  waivedEuEea: string;
  emptyBody: React.ReactNode;
}

const COPY: Record<RequirementsAudience, CopyPack> = {
  employee: {
    heading: 'What your destination requires',
    subheading: 'Based on where you’re moving and your nationality. Your forms below are how you satisfy these.',
    loading: 'Loading your destination requirements…',
    failedTitle: 'We couldn’t load your destination requirements',
    failedBody: (
      <>
        This is a problem on our side — it does <strong>not</strong> mean nothing is required of
        you. Please retry before relying on this page.
      </>
    ),
    waivedNationalityTitle: 'Not required for your nationality',
    waivedOwnNational:
      'Because you are a national of the destination country, these immigration requirements don’t apply:',
    waivedEuEea:
      'Because you have EU/EEA freedom of movement, these immigration requirements don’t apply:',
    emptyBody: (
      <>
        We don’t have destination requirements for your case yet. This does <strong>not</strong>{' '}
        mean nothing is required of you — please confirm with your HR contact.
      </>
    ),
  },
  hr: {
    heading: 'What this destination requires',
    subheading:
      'Based on the destination and the employee’s nationality. The forms below are how these get satisfied.',
    loading: 'Loading destination requirements…',
    failedTitle: 'We couldn’t load the destination requirements',
    failedBody: (
      <>
        This is a problem on our side — it does <strong>not</strong> mean nothing is required of
        this employee. Please retry before relying on this page.
      </>
    ),
    waivedNationalityTitle: 'Not required for this employee’s nationality',
    waivedOwnNational:
      'Because this employee is a national of the destination country, these immigration requirements don’t apply:',
    waivedEuEea:
      'Because this employee has EU/EEA freedom of movement, these immigration requirements don’t apply:',
    emptyBody: (
      <>
        We don’t have destination requirements for this case yet. This does <strong>not</strong>{' '}
        mean nothing is required of this employee — treat it as a gap to confirm, not as an answer.
      </>
    ),
  },
};

export const DestinationRequirements: React.FC<{
  caseId: string;
  audience?: RequirementsAudience;
  /**
   * [AIQ-1902] Report the loaded dossier to the host page. The HR cockpit's Path tile
   * needs to know whether any requirement survived, so it can stop saying "No permit
   * mapping for this destination yet." above a list of fourteen of them.
   *
   * A callback rather than a second fetch in the caller: this component owns the
   * four-state discipline documented above, and a parallel fetch would be a second
   * copy of it that can disagree with this one. `null` means loading or failed —
   * i.e. "no answer", never "no requirements".
   */
  onLoaded?: (data: CaseRequirementsDTO | null) => void;
}> = ({ caseId, audience = 'employee', onLoaded }) => {
  const copy = COPY[audience];
  const [data, setData] = useState<CaseRequirementsDTO | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'failed'>('loading');
  const [reloadKey, setReloadKey] = useState(0);

  // Held in a ref, and deliberately NOT in the effect's dependency array: callers pass
  // an inline arrow, which is a new identity every render, so depending on it would
  // refetch the dossier in a loop.
  const onLoadedRef = useRef(onLoaded);
  onLoadedRef.current = onLoaded;

  useEffect(() => {
    if (!caseId) return;
    let cancelled = false;
    setState('loading');
    onLoadedRef.current?.(null);
    getRequirements(caseId)
      .then((res) => {
        if (cancelled) return;
        setData(res);
        setState('ready');
        onLoadedRef.current?.(res);
      })
      .catch(() => {
        if (cancelled) return;
        // Deliberately NOT "render nothing". A backend hiccup must not quietly
        // tell someone they have no legal obligations.
        setData(null);
        setState('failed');
        onLoadedRef.current?.(null);
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
        <h2 className="text-lg font-semibold text-[#0b2b43]">{copy.heading}</h2>
        <p className="text-xs text-[#64748b] mt-0.5">{copy.subheading}</p>
      </div>

      {state === 'loading' && <div className="text-sm text-[#6b7280]">{copy.loading}</div>}

      {state === 'failed' && (
        <div
          data-testid="requirements-error"
          className="rounded-xl border border-[#fecaca] bg-[#fff5f5] px-4 py-3 text-sm text-[#7a2a2a]"
        >
          <div className="font-semibold mb-1">{copy.failedTitle}</div>
          <div className="mb-2">{copy.failedBody}</div>
          <Button variant="outline" size="sm" onClick={() => setReloadKey((k) => k + 1)}>
            Retry
          </Button>
        </div>
      )}

      {state === 'ready' && (
        <>
          <RequirementsCoverageNotice
            covered={data?.covered}
            destCountry={data?.destCountry}
            catalogReady={data?.catalogReady}
            catalogNotReadyReason={data?.catalogNotReadyReason}
          />

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
                {copy.waivedNationalityTitle}
              </div>
              <div className="mb-2">
                {data?.nationalityClass === 'OWN_NATIONAL'
                  ? copy.waivedOwnNational
                  : copy.waivedEuEea}
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
          {/* When the engine could not classify the nationality it falls back to
              THIRD_COUNTRY — the most demanding track — and DELIBERATELY stays silent
              (rules_engine.py: no nationalityClass, no waived list, no confirmation), so
              that an unknown nationality can never be read as free movement. Correct, but
              it leaves the reader with a list they cannot account for. HR is the persona
              who can actually go and fill that field in, so tell them. */}
          {audience === 'hr' && data?.covered !== false && !data?.nationalityClass && (
            <div
              data-testid="nationality-unknown"
              className="mt-4 rounded-xl border border-[#fde68a] bg-[#fffbeb] px-4 py-3 text-sm text-[#713f12]"
            >
              <div className="text-sm font-semibold mb-1">
                This employee’s nationality isn’t on file
              </div>
              <div>
                So this list is the fullest one — the route for someone with no freedom of
                movement. Some of it may not apply. Adding their nationality to the case will
                narrow it and, where they have EU/EEA rights, state what they don’t need.
              </div>
            </div>
          )}

          {Object.keys(grouped).length === 0 && data?.covered !== false && (
            <div className="mt-4 rounded-xl border border-[#e2e8f0] bg-[#f8fafc] px-4 py-3 text-sm text-[#4b5563]">
              {copy.emptyBody}
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
