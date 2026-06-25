import React from 'react';
import type { SourceRecordDTO } from '../../types';
import { StalenessBadge } from '../antigravity/StalenessBadge';
import { assertSafeUrl } from '../../utils/url';

interface CitationsProps {
  sources: SourceRecordDTO[];
}

/**
 * I-2 (BureauAI audit): cited-source list, now with a freshness signal.
 * Each source carries an additive StalenessBadge keyed on `retrievedAt` (when we
 * last fetched/verified it) — it renders nothing while the source is fresh, so
 * the citation list is unchanged for current sources and only flags stale ones.
 * (A trust-tier badge would need `SourceRecordDTO` to carry a tier — deferred
 * with the step-level citation work, W1-4.)
 */
export const Citations: React.FC<CitationsProps> = ({ sources }) => {
  if (!sources.length) return null;
  return (
    <div className="mt-2 space-y-1 text-xs text-[#6b7280]">
      {sources.slice(0, 3).map((source) => (
        <div key={source.id} className="flex items-center gap-2">
          <a
            href={assertSafeUrl(source.url)}
            target="_blank"
            rel="noreferrer"
            title={`Retrieved ${new Date(source.retrievedAt).toLocaleDateString('en-US')}`}
            className="text-[#0b2b43] hover:underline"
          >
            {source.publisherDomain}
          </a>
          <StalenessBadge lastVerified={source.retrievedAt} sourceUrl={source.url} />
        </div>
      ))}
    </div>
  );
};
