/**
 * ServicesContextBanner (AIQ-1249d)
 *
 * Compact "Services for your {origin} → {dest} move · {date}" banner shown above
 * the ServicesNavRibbon so the employee always sees which move the services flow
 * is scoped to. Renders nothing when neither origin nor destination is known.
 */
import React from 'react';

interface ServicesContextBannerProps {
  originCity?: string | null;
  destCity?: string | null;
  /** ISO date (YYYY-MM-DD) of the move; optional. */
  date?: string | null;
}

function formatMoveDate(date?: string | null): string | null {
  const raw = (date || '').trim();
  if (!raw) return null;
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return raw;
  return parsed.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

export const ServicesContextBanner: React.FC<ServicesContextBannerProps> = ({
  originCity,
  destCity,
  date,
}) => {
  const origin = (originCity || '').trim();
  const dest = (destCity || '').trim();
  if (!origin && !dest) return null;
  const corridor = origin && dest ? `${origin} → ${dest}` : dest || origin;
  const when = formatMoveDate(date);

  return (
    <div
      className="mb-4 rounded-lg border border-[#e2e8f0] bg-[#f8fafc] px-4 py-2.5 text-sm text-[#334155]"
      data-testid="services-context-banner"
    >
      Services for your{' '}
      <span className="font-semibold text-[#0b2b43]">{corridor}</span> move
      {when ? <span className="text-[#64748b]"> · {when}</span> : null}
    </div>
  );
};
