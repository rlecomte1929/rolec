import React, { useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import type { CountryProfileDTO } from '../../types';
import type { AdminRequirementReview, ReviewStatus } from '../../api/admin';
import { Card, Button, Badge, CountryFlag, Input } from '../antigravity';
import {
  type RequirementStatusFilter,
  catalogConfidenceScore,
  confidenceLevel,
  confidencePercent,
  countRequirementStatuses,
  displayCatalogLabel,
  displayCountryName,
  filterRequirements,
  groupRequirementsByPillar,
} from './countryCatalog';

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

const STATUS_FILTERS: { id: RequirementStatusFilter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'pending', label: 'Pending' },
  { id: 'approved', label: 'Published' },
  { id: 'rejected', label: 'Withheld' },
];

/** null nationality classes means "applies to everyone" — worth stating, not leaving blank. */
const audience = (classes?: string[] | null) =>
  !classes || classes.length === 0 ? 'All nationalities' : classes.map(displayCatalogLabel).join(' · ');

function severityVariant(severity: string): 'error' | 'warning' | 'neutral' {
  const value = severity.toUpperCase();
  if (value === 'BLOCK' || value === 'CRITICAL' || value === 'ERROR' || value === 'HIGH') return 'error';
  if (value === 'WARN' || value === 'WARNING' || value === 'MEDIUM') return 'warning';
  return 'neutral';
}

function reviewAccent(status: ReviewStatus): string {
  if (status === 'pending') return 'border-l-amber-600';
  if (status === 'approved') return 'border-l-accent-500';
  return 'border-l-rose-700';
}

export const CountryDetail: React.FC<CountryDetailProps> = ({
  profile,
  requirements,
  pendingCount,
  busyId,
  onRerun,
  onReview,
}) => {
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState<RequirementStatusFilter>('all');
  const score = catalogConfidenceScore(profile.confidenceScore, requirements.length);
  const level = confidenceLevel(score);
  const confidenceVariant = level === 'high' ? 'success' : level === 'medium' ? 'warning' : 'error';
  const counts = useMemo(() => countRequirementStatuses(requirements), [requirements]);
  const visible = useMemo(
    () => filterRequirements(requirements, query, status),
    [requirements, query, status],
  );
  const groups = useMemo(() => groupRequirementsByPillar(visible), [visible]);

  return (
    <div className="space-y-6">
      <Card padding="lg">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-3">
              <CountryFlag
                country={profile.countryCode}
                label={displayCountryName(profile.countryCode)}
                className="text-lg font-semibold text-navy-800"
              />
              <span className="font-mono text-xs uppercase tracking-wide text-slate-500">{profile.countryCode}</span>
              {level !== 'unknown' && (
                <Badge variant={confidenceVariant} size="sm">
                  Confidence {confidencePercent(score)}%
                </Badge>
              )}
            </div>
            <div className="mt-1 text-xs text-slate-500">
              Last updated: {profile.lastUpdatedAt ? new Date(profile.lastUpdatedAt).toLocaleString('en-US') : 'Never'}
            </div>
          </div>
          <Button onClick={onRerun}>Re-run research</Button>
        </div>
      </Card>

      {pendingCount > 0 && (
        <Card padding="lg">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-sm text-navy-800">
              <span className="font-semibold">{pendingCount}</span>{' '}
              {pendingCount === 1 ? 'requirement is' : 'requirements are'} waiting for review. Until
              you publish them they are not served to employees, to HR, or to the public corridor
              endpoint.
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setStatus('pending')}
              aria-pressed={status === 'pending'}
            >
              Show pending
            </Button>
          </div>
        </Card>
      )}

      <Card padding="lg">
        <div className="text-sm font-semibold text-navy-800 mb-3">Sources</div>
        {profile.sources.length === 0 ? (
          <div className="text-xs text-slate-500">No source records for this country.</div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {profile.sources.map((source) => (
              <div
                key={source.id}
                className="max-w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2"
              >
                <div className="text-sm font-medium text-navy-800">{source.title}</div>
                {source.publisherDomain && (
                  <div className="font-mono text-[11px] text-slate-500">{source.publisherDomain}</div>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* fix: BUG-260908-9601 — group and filter the requirement database so review work is scannable */}
      <Card padding="lg">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="text-sm font-semibold text-navy-800">
              Requirements ({counts.all})
            </div>
            <p className="mt-1 text-xs text-slate-500">
              Grouped by pillar. Pending rows sit first so unpublished obligations are not buried.
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative w-full sm:w-64">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" aria-hidden="true" />
              <Input
                unstyled
                value={query}
                onChange={setQuery}
                placeholder="Search title, pillar, or source"
                aria-label="Search requirements"
                className="w-full rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm text-navy-800 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-navy-800"
              />
            </div>
            <div className="inline-flex flex-wrap rounded-lg border border-slate-200 bg-white p-0.5" role="group" aria-label="Filter requirements by review status">
              {STATUS_FILTERS.map((opt) => (
                <Button
                  key={opt.id}
                  unstyled
                  onClick={() => setStatus(opt.id)}
                  aria-pressed={status === opt.id}
                  className={`rounded-md px-3 py-1.5 text-xs font-medium ${
                    status === opt.id
                      ? 'bg-navy-50 text-navy-800'
                      : 'text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  {opt.label}
                  <span className="ml-1 font-mono text-slate-500">{counts[opt.id]}</span>
                </Button>
              ))}
            </div>
          </div>
        </div>

        {requirements.length === 0 ? (
          <div className="mt-4 rounded-xl border border-dashed border-slate-200 px-4 py-8 text-center text-sm text-slate-600">
            No requirements are configured for this country yet.
          </div>
        ) : visible.length === 0 ? (
          <div className="mt-4 rounded-xl border border-dashed border-slate-200 px-4 py-8 text-center text-sm text-slate-600">
            No requirements match this search or filter.
          </div>
        ) : (
          <div className="mt-4 space-y-6">
            {groups.map((group) => (
              <section key={group.pillar} aria-label={displayCatalogLabel(group.pillar)}>
                <div className="mb-2 flex items-center justify-between gap-3 border-b border-slate-200 pb-2">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    {displayCatalogLabel(group.pillar)}
                  </h3>
                  <span className="font-mono text-xs text-slate-500">{group.items.length}</span>
                </div>
                <div className="space-y-3">
                  {group.items.map((item) => (
                    <RequirementCard
                      key={item.id}
                      item={item}
                      busy={busyId === item.id}
                      onReview={onReview}
                    />
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
};

function RequirementCard({
  item,
  busy,
  onReview,
}: {
  item: AdminRequirementReview;
  busy: boolean;
  onReview: (requirementId: string, status: Exclude<ReviewStatus, 'pending'>) => void;
}) {
  const review = REVIEW[item.reviewStatus] ?? REVIEW.pending;
  const prov = item.verificationStatus ? PROVENANCE[item.verificationStatus] : undefined;

  return (
    <div className={`rounded-xl border border-slate-200 border-l-4 bg-white p-4 ${reviewAccent(item.reviewStatus)}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-navy-800">{item.title}</div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Badge variant="neutral" size="sm">{displayCatalogLabel(item.purpose)}</Badge>
            <Badge variant={severityVariant(item.severity)} size="sm">{displayCatalogLabel(item.severity)}</Badge>
            <Badge variant="neutral" size="sm">Owner {displayCatalogLabel(item.owner)}</Badge>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <Badge variant={review.variant} size="sm">{review.label}</Badge>
          {prov && <Badge variant={prov.variant} size="sm">{prov.label}</Badge>}
        </div>
      </div>

      <p className="mt-3 whitespace-pre-line text-sm text-slate-700">{item.description}</p>

      <div className="mt-3 text-xs text-slate-500">
        Applies to: {audience(item.appliesToNationalityClasses)}
        {item.appliesToAssignmentTypes?.length
          ? ` · ${item.appliesToAssignmentTypes.map(displayCatalogLabel).join(', ')}`
          : ''}
      </div>

      {item.citations.length > 0 && (
        <ul className="mt-2 space-y-1 text-xs text-slate-500">
          {item.citations.map((c) => (
            <li key={c.id} className="truncate">
              {c.url ? (
                <a
                  href={c.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent-600 underline"
                  title={c.url}
                >
                  {c.title}
                </a>
              ) : (
                // No URL means the backend could not resolve this reference at all.
                // Say so — an unresolvable citation on a row about to be published is
                // the defect this screen exists to catch, not a cosmetic gap.
                <span className="text-amber-800">{c.title} (unresolved source)</span>
              )}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-4 flex items-center gap-2">
        {item.reviewStatus !== 'approved' && (
          <Button
            size="sm"
            disabled={busy}
            onClick={() => onReview(item.id, 'approved')}
          >
            Publish
          </Button>
        )}
        {item.reviewStatus !== 'rejected' && (
          <Button
            size="sm"
            variant="secondary"
            disabled={busy}
            onClick={() => onReview(item.id, 'rejected')}
          >
            Withhold
          </Button>
        )}
        {item.reviewedBy && (
          <span className="text-xs text-slate-500">
            {item.reviewStatus} by {item.reviewedBy}
            {item.reviewedAt ? ` on ${new Date(item.reviewedAt).toLocaleDateString('en-US')}` : ''}
          </span>
        )}
      </div>
    </div>
  );
}
