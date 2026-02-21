import React, { useState } from 'react';
import { Card, Badge, Button } from '../../components/antigravity';
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

const MapPinIcon = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
    <circle cx="12" cy="10" r="3" />
  </svg>
);

const TransitIcon = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
    <rect x="1" y="3" width="15" height="16" rx="2" />
    <path d="M16 8h4l2 4v4h-6" />
    <circle cx="5.5" cy="18.5" r="2.5" />
    <circle cx="18.5" cy="18.5" r="2.5" />
  </svg>
);

/** Build Google Maps URL for a location */
function mapsUrl(query: string) {
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
}

/** Build Google Maps directions URL: office → destination, transit */
function mapsDirectionsUrl(origin: string, destination: string) {
  return `https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent(origin)}&destination=${encodeURIComponent(destination)}&travelmode=transit`;
}

function RecCard({
  item,
  category,
  criteriaEcho,
  defaultExpanded = false,
  isInPackage,
  onTogglePackage,
}: {
  item: RecommendationItem;
  category: string;
  criteriaEcho?: Record<string, unknown>;
  defaultExpanded?: boolean;
  isInPackage: boolean;
  onTogglePackage: () => void;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const tier = item.tier || 'ok';
  const avail = item.metadata?.availability_level || 'high';
  const isScarce = avail === 'low' || avail === 'scarce';
  const cost = item.metadata?.estimated_cost_usd;
  const costType = item.metadata?.cost_type;
  const costLabel =
    cost != null
      ? costType === 'monthly'
        ? `USD ${cost.toLocaleString()}/mo`
        : costType === 'annual'
          ? `USD ${cost.toLocaleString()}/yr`
          : `USD ${cost.toLocaleString()}`
      : null;

  const mapQuery = item.metadata?.map_query as string | undefined;
  const officeAddress = (criteriaEcho?.office_address as string) || '';
  const showMapActions = mapQuery && (category === 'living_areas' || category === 'schools');

  return (
    <Card
      padding="md"
      className={`hover:shadow-md transition-shadow ${isInPackage ? 'ring-2 ring-[#0b2b43]' : ''}`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-[#0b2b43]">{item.name}</h3>
          <div className="flex flex-wrap items-center gap-2 mt-1">
            <span className="text-lg font-bold text-[#0b2b43]">{item.score}/100</span>
            <span
              className={`px-2 py-0.5 rounded text-xs font-medium ${TIER_COLORS[tier] || TIER_COLORS.ok}`}
            >
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
          {costLabel && (
            <p className="text-sm font-medium text-[#0b2b43] mt-1">{costLabel}</p>
          )}
          <p className="text-sm text-[#4b5563] mt-2">{item.summary}</p>
          {item.pros.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {item.pros.map((p) => (
                <Badge key={p} variant="success" size="sm">
                  {p}
                </Badge>
              ))}
            </div>
          )}
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-sm text-[#0b2b43] hover:underline"
          >
            {expanded ? 'Hide details' : 'Why this? ▼'}
          </button>
          {showMapActions && (
            <>
              <a
                href={mapsUrl(mapQuery!)}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-[#0b2b43] hover:underline flex items-center gap-1"
              >
                <MapPinIcon />
                View on map
              </a>
              {officeAddress && (
                <a
                  href={mapsDirectionsUrl(officeAddress, mapQuery!)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-[#0b2b43] hover:underline flex items-center gap-1"
                >
                  <TransitIcon />
                  Commute from office (transit)
                </a>
              )}
            </>
          )}
        </div>
        <Button
          size="sm"
          variant={isInPackage ? 'outline' : undefined}
          onClick={onTogglePackage}
        >
          {isInPackage ? '✓ In package' : 'Add to package'}
        </Button>
      </div>
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
            <div className="text-sm text-amber-700">Cons: {item.cons.join(', ')}</div>
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
  selectedPackage: Map<string, string>;
  onSelectedPackageChange: (pkg: Map<string, string>) => void;
  onStartOver: () => void;
  onViewSummary: () => void;
}

export const RecommendationResults: React.FC<Props> = ({
  results,
  categoryLabels,
  selectedPackage,
  onSelectedPackageChange,
  onStartOver,
  onViewSummary,
}) => {
  const entries = Object.entries(results);
  const [activeTab, setActiveTab] = useState(entries[0]?.[0] ?? '');

  if (entries.length === 0) return null;

  const togglePackage = (category: string, itemId: string) => {
    const next = new Map(selectedPackage);
    if (next.get(category) === itemId) {
      next.delete(category);
    } else {
      next.set(category, itemId);
    }
    onSelectedPackageChange(next);
  };

  const packageCount = selectedPackage.size;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h2 className="text-xl font-semibold text-[#0b2b43]">Your recommendations</h2>
        <div className="flex items-center gap-3">
          {packageCount > 0 && (
            <Button onClick={onViewSummary}>
              View package ({packageCount}) →
            </Button>
          )}
          <button onClick={onStartOver} className="text-sm text-[#0b2b43] hover:underline">
            Start over
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 border-b border-[#e2e8f0] pb-4">
        {entries.map(([category, res]) => (
          <button
            key={category}
            onClick={() => setActiveTab(category)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === category
                ? 'bg-[#0b2b43] text-white'
                : 'bg-white border border-[#e2e8f0] text-[#4b5563] hover:border-[#0b2b43] hover:text-[#0b2b43]'
            }`}
          >
            {categoryLabels[category] || category}
            <span className="ml-1.5 text-xs opacity-80">
              ({res.recommendations.length})
            </span>
          </button>
        ))}
      </div>

      {entries.map(([category, res]) =>
        activeTab === category ? (
          <div key={category}>
            <h3 className="text-lg font-medium text-[#0b2b43] mb-4">
              {categoryLabels[category] || category}
            </h3>
            <p className="text-sm text-[#6b7280] mb-4">
              Choose one option per service to build your relocation package. You can compare costs
              with your HR policy in the summary.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {res.recommendations.map((item, idx) => (
                <RecCard
                  key={item.item_id}
                  item={item}
                  category={category}
                  criteriaEcho={res.criteria_echo}
                  defaultExpanded={idx === 0}
                  isInPackage={selectedPackage.get(category) === item.item_id}
                  onTogglePackage={() => togglePackage(category, item.item_id)}
                />
              ))}
            </div>
          </div>
        ) : null
      )}
    </div>
  );
};
