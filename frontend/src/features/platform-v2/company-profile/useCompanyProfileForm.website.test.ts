import { describe, expect, it } from 'vitest';
import { sanitizeWebsiteHost, valuesFromCompany, valuesToPayload } from './useCompanyProfileForm';

describe('sanitizeWebsiteHost', () => {
  it('strips a leading space and protocol', () => {
    expect(sanitizeWebsiteHost(' aurora-energy.com')).toBe('aurora-energy.com');
    expect(sanitizeWebsiteHost('https:// aurora-energy.com')).toBe('aurora-energy.com');
    expect(sanitizeWebsiteHost('https://aurora-energy.com')).toBe('aurora-energy.com');
  });
});

describe('valuesFromCompany website', () => {
  it('does not keep a protocol for the overlay field', () => {
    expect(valuesFromCompany({ website: ' https://aurora-energy.com ' }).website).toBe('aurora-energy.com');
  });
});

describe('valuesToPayload website', () => {
  it('stores a trimmed host', () => {
    expect(valuesToPayload({
      name: 'Aurora',
      legal_name: '',
      industry: '',
      size_band: '',
      website: ' https://aurora-energy.com ',
      country: '',
      hq_city: '',
      address: '',
      phone: '',
      hr_contact: '',
      support_email: '',
      default_destination_country: '',
      default_working_location: '',
    }).website).toBe('aurora-energy.com');
  });
});
