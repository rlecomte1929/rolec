import { describe, it, expect } from 'vitest';
import { mergeIntakeDraft, clampIntakeStep } from '../intakeHydration';

/**
 * Regression guard for intake persistence — the "fill steps 1–2 → reload →
 * assert all fields + current step persisted" contract, at the unit level.
 *
 * These exercise the REAL hydration helpers the wizard runs on mount
 * (EmployeeIntakePage imports the same `mergeIntakeDraft`/`clampIntakeStep`), so
 * a regression in the restore logic fails here. The companion Playwright spec
 * (e2e/intake-persistence.spec.ts) covers the same flow end-to-end in a browser.
 */

// Mirrors the relevant slice of EmployeeIntakePage's INITIAL_DATA — the inputs
// to the merge. Note the NON-empty defaults (`purpose`, `members`) that must
// still be restorable.
const INITIAL = {
  origin_country: '',
  origin_city: '',
  dest_country: '',
  dest_city: '',
  target_date: '',
  purpose: 'Employment',
  full_name: '',
  email: '',
  nationality: '',
  passport_country: '',
  passport_expiry: '',
  members: [{ id: 'self', kind: 'self' }],
  has_pets: null as boolean | null,
};

// A saved draft as it would come back from GET …/intake after the user filled
// steps 1 and 2, then reloaded.
const SAVED_DRAFT: Record<string, unknown> = {
  origin_country: 'FR',
  origin_city: 'Lyon',
  dest_country: 'JP',
  dest_city: 'Tokyo',
  target_date: '2026-12-01',
  purpose: 'Study',
  has_pets: false,
  full_name: 'Élise Moreau',
  email: 'employee@testingapril.com',
  nationality: 'FR',
  passport_country: 'FR',
  passport_expiry: '2030-05-01',
};

describe('intake persistence — mergeIntakeDraft (reload restore)', () => {
  it('restores every step-1 and step-2 field from the saved draft', () => {
    const merged = mergeIntakeDraft({ ...INITIAL }, SAVED_DRAFT, INITIAL);
    // Step 1
    expect(merged.origin_country).toBe('FR');
    expect(merged.origin_city).toBe('Lyon');
    expect(merged.dest_country).toBe('JP');
    expect(merged.dest_city).toBe('Tokyo');
    expect(merged.target_date).toBe('2026-12-01');
    expect(merged.purpose).toBe('Study'); // non-empty default ('Employment') still restored
    expect(merged.has_pets).toBe(false); // null default → restored even to falsy `false`
    // Step 2
    expect(merged.full_name).toBe('Élise Moreau');
    expect(merged.email).toBe('employee@testingapril.com');
    expect(merged.nationality).toBe('FR');
    expect(merged.passport_country).toBe('FR');
    expect(merged.passport_expiry).toBe('2030-05-01');
  });

  it('does not clobber a field the user actively typed during hydration', () => {
    // User typed a destination city before the draft fetch resolved — their edit
    // (differs from the '' default) must win over the saved value.
    const current = { ...INITIAL, dest_city: 'Osaka' };
    const merged = mergeIntakeDraft(current, SAVED_DRAFT, INITIAL);
    expect(merged.dest_city).toBe('Osaka');
    // …but untouched fields still hydrate.
    expect(merged.origin_city).toBe('Lyon');
  });

  it('restores a non-empty-default array field (members)', () => {
    const savedMembers = [
      { id: 'self', kind: 'self' },
      { id: 'p1', kind: 'partner', name: 'Sam' },
    ];
    const merged = mergeIntakeDraft({ ...INITIAL }, { members: savedMembers }, INITIAL);
    expect(merged.members).toHaveLength(2);
    expect(merged.members[1]).toMatchObject({ kind: 'partner', name: 'Sam' });
  });

  it('ignores draft keys not present in the form (no crash, no leak)', () => {
    const merged = mergeIntakeDraft({ ...INITIAL }, { __unknown: 'x', origin_city: 'Lyon' }, INITIAL) as Record<string, unknown>;
    expect(merged.origin_city).toBe('Lyon');
    expect(merged.__unknown).toBe('x'); // copied through but harmless — wizard reads known keys only
  });
});

describe('intake persistence — clampIntakeStep (resume at saved step)', () => {
  it('returns the saved step when in range', () => {
    expect(clampIntakeStep(2, 5)).toBe(2);
    expect(clampIntakeStep(5, 5)).toBe(5);
  });

  it('clamps an out-of-range saved step into [1, totalSteps]', () => {
    expect(clampIntakeStep(99, 5)).toBe(5);
    expect(clampIntakeStep(0, 5)).toBe(1);
    expect(clampIntakeStep(-3, 5)).toBe(1);
  });
});
