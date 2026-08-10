/**
 * [AIQ-1783] Copy for the two paid-ad landing pages (ADS-3).
 *
 * Hero lines, CTAs, the qualifying question and the disclaimer are specified
 * VERBATIM in the task and in playbook §7. Do not reword them to taste — they are
 * matched to ad creative, and the disclaimer is a compliance requirement.
 *
 * Two hard rules for anything added here:
 *  1. No visa, immigration, or tax OUTCOME claim. Ever. ReloPass coordinates; it
 *     does not determine what an authority decides. `scripts/check_compliance_claims.py`
 *     scans this directory in CI.
 *  2. Infrastructure framing only — no "journey", "adventure", suitcases or airplanes.
 *     Proof blocks use interface screenshots, not adjectives.
 */

export interface AdProofAnchor {
  title: string;
  body: string;
  image: string;
  imageAlt: string;
}

/** Segment A — the HR / mobility buyer. */
export const mobilityTeamsContent = {
  meta: {
    title: 'Mobility teams · ReloPass',
    description:
      'Cases, documents, providers, and status on one record. Coordination software for HR and mobility teams.',
    ogUrl: 'https://www.relopass.com/mobility-teams',
  },
  hero: {
    eyebrow: 'For HR and mobility teams',
    headline: 'Relocation fails in the handoffs.',
    subheadline:
      'Cases, documents, providers, and status on one record. Built for HR and mobility teams.',
  },
  /** Three concrete workflow anchors. Real interface, not illustration. */
  proof: [
    {
      title: 'One case record',
      body: 'Every person, document, and decision for a move sits on a single record instead of a thread and three spreadsheets.',
      image: '/screenshot-hero-case-card.png',
      imageAlt: 'A ReloPass case record showing assignment details and status',
    },
    {
      title: 'Vendor work tied to the case',
      body: 'Providers are selected, briefed, and tracked against the case they belong to — so nobody has to ask who is doing what.',
      image: '/screenshot-provider-recommendations.png',
      imageAlt: 'Provider recommendations attached to a relocation case',
    },
    {
      title: 'Deadlines you can see',
      body: 'Dates and owners across every open case in one view, so a slipped step is visible before it becomes a problem.',
      image: '/screenshot-hr-assignments.png',
      imageAlt: 'An HR view listing relocation assignments with status and dates',
    },
  ] as AdProofAnchor[],
  primaryCta: 'Structure how you run relocation. Start with one case.',
  secondaryCta: 'Book a 20-minute walkthrough',
  form: {
    heading: 'Start with one case',
    /** The qualifying question — one dropdown, enables lead scoring. */
    qualifyingLabel: 'How many relocations do you run a year?',
    qualifyingOptions: ['1–5', '6–20', '21–50', '51–200', '200+'],
    submitLabel: 'Request access',
    successMessage: "Thanks — we'll be in touch shortly.",
  },
} as const;

/** Segment B — the employee. The gate is the entire commercial point. */
export const relocationChecklistContent = {
  meta: {
    title: 'Relocation checklist · ReloPass',
    description:
      'A structured checklist of documents, deadlines, and who owns each step of a cross-border move.',
    ogUrl: 'https://www.relopass.com/relocation-checklist',
  },
  hero: {
    eyebrow: 'For people relocating',
    headline: 'Know what your relocation requires.',
    subheadline:
      'A structured checklist of documents, deadlines, and who owns each step.',
  },
  whatYouGet: [
    'The documents a move like yours typically requires, grouped by who issues them.',
    'The order steps happen in, and which ones block the others.',
    'Who owns each step — you, your employer, or a provider.',
  ],
  form: {
    heading: 'Get the checklist',
    emailLabel: 'Work email',
    /** ← This field is the entire commercial point of segment B. */
    employerLabel: 'Who do you work for?',
    submitLabel: 'Send me the checklist',
    successMessage: 'Check your inbox — the checklist is on its way.',
  },
  softBridge: 'Coordinated by your HR team in ReloPass.',
  /**
   * VERBATIM and non-negotiable. States what ReloPass is NOT — a disclaimer, not a
   * compliance claim, which is why it is safe to ship (see the repo compliance gate).
   */
  disclaimer:
    'ReloPass is coordination software. It does not provide legal, immigration, or tax advice.',
} as const;
