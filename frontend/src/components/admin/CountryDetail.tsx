import React from 'react';
import type { CountryProfileDTO } from '../../types';
import type { AdminRequirementReview, ReviewStatus } from '../../api/admin';
import { Card, Button, Badge } from '../antigravity';

interface CountryDetailProps {
  profile: CountryProfileDTO;
  requirements: AdminRequirementReview[];
  pendingCount: number;
  busyId: string | null;
  onRerun: () => void;
  onReview: (requirementId: string, status: Exclude<ReviewStatus, 'pending'>) => void;
}

// Same vocabulary the employee sees in RequirementList.tsx — an admin approving content must
// read the label the reader will read, not a second private wording.
const PROVENANCE: Record<string, { label: string; variant: 'neutral' | 'info' | 'success' }> = {
  representative: { label: 'Representative', variant: 'neutral' },
  corpus_grounded: { label: 'Source-grounded', variant: 'info' },
  expert_verified: { label: 'Expert-verified', variant: 'success' },
  // Production stores `verified` for INTERNALLY reviewed rows. The backend passes
  // verification_status straight through — there is no translation layer — so this map
  // must honour the value the database actually holds, or the badge silently disappears.
  //
  // It must NOT, however, borrow the expert label. Measured 2026-08-20: all ten `verified`
  // rows are Norway, reviewed_by='romain', attestation_status=null, and `expert_verified`
  // is 0 across the entire catalog. disclaimers.py reserves "expert_verified" for content
  // "signed off by a licensed immigration lawyer" — no lawyer has seen these. Rendering
  // them as "Expert-verified" asserted a status we do not hold, to the reader least able
  // to check it. Missing provenance is a gap; a false provenance claim is a liability, and
  // it is the same mistake as the "EU AI Act Ready" badge (AIQ-1513).
  //
  // 'info', not 'success': the green rung stays reserved for genuine external sign-off, so
  // the first real counsel attestation is visibly distinct rather than lost among ten rows
  // already wearing the strongest badge we have.
  verified: { label: 'Reviewed', variant: 'info' },
};

const REVIEW: Record<ReviewStatus, { label: string; variant: 'warning' | 'success' | 'error' }> = {
  pending: { label: 'Pending review', variant: 'warning' },
  approved: { label: 'Published', variant: 'success' },
  rejected: { label: 'Withheld', variant: 'error' },
};

/** null nationality classes means "applies to everyone" — worth stating, not leaving blank. */
const audience = (classes?: string[] | null) =>
  !classes || classes.length === 0 ? 'All nationalities' : classes.join(' · ');

export const CountryDetail: React.FC<CountryDetailProps> = ({
  profile,
  requirements,
  pendingCount,
  busyId,
  onRerun,
  onReview,
}) => {
  return (
    <div className="space-y-6">
      <Card padding="lg">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-lg font-semibold text-[#0b2b43]">{profile.countryCode}</div>
            <div className="text-xs text-[#6b7280]">
              Last updated: {profile.lastUpdatedAt ? new Date(profile.lastUpdatedAt).toLocaleString('en-US') : '-'}
            </div>
          </div>
          <Button onClick={onRerun}>Re-run research</Button>
        </div>
      </Card>

      {pendingCount > 0 && (
        <Card padding="lg">
          <div className="text-sm text-[#0b2b43]">
            <span className="font-semibold">{pendingCount}</span>{' '}
            {pendingCount === 1 ? 'requirement is' : 'requirements are'} waiting for review. Until
            you publish them they are not served to employees, to HR, or to the public corridor
            endpoint.
          </div>
        </Card>
      )}

      <Card padding="lg">
        <div className="text-sm font-semibold text-[#0b2b43] mb-3">Sources</div>
        <div className="space-y-2 text-sm">
          {profile.sources.map((source) => (
            <div key={source.id} className="border border-[#e2e8f0] rounded-lg p-3">
              <div className="font-semibold text-[#0b2b43]">{source.title}</div>
              <div className="text-xs text-[#6b7280]">{source.publisherDomain}</div>
            </div>
          ))}
          {profile.sources.length === 0 && (
            <div className="text-xs text-[#6b7280]">No source records for this country.</div>
          )}
        </div>
      </Card>

      <Card padding="lg">
        <div className="text-sm font-semibold text-[#0b2b43] mb-3">
          Requirements ({requirements.length})
        </div>
        <div className="space-y-3">
          {requirements.map((item) => (
            <div key={item.id} className="border border-[#e2e8f0] rounded-lg p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-[#0b2b43]">{item.title}</div>
                  <div className="text-xs text-[#6b7280] mt-1">
                    {item.pillar} · {item.purpose} · {item.severity} · owner {item.owner}
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2 shrink-0">
                  {(() => {
                    const review = REVIEW[item.reviewStatus] ?? REVIEW.pending;
                    const prov = item.verificationStatus ? PROVENANCE[item.verificationStatus] : undefined;
                    return (
                      <>
                        <Badge variant={review.variant} size="sm">{review.label}</Badge>
                        {prov && <Badge variant={prov.variant} size="sm">{prov.label}</Badge>}
                      </>
                    );
                  })()}
                </div>
              </div>

              <p className="text-sm text-[#334155] mt-3 whitespace-pre-line">{item.description}</p>

              <div className="text-xs text-[#6b7280] mt-3">
                Applies to: {audience(item.appliesToNationalityClasses)}
                {item.appliesToAssignmentTypes?.length
                  ? ` · ${item.appliesToAssignmentTypes.join(', ')}`
                  : ''}
              </div>

              {item.citations.length > 0 && (
                <ul className="text-xs text-[#6b7280] mt-2 space-y-1">
                  {item.citations.map((c) => (
                    <li key={c.id} className="truncate">
                      {c.url ? (
                        <a
                          href={c.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="underline"
                          title={c.url}
                        >
                          {c.title}
                        </a>
                      ) : (
                        // No URL means the backend could not resolve this reference at all.
                        // Say so — an unresolvable citation on a row about to be published is
                        // the defect this screen exists to catch, not a cosmetic gap.
                        <span className="text-[#b45309]">{c.title} (unresolved source)</span>
                      )}
                    </li>
                  ))}
                </ul>
              )}

              <div className="flex items-center gap-2 mt-4">
                {item.reviewStatus !== 'approved' && (
                  <Button
                    size="sm"
                    disabled={busyId === item.id}
                    onClick={() => onReview(item.id, 'approved')}
                  >
                    Publish
                  </Button>
                )}
                {item.reviewStatus !== 'rejected' && (
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={busyId === item.id}
                    onClick={() => onReview(item.id, 'rejected')}
                  >
                    Withhold
                  </Button>
                )}
                {item.reviewedBy && (
                  <span className="text-xs text-[#6b7280]">
                    {item.reviewStatus} by {item.reviewedBy}
                    {item.reviewedAt ? ` on ${new Date(item.reviewedAt).toLocaleDateString('en-US')}` : ''}
                  </span>
                )}
              </div>
            </div>
          ))}
          {requirements.length === 0 && (
            <div className="text-xs text-[#6b7280]">
              No requirements are configured for this country yet.
            </div>
          )}
        </div>
      </Card>
    </div>
  );
};
