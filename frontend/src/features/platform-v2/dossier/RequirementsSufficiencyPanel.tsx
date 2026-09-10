import React, { useCallback, useEffect, useState } from 'react';
import { Button } from '../../../components/antigravity';
import { ImmigrationDisclaimer } from '../../../components/requirements/ImmigrationDisclaimer';
import { requirementsAPI } from '../../../api/client';
import type { RequirementsSufficiency } from '../../../api/client';
import { getCountryName } from '../../../utils/countries';

/**
 * [AIQ-1821] The official requirements recorded for this case's destination, each with the
 * government source it came from — and, kept deliberately separate, the intake details we
 * still need from the employee.
 *
 * WHY THE TWO HALVES ARE SEPARATE. `frontend/src/api/relocation.ts` records that
 * `buildRequirementsFromMissingFields` was deleted because it rendered intake gaps as though
 * they were legal requirements — "two different claims". `supporting_requirements` are facts
 * an authority published and an admin approved. `missing_fields` are questions our own form
 * has not collected. Never merge them, never let one borrow the other's authority.
 *
 * WHY TWO SOURCE TREATMENTS. [AIQ-2132] `list_approved_requirement_facts` serves two evidence
 * states side by side: PR #1851 excludes only `evidence_verified = FALSE`, because NULL means
 * "never checked", not "wrong". Measured on production 2026-08-22, of the 205 served facts
 * **121 are verified and 84 have never been checked** — and this panel rendered both with the
 * same "Source: host" anchor, so a mover could not tell them apart. The label now carries the
 * difference (never colour alone), and an absent `citation_status` falls to the weaker claim.
 * This changes how a citation is described, never which facts are served.
 *
 * WHY A CONDITIONAL FACT IS NOT AN ASSERTION. A record tagged `assertion_mode: 'conditional'`
 * states a consequence whose trigger it does not itself determine — the two ES→IE entry-visa
 * records assert a SEQUENCE, while whether a nationality is visa-required is a separate ISD
 * lookup. Rendered flat, they tell a mover she is visa-required on the authority of a page
 * that never says so. So the condition is shown beside the fact, never dropped. `non_obvious`
 * marks the traps (16 of the 38 ES→IE records) where the cost of not knowing is high and
 * nothing else prompts you. Both are labels on a fact we already serve — neither changes
 * WHICH facts are served.
 *
 * WHY EMPTY IS NOT "COMPLETE". The endpoint answers HTTP 200 for `insufficient_data` and
 * `unavailable` too, so a naive render would show a reassuring empty panel while the backend
 * is broken. Every state below is distinguishable, and no state ever says "you're all set".
 */

/** Suppressed from the gaps list — see SUPPRESSED_FIELDS below. */
const UNSATISFIABLE_FIELDS = new Set(['passport_expiry_date']);

/**
 * `passport_expiry_date` can never leave `missing_fields`: the profile snapshot has no such
 * key, so it is reported missing forever. AIQ-1821 stopped the extractor emitting it, but
 * rows written before that fix still carry it (2 live rows at the time of writing), so the
 * guard stays until those are re-extracted. Showing it would be a to-do nobody can complete.
 */
const SUPPRESSED_FIELDS = UNSATISFIABLE_FIELDS;

const FIELD_LABELS: Record<string, string> = {
  origin_country: 'Country you are moving from',
  destination_country: 'Country you are moving to',
  move_date: 'Target move date',
  employment_type: 'Type of contract',
  employer_country: 'Country your employer is in',
  dependents: 'Whether family are moving with you',
  nationality: 'Your nationality',
  current_location: 'Where you currently live',
  visa_type: 'Which visa or permit route applies',
};

const labelFor = (field: string): string =>
  FIELD_LABELS[field] ??
  field
    .replace(/_/g, ' ')
    .replace(/^./, (c) => c.toUpperCase());

const hostOf = (url: string): string => {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
};

type LoadState = 'loading' | 'ready' | 'failed';

interface Props {
  caseId: string;
  /** Deep link used by the "complete your details" action. */
  intakeHref?: string;
}

export const RequirementsSufficiencyPanel: React.FC<Props> = ({ caseId, intakeHref }) => {
  const [data, setData] = useState<RequirementsSufficiency | null>(null);
  const [state, setState] = useState<LoadState>('loading');
  const [failureKind, setFailureKind] = useState<'forbidden' | 'notFound' | 'error'>('error');
  const [reloadKey, setReloadKey] = useState(0);

  const retry = useCallback(() => setReloadKey((k) => k + 1), []);

  useEffect(() => {
    if (!caseId) return;
    let cancelled = false;
    setState('loading');
    requirementsAPI
      .getSufficiency(caseId)
      .then((res) => {
        if (cancelled) return;
        setData(res);
        setState('ready');
      })
      .catch((err: { response?: { status?: number } }) => {
        if (cancelled) return;
        // Deliberately NOT "render nothing". A failure must never read as "nothing is
        // required of you" — the same rule DestinationRequirements follows.
        const status = err?.response?.status;
        setFailureKind(status === 403 ? 'forbidden' : status === 404 ? 'notFound' : 'error');
        setData(null);
        setState('failed');
      });
    return () => {
      cancelled = true;
    };
  }, [caseId, reloadKey]);

  const facts = data?.supporting_requirements ?? [];
  const gaps = (data?.missing_fields ?? []).filter((f) => !SUPPRESSED_FIELDS.has(f));
  const degraded = data != null && data.compute_status !== 'ok';
  const noDestination = data != null && data.compute_status === 'ok' && !data.destination_country;

  return (
    <section data-testid="requirements-sufficiency" className="mb-6">
      <div className="mb-3">
        <h2 className="text-lg font-semibold text-[#0b2b43]">
          Official requirements on record
        </h2>
        <p className="mt-0.5 text-xs text-slate-500">
          Published by the authorities for your destination, reviewed by our team before
          appearing here.
        </p>
      </div>

      {state === 'loading' && (
        <div aria-busy="true" className="text-sm text-slate-500">
          Loading the requirements on record…
        </div>
      )}

      {state === 'failed' && (
        <div
          data-testid="sufficiency-error"
          className="rounded-xl border border-[#fecaca] bg-[#fff5f5] px-4 py-3 text-sm text-[#7a2a2a]"
        >
          <div className="mb-1 font-semibold">
            {failureKind === 'forbidden'
              ? 'You don’t have access to this case'
              : failureKind === 'notFound'
                ? 'We couldn’t find this case'
                : 'We couldn’t load the requirements on record'}
          </div>
          {failureKind === 'error' && (
            <>
              <div className="mb-2">
                This is a problem on our side — it does <strong>not</strong> mean nothing is
                required of you. Please retry before relying on this page.
              </div>
              <Button variant="outline" size="sm" onClick={retry}>
                Retry
              </Button>
            </>
          )}
        </div>
      )}

      {state === 'ready' && (
        <>
          {degraded && (
            <div
              data-testid="sufficiency-degraded"
              className="mb-3 rounded-xl border border-[#fde68a] bg-[#fffbeb] px-4 py-3 text-sm text-[#78350f]"
            >
              <div className="mb-1 font-semibold">We couldn’t work this out yet</div>
              <div className="mb-2">
                {data?.message ??
                  'More information is needed before this can be calculated.'}{' '}
                This does <strong>not</strong> mean nothing is required of you.
              </div>
              <Button variant="outline" size="sm" onClick={retry}>
                Retry
              </Button>
            </div>
          )}

          {!degraded && noDestination && (
            <div
              data-testid="sufficiency-no-destination"
              className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600"
            >
              Your destination isn’t set on this case yet, so we can’t show what it requires.
            </div>
          )}

          {!degraded && !noDestination && facts.length === 0 && (
            <div
              data-testid="sufficiency-empty"
              className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600"
            >
              We don’t yet hold reviewed requirements for{' '}
              <strong>{getCountryName(data?.destination_country) || data?.destination_country}</strong>. This corridor is not ready — that
              is a catalog gap, <strong>not</strong> a finding that nothing is required of you.
            </div>
          )}

          {!degraded && facts.length > 0 && (
            <ul className="space-y-2">
              {facts.map((fact) => {
                const verified = fact.citation_status === 'verified';
                const conditional = fact.assertion_mode === 'conditional';
                return (
                  <li
                    key={fact.fact_id}
                    data-testid="sufficiency-fact"
                    className="rounded-xl border border-slate-200 bg-white px-4 py-3"
                  >
                    {fact.non_obvious && (
                      <p
                        data-testid="sufficiency-fact-trap"
                        className="mb-1 text-xs font-semibold uppercase tracking-wide text-[#0b2b43]"
                      >
                        Easy to miss
                      </p>
                    )}
                    {conditional && (
                      <p
                        data-testid="sufficiency-fact-conditional"
                        className="mb-1 text-xs font-semibold text-slate-600"
                      >
                        Applies only in certain cases
                      </p>
                    )}
                    <p className="text-sm text-slate-800">{fact.fact_text}</p>
                    {conditional && fact.conditional_on && (
                      <p
                        data-testid="sufficiency-fact-condition"
                        className="mt-1 text-xs text-slate-600"
                      >
                        Depends on: {fact.conditional_on}
                      </p>
                    )}
                    <a
                      href={fact.source_url}
                      target="_blank"
                      rel="noreferrer"
                      data-testid={
                        verified ? 'sufficiency-source-verified' : 'sufficiency-source-unverified'
                      }
                      className={
                        verified
                          ? 'mt-1 inline-block text-xs text-[#1f8e8b] hover:underline'
                          : 'mt-1 inline-block text-xs text-slate-500 hover:underline'
                      }
                    >
                      {verified
                        ? `Verified source: ${hostOf(fact.source_url)}`
                        : `Source — not independently verified: ${hostOf(fact.source_url)}`}
                    </a>
                  </li>
                );
              })}
            </ul>
          )}

          {/* A SEPARATE claim: our form is incomplete. Not a legal obligation. */}
          {gaps.length > 0 && (
            <div
              data-testid="sufficiency-gaps"
              className="mt-4 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3"
            >
              <h3 className="text-sm font-semibold text-[#0b2b43]">
                Details we still need from you
              </h3>
              <p className="mt-0.5 text-xs text-slate-500">
                These are answers missing from your own intake — not requirements from the
                authorities. Filling them in lets us tailor the guidance above.
              </p>
              <ul className="mt-2 list-inside list-disc text-sm text-slate-700">
                {gaps.map((field) => (
                  <li key={field}>{labelFor(field)}</li>
                ))}
              </ul>
              {intakeHref && (
                <a
                  href={intakeHref}
                  className="mt-2 inline-block text-sm text-[#1f8e8b] hover:underline"
                >
                  Complete your details
                </a>
              )}
            </div>
          )}

          {facts.length > 0 && <ImmigrationDisclaimer className="mt-4" />}
        </>
      )}
    </section>
  );
};

export default RequirementsSufficiencyPanel;
