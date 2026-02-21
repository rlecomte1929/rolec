import React, { useState, useEffect } from 'react';
import { Card, Button } from '../../components/antigravity';
import { employeeAPI } from '../../api/client';
import type { RecommendationResponse, RecommendationItem } from './types';

/** Category key to policy cap key */
const CATEGORY_TO_CAP: Record<string, string> = {
  housing: 'housing_monthly_usd',
  schools: 'schools_usd',
  movers: 'movers_usd',
};

const CATEGORY_COST_TYPE: Record<string, 'monthly' | 'annual' | 'one_time'> = {
  housing: 'monthly',
  schools: 'annual',
  movers: 'one_time',
};

function getItemCost(item: RecommendationItem, costType: string): number {
  const usd = item.metadata?.estimated_cost_usd;
  if (usd == null) return 0;
  if (costType === 'monthly') return usd;
  if (costType === 'annual') return usd;
  return usd;
}

interface PolicyCaps {
  housing_monthly_usd: number;
  movers_usd: number;
  schools_usd: number;
}

interface Props {
  results: Record<string, RecommendationResponse>;
  selectedPackage: Map<string, string>;
  categoryLabels: Record<string, string>;
  onBack: () => void;
  onStartOver: () => void;
}

export const PackageSummary: React.FC<Props> = ({
  results,
  selectedPackage,
  categoryLabels,
  onBack,
  onStartOver,
}) => {
  const [policyCaps, setPolicyCaps] = useState<PolicyCaps | null>(null);

  useEffect(() => {
    employeeAPI
      .getPolicyCaps()
      .then(setPolicyCaps)
      .catch(() => setPolicyCaps(null));
  }, []);

  const packageItems: { category: string; item: RecommendationItem }[] = [];
  for (const [category, res] of Object.entries(results)) {
    const itemId = selectedPackage.get(category);
    if (!itemId) continue;
    const item = res.recommendations.find((r) => r.item_id === itemId);
    if (item) packageItems.push({ category, item });
  }

  const comparison: { category: string; label: string; total: number; cap: number; covered: number; extra: number }[] =
    [];
  if (policyCaps) {
    for (const { category, item } of packageItems) {
      const capKey = CATEGORY_TO_CAP[category];
      const costType = CATEGORY_COST_TYPE[category] || 'one_time';
      const total = getItemCost(item, costType);
      const cap =
        capKey === 'housing_monthly_usd'
          ? policyCaps.housing_monthly_usd
          : capKey === 'movers_usd'
            ? policyCaps.movers_usd
            : capKey === 'schools_usd'
              ? policyCaps.schools_usd
              : 0;
      const covered = Math.min(total, cap);
      const extra = Math.max(0, total - cap);
      comparison.push({
        category,
        label: categoryLabels[category] || category,
        total,
        cap,
        covered,
        extra,
      });
    }
  }

  const totalPackage = comparison.reduce((s, c) => s + c.total, 0);
  const totalCovered = comparison.reduce((s, c) => s + c.covered, 0);
  const totalExtra = comparison.reduce((s, c) => s + c.extra, 0);

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-[#0b2b43]">My Relocation Service Package</h2>
        <div className="flex gap-2">
          <Button variant="outline" onClick={onBack}>
            ← Edit selections
          </Button>
          <button onClick={onStartOver} className="text-sm text-[#0b2b43] hover:underline">
            Start over
          </button>
        </div>
      </div>

      {packageItems.length === 0 ? (
        <Card padding="lg">
          <p className="text-[#6b7280]">
            No items in your package yet. Go back and add recommendations to compare with your HR policy.
          </p>
          <Button className="mt-4" onClick={onBack}>
            Edit selections
          </Button>
        </Card>
      ) : (
        <>
          <Card padding="lg">
            <h3 className="font-semibold text-[#0b2b43] mb-4">Selected services</h3>
            <ul className="space-y-2">
              {packageItems.map(({ category, item }) => {
                const cost = item.metadata?.estimated_cost_usd;
                const costType = item.metadata?.cost_type || 'one_time';
                const costLabel =
                  costType === 'monthly'
                    ? `USD ${cost?.toLocaleString()}/mo`
                    : costType === 'annual'
                      ? `USD ${cost?.toLocaleString()}/yr`
                      : cost != null
                        ? `USD ${cost.toLocaleString()}`
                        : '—';
                return (
                  <li key={`${category}-${item.item_id}`} className="flex justify-between py-2 border-b border-[#e2e8f0] last:border-0">
                    <span>
                      <strong>{item.name}</strong>
                      <span className="ml-2 text-sm text-[#6b7280]">
                        ({categoryLabels[category] || category})
                      </span>
                    </span>
                    <span className="font-medium text-[#0b2b43]">{costLabel}</span>
                  </li>
                );
              })}
            </ul>
          </Card>

          {policyCaps && comparison.length > 0 && (
            <Card padding="lg">
              <h3 className="font-semibold text-[#0b2b43] mb-2">HR Policy Comparison</h3>
              <p className="text-sm text-[#6b7280] mb-6">
                See how much your company covers vs. what you may pay out of pocket.
              </p>

              <div className="space-y-6 mb-8">
                {comparison.map((c) => (
                  <div key={c.category}>
                    <div className="flex justify-between text-sm mb-2">
                      <span className="font-medium text-[#0b2b43]">{c.label}</span>
                      <span>
                        Total: USD {c.total.toLocaleString()}
                        {c.cap > 0 && (
                          <span className="ml-2 text-[#6b7280]">
                            (Cap: USD {c.cap.toLocaleString()})
                          </span>
                        )}
                      </span>
                    </div>
                    <div className="h-8 flex rounded-lg overflow-hidden bg-[#e2e8f0]">
                      <div
                        className="bg-[#22c55e] flex items-center justify-end pr-2 transition-all"
                        style={{
                          width: c.total > 0 ? `${(c.covered / c.total) * 100}%` : '0%',
                          minWidth: c.covered > 0 ? 48 : 0,
                        }}
                      >
                        {c.covered > 0 && (
                          <span className="text-xs font-medium text-white">Covered</span>
                        )}
                      </div>
                      <div
                        className="bg-[#f97316] flex items-center pl-2 transition-all"
                        style={{
                          width: c.total > 0 ? `${(c.extra / c.total) * 100}%` : '0%',
                          minWidth: c.extra > 0 ? 48 : 0,
                        }}
                      >
                        {c.extra > 0 && (
                          <span className="text-xs font-medium text-white">Extra</span>
                        )}
                      </div>
                    </div>
                    <div className="flex justify-between text-xs text-[#6b7280] mt-1">
                      <span>Company covers: USD {c.covered.toLocaleString()}</span>
                      {c.extra > 0 && (
                        <span className="text-[#f97316] font-medium">
                          You pay: USD {c.extra.toLocaleString()}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              <div className="pt-6 border-t border-[#e2e8f0] space-y-2">
                <div className="flex justify-between font-semibold text-[#0b2b43]">
                  <span>Total package cost</span>
                  <span>USD {totalPackage.toLocaleString()}</span>
                </div>
                <div className="flex justify-between text-[#22c55e]">
                  <span>Company covered</span>
                  <span>USD {totalCovered.toLocaleString()}</span>
                </div>
                {totalExtra > 0 && (
                  <div className="flex justify-between text-[#f97316] font-medium">
                    <span>Your out-of-pocket</span>
                    <span>USD {totalExtra.toLocaleString()}</span>
                  </div>
                )}
              </div>
            </Card>
          )}

          {!policyCaps && (
            <p className="text-sm text-[#6b7280]">
              Policy caps could not be loaded. Cost comparison is based on estimated values from recommendations.
            </p>
          )}
        </>
      )}
    </div>
  );
};
