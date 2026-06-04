import { describe, it, expect } from 'vitest';
import { buildImmigrationSummary, type ImmigrationContext } from './immigrationContext';

describe('buildImmigrationSummary (IMM-15)', () => {
  it('builds the full human-readable summary HR can edit', () => {
    const ctx: ImmigrationContext = {
      visa_type: 'blue_card',
      corridor_from: 'FR',
      corridor_to: 'DE',
      move_date: '2026-09-01',
      employee_nationality: 'Indian',
      has_dependents: true,
      dependents_count: 1,
      risk_flags: [{ flag_type: 'bfa_pre_approval', title: 'BfA pre-approval needed' }],
    };
    expect(buildImmigrationSummary(ctx)).toBe(
      'Blue Card application, FR→DE corridor. Employee is Indian national. ' +
        'Move date: 2026-09-01. Dependents: 1 dependent. Risk flags: BfA pre-approval needed.'
    );
  });

  it('pluralises dependents', () => {
    const ctx: ImmigrationContext = { visa_type: 'work_permit', has_dependents: true, dependents_count: 3 };
    expect(buildImmigrationSummary(ctx)).toContain('Dependents: 3 dependents.');
  });

  it('omits sections with no data (no dependents, no risk flags)', () => {
    const ctx: ImmigrationContext = {
      visa_type: 'blue_card',
      corridor_from: 'FR',
      corridor_to: 'DE',
      has_dependents: false,
      dependents_count: 0,
      risk_flags: [],
    };
    const out = buildImmigrationSummary(ctx);
    expect(out).toBe('Blue Card application, FR→DE corridor.');
    expect(out).not.toContain('Dependents');
    expect(out).not.toContain('Risk flags');
  });

  it('joins multiple risk flags', () => {
    const ctx: ImmigrationContext = {
      visa_type: 'blue_card',
      risk_flags: [
        { flag_type: 'bfa_pre_approval', title: 'BfA pre-approval needed' },
        { flag_type: 'passport_expiry', title: 'Passport expires soon' },
      ],
    };
    expect(buildImmigrationSummary(ctx)).toContain(
      'Risk flags: BfA pre-approval needed; Passport expires soon.'
    );
  });
});
