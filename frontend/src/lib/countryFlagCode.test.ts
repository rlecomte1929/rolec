import { describe, it, expect } from 'vitest';
import { countryFlagCode } from './countryFlagCode';

describe('countryFlagCode', () => {
  it('maps country names to ISO alpha-2 (lowercase)', () => {
    expect(countryFlagCode('Germany')).toBe('de');
    expect(countryFlagCode('France')).toBe('fr');
    expect(countryFlagCode('India')).toBe('in');
  });
  it('maps demonyms (nationalities) to ISO alpha-2', () => {
    expect(countryFlagCode('German')).toBe('de');
    expect(countryFlagCode('Indian')).toBe('in');
    expect(countryFlagCode('Polish')).toBe('pl');
  });
  it('accepts an existing ISO alpha-2 code', () => {
    expect(countryFlagCode('DE')).toBe('de');
    expect(countryFlagCode('DK')).toBe('dk');
    expect(countryFlagCode('FI')).toBe('fi');
    expect(countryFlagCode('EC')).toBe('ec');
    expect(countryFlagCode('UK')).toBe('gb');
  });

  it('maps destination names that were missing from the original corridor list', () => {
    expect(countryFlagCode('Denmark')).toBe('dk');
    expect(countryFlagCode('Ecuador')).toBe('ec');
    expect(countryFlagCode('Finland')).toBe('fi');
  });
  it('is case- and whitespace-insensitive', () => {
    expect(countryFlagCode('  french ')).toBe('fr');
  });
  it('returns null for unknown input', () => {
    expect(countryFlagCode('Atlantis')).toBeNull();
    expect(countryFlagCode('')).toBeNull();
  });
});
