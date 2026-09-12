import { describe, expect, it } from 'vitest';
import {
  buildCommandCenterInsights,
  INCOMPLETE_CORRIDOR_LABEL,
  isIncompleteCorridor,
  spendIsTracked,
} from './commandCenterInsights';

describe('commandCenterInsights', () => {
  it('treats a missing origin or destination as incomplete', () => {
    expect(isIncompleteCorridor(null, 'FR')).toBe(true);
    expect(isIncompleteCorridor('IE', '')).toBe(true);
    expect(isIncompleteCorridor('IE', 'ES')).toBe(false);
    expect(INCOMPLETE_CORRIDOR_LABEL).toBe('Incomplete corridor');
  });

  it('does not treat a zero estimate as tracked spend', () => {
    expect(spendIsTracked(0, 0)).toBe(false);
    expect(spendIsTracked(1200, 0)).toBe(true);
    expect(spendIsTracked(0, 5000)).toBe(true);
  });

  it('returns null when there is nothing beyond the KPI cards', () => {
    expect(
      buildCommandCenterInsights({
        behindCount: 0,
        atRiskCount: 0,
        incompleteCorridorCount: 0,
        redCount: 0,
      }),
    ).toBeNull();
  });

  it('names behind-schedule and incomplete corridors', () => {
    expect(
      buildCommandCenterInsights({
        behindCount: 2,
        atRiskCount: 1,
        incompleteCorridorCount: 3,
        redCount: 0,
      }),
    ).toBe('2 cases are behind schedule. 1 at risk (delayed 5+ days). 3 missing origin or destination.');
  });
});
