import { describe, it, expect } from 'vitest';
import { displayNameOrEmail, isInactiveOrIncompleteCase, orEmptyLabel } from './caseDisplay';

describe('displayNameOrEmail', () => {
  it('prefers the display name when present', () => {
    expect(displayNameOrEmail('Adrien Moreau', 'a@b.com')).toBe('Adrien Moreau');
  });
  it('falls back to email only when the name is empty/null', () => {
    expect(displayNameOrEmail('', 'a@b.com')).toBe('a@b.com');
    expect(displayNameOrEmail(null, 'a@b.com')).toBe('a@b.com');
    expect(displayNameOrEmail('   ', 'a@b.com')).toBe('a@b.com');
  });
  it('returns an intentional label when neither name nor email exists', () => {
    expect(displayNameOrEmail(null, null)).toBe('Unnamed case');
  });
});

describe('orEmptyLabel', () => {
  it('returns the value untouched when present', () => {
    expect(orEmptyLabel('Germany', 'Destination not set')).toEqual({ text: 'Germany', isEmpty: false });
  });
  it('returns the intentional label (never "-"/"tbd") when empty', () => {
    expect(orEmptyLabel('', 'Destination not set')).toEqual({ text: 'Destination not set', isEmpty: true });
    expect(orEmptyLabel(null, 'Route not set')).toEqual({ text: 'Route not set', isEmpty: true });
    expect(orEmptyLabel('  ', 'Route not set')).toEqual({ text: 'Route not set', isEmpty: true });
  });
  it('never surfaces a bare dash or tbd', () => {
    const r = orEmptyLabel(undefined, 'Destination not set');
    expect(r.text).not.toBe('-');
    expect(r.text.toLowerCase()).not.toContain('tbd');
  });
});

describe('isInactiveOrIncompleteCase', () => {
  it('flags destination-not-set rows', () => {
    expect(isInactiveOrIncompleteCase({ status: 'awaiting_intake', case: { host_country: '' } })).toBe(true);
  });
  it('flags not-started statuses even with a destination', () => {
    expect(
      isInactiveOrIncompleteCase({
        status: 'assigned',
        case: { host_country: 'Spain' },
      }),
    ).toBe(true);
  });
  it('leaves an in-progress case with a destination unmarked', () => {
    expect(
      isInactiveOrIncompleteCase({
        status: 'awaiting_intake',
        case: { host_country: 'Spain' },
      }),
    ).toBe(false);
  });
});
