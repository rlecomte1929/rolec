/**
 * [F14] Cap-compare bridge between the Services-catalog vocabulary and the HR
 * policy-config caps API — now backed by the ONE shared controlled taxonomy at
 * shared/service_benefit_taxonomy.json (the same file the backend budget-summary
 * rollup and caps/compare resolver read). Do NOT add a local service→benefit map
 * here: the previous in-file table spoke keys (housing/movers/schools/banking_setup/
 * insurance/settling_in_allowance) that did not exist in the policy matrix's
 * canonical vocabulary, so every compare line came back
 * `no_cap_for_benefit_in_context` and over-cap could never fire.
 *
 * The contract now: `benefitKeyForProviderService` returns the CANONICAL service
 * key (aliases resolved), which is sent as the `benefit_key` of a caps/compare
 * estimate line. The backend resolves it through the same shared taxonomy to the
 * constituent policy benefit_keys and aggregates their published currency caps
 * (movers → shipment_of_goods + removal_expenses + storage), so an over-cap
 * estimate produces a real `within_cap: false` result. Coverage is guarded by
 * frontend/src/features/services/__tests__/serviceTaxonomyCoverage.test.ts.
 */
import sharedTaxonomy from '../../../../shared/service_benefit_taxonomy.json';

const SERVICES: Record<string, string[]> = sharedTaxonomy.services;
const ALIASES: Record<string, string> = sharedTaxonomy.aliases;

/** Lowercase/trim/underscore a raw service key and resolve known aliases
 *  (serviceConfig backendKeys, legacy intake and RFQ vocabularies). */
export function canonicalProviderServiceKey(serviceKey: string): string {
  const k = String(serviceKey || '')
    .trim()
    .toLowerCase()
    .replace(/-/g, '_');
  return ALIASES[k] ?? k;
}

/** The policy benefit_keys whose published caps make up this service's budget
 *  (empty when the taxonomy declares the service uncapped, or the key is unknown). */
export function policyBenefitKeysForService(serviceKey: string): string[] {
  return SERVICES[canonicalProviderServiceKey(serviceKey)] ?? [];
}

/**
 * Resolve the key to send as `benefit_key` on a caps/compare estimate line, or
 * null if the service has no policy benefit at all (skip the API line and render
 * the honest "unmapped" state).
 */
export function benefitKeyForProviderService(serviceKey: string): string | null {
  const canonical = canonicalProviderServiceKey(serviceKey);
  if (!canonical) return null;
  return (SERVICES[canonical] ?? []).length > 0 ? canonical : null;
}

export function humanizeServiceKey(serviceKey: string): string {
  return String(serviceKey || '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
