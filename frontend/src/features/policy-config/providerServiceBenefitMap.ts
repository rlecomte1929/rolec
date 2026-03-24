/**
 * Maps relocation provider / services-module keys (case_services.service_key, RFQ service_key)
 * to published policy matrix benefit_key values used by HR policy-config caps compare API.
 *
 * Keep this table explicit: add a row when a new service module should participate in cap comparison.
 * Keys must match what your company publishes in the policy config (see policy template / HR matrix).
 */
export const PROVIDER_SERVICE_TO_POLICY_BENEFIT_KEY: Record<string, string> = {
  housing: 'housing',
  movers: 'movers',
  schools: 'schools',
  banks: 'banking_setup',
  insurances: 'insurance',
  electricity: 'settling_in_allowance',
};

/**
 * Resolve benefit_key for caps/compare, or null if the service is not mapped (skip API line).
 */
export function benefitKeyForProviderService(serviceKey: string): string | null {
  const k = String(serviceKey || '')
    .trim()
    .toLowerCase();
  if (!k) return null;
  return PROVIDER_SERVICE_TO_POLICY_BENEFIT_KEY[k] ?? null;
}

export function humanizeServiceKey(serviceKey: string): string {
  return String(serviceKey || '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
