/**
 * Gap 7 — deterministic verification harness (Case Command, Model A).
 *
 * Locks the definition of done: identical inputs → BYTE-IDENTICAL structured
 * output across 10 consecutive runs, per corridor × employee type, against a
 * committed golden shape, plus a perturbation check. No LLM, no clock
 * dependence (a fixed `today` is pinned so the harness is stable whenever it runs).
 *
 * Reconciliation note: v2 Gap 7 (T7.1) referenced "6 obligations". That figure
 * was a Model-B (`case_obligations`) construct. Model A produces a deterministic
 * requirement roadmap; its real, authored, stable counts are pinned below and
 * were captured directly from `runCaseCheck` on 2026-08-22.
 */
import { describe, expect, it } from 'vitest';
import {
  runCaseCheck,
  type CorridorId,
  type EmployeeType,
  type CaseCheckResult,
} from './rule-engine';

/** Pinned evaluation date — keeps the golden stable independent of run date. */
const FIXED_TODAY = '2026-08-10';

interface Golden {
  total: number;
  green: number;
  amber: number;
  red: number;
  confirmed: number;
  firstId: string;
  lastId: string;
}

interface Scenario {
  name: string;
  corridor: CorridorId;
  employeeType: EmployeeType;
  anchor: string;
  golden: Golden;
}

const SCENARIOS: Scenario[] = [
  {
    name: 'FR→NO · eea · future move',
    corridor: 'france-norway', employeeType: 'eea', anchor: '2026-12-01',
    golden: { total: 15, green: 15, amber: 0, red: 0, confirmed: 0, firstId: 'passport-validity', lastId: 'first-paycheck-check' },
  },
  {
    name: 'FR→NO · non-eea · future move',
    corridor: 'france-norway', employeeType: 'non-eea', anchor: '2026-12-01',
    golden: { total: 19, green: 18, amber: 1, red: 0, confirmed: 0, firstId: 'udi-work-permit', lastId: 'first-paycheck-check' },
  },
  {
    name: 'NO→FR · eea · past departure (retrospective)',
    corridor: 'norway-france', employeeType: 'eea', anchor: '2026-06-01',
    golden: { total: 24, green: 1, amber: 0, red: 21, confirmed: 2, firstId: 'b1-applicable-social-security', lastId: 'b5-income-tax-split-year' },
  },
  {
    name: 'NO→FR · non-eea · future departure',
    corridor: 'norway-france', employeeType: 'non-eea', anchor: '2026-12-01',
    golden: { total: 23, green: 23, amber: 0, red: 0, confirmed: 0, firstId: 'c2b-french-long-stay-visa', lastId: 'b5-income-tax-split-year' },
  },
  {
    name: 'ES→IE · non-eea · contract signed',
    corridor: 'spain-ireland', employeeType: 'non-eea', anchor: '2026-12-01',
    golden: { total: 12, green: 12, amber: 0, red: 0, confirmed: 0, firstId: 'csep-contract-signed', lastId: 'ie-bank-account' },
  },
];

const snapshot = (r: CaseCheckResult): string => JSON.stringify(r);

describe('Gap 7 — 10 consecutive runs are byte-identical (T7.1)', () => {
  for (const s of SCENARIOS) {
    it(`${s.name} — identical output across 10 runs`, () => {
      const runs = Array.from({ length: 10 }, () =>
        snapshot(runCaseCheck(s.employeeType, s.anchor, FIXED_TODAY, s.corridor)),
      );
      for (const r of runs) expect(r).toBe(runs[0]);
    });

    it(`${s.name} — matches the committed golden shape`, () => {
      const r = runCaseCheck(s.employeeType, s.anchor, FIXED_TODAY, s.corridor);
      expect(r.counts).toEqual({
        green: s.golden.green,
        amber: s.golden.amber,
        red: s.golden.red,
        confirmed: s.golden.confirmed,
        total: s.golden.total,
      });
      expect(r.counts.total).toBe(r.requirements.length);
      expect(r.requirements[0].id).toBe(s.golden.firstId);
      expect(r.requirements[r.requirements.length - 1].id).toBe(s.golden.lastId);
    });
  }
});

describe('Gap 7 — new-state coverage on the reverse corridor (T7.2)', () => {
  it('NO→FR retrospective case surfaces a red, two confirmed, and an Employer (not engaged) item', () => {
    const r = runCaseCheck('eea', '2026-06-01', FIXED_TODAY, 'norway-france');
    expect(r.counts.red).toBeGreaterThan(0);
    expect(r.counts.confirmed).toBe(2);
    expect(r.requirements.some((x) => x.feasibility === 'confirmed')).toBe(true);
    expect(r.requirements.some((x) => x.owner === 'Employer (not engaged)')).toBe(true);
  });
});

describe('Gap 7 — perturbation is deterministic (T7.3)', () => {
  it('moving the anchor date changes output, and the change is itself stable across 10 runs', () => {
    const base = snapshot(runCaseCheck('non-eea', '2026-12-01', FIXED_TODAY, 'france-norway'));
    const perturbed = Array.from({ length: 10 }, () =>
      snapshot(runCaseCheck('non-eea', '2026-12-08', FIXED_TODAY, 'france-norway')),
    );
    expect(perturbed[0]).not.toBe(base);
    for (const r of perturbed) expect(r).toBe(perturbed[0]);
  });
});
