import '@testing-library/jest-dom/vitest';
import React, { useState } from 'react';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// AIQ-1691: the Add-to-package audit log (POST /api/ai/decisions) 400'd on every 2nd+
// pick per category. Root cause: a comparison vendor added AFTER the top match is
// already shortlisted is not an override, but logDecision derived decision='override'
// from rank>0 and sent it with a null reason — which the endpoint rejects (reason
// required for override). This test reproduces the rapid-adds scenario and asserts the
// audit log is NEVER an override-with-no-reason.

const createAIDecision = vi.fn(() => Promise.resolve({} as unknown));
vi.mock('../../../api/aiDecisions', () => ({
  createAIDecision: (...a: unknown[]) => createAIDecision(...a),
}));
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

const results: Record<string, RecommendationResponse> = {
  movers: {
    category: 'movers',
    generated_at: '',
    criteria_echo: {},
    // rank 0 = top match, then two comparison vendors.
    recommendations: [mkItem('m-top'), mkItem('m-2'), mkItem('m-3')],
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

const addButtons = () => screen.getAllByRole('button', { name: /Add to package/i });

describe('AIQ-1691 — Add-to-package audit log never 400s', () => {
  beforeEach(() => createAIDecision.mockClear());
  afterEach(cleanup);

  it('logs decision=accept for the top match AND for comparison vendors added after it', () => {
    render(<Harness />);

    // 1st pick: the top match (rank 0) → accept.
    fireEvent.click(addButtons()[0]);
    // 2nd + 3rd picks: comparison vendors, top match already shortlisted → still accept,
    // NOT override. (Before the fix these sent decision='override' + null reason → 400.)
    fireEvent.click(addButtons()[0]);
    fireEvent.click(addButtons()[0]);

    const bodies = createAIDecision.mock.calls.map((c) => c[0] as { decision: string; reason?: string });
    expect(bodies.length).toBe(3);
    for (const body of bodies) {
      expect(body.decision).toBe('accept');
    }
    // The exact 400 condition — an override with no reason — must never be sent.
    expect(bodies.some((b) => b.decision === 'override' && !b.reason)).toBe(false);
  });
});
