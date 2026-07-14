/**
 * [AIQ-1520] The shortlist went from ONE vendor per service to MANY, so a real RFQ can ask
 * three movers for a price.
 *
 * Real users have the OLD shape on disk right now — in localStorage (`services_shortlist`)
 * and inside the server-side `services_state` blob. Hydration must migrate it silently. If it
 * throws, the whole services flow dies on load; if it returns the wrong shape, every vendor
 * membership check reads `undefined` and the employee's shortlist quietly empties.
 */
import { describe, it, expect } from 'vitest';
import { toShortlistMap } from '../ServicesFlowContext';

describe('toShortlistMap', () => {
  it('migrates the legacy single-value shape', () => {
    // Exactly what is on disk today: [category, item_id][]
    const legacy = [['movers', 'm-2'], ['living_areas', 'h-7']];
    expect(toShortlistMap(legacy)).toEqual(
      new Map([['movers', ['m-2']], ['living_areas', ['h-7']]]),
    );
  });

  it('passes the new multi-vendor shape through unchanged', () => {
    const next = [['movers', ['m-2', 'm-4', 'm-9']]];
    expect(toShortlistMap(next)).toEqual(new Map([['movers', ['m-2', 'm-4', 'm-9']]]));
  });

  it('is idempotent — save then re-read is stable', () => {
    const once = toShortlistMap([['movers', 'm-2']]);
    const serialised = Array.from(once.entries());
    expect(toShortlistMap(serialised)).toEqual(once);
  });

  it('handles a mixed blob (old case, newly saved category)', () => {
    const mixed = [['movers', ['m-2', 'm-4']], ['living_areas', 'h-7']];
    expect(toShortlistMap(mixed)).toEqual(
      new Map([['movers', ['m-2', 'm-4']], ['living_areas', ['h-7']]]),
    );
  });

  it('PRUNES empty arrays — ServicesEstimate gates its CTA on shortlist.size', () => {
    // A category whose last vendor was de-selected must not survive as an empty key, or the
    // "Request quotations" button turns on with nothing shortlisted.
    expect(toShortlistMap([['movers', []]]).size).toBe(0);
    expect(toShortlistMap([['movers', ['m-2']], ['schools', []]]).size).toBe(1);
  });

  it('never throws on junk', () => {
    expect(toShortlistMap(null).size).toBe(0);
    expect(toShortlistMap(undefined).size).toBe(0);
    expect(toShortlistMap('nonsense').size).toBe(0);
    expect(toShortlistMap([['movers'], null, 42, ['', 'x'], ['ok', 123]]).size).toBe(0);
  });
});
