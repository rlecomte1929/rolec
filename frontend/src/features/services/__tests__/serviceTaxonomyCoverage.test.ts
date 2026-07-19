/**
 * [F14] Guard: every Services-catalog category must be declared in the ONE shared
 * service→benefit taxonomy (shared/service_benefit_taxonomy.json) that both the
 * frontend cap-compare bridge and the backend budget-summary / caps-compare
 * resolver read. Before this taxonomy existed, the two sides spoke disjoint
 * vocabularies, every compare line answered `no_cap_for_benefit_in_context`, and
 * over-cap (the Policy Exception → HR notification trigger) could never fire.
 *
 * The backend twin of this guard (backend/tests/test_service_benefit_taxonomy.py)
 * additionally proves every mapped benefit_key exists in the policy matrix's
 * canonical vocabulary — together they pin the vocabulary intersection shut.
 */
import { describe, expect, it } from 'vitest';
import sharedTaxonomy from '../../../../../shared/service_benefit_taxonomy.json';
import {
  benefitKeyForProviderService,
  canonicalProviderServiceKey,
  policyBenefitKeysForService,
} from '../../policy-config/providerServiceBenefitMap';
import { SERVICE_CONFIG } from '../serviceConfig';

const services: Record<string, string[]> = sharedTaxonomy.services;
const aliases: Record<string, string> = sharedTaxonomy.aliases;

describe('shared service→benefit taxonomy coverage (F14)', () => {
  it('declares every Services-catalog category (mapped or explicitly uncapped)', () => {
    const missing = SERVICE_CONFIG.map((s) => s.key).filter(
      (key) => !(key in services) && !(key in aliases),
    );
    expect(
      missing,
      `Services-catalog categories missing from shared/service_benefit_taxonomy.json: ${missing.join(', ')}. ` +
        'Declare each one — map it to canonical policy benefit_keys, or declare it explicitly uncapped with [].',
    ).toEqual([]);
  });

  it('declares every backendKey the catalog uses (so estimate rows keyed on backend vocabulary resolve)', () => {
    const backendKeys = SERVICE_CONFIG.filter((s) => s.backendKey).map((s) => s.backendKey as string);
    const missing = backendKeys.filter((key) => !(key in services) && !(key in aliases));
    expect(missing).toEqual([]);
  });

  it('keeps the vocabulary intersection non-empty: the core purchasable services map to real caps', () => {
    // If these ever return null again, no selectable service can breach a cap and
    // the Policy Exception path goes unreachable — the original F14 failure.
    for (const service of ['housing', 'movers', 'schools', 'banks']) {
      expect(benefitKeyForProviderService(service), `${service} lost its cap mapping`).not.toBeNull();
      expect(policyBenefitKeysForService(service).length).toBeGreaterThan(0);
    }
  });

  it('resolves aliases (backendKeys, legacy intake and RFQ vocabularies) onto declared services', () => {
    for (const [alias, target] of Object.entries(aliases)) {
      expect(services, `alias '${alias}' points at undeclared service '${target}'`).toHaveProperty(target);
      expect(services, `'${alias}' must not be both an alias and a service`).not.toHaveProperty(alias);
    }
    expect(canonicalProviderServiceKey('living_areas')).toBe('housing');
    expect(canonicalProviderServiceKey('moving')).toBe('movers');
    expect(benefitKeyForProviderService('living_areas')).toBe('housing');
  });

  it('returns null (unmapped, not a fake compare line) for explicitly uncapped services', () => {
    for (const service of ['pets', 'insurances', 'electricity']) {
      expect(benefitKeyForProviderService(service)).toBeNull();
    }
    expect(benefitKeyForProviderService('totally_unknown_service')).toBeNull();
  });

  it('taxonomy values are non-empty canonical-looking benefit keys', () => {
    for (const [service, keys] of Object.entries(services)) {
      for (const key of keys) {
        expect(key, `service '${service}' maps to a blank benefit_key`).toMatch(/^[a-z][a-z0-9_]+$/);
      }
    }
  });
});
