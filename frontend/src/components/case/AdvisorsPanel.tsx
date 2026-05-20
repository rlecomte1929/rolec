/**
 * AdvisorsPanel — GAP 4
 *
 * Shows immigration advisors matched to the relocation corridor.
 * Displayed in the HR case detail view, below the immigration status panel.
 *
 * Features:
 *  - Corridor-matched advisors from POST /api/advisors/match
 *  - Company-preferred advisors surfaced first with a "Preferred" badge
 *  - Platform preferred-partner badge
 *  - Ratings, SLA, specialisms, languages
 *  - Verified badge
 *  - Graceful empty/error state (hides entirely on failure)
 */

import React, { useCallback, useEffect, useState } from 'react';
import { matchAdvisors, type AdvisorProfile } from '../../api/advisors';

interface Props {
  originCountry?: string;
  destinationCountry?: string;
  caseId?: string;
}

function StarRating({ rating }: { rating: number }) {
  const full = Math.floor(rating);
  const half = rating - full >= 0.25 && rating - full < 0.75;
  const empty = 5 - full - (half ? 1 : 0);
  return (
    <span className="text-amber-400 text-xs" aria-label={`${rating} out of 5 stars`}>
      {'★'.repeat(full)}{half ? '½' : ''}{'☆'.repeat(empty)}
    </span>
  );
}

export const AdvisorsPanel: React.FC<Props> = ({
  originCountry,
  destinationCountry,
  caseId,
}) => {
  const [advisors, setAdvisors] = useState<AdvisorProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    if (!destinationCountry && !originCountry) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setFailed(false);
    try {
      const resp = await matchAdvisors({
        origin_country: originCountry,
        destination_country: destinationCountry,
        case_id: caseId,
      });
      setAdvisors(resp.advisors.slice(0, 5)); // show top 5
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, [originCountry, destinationCountry, caseId]);

  useEffect(() => { void load(); }, [load]);

  // Render nothing on failure — non-critical widget
  if (failed || (!loading && advisors.length === 0)) return null;

  return (
    <div className="rounded-xl border border-[#e2e8f0] bg-white overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-[#f1f5f9]">
        <div>
          <div className="text-sm font-semibold text-[#0b2b43]">Immigration advisors</div>
          <p className="text-xs text-[#94a3b8] mt-0.5">
            {destinationCountry
              ? `Matched for ${originCountry ? `${originCountry} → ` : ''}${destinationCountry}`
              : 'Global coverage'}
          </p>
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="divide-y divide-[#f1f5f9]">
          {[1, 2, 3].map((i) => (
            <div key={i} className="px-5 py-4 flex items-start gap-4 animate-pulse">
              <div className="h-10 w-10 rounded-full bg-[#f1f5f9] shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-3 bg-[#f1f5f9] rounded w-36" />
                <div className="h-3 bg-[#f1f5f9] rounded w-56" />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <ul className="divide-y divide-[#f1f5f9]">
          {advisors.map((adv) => (
            <li key={adv.id} className="px-5 py-4 flex items-start gap-4">
              {/* Avatar */}
              <div className="h-10 w-10 rounded-full bg-[#eef4f8] text-[#0b2b43] flex items-center justify-center text-sm font-semibold shrink-0 border border-[#e2e8f0]">
                {adv.logo_initials || adv.name.slice(0, 2).toUpperCase()}
              </div>

              {/* Details */}
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold text-[#0b2b43]">{adv.name}</span>

                  {/* Badges */}
                  {adv.preferred_for_company && (
                    <span className="inline-flex items-center rounded-full bg-[#eff6ff] border border-[#bfdbfe] px-2 py-0.5 text-xs font-medium text-[#1d4ed8]">
                      Preferred
                    </span>
                  )}
                  {adv.preferred_partner && !adv.preferred_for_company && (
                    <span className="inline-flex items-center rounded-full bg-[#f0fdf4] border border-[#bbf7d0] px-2 py-0.5 text-xs font-medium text-[#166534]">
                      Partner
                    </span>
                  )}
                  {adv.verified && (
                    <span className="inline-flex items-center gap-0.5 text-xs text-[#0369a1]" title="Verified">
                      <svg className="w-3 h-3" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clipRule="evenodd" />
                      </svg>
                      Verified
                    </span>
                  )}
                </div>

                <div className="text-xs text-[#6b7280] mt-0.5">
                  {adv.firm}{adv.title ? ` · ${adv.title}` : ''}
                </div>

                {/* Rating + SLA */}
                <div className="flex flex-wrap items-center gap-3 mt-1.5">
                  {adv.rating != null && (
                    <span className="flex items-center gap-1">
                      <StarRating rating={adv.rating} />
                      <span className="text-xs text-[#6b7280]">
                        {adv.rating.toFixed(1)}
                        {adv.rating_count > 0 && ` (${adv.rating_count})`}
                      </span>
                    </span>
                  )}
                  {adv.response_sla && (
                    <span className="text-xs text-[#6b7280]">⏱ {adv.response_sla}</span>
                  )}
                </div>

                {/* Specialisms */}
                {adv.specialisms.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {adv.specialisms.slice(0, 4).map((s) => (
                      <span
                        key={s}
                        className="rounded-full bg-[#f1f5f9] px-2 py-0.5 text-xs text-[#475569]"
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                )}

                {/* Languages */}
                {adv.languages.length > 0 && (
                  <div className="mt-1.5 text-xs text-[#94a3b8]">
                    Languages: {adv.languages.join(', ').toUpperCase()}
                  </div>
                )}
              </div>

              {/* Contact CTA */}
              {adv.contact_url && (
                <a
                  href={adv.contact_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="shrink-0 rounded-lg border border-[#0b2b43] bg-white px-3 py-1.5 text-xs font-medium text-[#0b2b43] hover:bg-[#f8fafc] transition-colors whitespace-nowrap"
                >
                  Contact
                </a>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
