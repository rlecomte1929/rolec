import React from 'react';

/**
 * ProcessingTimeBadge — user-facing surface for P2-04's processing-time estimate.
 *
 * Renders the estimate produced by the backend `processingTimeEstimate()` service
 * (P2-04a) as an inline, source-aware display:
 *   - platform_data → confident styling + "(based on N similar cases)"
 *   - official_only → muted styling + "(official estimate — insufficient platform data)"
 *     with a linked source citation when available.
 *
 * Presentational only — it takes the estimate as a prop and never fetches. When
 * the estimate is null/undefined (the service found no source) it renders nothing,
 * upholding the rule that we never show a processing time without a source.
 */

/** Mirrors the backend ProcessingTimeEstimate JSON shape (P2-04a). */
export interface ProcessingTimeEstimate {
  p50_days: number;
  p90_days: number;
  source: 'platform_data' | 'official_only';
  sample_size: number;
  last_updated?: string;
  source_url?: string | null;
}

interface ProcessingTimeBadgeProps {
  estimate: ProcessingTimeEstimate | null | undefined;
  size?: 'sm' | 'md';
}

/** Days → whole weeks, floored at 1 so we never show "0 weeks". */
function toWeeks(days: number): number {
  return Math.max(1, Math.round(days / 7));
}

/** Format a p50–p90 day span as a human week range, e.g. "4–12 weeks" / "3 weeks". */
function formatWeekRange(p50Days: number, p90Days: number): string {
  const low = toWeeks(p50Days);
  const high = toWeeks(Math.max(p50Days, p90Days));
  if (low === high) {
    return `${low} week${low === 1 ? '' : 's'}`;
  }
  return `${low}–${high} weeks`;
}

export const ProcessingTimeBadge: React.FC<ProcessingTimeBadgeProps> = ({
  estimate,
  size = 'md',
}) => {
  // No source → render nothing (never a processing time without a source).
  if (!estimate) {
    return null;
  }

  const isPlatform = estimate.source === 'platform_data';
  const range = formatWeekRange(estimate.p50_days, estimate.p90_days);
  const textSize = size === 'sm' ? 'text-xs' : 'text-sm';

  // Confidence indicator: filled teal dot (platform data) vs hollow grey ring
  // (official fallback) — a clear, at-a-glance difference between the two sources.
  const dot = isPlatform
    ? 'bg-[#1f8e8b]'
    : 'bg-transparent border border-[#9ca3af]';
  const dotSize = size === 'sm' ? 'w-2 h-2' : 'w-2.5 h-2.5';

  return (
    <span
      className={`inline-flex items-center gap-1.5 ${textSize} text-[#374151]`}
      data-testid="processing-time-badge"
      data-source={estimate.source}
    >
      <span className={`rounded-full shrink-0 ${dotSize} ${dot}`} aria-hidden />
      <span>
        Est. processing: <span className="font-medium">{range}</span>{' '}
        {isPlatform ? (
          <span className="text-[#6b7280]">
            (based on {estimate.sample_size} similar{' '}
            {estimate.sample_size === 1 ? 'case' : 'cases'})
          </span>
        ) : (
          <span className="text-[#6b7280]">
            (
            {estimate.source_url ? (
              <a
                href={estimate.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="underline hover:text-[#374151]"
              >
                official estimate
              </a>
            ) : (
              'official estimate'
            )}{' '}
            — insufficient platform data)
          </span>
        )}
      </span>
    </span>
  );
};
