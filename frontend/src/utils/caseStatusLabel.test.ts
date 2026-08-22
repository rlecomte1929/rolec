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
    // [AIQ-2088] `approved` is MID-lifecycle — granted when HR reviews the submitted
    // intake, weeks before the move — so it must not read 'Complete'. `closed` is the
    // terminal state and covers a finished move as well as an abandoned one, so it
    // must not read 'Canceled', which asserts the second.
    expect(getCaseStatusLabel('approved')).toBe('Approved');
    expect(getCaseStatusLabel('rejected')).toBe('Rejected');
    expect(getCaseStatusLabel('closed')).toBe('Closed');
    expect(getCaseStatusLabel('approved')).not.toBe('Complete');
    expect(getCaseStatusLabel('closed')).not.toBe('Canceled');
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
