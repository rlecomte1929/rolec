import { describe, it, expect } from 'vitest';
import { computeMilestoneTargets, daysOverdue } from '../milestoneTimeline';

describe('computeMilestoneTargets', () => {
  const targets = computeMilestoneTargets('2026-06-01');
  const byType = Object.fromEntries(targets.map((t) => [t.type, t.targetISO]));

  it('calculates each milestone date as the correct offset from the move date', () => {
    expect(byType.dossier_assembly_start).toBe('2026-04-02'); // -60d
    expect(byType.criminal_record_check).toBe('2026-04-07');  // -55d
    expect(byType.application_filed).toBe('2026-05-02');       // -30d
    expect(byType.visa_decision_expected).toBe('2026-05-27');  // -5d
    expect(byType.arrival).toBe('2026-06-01');                 // 0d
    expect(byType.local_registration).toBe('2026-06-15');      // +14d
    expect(byType.work_permit_issued).toBe('2026-07-01');      // +30d
  });

  it('produces the full 8-milestone sequence in order', () => {
    expect(targets.map((t) => t.type)).toEqual([
      'dossier_assembly_start',
      'criminal_record_check',
      'application_filed',
      'biometric_appointment',
      'visa_decision_expected',
      'arrival',
      'local_registration',
      'work_permit_issued',
    ]);
  });
});

describe('daysOverdue', () => {
  it('counts whole days overdue for a past target', () => {
    expect(daysOverdue('2026-06-01', '2026-06-04', false)).toBe(3);
  });

  it('returns 0 for a future target', () => {
    expect(daysOverdue('2026-06-10', '2026-06-04', false)).toBe(0);
  });

  it('returns 0 when the milestone is completed, even if past', () => {
    expect(daysOverdue('2026-06-01', '2026-06-04', true)).toBe(0);
  });
});
