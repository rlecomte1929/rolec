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
}

/** Services grouped by phase, each group sorted alphabetically by title. */
export const SERVICE_CONFIG: ServiceItem[] = [
  // Before you move (alphabetically: Housing, Movers, Schools, Temp accommodation, Visa)
  { key: 'housing', title: 'Housing', description: 'Recommended neighbourhoods and housing options', icon: '🏠', group: 'before', enabled: true, backendKey: 'living_areas' },
  { key: 'movers', title: 'Movers', description: 'International relocation and moving companies', icon: '📦', group: 'before', enabled: true, backendKey: 'movers' },
  { key: 'schools', title: 'Schools / Childcare', description: 'International and local school recommendations', icon: '🎒', group: 'before', enabled: true, backendKey: 'schools' },
  { key: 'temp_accommodation', title: 'Temporary accommodation', description: 'Short-term stays before permanent housing', icon: '🏨', group: 'before', enabled: false },
  { key: 'visa', title: 'Visa & permits', description: 'Immigration and work permit support', icon: '📋', group: 'before', enabled: false },
  // Upon arrival
  { key: 'banks', title: 'Banking', description: 'Banking and account setup for expats', icon: '🏦', group: 'arrival', enabled: true, backendKey: 'banks' },
  { key: 'electricity', title: 'Utilities: Electricity', description: 'Utilities and electricity retailers', icon: '⚡', group: 'arrival', enabled: true, backendKey: 'electricity' },
  { key: 'insurances', title: 'Insurance', description: 'Health, travel, and life insurance providers', icon: '🛡️', group: 'arrival', enabled: true, backendKey: 'insurances' },
  { key: 'internet', title: 'Internet', description: 'Home broadband and connectivity', icon: '📶', group: 'arrival', enabled: false },
  { key: 'mobile', title: 'Mobile plan', description: 'Local SIM and mobile services', icon: '📱', group: 'arrival', enabled: false },
  { key: 'registration', title: 'Registration / ID number / municipality', description: 'Local registration and official paperwork', icon: '📄', group: 'arrival', enabled: false },
  // Settle & thrive
  { key: 'community', title: 'Community / integration', description: 'Connect with local communities', icon: '🤝', group: 'settle', enabled: false },
  { key: 'drivers_license', title: "Driver's license exchange", description: 'Convert your license for local use', icon: '🪪', group: 'settle', enabled: false },
  { key: 'language', title: 'Language courses', description: 'Learn the local language', icon: '📚', group: 'settle', enabled: false },
  { key: 'spouse', title: 'Spouse support', description: 'Employment and integration for partners', icon: '💼', group: 'settle', enabled: false },
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
  living_areas: 'Living Areas',
  schools: 'Schools',
  movers: 'Movers',
  banks: 'Banks',
  insurances: 'Insurances',
  electricity: 'Electricity',
};
