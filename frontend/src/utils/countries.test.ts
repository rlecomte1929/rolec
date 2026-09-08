import { describe, expect, it } from 'vitest';
import { getCountryName } from './countries';

describe('getCountryName', () => {
  it('resolves an ISO code to its display name', () => {
    expect(getCountryName('NO')).toBe('Norway');
    expect(getCountryName('FR')).toBe('France');
  });

  it('is case-insensitive on the code', () => {
    expect(getCountryName('no')).toBe('Norway');
  });

  it('passes through values that are already display names', () => {
    expect(getCountryName('France')).toBe('France');
  });

  it('passes through unknown free text unchanged', () => {
    expect(getCountryName('Atlantis')).toBe('Atlantis');
  });

  it('returns empty string for null/undefined/blank', () => {
    expect(getCountryName(null)).toBe('');
    expect(getCountryName(undefined)).toBe('');
    expect(getCountryName('  ')).toBe('');
  });

  it('resolves identity-list countries that are not relocation destinations', () => {
    expect(getCountryName('LB')).toBe('Lebanon');
  });
});
