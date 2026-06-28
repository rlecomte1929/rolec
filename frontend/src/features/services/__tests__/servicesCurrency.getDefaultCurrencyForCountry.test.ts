import { describe, it, expect } from 'vitest';
import {
  getDefaultCurrencyForCountry,
  SERVICES_DISPLAY_CURRENCIES,
} from '../servicesCurrency';

const SUPPORTED = new Set(SERVICES_DISPLAY_CURRENCIES.map((c) => c.code));

describe('getDefaultCurrencyForCountry (AIQ-1327)', () => {
  it('maps eurozone destinations to EUR', () => {
    for (const cc of ['NL', 'FR', 'DE', 'ES', 'IT', 'IE', 'PT']) {
      expect(getDefaultCurrencyForCountry(cc)).toBe('EUR');
    }
  });

  it('maps the displayed non-EUR currencies correctly', () => {
    expect(getDefaultCurrencyForCountry('GB')).toBe('GBP');
    expect(getDefaultCurrencyForCountry('US')).toBe('USD');
    expect(getDefaultCurrencyForCountry('CH')).toBe('CHF');
    expect(getDefaultCurrencyForCountry('CA')).toBe('CAD');
    expect(getDefaultCurrencyForCountry('AU')).toBe('AUD');
    expect(getDefaultCurrencyForCountry('NO')).toBe('NOK');
    expect(getDefaultCurrencyForCountry('SE')).toBe('SEK');
    expect(getDefaultCurrencyForCountry('DK')).toBe('DKK');
    expect(getDefaultCurrencyForCountry('JP')).toBe('JPY');
  });

  it('is case- and whitespace-insensitive', () => {
    expect(getDefaultCurrencyForCountry(' nl ')).toBe('EUR');
    expect(getDefaultCurrencyForCountry('gb')).toBe('GBP');
  });

  it('falls back to USD for unsupported / unknown / empty inputs', () => {
    // SG (SGD), AE (AED), IN (INR), HK (HKD) — real countries, currencies we do not display.
    for (const cc of ['SG', 'AE', 'IN', 'HK', 'ZZ', '', null, undefined]) {
      expect(getDefaultCurrencyForCountry(cc)).toBe('USD');
    }
  });

  it('only ever returns a currency the selector can display', () => {
    for (const cc of ['NL', 'GB', 'US', 'JP', 'SG', 'XX', '']) {
      expect(SUPPORTED.has(getDefaultCurrencyForCountry(cc))).toBe(true);
    }
  });
});
