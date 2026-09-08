/**
 * Norway → France — Gap 1 acceptance verification (Case Command, Model A).
 *
 * Test-only, additive. Verifies the two Gap-1 acceptance criteria that the
 * existing NO→FR suite did not assert explicitly:
 *   - AC1: the corridor covers all four phases (A exit · B employment ·
 *     C establishment · D customs) and renders them in a run case.
 *   - AC4: the Phase-D customs relief is gated on the Phase-A Norway exit
 *     evidence.
 *
 * Model-A reconciliation: v2's Gap-1 AC2 ("Waiting on: [upstream]") and AC4
 * ("blocked until X completed") are Model-B (`obligation_dependencies`) DAG
 * constructs. Model A has no computed blocking DAG — the dependency is authored
 * and surfaced as a free-text `dependencyNote`. These tests assert that
 * linkage in its Model-A form. No engine or UI code is changed.
 */
import { describe, expect, it } from 'vitest';
import { NORWAY_FRANCE_REQUIREMENTS, runCaseCheck } from './rule-engine';

const byId = (id: string) => NORWAY_FRANCE_REQUIREMENTS.find((r) => r.id === id);

describe('NO→FR Gap 1 — four-phase coverage (AC1)', () => {
  it('authors all four phases: A exit · B employment · C establishment · D customs', () => {
    const hasPrefix = (re: RegExp) => NORWAY_FRANCE_REQUIREMENTS.some((r) => re.test(r.id));
    expect(hasPrefix(/^a\d/)).toBe(true); // Phase A — Norway exit admin
    expect(hasPrefix(/^b\d/)).toBe(true); // Phase B — cross-border employment / social security
    expect(hasPrefix(/^c\d/)).toBe(true); // Phase C — France establishment
    expect(hasPrefix(/^d\d/)).toBe(true); // Phase D — France customs
  });

  it('the rendered roadmap spans all four phases for an EEA return case', () => {
    const r = runCaseCheck('eea', '2026-06-01', '2026-08-10', 'norway-france');
    const phases = new Set(r.requirements.map((x) => x.id[0]));
    expect(phases.has('a')).toBe(true);
    expect(phases.has('b')).toBe(true);
    expect(phases.has('c')).toBe(true);
    expect(phases.has('d')).toBe(true);
  });

  it('authored requirement count is stable (regression tripwire)', () => {
    expect(NORWAY_FRANCE_REQUIREMENTS.length).toBe(25);
  });
});

describe('NO→FR Gap 1 — customs relief gated on the Norway exit evidence (AC4, as a dependencyNote)', () => {
  it('the Phase-A exit-evidence item exists and states it gates the French customs relief', () => {
    const a10 = byId('a10-customs-export-evidence');
    expect(a10).toBeDefined();
    expect(a10!.dependencyNote ?? '').toMatch(/customs relief/i);
    expect(a10!.dependencyNote ?? '').toMatch(/vehicle import/i);
  });

  it('the Phase-D household-goods and vehicle items point back at the Norway exit evidence', () => {
    const d1 = byId('d1-household-goods-customs-relief');
    const d2 = byId('d2-vehicle-import');
    expect(d1).toBeDefined();
    expect(d2).toBeDefined();
    expect(d1!.dependencyNote ?? '').toMatch(/exit evidence/i);
    expect(d2!.dependencyNote ?? '').toMatch(/exit evidence/i);
  });

  it('both customs items are flagged non-obvious (the EEA-is-not-EU-customs-union trap)', () => {
    expect(byId('d1-household-goods-customs-relief')!.nonObvious).toBe(true);
    expect(byId('d2-vehicle-import')!.nonObvious).toBe(true);
  });
});
