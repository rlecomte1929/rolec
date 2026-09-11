/**
 * Service config for relocation plan selection.
 * Maps to backend: living_areas, schools, movers, banks, insurances, electricity.
 */

export type ServiceGroup = 'before' | 'arrival' | 'settle';

export type ServiceKey =
  | 'visa'
  | 'housing'
  | 'schools'
  | 'childcare'
  | 'movers'
  | 'pets'
  | 'temp_accommodation'
  | 'banks'
  | 'insurances'
  | 'registration'
  | 'electricity'
  | 'internet'
  | 'mobile'
  | 'transport'
  | 'drivers_license'
  | 'language'
  | 'spouse'
  | 'community';

export interface ServiceItem {
  key: ServiceKey;
  title: string;
  description: string;
  icon: string;
  group: ServiceGroup;
  enabled: boolean;
  /** Backend category key - only for enabled services */
  backendKey?: string;
  /** Locked in the Select-services grid until HR has curated ≥1 vendor for the
   *  employee's destination (Pets). Rendered as a disabled "Coming soon" tile. */
  requiresCuration?: boolean;
}

/** Services grouped by phase, each group sorted alphabetically by title. */
export const SERVICE_CONFIG: ServiceItem[] = [
  // Before you move (alphabetically: Housing, Movers, Schools, Temp accommodation, Visa)
  { key: 'housing', title: 'Housing', description: 'Recommended neighbourhoods and housing options', icon: '🏠', group: 'before', enabled: true, backendKey: 'living_areas' },
  { key: 'movers', title: 'Movers', description: 'International relocation and moving companies', icon: '📦', group: 'before', enabled: true, backendKey: 'movers' },
  { key: 'schools', title: 'Schools / Childcare', description: 'International and local school recommendations', icon: '🎒', group: 'before', enabled: true, backendKey: 'schools' },
  { key: 'pets', title: 'Pets', description: 'Pet relocation, travel documents, and quarantine requirements', icon: '🐾', group: 'before', enabled: true, backendKey: 'pets', requiresCuration: true },
  { key: 'temp_accommodation', title: 'Temporary accommodation', description: 'Short-term stays before permanent housing', icon: '🏨', group: 'before', enabled: false },
  { key: 'visa', title: 'Visa & permits', description: 'Immigration and work permit support', icon: '📋', group: 'before', enabled: false },
  // Upon arrival
  { key: 'banks', title: 'Banking', description: 'Banking and account setup for expats', icon: '🏦', group: 'arrival', enabled: true, backendKey: 'banks' },
  { key: 'electricity', title: 'Utilities: Electricity', description: 'Utilities and electricity retailers', icon: '⚡', group: 'arrival', enabled: true, backendKey: 'electricity' },
  { key: 'insurances', title: 'Insurance', description: 'Health, travel, and life insurance providers', icon: '🛡️', group: 'arrival', enabled: true, backendKey: 'insurance' },
  { key: 'internet', title: 'Internet', description: 'Home broadband and connectivity', icon: '📶', group: 'arrival', enabled: false },
  { key: 'mobile', title: 'Mobile plan', description: 'Local SIM and mobile services', icon: '📱', group: 'arrival', enabled: false },
  { key: 'registration', title: 'Registration / ID number / municipality', description: 'Local registration and official paperwork', icon: '📄', group: 'arrival', enabled: false },
  // Settle & thrive
  { key: 'community', title: 'Community / integration', description: 'Connect with local communities', icon: '🤝', group: 'settle', enabled: false },
  { key: 'drivers_license', title: "Driver's license exchange", description: 'Convert your license for local use', icon: '🪪', group: 'settle', enabled: false },
  { key: 'language', title: 'Language courses', description: 'Learn the local language', icon: '📚', group: 'settle', enabled: false },
  { key: 'spouse', title: 'Spouse support', description: 'Employment and integration for partners', icon: '💼', group: 'settle', enabled: true, backendKey: 'partner_career' },
  { key: 'transport', title: 'Transportation pass', description: 'Public transport and mobility', icon: '🚌', group: 'settle', enabled: false },
];

export const GROUP_LABELS: Record<ServiceGroup, { title: string; subtitle: string }> = {
  before: {
    title: 'Before you move',
    subtitle: 'Plan the essentials before departure',
  },
  arrival: {
    title: 'Upon arrival',
    subtitle: 'Get set up quickly in the first days',
  },
  settle: {
    title: 'Settle & thrive',
    subtitle: 'Build stability for the long run',
  },
};

/** Map backend keys to display labels for wizard results */
export const CATEGORY_LABELS: Record<string, string> = {
  living_areas: 'Neighbourhoods',
  housing_agencies: 'Housing Agencies',
  schools: 'Schools',
  movers: 'Movers',
  banks: 'Banks',
  insurances: 'Insurances',
  electricity: 'Electricity',
  partner_career: 'Partner career support',
};

/**
 * backendKey → canonical service key (e.g. 'living_areas' → 'housing').
 *
 * The recommendations/estimate surfaces speak `backendKey`, while the policy engine, the
 * /budget-summary caps and the Benefit-comparison page all speak the canonical `key`. Two
 * surfaces writing exception requests in two vocabularies would file 'living_areas' and
 * 'housing' as separate asks for the same benefit, and the duplicate-request badge — which
 * matches on category — would not see across them.
 *
 * Derived from SERVICE_CONFIG so it cannot drift from the one table that owns the mapping.
 */
const BACKEND_KEY_TO_CANONICAL: Record<string, string> = {
  ...Object.fromEntries(
    SERVICE_CONFIG.filter((s) => s.backendKey).map((s) => [s.backendKey as string, s.key]),
  ),
  // housing_agencies is a fan-out sibling of living_areas (both surface under the
  // "Housing" step), so it groups under the canonical 'housing' for caps/shortlist/
  // exception matching. It is not a separately-selectable service, hence not in
  // SERVICE_CONFIG.
  housing_agencies: 'housing',
};

/** Canonical service key for a category that may be expressed as a backendKey.
 *  Unknown/already-canonical values pass through unchanged. */
export function canonicalServiceKey(category: string): string {
  return BACKEND_KEY_TO_CANONICAL[category] ?? category;
}

/** Enabled catalog tiles for this household. Spouse is hidden unless a partner exists. */
export function enabledServicesForHousehold(hasPartner: boolean): ServiceItem[] {
  return SERVICE_CONFIG.filter((svc) => {
    if (!svc.enabled) return false;
    if (svc.key === 'spouse' && !hasPartner) return false;
    return true;
  });
}

/** The backendKey(s) a canonical key is known by — the inverse of canonicalServiceKey.
 *  Used to alias a canonical-keyed cap onto the backendKey the estimate page looks up.
 *  Returns [] when the canonical key has no distinct backendKey (they're the same string). */
export function backendKeysForCanonical(canonicalKey: string): string[] {
  return SERVICE_CONFIG.filter(
    (s) => s.key === canonicalKey && s.backendKey && s.backendKey !== s.key,
  ).map((s) => s.backendKey as string);
}
