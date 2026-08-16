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

/**
 * What the case cockpit's Path card should say.
 *
 * The card used to read ONLY the static map above, so a destination absent from those 20 keys
 * rendered "No permit mapping for this destination yet" — regardless of how much approved
 * requirement content the platform actually held. Ireland was the case that exposed it: 14
 * approved `requirement_items` served on the corridor endpoint, and a cockpit insisting there
 * was no mapping.
 *
 * The live requirements now lead and the static map is only a fallback label, so a corridor
 * whose content exists can never again be described as unmapped.
 *
 * `covered === false` is deliberately distinct from an empty list: the first means "we hold no
 * catalogue for this destination", the second means "we checked and nothing applies". Collapsing
 * them is the AIQ-1473c failure — an empty list that reads as "nothing is required".
 */
export interface PathSummary {
  /** Headline; null renders the card's own "To be determined". */
  label: string | null;
  detail: string;
}

export function derivePathSummary(
  destination: string | null | undefined,
  requirements: RequirementsForPath | null,
): PathSummary {
  const fallback = destinationPermitLabel(destination);

  if (!destination) {
    return { label: null, detail: 'Awaiting destination from intake.' };
  }

  // Not loaded yet (or the fetch failed): behave exactly as before rather than claiming
  // anything new about coverage.
  if (!requirements) {
    return {
      label: fallback,
      detail: fallback
        ? 'Indicative — confirm with the relevant authority.'
        : 'Checking requirements for this destination…',
    };
  }

  const items = requirements.requirements ?? [];

  if (requirements.covered === false) {
    return {
      label: fallback,
      detail: 'No requirements catalogue for this destination yet.',
    };
  }

  if (items.length === 0) {
    return {
      label: fallback,
      detail: 'No requirements apply to this case.',
    };
  }

  // Prefer a RESIDENCE-pillar item: that is the permit/visa track, which is what the card is
  // naming. Falling back to the static label keeps the familiar wording for the 20 mapped
  // destinations rather than replacing "EU Blue Card" with a raw requirement title.
  const residence = items.find((i) => (i.pillar || '').toUpperCase() === 'RESIDENCE');
  const label = fallback ?? residence?.title ?? items[0]?.title ?? null;
  const noun = items.length === 1 ? 'requirement' : 'requirements';
  return {
    label,
    detail: `${items.length} ${noun} identified — indicative, confirm with the relevant authority.`,
  };
}

/** Structural subset of CaseRequirementsDTO — keeps this module free of the api import chain. */
export interface RequirementsForPath {
  requirements?: Array<{ pillar?: string; title?: string }>;
  covered?: boolean;
}
