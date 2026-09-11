import { describe, it, expect } from 'vitest';
import { enabledServicesForHousehold, SERVICE_CONFIG, WIZARD_SERVICE_KEYS } from '../serviceConfig';

describe('enabledServicesForHousehold', () => {
  it('includes spouse only when a partner is present', () => {
    const withPartner = enabledServicesForHousehold(true).map((s) => s.key);
    const without = enabledServicesForHousehold(false).map((s) => s.key);
    expect(withPartner).toContain('spouse');
    expect(without).not.toContain('spouse');
  });

  it('maps spouse to the partner_career backend key', () => {
    const spouse = SERVICE_CONFIG.find((s) => s.key === 'spouse');
    expect(spouse?.enabled).toBe(true);
    expect(spouse?.backendKey).toBe('partner_career');
  });

  it('includes spouse in the preferences/recommendations wizard keys', () => {
    expect(WIZARD_SERVICE_KEYS).toContain('spouse');
  });
});
