import React, { useState } from 'react';
import { Card, Badge } from '../../components/antigravity';
import type { RecommendationItem, RecommendationResponse } from './types';

const TIER_LABELS: Record<string, string> = {
  best_match: 'Best match',
  good_fit: 'Good fit',
  ok: 'OK',
  weak: 'Consider',
};

const TIER_COLORS: Record<string, string> = {
  best_match: 'bg-green-100 text-green-800',
  good_fit: 'bg-blue-100 text-blue-800',
  ok: 'bg-amber-100 text-amber-800',
  weak: 'bg-slate-100 text-slate-600',
};

function RatingStars({ rating }: { rating?: number }) {
  if (rating == null) return null;
  const full = Math.floor(rating);
  const half = rating % 1 >= 0.5;
  return (
    <span className="inline-flex items-center gap-0.5 text-amber-500">
      {'★'.repeat(full)}
      {half && '½'}
      {'☆'.repeat(5 - full - (half ? 1 : 0))}
      <span className="ml-1 text-sm text-[#6b7280]">({rating.toFixed(1)})</span>
    </span>
  );
}

function RecCard({ item, defaultExpanded = false }: { item: RecommendationItem; defaultExpanded?: boolean }) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const tier = item.tier || 'ok';
  const avail = item.metadata?.availability_level || 'high';
  const isScarce = avail === 'low' || avail === 'scarce';

  return (
    <Card padding="md" className="hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-[#0b2b43]">{item.name}</h3>
          <div className="flex flex-wrap items-center gap-2 mt-1">
            <span className="text-lg font-bold text-[#0b2b43]">{item.score}/100</span>
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${TIER_COLORS[tier] || TIER_COLORS.ok}`}>
              {TIER_LABELS[tier] || tier}
            </span>
            {item.metadata?.rating != null && (
              <RatingStars rating={item.metadata.rating} />
            )}
            {isScarce && (
              <span className="px-2 py-0.5 rounded text-xs bg-amber-100 text-amber-800">
                Limited availability
              </span>
            )}
          </div>
          <p className="text-sm text-[#4b5563] mt-2">{item.summary}</p>
          {item.pros.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {item.pros.map((p) => (
                <Badge key={p} variant="success" size="sm">{p}</Badge>
              ))}
            </div>
          )}
        </div>
      </div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="mt-3 text-sm text-[#0b2b43] hover:underline"
      >
        {expanded ? 'Hide details' : 'Why this? ▼'}
      </button>
      {expanded && (
        <div className="mt-3 pt-3 border-t border-[#e2e8f0] space-y-2">
          <p className="text-sm text-[#4b5563]">{item.rationale}</p>
          {Object.keys(item.breakdown || {}).length > 0 && (
            <div className="space-y-1">
              <span className="text-xs font-medium text-[#6b7280]">Score breakdown:</span>
              <div className="flex flex-wrap gap-2">
                {Object.entries(item.breakdown).map(([k, v]) => (
                  <span key={k} className="text-xs bg-[#f1f5f9] px-2 py-0.5 rounded">
                    {k}: {typeof v === 'number' ? v.toFixed(0) : v}
                  </span>
                ))}
              </div>
            </div>
          )}
          {item.cons.length > 0 && (
            <div className="text-sm text-amber-700">
              Cons: {item.cons.join(', ')}
            </div>
          )}
          {item.metadata?.next_available_days != null && isScarce && (
            <p className="text-xs text-amber-700">
              Next available in ~{item.metadata.next_available_days} days
            </p>
          )}
        </div>
      )}
    </Card>
  );
}

interface Props {
  results: Record<string, RecommendationResponse>;
  categoryLabels: Record<string, string>;
  onStartOver: () => void;
}

export const RecommendationResults: React.FC<Props> = ({
  results,
  categoryLabels,
  onStartOver,
}) => {
  const entries = Object.entries(results);
  if (entries.length === 0) return null;

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-[#0b2b43]">Your recommendations</h2>
        <button
          onClick={onStartOver}
          className="text-sm text-[#0b2b43] hover:underline"
        >
          Start over
        </button>
      </div>
      {entries.map(([category, res]) => (
        <div key={category}>
          <h3 className="text-lg font-medium text-[#0b2b43] mb-4">
            {categoryLabels[category] || category}
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {res.recommendations.map((item, idx) => (
              <RecCard key={item.item_id} item={item} defaultExpanded={idx === 0} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};
