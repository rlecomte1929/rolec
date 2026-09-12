import { describe, expect, it } from 'vitest';
import { resolveOverviewState, OVERVIEW_DEGRADED_MESSAGE } from './overviewResolution';

const counts = { linkedCount: 0, pendingCount: 0 };

describe('resolveOverviewState', () => {
  it('shows the manual-claim onboarding only when the overview actually resolved empty', () => {
    const out = resolveOverviewState({ ...counts });
    expect(out.unresolved).toBe(false);
    expect(out.showManualClaim).toBe(true);
    expect(out.showAssignmentSections).toBe(false);
  });

  // REGRESSION: a failed fetch returns linkedCount 0 alongside overviewError, so the
  // count-derived "you have no case" claim used to render underneath the error alert.
  it('never claims "no case" while the overview is in an error state', () => {
    const out = resolveOverviewState({ ...counts, overviewError: 'Something went wrong on our side.' });
    expect(out.unresolved).toBe(true);
    expect(out.showManualClaim).toBe(false);
    expect(out.showAssignmentSections).toBe(false);
  });

  // The backend swallows a build failure into HTTP 200 + overview_degraded, so zero
  // counts arrive on a successful response. Same claim, same suppression.
  it('never claims "no case" when the backend flagged the payload degraded', () => {
    const out = resolveOverviewState({ ...counts, overviewDegraded: true });
    expect(out.unresolved).toBe(true);
    expect(out.showManualClaim).toBe(false);
    expect(out.showAssignmentSections).toBe(false);
  });

  it('keeps the resolved-and-linked path unchanged', () => {
    const out = resolveOverviewState({ linkedCount: 2, pendingCount: 0 });
    expect(out.unresolved).toBe(false);
    expect(out.showManualClaim).toBe(false);
    expect(out.showAssignmentSections).toBe(true);
  });

  it('keeps the resolved-and-pending-only path unchanged', () => {
    const out = resolveOverviewState({ linkedCount: 0, pendingCount: 1 });
    expect(out.showManualClaim).toBe(false);
    expect(out.showAssignmentSections).toBe(true);
  });

  it('still renders rows it actually has, even when degraded', () => {
    const out = resolveOverviewState({ linkedCount: 1, pendingCount: 0, overviewDegraded: true });
    expect(out.unresolved).toBe(true);
    expect(out.showManualClaim).toBe(false);
    expect(out.showAssignmentSections).toBe(true);
  });

  it('offers a degraded message that does not blame the reader', () => {
    expect(OVERVIEW_DEGRADED_MESSAGE).not.toMatch(/your connection/i);
    expect(OVERVIEW_DEGRADED_MESSAGE.length).toBeGreaterThan(0);
  });
});
