import React, { useMemo, useState } from 'react';
import type { CountryProfileDTO } from '../../types';
import type { AdminRequirementReview, ReviewStatus } from '../../api/admin';
import { Badge, Button, Card, Checkbox } from '../antigravity';
import { getCountryName } from '../../utils/countries';

interface CountryDetailProps {
  profile: CountryProfileDTO;
  requirements: AdminRequirementReview[];
  pendingCount: number;
  busyId: string | null;
  onRerun: () => void;
  onReview: (requirementId: string, status: Exclude<ReviewStatus, 'pending'>) => void;
  onReviewBatch?: (ids: string[], status: Exclude<ReviewStatus, 'pending'>) => void;
}

const PROVENANCE: Record<string, { label: string; variant: 'neutral' | 'info' | 'success' }> = {
  representative: { label: 'Representative', variant: 'neutral' },
  corpus_grounded: { label: 'Source-grounded', variant: 'info' },
  expert_verified: { label: 'Expert-verified', variant: 'success' },
  verified: { label: 'Reviewed', variant: 'info' },
};

const REVIEW: Record<ReviewStatus, { label: string; variant: 'warning' | 'success' | 'error' }> = {
  pending: { label: 'Pending review', variant: 'warning' },
  approved: { label: 'Published', variant: 'success' },
  rejected: { label: 'Withheld', variant: 'error' },
};

const audience = (classes?: string[] | null) =>
  !classes || classes.length === 0 ? 'All nationalities' : classes.join(' · ');

export const CountryDetail: React.FC<CountryDetailProps> = ({
  profile,
  requirements,
  pendingCount,
  busyId,
  onRerun,
  onReview,
  onReviewBatch,
}) => {
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  const ids = useMemo(() => requirements.map((r) => r.id), [requirements]);
  const allSelected = ids.length > 0 && ids.every((id) => selected.has(id));
  const selectedList = ids.filter((id) => selected.has(id));
  const busy = busyId !== null;
  const countryLabel = getCountryName(profile.countryCode);

  const toggle = (id: string, checked: boolean) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  };

  const toggleAll = (checked: boolean) => {
    setSelected(checked ? new Set(ids) : new Set());
  };

  const runBatch = (status: Exclude<ReviewStatus, 'pending'>) => {
    if (!onReviewBatch || selectedList.length === 0) return;
    onReviewBatch(selectedList, status);
    setSelected(new Set());
  };

  return (
    <div className="space-y-6">
      <Card padding="lg">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-lg font-semibold text-[#0b2b43]">{countryLabel}</div>
            <div className="text-xs text-slate-500">
              Last updated:{' '}
              {profile.lastUpdatedAt ? new Date(profile.lastUpdatedAt).toLocaleString('en-GB') : '—'}
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
              <div className="text-xs text-slate-500">{source.publisherDomain}</div>
            </div>
          ))}
          {profile.sources.length === 0 && (
            <div className="text-xs text-slate-500">No source records for this country.</div>
          )}
        </div>
      </Card>

      <Card padding="lg">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div className="text-sm font-semibold text-[#0b2b43]">
            Requirements ({requirements.length})
          </div>
          {requirements.length > 0 && (
            <div className="flex flex-wrap items-center gap-3">
              <label className="inline-flex items-center gap-2 text-sm text-[#0b2b43]">
                <Checkbox
                  checked={allSelected}
                  disabled={busy}
                  onChange={(e) => toggleAll(e.target.checked)}
                  aria-label="Select all requirements"
                />
                Select all
              </label>
              <Button
                size="sm"
                disabled={busy || selectedList.length === 0}
                onClick={() => runBatch('approved')}
              >
                Publish selected ({selectedList.length})
              </Button>
              <Button
                size="sm"
                variant="secondary"
                disabled={busy || selectedList.length === 0}
                onClick={() => runBatch('rejected')}
              >
                Withhold selected
              </Button>
            </div>
          )}
        </div>
        <div className="space-y-3">
          {requirements.map((item) => (
            <div key={item.id} className="border border-[#e2e8f0] rounded-lg p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3 min-w-0">
                  <Checkbox
                    className="mt-1"
                    checked={selected.has(item.id)}
                    disabled={busy}
                    onChange={(e) => toggle(item.id, e.target.checked)}
                    aria-label={`Select ${item.title}`}
                  />
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-[#0b2b43]">{item.title}</div>
                    <div className="text-xs text-slate-500 mt-1">
                      {item.pillar} · {item.purpose} · {item.severity} · owner {item.owner}
                    </div>
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

              <p className="text-sm text-[#334155] mt-3 whitespace-pre-line pl-7">{item.description}</p>

              <div className="text-xs text-slate-500 mt-3 pl-7">
                Applies to: {audience(item.appliesToNationalityClasses)}
                {item.appliesToAssignmentTypes?.length
                  ? ` · ${item.appliesToAssignmentTypes.join(', ')}`
                  : ''}
              </div>

              {item.citations.length > 0 && (
                <ul className="text-xs text-slate-500 mt-2 space-y-1 pl-7">
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
                        <span className="text-[#b45309]">{c.title} (unresolved source)</span>
                      )}
                    </li>
                  ))}
                </ul>
              )}

              <div className="flex items-center gap-2 mt-4 pl-7">
                {item.reviewStatus !== 'approved' && (
                  <Button
                    size="sm"
                    disabled={busyId === item.id || busy}
                    onClick={() => onReview(item.id, 'approved')}
                  >
                    Publish
                  </Button>
                )}
                {item.reviewStatus !== 'rejected' && (
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={busyId === item.id || busy}
                    onClick={() => onReview(item.id, 'rejected')}
                  >
                    Withhold
                  </Button>
                )}
                {item.reviewedBy && (
                  <span className="text-xs text-slate-500">
                    {item.reviewStatus} by {item.reviewedBy}
                    {item.reviewedAt ? ` on ${new Date(item.reviewedAt).toLocaleDateString('en-GB')}` : ''}
                  </span>
                )}
              </div>
            </div>
          ))}
          {requirements.length === 0 && (
            <div className="text-xs text-slate-500">
              No requirements are configured for this country yet.
            </div>
          )}
        </div>
      </Card>
    </div>
  );
};
