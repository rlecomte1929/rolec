import { describe, expect, it } from 'vitest';
import { getCaseStatusLabel } from './caseStatusLabel';

describe('getCaseStatusLabel', () => {
  it('maps both "created" and "assigned" to the same "Not started" label', () => {
    expect(getCaseStatusLabel('created')).toBe('Not started');
    expect(getCaseStatusLabel('assigned')).toBe('Not started');
  });

  it('labels awaiting_intake as "Intake in progress" (same state, no separate enum)', () => {
    expect(getCaseStatusLabel('awaiting_intake')).toBe('Intake in progress');
  });

  it('never surfaces the raw "assigned" / "awaiting intake" wording', () => {
    expect(getCaseStatusLabel('assigned')).not.toContain('assigned');
    expect(getCaseStatusLabel('awaiting_intake')).not.toContain('awaiting');
  });

  it('maps the remaining lifecycle statuses', () => {
    expect(getCaseStatusLabel('submitted')).toBe('Awaiting HR review');
    expect(getCaseStatusLabel('approved')).toBe('Complete');
    expect(getCaseStatusLabel('rejected')).toBe('Rejected');
    expect(getCaseStatusLabel('closed')).toBe('Canceled');
  });

  it('is case-insensitive', () => {
    expect(getCaseStatusLabel('AWAITING_INTAKE')).toBe('Intake in progress');
  });

  it('humanises unknown pipeline statuses instead of flattening them', () => {
    expect(getCaseStatusLabel('visa_submitted')).toBe('visa submitted');
    expect(getCaseStatusLabel('discovery')).toBe('discovery');
  });

  it('returns an em dash for empty/missing status', () => {
    expect(getCaseStatusLabel('')).toBe('—');
    expect(getCaseStatusLabel(null)).toBe('—');
    expect(getCaseStatusLabel(undefined)).toBe('—');
  });
});
