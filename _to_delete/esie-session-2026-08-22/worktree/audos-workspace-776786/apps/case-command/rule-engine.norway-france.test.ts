/**
 * Norway→France (NO_FR) — the reverse-direction authoring stress test (Gap 1).
 *
 * The corridor that validates two structural facts the FR→NO template never
 * exercised: retrospective anchors (the reference mover has ALREADY left
 * Norway) and orphaned employer obligations on an unsupported move.
 * Content is an AUTHORING DRAFT — sourced, informational, not counsel-assured.
 */
import { describe, expect, it } from 'vitest';
import {
  CORRIDORS,
  FRANCE_NORWAY_REQUIREMENTS,
  SPAIN_IRELAND_REQUIREMENTS,
  NORWAY_FRANCE_REQUIREMENTS,
  runCaseCheck,
} from './rule-engine';

const TODAY = '2026-08-10';
const check = (departure: string, employeeType: 'eea' | 'non-eea' = 'eea', today = TODAY) =>
  runCaseCheck(employeeType, departure, today, 'norway-france');

describe('Norway → France — anchoring & determinism', () => {
  it('anchors on the departure date and labels T−0 accordingly', () => {
    const result = check('2026-06-01');
    expect(result.corridor).toBe('norway-france');
    expect(result.anchorKind).toBe('move-date');
    const zero = result.requirements.find((r) => r.offsetWeeks === 0);
    expect(zero?.offsetLabel).toBe('T−0 (departure date)');
  });

  it('is deterministic — identical inputs, identical output', () => {
    expect(check('2026-06-01')).toEqual(check('2026-06-01'));
  });
});

describe('Norway → France — retrospective anchors (the mover already left)', () => {
  it('flags wholly elapsed windows red instead of silently missing them', () => {
    // Departed 10 weeks ago — the Folkeregisteret move-notice window (~T+1) is long gone.
    const result = check('2026-06-01');
    const flytting = result.requirements.find((r) => r.id === 'a1-folkeregisteret-move-notice');
    expect(flytting?.feasibility).toBe('red');
  });

  it('surfaces the retrospective-triage warning for a past departure', () => {
    const result = check('2026-06-01');
    expect(result.moveDatePassedWarning).not.toBeNull();
    expect(result.moveDatePassedWarning).toContain('retrospectively');
  });

  it('a future departure computes forward like any move-date corridor', () => {
    const result = check('2026-12-01');
    const flytting = result.requirements.find((r) => r.id === 'a1-folkeregisteret-move-notice');
    expect(flytting?.feasibility).toBe('green');
  });
});

describe('Norway → France — confirmed-clear positive states (Gap 3)', () => {
  it('renders the French citizen\u2019s immigration step as confirmed, never red/amber', () => {
    for (const departure of ['2026-06-01', '2026-12-01']) {
      const result = check(departure, 'eea');
      const immigration = result.requirements.find((r) => r.id === 'c2-immigration-right-of-entry');
      expect(immigration?.feasibility).toBe('confirmed');
    }
  });

  it('counts confirmed items separately from green/amber/red', () => {
    const result = check('2026-06-01', 'eea');
    expect(result.counts.confirmed).toBe(2); // immigration + no-address-registry
    expect(result.counts.total).toBe(result.requirements.length);
  });

  it('hides the confirmed-clear citizen steps from the non-EEA profile', () => {
    const ids = check('2026-06-01', 'non-eea').requirements.map((r) => r.id);
    expect(ids).not.toContain('c2-immigration-right-of-entry');
    expect(ids).toContain('c2b-french-long-stay-visa');
  });
});

describe('Norway → France — employer obligations stay surfaced (Gap 4)', () => {
  it('URSSAF registration and PE risk are employer-owned, not moved onto the employee', () => {
    const result = check('2026-06-01');
    const urssaf = result.requirements.find((r) => r.id === 'b2-urssaf-foreign-employer');
    const pe = result.requirements.find((r) => r.id === 'b3-permanent-establishment-risk');
    expect(urssaf?.owner).toBe('Employer (not engaged)');
    expect(pe?.owner).toBe('Employer (not engaged)');
  });

  it('flags the non-obvious traps this corridor exists to surface', () => {
    const nonObviousIds = NORWAY_FRANCE_REQUIREMENTS.filter((r) => r.nonObvious).map((r) => r.id);
    expect(nonObviousIds).toContain('b2-urssaf-foreign-employer'); // employer almost certainly unaware
    expect(nonObviousIds).toContain('d1-household-goods-customs-relief'); // EEA-is-not-EU-customs-union
    expect(nonObviousIds).toContain('a2-preserve-bankid'); // deregistration sequencing trap
  });
});

describe('corridor isolation', () => {
  it('shares no requirement ids with the other corridors', () => {
    const others = new Set([
      ...FRANCE_NORWAY_REQUIREMENTS.map((r) => r.id),
      ...SPAIN_IRELAND_REQUIREMENTS.map((r) => r.id),
    ]);
    for (const r of NORWAY_FRANCE_REQUIREMENTS) {
      expect(others.has(r.id)).toBe(false);
    }
  });

  it('derives its own runway from its own offsets', () => {
    const earliest = Math.abs(Math.min(0, ...NORWAY_FRANCE_REQUIREMENTS.map((r) => r.offsetWeeks)));
    expect(CORRIDORS['norway-france'].criticalRunwayDays).toBe(earliest * 7);
  });

  it('does not disturb the default corridor', () => {
    const result = runCaseCheck('eea', '2026-12-01', TODAY);
    expect(result.corridor).toBe('france-norway');
  });
});
