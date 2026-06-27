/**
 * N11-FU2 (AIQ-851 follow-up) — low-confidence warning in the HR policy
 * extraction review UI.
 *
 * Validates that a per-field confidence below the 0.5 "verify manually" tier
 * renders a visible warning indicator in the review row, and that a
 * high-confidence field does not.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import {
  ReviewRow,
  isLowConfidence,
  LOW_CONFIDENCE_THRESHOLD,
} from '../PolicyReviewQueuePage';
import type { ReviewQueueItem } from '../../../../api/policyBuilderPipeline';

// The page module constructs the Supabase client at import time, which needs
// env vars absent in the test runner. Mock it (hoisted before the import below).
vi.mock('../../../../api/supabase', () => ({
  supabase: {
    auth: {
      getSession: () => Promise.resolve({ data: { session: null } }),
      onAuthStateChange: () => ({ data: { subscription: { unsubscribe() {} } } }),
    },
    from: () => ({ select: () => ({}) }),
  },
}));

afterEach(cleanup);

function makeItem(overrides: Partial<ReviewQueueItem> = {}): ReviewQueueItem {
  return {
    id: 'fact-1',
    category_code: 'housing_allowance',
    category_display_name: 'Housing allowance',
    tier: null,
    value: 2500,
    unit: 'month',
    currency: 'EUR',
    source_doc: 'policy.pdf',
    source_page: 3,
    source_quote: 'Housing allowance: EUR 2,500 / month.',
    confidence_score: 0.95,
    ambiguity_flag: false,
    status: 'pending',
    hr_override_value: null,
    rejection_note: null,
    conflicts: [],
    fact_type: 'benefit',
    snapshot_id: 'snap-1',
    ...overrides,
  };
}

function renderRow(item: ReviewQueueItem) {
  return render(
    <table>
      <tbody>
        <ReviewRow
          item={item}
          onApprove={() => {}}
          onEdit={() => {}}
          onReject={() => {}}
          loading={false}
        />
      </tbody>
    </table>,
  );
}

describe('isLowConfidence', () => {
  it('flags scores below the 0.5 threshold', () => {
    expect(isLowConfidence(0.1)).toBe(true);
    expect(isLowConfidence(0.49)).toBe(true);
  });

  it('does not flag scores at or above the threshold, or null', () => {
    expect(isLowConfidence(LOW_CONFIDENCE_THRESHOLD)).toBe(false);
    expect(isLowConfidence(0.9)).toBe(false);
    expect(isLowConfidence(null)).toBe(false);
  });
});

describe('ReviewRow low-confidence warning', () => {
  it('renders a visible warning indicator for a field with confidence < 0.5', () => {
    renderRow(makeItem({ confidence_score: 0.1 }));
    expect(
      screen.getByLabelText('Low confidence — verify manually'),
    ).toBeInTheDocument();
  });

  it('does not render the warning for a high-confidence field', () => {
    renderRow(makeItem({ confidence_score: 0.95 }));
    expect(
      screen.queryByLabelText('Low confidence — verify manually'),
    ).not.toBeInTheDocument();
  });
});
