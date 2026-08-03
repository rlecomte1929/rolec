/**
 * AIQ-1752 — France→Norway regression suite.
 *
 * The snapshots were captured against the engine BEFORE ES_IE was added and before
 * runCaseCheck was generalised, and they guard the STRUCTURE of the output: the
 * requirement list, ordering, offsets, per-item feasibility and counts must all be
 * byte-identical after the generalisation.
 *
 * ONE deliberate exception: the critical-banner threshold moved from a hardcoded 42
 * days to this corridor's own derived runway (112 days — its earliest requirement is
 * the UDI work permit at T−16 weeks). That is an intentional behaviour change, made
 * because the old 6-week figure was SHORTER than the corridor's own longest-lead
 * step, so the banner could stay silent while that step was already unachievable.
 *
 * `fires in the newly-covered 42–112 day band` is the test that pins the change.
 * Everything else here must not move — if another snapshot fails, investigate rather
 * than running `-u`.
 */
import { describe, expect, it } from 'vitest';
import { CORRIDORS, FRANCE_NORWAY_REQUIREMENTS, runCaseCheck } from './rule-engine';

// Fixed dates: the engine is pure, so identical inputs must always give identical
// output. Nothing here may depend on the wall clock.
const TODAY = '2026-08-03';

describe('France → Norway (regression — behaviour must not change)', () => {
  it.each([
    ['eea', '2026-12-01'],       // comfortable horizon
    ['non-eea', '2026-12-01'],   // comfortable, permit track
    ['eea', '2026-09-01'],       // ~4 weeks out
    ['non-eea', '2026-09-01'],   // ~4 weeks out, inside the 6-week banner
    ['non-eea', '2026-08-10'],   // 1 week out
    ['eea', '2026-07-01'],       // move date already passed
  ] as const)('is stable for %s / %s', (employeeType, moveDate) => {
    expect(runCaseCheck(employeeType, moveDate, TODAY)).toMatchSnapshot();
  });

  it('anchors requirements on the move date', () => {
    const result = runCaseCheck('eea', '2026-12-01', TODAY);
    expect(result.corridor).toBe('france-norway');
    // offsetWeeks 0 means T−0, i.e. the move date itself.
    for (const r of result.requirements.filter((x) => x.offsetWeeks === 0)) {
      expect(r.actionByDate).toBe('2026-12-01');
    }
  });

  it('fires the non-EEA banner close in, and not at a comfortable horizon', () => {
    // 7 days out — fired before and after the threshold change.
    expect(runCaseCheck('non-eea', '2026-08-10', TODAY).criticalBanner).not.toBeNull();
    // 120 days out — beyond even the derived 112-day runway.
    expect(runCaseCheck('non-eea', '2026-12-01', TODAY).criticalBanner).toBeNull();
    // EEA nationals never get it, at any horizon.
    expect(runCaseCheck('eea', '2026-08-10', TODAY).criticalBanner).toBeNull();
  });

  it('fires in the newly-covered 42–112 day band (INTENTIONAL behaviour change)', () => {
    // 59 days out. Under the old hardcoded 42-day rule this was silent; under the
    // corridor's own derived 112-day runway it warns — correctly, because the UDI
    // work permit at T−16 weeks is already unachievable at this point.
    const result = runCaseCheck('non-eea', '2026-10-01', TODAY);
    expect(result.criticalBanner).not.toBeNull();

    // The boundary itself: 112 days out is exactly the runway, so not yet short.
    expect(runCaseCheck('non-eea', '2026-11-23', TODAY).criticalBanner).toBeNull();
    // 111 days — one day inside.
    expect(runCaseCheck('non-eea', '2026-11-22', TODAY).criticalBanner).not.toBeNull();
  });

  it('derives its runway from its own earliest offset, not a constant', () => {
    const earliest = Math.min(...FRANCE_NORWAY_REQUIREMENTS.map((r) => r.offsetWeeks));
    expect(CORRIDORS['france-norway'].criticalRunwayDays).toBe(Math.abs(earliest) * 7);
    expect(CORRIDORS['france-norway'].criticalRunwayDays).not.toBe(42);
  });

  it('is deterministic', () => {
    expect(runCaseCheck('non-eea', '2026-09-01', TODAY))
      .toEqual(runCaseCheck('non-eea', '2026-09-01', TODAY));
  });
});
