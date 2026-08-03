/**
 * AIQ-1752 — Spain→Ireland (Critical Skills Employment Permit).
 *
 * The corridor that inverts the model: offsets run FORWARD from contract signature,
 * and the permit is the employer's obligation rather than the employee's.
 */
import { describe, expect, it } from 'vitest';
import {
  CORRIDORS,
  FRANCE_NORWAY_REQUIREMENTS,
  SPAIN_IRELAND_REQUIREMENTS,
  runCaseCheck,
} from './rule-engine';

const TODAY = '2026-08-03';
const check = (contractSigned: string, today = TODAY) =>
  runCaseCheck('non-eea', contractSigned, today, 'spain-ireland');

describe('Spain → Ireland — anchoring', () => {
  it('anchors on contract signature, running offsets forward', () => {
    const result = check('2026-08-03');
    expect(result.corridor).toBe('spain-ireland');
    expect(result.anchorKind).toBe('contract-signed');
    // Every requirement lands on or after signature — the inverse of a move-date
    // corridor, where the work sits before the anchor.
    for (const r of result.requirements) {
      expect(r.actionByDate >= '2026-08-03').toBe(true);
    }
  });

  it('labels T−0 as the contract date, not the move date', () => {
    const zero = check('2026-08-03').requirements.find((r) => r.offsetWeeks === 0);
    expect(zero?.offsetLabel).toBe('T−0 (contract signed)');
  });

  it('is deterministic', () => {
    expect(check('2026-05-01')).toEqual(check('2026-05-01'));
  });
});

describe('Spain → Ireland — the banner measures time SINCE signature', () => {
  // The direction that matters: a contract-anchored corridor is at risk when the
  // chain has NOT had time to run, so the interval is elapsed-since-signature.
  // Measuring time-until would make a signature further ahead look safer.

  it('warns when the contract was signed too recently', () => {
    // Signed 3 weeks ago; the chain needs ~18.
    expect(check('2026-07-13').criticalBanner).not.toBeNull();
  });

  it('warns when the contract has not been signed yet', () => {
    // Still in the future — nothing in the chain has started.
    expect(check('2026-10-12').criticalBanner).not.toBeNull();
    // Further into the future is not safer.
    expect(check('2027-05-10').criticalBanner).not.toBeNull();
  });

  it('goes quiet once enough time has elapsed for the chain to complete', () => {
    // Signed 126 days ago — the full derived runway has elapsed.
    expect(check('2026-03-30').criticalBanner).toBeNull();
  });

  it('boundary: one day short still warns, exactly the runway does not', () => {
    // The comparison is strict (`interval < runway`), matching France→Norway:
    // having exactly the required runway is not "too short".
    expect(check('2026-03-31').criticalBanner).not.toBeNull(); // 125 days elapsed
    expect(check('2026-03-30').criticalBanner).toBeNull();     // 126 days elapsed
  });

  it('derives its runway from its own offsets, not from France→Norway', () => {
    const latest = Math.max(...SPAIN_IRELAND_REQUIREMENTS.map((r) => r.offsetWeeks));
    expect(CORRIDORS['spain-ireland'].criticalRunwayDays).toBe(latest * 7);
    expect(CORRIDORS['spain-ireland'].criticalRunwayDays)
      .not.toBe(CORRIDORS['france-norway'].criticalRunwayDays);
  });
});

describe('Spain → Ireland — the permit is the employer’s obligation', () => {
  it('models every employment-permit step as HR-owned', () => {
    const permitSteps = SPAIN_IRELAND_REQUIREMENTS.filter(
      (r) => /permit/i.test(r.id) || /permit/i.test(r.title),
    );
    expect(permitSteps.length).toBeGreaterThan(0);
    for (const step of permitSteps) {
      expect(step.owner).toBe('HR');
    }
  });

  it('leaves the visa with the employee — it is genuinely theirs to file', () => {
    const visa = SPAIN_IRELAND_REQUIREMENTS.find((r) => r.id === 'ie-d-visa-application');
    expect(visa?.owner).toBe('Employee');
  });

  it('flags the non-obvious traps this corridor exists to surface', () => {
    const nonObviousIds = SPAIN_IRELAND_REQUIREMENTS
      .filter((r) => r.nonObvious)
      .map((r) => r.id);
    // Spanish residence not transferring, and the permit not being immigration
    // permission, are the two facts a mover who has "already lived in the EU" gets
    // wrong. Both must be surfaced, not buried.
    expect(nonObviousIds).toContain('ie-spanish-ltr-does-not-transfer');
    expect(nonObviousIds).toContain('csep-permit-granted');
  });
});

describe('corridor isolation', () => {
  it('the two corridors share no requirement ids', () => {
    const frNo = new Set(FRANCE_NORWAY_REQUIREMENTS.map((r) => r.id));
    for (const r of SPAIN_IRELAND_REQUIREMENTS) {
      expect(frNo.has(r.id)).toBe(false);
    }
  });

  it('defaults to france-norway when no corridor is given', () => {
    const result = runCaseCheck('eea', '2026-12-01', TODAY);
    expect(result.corridor).toBe('france-norway');
    expect(result.anchorKind).toBe('move-date');
  });
});
