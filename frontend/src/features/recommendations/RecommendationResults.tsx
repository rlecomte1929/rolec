import React, { useState } from 'react';
import { Card, Badge, Button, Alert } from '../../components/antigravity';
import type { RecommendationItem, RecommendationResponse } from './types';
import { formatEstimationFromUsd } from '../services/servicesCurrency';
import { createAIDecision } from '../../api/aiDecisions';
import { rateProvider } from './api';

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

const WARNING_LABELS: Record<string, string> = {
  above_budget: 'Above budget',
  above_policy: 'Above policy limit',
  low_availability: 'Limited availability',
  wrong_destination: 'Wrong destination',
  waitlist: 'Waitlist may apply',
};

/**
 * Friendly labels for the score-dimension keys returned by each scoring
 * plugin. Plugins use snake_case (coverage / family_coverage / etc.);
 * this mapping turns them into title-case for the UI. Unknown keys
 * fall back to a generic prettifier (snake_case → Title Case).
 */
const SCORE_DIMENSION_LABELS: Record<string, string> = {
  coverage: 'Coverage match',
  deductible: 'Deductible',
  family: 'Family coverage',
  family_coverage: 'Family coverage',
  rating: 'User rating',
  availability: 'Availability',
  green: 'Green energy',
  flex: 'Flexibility',
  flex_score: 'Flexibility',
  trans: 'Transparent pricing',
  curriculum: 'Curriculum match',
  language: 'Language match',
  distance: 'Distance to office',
  experience: 'Experience',
  budget: 'Budget fit',
  speed: 'Service speed',
  insurance: 'Insurance included',
};

function prettyDimensionLabel(key: string): string {
  if (SCORE_DIMENSION_LABELS[key]) return SCORE_DIMENSION_LABELS[key];
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * One scoring-dimension chip. Color reflects strength so HR/employee
 * can scan the row visually (green = strong contributor, amber = mid,
 * red = weak). Score is on a 0–100 scale by plugin convention.
 */
function ScoreDimensionChip({ label, value }: { label: string; value: number }) {
  const tone =
    value >= 80
      ? 'bg-green-100 text-green-800 border-green-200'
      : value >= 50
        ? 'bg-amber-100 text-amber-800 border-amber-200'
        : 'bg-red-50 text-red-700 border-red-200';
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-xs font-medium ${tone}`}
      title={`Dimension contributes ${value.toFixed(0)} of 100 to the overall score`}
    >
      <span>{prettyDimensionLabel(label)}</span>
      <span className="font-semibold">{value.toFixed(0)}</span>
    </span>
  );
}

function RatingStars({ rating }: { rating?: number }) {
  if (rating == null || typeof rating !== 'number' || !Number.isFinite(rating)) return null;
  const clamped = Math.max(0, Math.min(5, rating));
  const full = Math.floor(clamped);
  const half = clamped % 1 >= 0.5;
  const empty = Math.max(0, 5 - full - (half ? 1 : 0));
  return (
    <span className="inline-flex items-center gap-0.5 text-amber-500">
      {'★'.repeat(full)}
      {half && '½'}
      {'☆'.repeat(empty)}
      <span className="ml-1 text-sm text-[#6b7280]">({clamped.toFixed(1)})</span>
    </span>
  );
}

/**
 * CATALOG-3 — interactive 1-5 star rater. Posts the employee's rating for this
 * provider on the current case; the backend aggregates it into the signal the
 * recommender scores. Only rendered when a caseId is in scope.
 */
function RateProviderControl({ supplierId, caseId }: { supplierId: string; caseId: string }) {
  const [hover, setHover] = useState(0);
  const [submitted, setSubmitted] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(false);

  const send = async (score: number) => {
    setSaving(true);
    setError(false);
    try {
      await rateProvider(supplierId, { caseId, score });
      setSubmitted(score);
    } catch {
      setError(true);
    } finally {
      setSaving(false);
    }
  };

  if (submitted != null) {
    return <span className="text-xs text-[#1f8e8b]">Thanks — you rated this {submitted}/5.</span>;
  }

  return (
    <span className="inline-flex items-center gap-1">
      <span className="text-xs text-[#6b7280]">Was this provider helpful?</span>
      <span className="inline-flex" role="radiogroup" aria-label="Rate this provider 1 to 5">
        {[1, 2, 3, 4, 5].map((n) => (
          <Button
            key={n}
            unstyled
            disabled={saving}
            aria-label={`${n} star${n > 1 ? 's' : ''}`}
            className={`px-0.5 text-base leading-none ${n <= hover ? 'text-amber-500' : 'text-[#cbd5e1]'} hover:text-amber-500`}
            onMouseEnter={() => setHover(n)}
            onMouseLeave={() => setHover(0)}
            onClick={() => send(n)}
          >
            ★
          </Button>
        ))}
      </span>
      {error && <span className="text-xs text-red-600">Couldn’t save — try again.</span>}
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
  displayCurrency,
  pendingConfirmActive,
  pendingConfirmSubmitting,
  topMatchName,
  onConfirmPick,
  onCancelPick,
  caseId,
}: {
  item: RecommendationItem;
  category: string;
  criteriaEcho?: Record<string, unknown>;
  defaultExpanded?: boolean;
  isInPackage: boolean;
  onTogglePackage: () => void;
  displayCurrency: string;
  /** When true, render the inline reason-capture for an AI-002 override pick. */
  pendingConfirmActive: boolean;
  /** Submit in flight — disables buttons, swaps Confirm label. */
  pendingConfirmSubmitting: boolean;
  /** Name of the rank-1 recommendation in this category (used in the prompt copy). */
  topMatchName?: string;
  onConfirmPick: (reason: string) => void;
  onCancelPick: () => void;
  /** CATALOG-3 — current case id; enables the provider rating control when set. */
  caseId?: string;
}) {
  const [overrideReason, setOverrideReason] = useState('');
  // Clear local reason text whenever this card stops being the active confirm target.
  React.useEffect(() => {
    if (!pendingConfirmActive) setOverrideReason('');
  }, [pendingConfirmActive]);
  const reasonMissing = !overrideReason.trim();
  const [expanded, setExpanded] = useState(defaultExpanded);
  const tier = item.tier || 'ok';
  const avail = item.metadata?.availability_level || 'high';
  const expl = item.explanation;
  const matchReasons = expl?.match_reasons?.length ? expl.match_reasons : item.pros;
  const warningFlags = expl?.warning_flags ?? [];
  const isScarce = avail === 'low' || avail === 'scarce';
  const costUsd = item.metadata?.estimated_cost_usd;
  const costType = item.metadata?.cost_type;
  const costLabel = formatEstimationFromUsd(costUsd, costType, displayCurrency);

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
            {caseId && <RateProviderControl supplierId={item.item_id} caseId={caseId} />}
            {isScarce && (
              <span className="px-2 py-0.5 rounded text-xs bg-amber-100 text-amber-800">
                Limited availability
              </span>
            )}
            {item.metadata?.company_preferred && (
              <span className="px-2 py-0.5 rounded text-xs bg-accent-100 text-accent-800 font-medium">
                Preferred by your company
              </span>
            )}
          </div>
          {costLabel && (
            <p className="text-sm font-medium text-[#0b2b43] mt-1">{costLabel}</p>
          )}
          <p className="text-sm text-[#4b5563] mt-2">
            {expl?.explanation_summary || item.summary}
          </p>
          {matchReasons.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {matchReasons.slice(0, 5).map((p) => (
                <Badge key={p} variant="success" size="sm">
                  {p}
                </Badge>
              ))}
            </div>
          )}
          {warningFlags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {warningFlags.map((flag) => (
                <span
                  key={flag}
                  className="px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800 border border-amber-200"
                >
                  ⚠ {WARNING_LABELS[flag] ?? flag}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Button unstyled
            onClick={() => setExpanded(!expanded)}
            className="text-sm text-[#0b2b43] hover:underline"
          >
            {expanded ? 'Hide details' : 'Why this? ▼'}
          </Button>
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
      {/* AI-003: inline override-reason capture when HR/employee picks a lower-ranked
          vendor. The confirm flow appears here (not via modal) so the user can keep
          the other recommendations visible while writing their reason. Submitting
          writes an ai_decisions row with decision='override' for EU AI Act Art. 14. */}
      {pendingConfirmActive && (
        <div className="mt-3 pt-3 border-t border-accent-200 bg-accent-50/50 -mx-6 -mb-6 px-6 pb-4 rounded-b-xl">
          <p className="text-xs font-semibold text-accent-800">
            Why this one
            {topMatchName ? <> over our top match <span className="font-normal italic">{topMatchName}</span></> : ' instead of the top match'}?
            <span className="text-rose-500 ml-1">*</span>
          </p>
          <textarea
            value={overrideReason}
            onChange={(e) => setOverrideReason(e.target.value)}
            rows={2}
            placeholder="Explain why this option fits this case better."
            className="mt-2 w-full rounded-md border border-accent-200 px-2.5 py-1.5 text-sm text-slate-700 placeholder:text-slate-300 focus:outline-none focus:ring-2 focus:ring-accent-200 resize-none bg-white"
            autoFocus
          />
          <div className="mt-2 flex items-center justify-between gap-3">
            <p className="text-[11px] text-accent-500">Logged for human oversight audit · EU AI Act Art. 14</p>
            <div className="flex items-center gap-2">
              <Button unstyled
                type="button"
                onClick={onCancelPick}
                disabled={pendingConfirmSubmitting}
                className="px-3 py-1.5 text-xs text-slate-600 hover:text-slate-800 transition-colors disabled:opacity-50"
              >
                Cancel
              </Button>
              <Button unstyled
                type="button"
                onClick={() => onConfirmPick(overrideReason.trim())}
                disabled={pendingConfirmSubmitting || reasonMissing}
                className="px-3 py-1.5 text-xs font-medium rounded-md bg-amber-500 text-white hover:bg-amber-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {pendingConfirmSubmitting ? 'Recording…' : 'Confirm pick'}
              </Button>
            </div>
          </div>
        </div>
      )}
      {expanded && (
        <div className="mt-3 pt-3 border-t border-[#e2e8f0] space-y-3">
          <p className="text-sm text-[#4b5563]">{item.rationale}</p>
          {(() => {
            const dims = expl?.score_dimensions ?? item.breakdown ?? {};
            const entries = Object.entries(dims).filter(
              ([, v]) => typeof v === 'number'
            ) as Array<[string, number]>;
            if (entries.length === 0) return null;
            // Sort highest contribution first so the strongest factors
            // lead — that's what HR / employees actually want to scan.
            entries.sort((a, b) => b[1] - a[1]);
            return (
              <div>
                <div className="text-xs font-medium text-[#0b2b43] mb-1.5">
                  How this score was built
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {entries.map(([k, v]) => (
                    <ScoreDimensionChip key={k} label={k} value={v} />
                  ))}
                </div>
                <p className="mt-1.5 text-xs text-[#6b7280]">
                  Each dimension is 0–100. The overall score weighs them
                  per the {category} plugin's formula. HR-configurable
                  weights ship in a follow-up sprint.
                </p>
              </div>
            );
          })()}
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
  displayCurrency: string;
  /** CATALOG-3 — current case id; enables provider rating on each card. */
  caseId?: string;
}

export const RecommendationResults: React.FC<Props> = ({
  results,
  categoryLabels,
  selectedPackage,
  onSelectedPackageChange,
  onStartOver,
  onViewSummary,
  displayCurrency,
  caseId,
}) => {
  const entries = Object.entries(results);
  const [activeTab, setActiveTab] = useState(entries[0]?.[0] ?? '');

  // AI-003 — pending override-pick state. When set, the matching RecCard
  // renders its inline reason-capture; submitting writes an ai_decisions row.
  const [pendingPick, setPendingPick] = useState<{
    category: string;
    item: RecommendationItem;
    rank: number; // 0-indexed; rank 0 == top match (never triggers this UI)
  } | null>(null);
  const [pendingSubmitting, setPendingSubmitting] = useState(false);
  const [logError, setLogError] = useState<string | null>(null);

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

  /**
   * Fire-and-forget POST to /api/ai/decisions. Never blocks the selection —
   * if the log fails, the user's pick still goes through and a non-blocking
   * error Alert appears at the top of the page. Per AI-002 / Art. 14:
   * accept = picked the top-ranked item, override = picked a lower rank.
   */
  const logDecision = (
    category: string,
    item: RecommendationItem,
    rank: number,
    reason: string | null
  ): void => {
    const decision = rank === 0 ? 'accept' : 'override';
    createAIDecision({
      feature: `service_recommendation_${category}`,
      recommendation_id: item.item_id,
      ai_output: {
        item_id: item.item_id,
        name: item.name,
        score: item.score,
        tier: item.tier,
        rank: rank + 1, // 1-indexed in audit payload for human-readability
        explanation: item.explanation,
      },
      decision,
      reason: reason ?? undefined,
    }).catch((e) => {
      const msg = e instanceof Error ? e.message : 'Failed to log AI decision';
      setLogError(`${msg} — your selection was saved, but the audit log entry could not be written.`);
      window.setTimeout(() => setLogError(null), 8000);
    });
  };

  /**
   * Single entry point for a vendor pick from the card's "Add to package" button.
   * Branches on:
   *   - already-in-package (deselection): toggle off, no log (append-only — the
   *     original "pick" event remains in the audit; removal is local state).
   *   - rank 0 (top match): commit + fire 'accept' log in background.
   *   - rank > 0: open the inline reason-capture; commit happens on Confirm.
   */
  const handleCardToggle = (category: string, item: RecommendationItem, rank: number) => {
    const currentlyInPackage = selectedPackage.get(category) === item.item_id;
    if (currentlyInPackage) {
      togglePackage(category, item.item_id);
      return;
    }
    if (rank === 0) {
      togglePackage(category, item.item_id);
      logDecision(category, item, 0, null);
      return;
    }
    setPendingPick({ category, item, rank });
  };

  const confirmPendingPick = async (reason: string) => {
    if (!pendingPick || !reason) return;
    setPendingSubmitting(true);
    try {
      // Commit the selection first (local + debounced server sync) so the user's
      // intent is reflected immediately even if the audit log POST is slow.
      togglePackage(pendingPick.category, pendingPick.item.item_id);
      logDecision(pendingPick.category, pendingPick.item, pendingPick.rank, reason);
      setPendingPick(null);
    } finally {
      setPendingSubmitting(false);
    }
  };

  const cancelPendingPick = () => {
    if (pendingSubmitting) return;
    setPendingPick(null);
  };

  const packageCount = selectedPackage.size;

  return (
    <div className="space-y-6">
      {logError && (
        <Alert variant="error">
          <p>{logError}</p>
        </Alert>
      )}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h2 className="text-xl font-semibold text-[#0b2b43]">Your recommendations</h2>
        <div className="flex items-center gap-3">
          {packageCount > 0 && (
            <Button onClick={onViewSummary}>
              View package ({packageCount}) →
            </Button>
          )}
          <Button unstyled onClick={onStartOver} className="text-sm text-[#0b2b43] hover:underline">
            Start over
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 border-b border-[#e2e8f0] pb-4">
        {entries.map(([category, res]) => (
          <Button unstyled
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
          </Button>
        ))}
      </div>

      {entries.map(([category, res]) =>
        activeTab === category ? (
          <div key={category}>
            <h3 className="text-lg font-medium text-[#0b2b43] mb-4">
              {categoryLabels[category] || category}
            </h3>
            <p className="text-sm text-[#6b7280] mb-4">
              Choose one option per service to build your relocation package. Estimates use your selected currency
              (set on Select services). You can compare costs with your HR policy in the summary.
            </p>
            {res.recommendations.length === 0 &&
            (res.criteria_echo as Record<string, unknown> | undefined)?.hr_curation_status === 'hr_pending' ? (
              <div className="rounded-lg border border-[#fde68a] bg-[#fffbeb] px-4 py-3 text-sm text-[#92400e]">
                <strong className="block text-[#0b2b43] mb-1">Your HR is finalizing providers for this category.</strong>
                Once HR has approved the vendors for your destination, they'll show up here automatically.
                Until then, hold off on this category — you can build the rest of your package and come back.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {res.recommendations.map((item, idx) => {
                  const isPendingThisCard =
                    pendingPick?.category === category && pendingPick.item.item_id === item.item_id;
                  return (
                    <RecCard
                      key={item.item_id}
                      item={item}
                      category={category}
                      criteriaEcho={res.criteria_echo}
                      defaultExpanded={idx === 0}
                      isInPackage={selectedPackage.get(category) === item.item_id}
                      onTogglePackage={() => handleCardToggle(category, item, idx)}
                      displayCurrency={displayCurrency}
                      pendingConfirmActive={isPendingThisCard}
                      pendingConfirmSubmitting={isPendingThisCard && pendingSubmitting}
                      topMatchName={res.recommendations[0]?.name}
                      onConfirmPick={confirmPendingPick}
                      onCancelPick={cancelPendingPick}
                      caseId={caseId}
                    />
                  );
                })}
              </div>
            )}
          </div>
        ) : null
      )}
    </div>
  );
};
