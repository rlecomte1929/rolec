import { describe, expect, it } from 'vitest';
import { toDestinationIso2 } from './immigrationAuthority';

describe('toDestinationIso2', () => {
  it('keeps ISO-2 codes', () => {
    expect(toDestinationIso2('de')).toBe('DE');
    expect(toDestinationIso2('IE')).toBe('IE');
  });

  it('maps CountryPicker names used on the assistant', () => {
    expect(toDestinationIso2('Germany')).toBe('DE');
    expect(toDestinationIso2('Ireland')).toBe('IE');
    expect(toDestinationIso2('Spain')).toBe('ES');
  });

  it('returns null for empty or unknown labels', () => {
    expect(toDestinationIso2('')).toBeNull();
    expect(toDestinationIso2('Narnia')).toBeNull();
  });
});
