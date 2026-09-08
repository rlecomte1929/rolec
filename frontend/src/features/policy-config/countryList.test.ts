import { describe, it, expect } from 'vitest';
import { COUNTRY_OPTIONS, countryName, isKnownCountryCode } from './countryList';
import { DESTINATION_COUNTRIES } from '../../utils/countries';

// AIQ-1341: identity fields (nationality, passport, country of incorporation) must
// source the full ISO list, while relocation-destination pickers keep the
// restricted list. These guards lock that contract so the destination allowlist
// can't silently leak back into identity fields (which blocked e.g. Lebanese users).
describe('country list contract (AIQ-1341)', () => {
  it('full COUNTRY_OPTIONS is the whole world and includes Lebanon', () => {
    expect(COUNTRY_OPTIONS.length).toBeGreaterThanOrEqual(170);
    const lebanon = COUNTRY_OPTIONS.find((c) => c.code === 'LB');
    expect(lebanon).toBeDefined();
    expect(lebanon?.name).toBe('Lebanon');
  });

  it('DESTINATION_COUNTRIES is the restricted relocation list without Lebanon', () => {
    expect(DESTINATION_COUNTRIES.length).toBeLessThan(60);
    expect(DESTINATION_COUNTRIES.some((c) => c.code === 'LB')).toBe(false);
  });

  it('the full identity list is strictly larger than the destination list', () => {
    expect(COUNTRY_OPTIONS.length).toBeGreaterThan(DESTINATION_COUNTRIES.length);
  });
});

// AIQ-1861: reported from the product (BUG-260804-980D, Michael) as
// "Company profile, country pull down => germany is between Czech and Denmark".
// Root cause: BOTH lists were ordered by ISO CODE and rendered by NAME, so CZ/DE/DK
// read out as Czech Republic, Germany, Denmark. Both module docstrings claimed
// "alphabetical by name" — the comment asserted the invariant the data broke.
describe('country lists are ordered by display name (AIQ-1861)', () => {
  const isSortedByName = (list: ReadonlyArray<{ name: string }>) =>
    list.every(
      (c, i) => i === 0 || list[i - 1].name.localeCompare(c.name, 'en') <= 0,
    );

  it('COUNTRY_OPTIONS is sorted by name', () => {
    expect(isSortedByName(COUNTRY_OPTIONS)).toBe(true);
  });

  it('DESTINATION_COUNTRIES is sorted by name', () => {
    expect(isSortedByName(DESTINATION_COUNTRIES)).toBe(true);
  });

  it('the reported case: Germany is NOT between Czech Republic and Denmark', () => {
    const names = DESTINATION_COUNTRIES.map((c) => c.name);
    const de = names.indexOf('Germany');
    expect(de).toBeGreaterThan(-1);
    expect(names[de - 1]).not.toBe('Czech Republic');
    expect(names[de + 1]).not.toBe('Denmark');
  });

  it('the list starts with an A-country, not whatever sorts first by code', () => {
    // The old order began Andorra (AD); Afghanistan (AF) sorts first by name.
    expect(COUNTRY_OPTIONS[0].name).toBe('Afghanistan');
  });

  it('sorting preserved every entry — nothing dropped or duplicated', () => {
    const codes = COUNTRY_OPTIONS.map((c) => c.code);
    expect(new Set(codes).size).toBe(codes.length);
    expect(COUNTRY_OPTIONS.find((c) => c.code === 'LB')?.name).toBe('Lebanon');
  });
});

describe('countryName display (BUG-260908-B3D0)', () => {
  it('resolves ISO codes case-insensitively', () => {
    expect(countryName('NO')).toBe('Norway');
    expect(countryName('no')).toBe('Norway');
  });

  it('treats UK as the United Kingdom', () => {
    expect(countryName('UK')).toBe('United Kingdom');
    expect(isKnownCountryCode('UK')).toBe(true);
  });

  it('passes through unknown text', () => {
    expect(countryName('Atlantis')).toBe('Atlantis');
    expect(isKnownCountryCode('Atlantis')).toBe(false);
  });
});
