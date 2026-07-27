import '@testing-library/jest-dom/vitest';
import React, { useState } from 'react';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

// Show-all-vetted: the backend now returns EVERY vetted provider; the UI defaults to
// the top `display_cap` and reveals the rest via "Show N more vetted providers", so no
// vetted provider is unreachable while the top-matches-first signal is preserved.

vi.mock('../../../api/aiDecisions', () => ({ createAIDecision: vi.fn(() => Promise.resolve({})) }));
vi.mock('../../../analytics', () => ({ track: vi.fn() }));
vi.mock('../api', () => ({ rateProvider: vi.fn(() => Promise.resolve({})) }));

import { RecommendationResults } from '../RecommendationResults';
import type { RecommendationItem, RecommendationResponse } from '../types';

const mkItem = (id: string): RecommendationItem => ({
  item_id: id,
  name: `Mover ${id}`,
  score: 80,
  tier: 'good_fit',
  summary: 'summary',
  rationale: 'rationale',
  breakdown: {},
  pros: [],
  cons: [],
  metadata: {},
});

// 12 vetted movers, display default 10 → 2 beyond the default view.
const results: Record<string, RecommendationResponse> = {
  movers: {
    category: 'movers',
    generated_at: '',
    criteria_echo: { display_cap: 10, masters_capped_by_display_limit: 2 },
    recommendations: Array.from({ length: 12 }, (_, i) => mkItem(`m-${i + 1}`)),
  },
};

function Harness() {
  const [pkg, setPkg] = useState<Map<string, string[]>>(new Map());
  return (
    <RecommendationResults
      results={results}
      categoryLabels={{ movers: 'Movers' }}
      selectedPackage={pkg}
      onSelectedPackageChange={setPkg}
      onStartOver={() => {}}
      onViewSummary={() => {}}
      displayCurrency="EUR"
      caseId="c1"
    />
  );
}

const cardButtons = () => screen.getAllByRole('button', { name: /Add to package|In package/i });

describe('AIQ show-all-vetted — every vetted provider is reachable', () => {
  afterEach(cleanup);

  it('defaults to the top display_cap and reveals the rest on "Show N more"', () => {
    render(<Harness />);

    // Default view: only the top 10 of 12 are rendered.
    expect(cardButtons()).toHaveLength(10);

    // The expand control announces the exact reachable overflow (matches the count).
    const showMore = screen.getByRole('button', { name: /Show 2 more vetted providers/i });
    fireEvent.click(showMore);

    // All 12 vetted movers are now reachable.
    expect(cardButtons()).toHaveLength(12);
    // And the control collapses back.
    expect(screen.getByRole('button', { name: /Show fewer/i })).toBeInTheDocument();
  });
});
