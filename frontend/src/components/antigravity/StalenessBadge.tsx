/**
 * [P2-08b] StalenessBadge — additive "source not recently verified" warning.
 *
 * Renders an inline amber advisory when a cited source's last-verified date is
 * older than its per-tier threshold (see ../../utils/staleness). When the
 * source is fresh, the date is missing, or it cannot be parsed, the component
 * renders nothing — staleness is purely additive and never blocks the surface
 * it sits on (P2-08 technical constraint).
 *
 * Sources on official Tier-1 authority forms default to the `tier1_critical`
 * 30-day threshold; pass `tier` to override.
 */
import React from 'react';
import { AlertTriangle } from 'lucide-react';
import { isStale, type Tier } from '../../utils/staleness';

const DEFAULT_TIER: Tier = 'tier1_critical';

/**
 * Safe wrapper around `isStale`: treats a missing or unparseable date as
 * not-stale (fail-open on missing data, matching the backend roadmap_staleness
 * convention) instead of throwing. Shared by the badge and any consumer that
 * needs to count/aggregate stale sources (e.g. the dossier overview banner).
 */
export function isSourceStale(
  lastVerified: string | null | undefined,
  tier: Tier = DEFAULT_TIER,
  now?: Date | string | number,
): boolean {
  if (!lastVerified) return false;
  try {
    return isStale(lastVerified, tier, now);
  } catch {
    return false;
  }
}

export interface StalenessBadgeProps {
  /** ISO date the cited source was last fetched/verified. */
  lastVerified: string | null | undefined;
  /** Official source URL the user is pointed to when the source is stale. */
  sourceUrl?: string | null;
  /** Staleness tier; defaults to the strict 30-day `tier1_critical`. */
  tier?: Tier;
  /** Injectable reference time for deterministic tests. */
  now?: Date | string | number;
  className?: string;
}

export const StalenessBadge: React.FC<StalenessBadgeProps> = ({
  lastVerified,
  sourceUrl,
  tier = DEFAULT_TIER,
  now,
  className,
}) => {
  if (!isSourceStale(lastVerified, tier, now)) return null;

  // Non-null: isSourceStale only returns true for a parseable date.
  const dateLabel = new Date(lastVerified as string).toLocaleDateString();

  return (
    <span
      role="status"
      data-testid="staleness-badge"
      className={`inline-flex items-start gap-1.5 rounded-md border border-[#e2d6bf] bg-[#f4efe5] px-2 py-1 text-[11px] font-medium leading-snug text-[#7a5e2a] ${className ?? ''}`}
    >
      <AlertTriangle className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <span>
        Source last verified {dateLabel} —{' '}
        {sourceUrl ? (
          <a
            href={sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="font-semibold underline underline-offset-2 hover:text-[#5c461f]"
          >
            we recommend verifying directly at the source
          </a>
        ) : (
          <>we recommend verifying directly at the official source</>
        )}
      </span>
    </span>
  );
};

export default StalenessBadge;
