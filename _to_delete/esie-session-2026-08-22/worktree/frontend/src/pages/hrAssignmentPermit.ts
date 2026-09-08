/**
 * Destination → indicative work-permit label. Derived from the real case
 * destination, never hardcoded to a single visa. Keyed by both country name
 * (how the wizard stores relocationBasics.destCountry, e.g. "Singapore") and
 * ISO alpha-2 code, so either representation resolves. Labels mirror the
 * corridor mapping in RelocatePlanIntakePage.tsx. Returns null for an
 * unknown/unmapped destination so the caller can show "To be determined"
 * rather than a fabricated permit.
 *
 * Kept in its own module (not the page) so it can be unit-tested without
 * pulling in the page's api/supabase import chain (which throws in jsdom).
 */
const DESTINATION_PERMIT_LABELS: Record<string, string> = {
  singapore: 'Employment Pass (EP)',
  sg: 'Employment Pass (EP)',
  germany: 'EU Blue Card',
  de: 'EU Blue Card',
  netherlands: 'Highly Skilled Migrant (HSM)',
  nl: 'Highly Skilled Migrant (HSM)',
  norway: 'Skilled Worker Permit (UDI)',
  no: 'Skilled Worker Permit (UDI)',
  'united kingdom': 'Skilled Worker Visa',
  gb: 'Skilled Worker Visa',
  canada: 'Work Permit',
  ca: 'Work Permit',
  france: 'EU Free Movement / national permit',
  fr: 'EU Free Movement / national permit',
  spain: 'EU Free Movement / national permit',
  es: 'EU Free Movement / national permit',
  italy: 'EU Free Movement / national permit',
  it: 'EU Free Movement / national permit',
  belgium: 'EU Free Movement / national permit',
  be: 'EU Free Movement / national permit',
};

export function destinationPermitLabel(destination?: string | null): string | null {
  if (!destination) return null;
  return DESTINATION_PERMIT_LABELS[destination.trim().toLowerCase()] ?? null;
}
