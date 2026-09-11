import { describe, it, expect } from 'vitest';
import { intakeToCaseDraft } from './intakeToCaseDraft';
import type { IntakeData } from './EmployeeIntakePage';

// Minimal IntakeData factory — only the fields the mapper reads matter; the rest
// default to empty. Cast through unknown so the test stays terse.
function makeIntake(overrides: Partial<IntakeData> = {}): IntakeData {
  return {
    origin_country: '', origin_city: '', dest_country: '', dest_city: '',
    target_date: '', purpose: '', email: '', full_name: '', nationality: '',
    passport_country: '', passport_expiry: '', members: [],
    job_title: '', contract_type: '', contract_start: '', salary_band: '',
    office_address: '',
    ...overrides,
  } as unknown as IntakeData;
}

describe('intakeToCaseDraft', () => {
  it('maps the core fields onto the canonical draft', () => {
    const d = intakeToCaseDraft(makeIntake({
      origin_country: 'FR', origin_city: 'Lyon', dest_country: 'DE', dest_city: 'Berlin',
      purpose: 'Employment', target_date: '2026-09-01',
      full_name: 'Lucas Martin', nationality: 'FR', passport_country: 'FR',
      passport_expiry: '2030-01-01', email: 'l@x.dev',
      job_title: 'Senior SWE', contract_type: 'permanent', contract_start: '2026-09-01',
      salary_band: 'L5', office_address: 'Berlin office',
    }));
    expect(d.relocationBasics).toMatchObject({
      originCountry: 'FR', originCity: 'Lyon', destCountry: 'DE', destCity: 'Berlin',
      purpose: 'Employment', targetMoveDate: '2026-09-01',
    });
    expect(d.employeeProfile).toMatchObject({ fullName: 'Lucas Martin', passportCountry: 'FR', email: 'l@x.dev' });
    expect(d.assignmentContext).toMatchObject({ jobTitle: 'Senior SWE', contractType: 'permanent', salaryBand: 'L5', workLocation: 'Berlin office' });
  });

  it('maps assignment_type onto assignmentContext.assignmentType (AIQ-1349)', () => {
    const sta = intakeToCaseDraft(makeIntake({ assignment_type: 'STA' } as Partial<IntakeData>));
    expect(sta.assignmentContext?.assignmentType).toBe('STA');
    const lta = intakeToCaseDraft(makeIntake({ assignment_type: 'LTA' } as Partial<IntakeData>));
    expect(lta.assignmentContext?.assignmentType).toBe('LTA');
    // empty → undefined so the backend deep-merge never clobbers
    expect(intakeToCaseDraft(makeIntake()).assignmentContext?.assignmentType).toBeUndefined();
  });

  it('maps social_security_regime onto assignmentContext.socialSecurityRegime', () => {
    const posted = intakeToCaseDraft(makeIntake({ social_security_regime: 'posted' } as Partial<IntakeData>));
    expect(posted.assignmentContext?.socialSecurityRegime).toBe('posted');
    const local = intakeToCaseDraft(makeIntake({ social_security_regime: 'local' } as Partial<IntakeData>));
    expect(local.assignmentContext?.socialSecurityRegime).toBe('local');
    expect(intakeToCaseDraft(makeIntake()).assignmentContext?.socialSecurityRegime).toBeUndefined();
  });

  it('leaves empty fields undefined (so the backend deep-merge keeps existing values)', () => {
    const d = intakeToCaseDraft(makeIntake({ dest_country: 'DE' }));
    expect(d.relocationBasics?.destCountry).toBe('DE');
    expect(d.relocationBasics?.originCountry).toBeUndefined();
    expect(d.employeeProfile?.fullName).toBeUndefined();
    expect(d.assignmentContext?.jobTitle).toBeUndefined();
  });

  it('derives hasDependents and spouse/children from members', () => {
    const withDeps = intakeToCaseDraft(makeIntake({
      members: [
        { id: 'self', kind: 'self' },
        // 'Yes' (capital) is the real value the intake <select> emits — a
        // lowercase fixture here previously masked the case-sensitive bug.
        { id: 'p', kind: 'partner', name: 'Priya', needs_work_permit: 'Yes' },
        { id: 'c', kind: 'child', dob: '2018-04-01' },
      ] as unknown as IntakeData['members'],
    }));
    expect(withDeps.relocationBasics?.hasDependents).toBe(true);
    expect(withDeps.familyMembers?.spouse).toMatchObject({ fullName: 'Priya', wantsToWork: true });
    expect(withDeps.familyMembers?.children).toEqual([{ dateOfBirth: '2018-04-01', relationship: 'child' }]);
  });

  it('hasDependents is false and spouse undefined when solo', () => {
    const solo = intakeToCaseDraft(makeIntake({ members: [{ id: 'self', kind: 'self' }] as unknown as IntakeData['members'] }));
    expect(solo.relocationBasics?.hasDependents).toBe(false);
    expect(solo.familyMembers?.spouse).toBeUndefined();
    expect(solo.familyMembers?.children).toEqual([]);
  });
});
