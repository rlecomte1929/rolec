/**
 * How it works page — 4-step operational sequence.
 * Phase 3 — April 2026
 */

export const howItWorksContent = {
  hero: {
    eyebrow: 'For HR and mobility teams',
    headline: 'How a relocation runs.',
    subheadline:
      'From the first case to the final step. Everything on one record.',
    trustMicrocopy: '30-minute walkthrough. No commitment.',
  },

  steps: [
    {
      number: '01',
      title: 'A case opens.',
      body: 'HR creates one record per employee: corridor, start date, policy applied. Every task, document, and update lives here.',
      image: '/screenshot-hero-case-card.png',
      imageAlt:
        'ReloPass case view showing a France to Singapore relocation with status, milestones, and documents on one record.',
    },
    {
      number: '02',
      title: 'The employee gets a plan.',
      body: 'Steps are sequenced from day one. The employee always knows what is next and what needs attention.',
      image: '/screenshot-employee-plan.png',
      imageAlt:
        'Employee relocation plan showing five phases with Pre-departure complete and Immigration in progress.',
    },
    {
      number: '03',
      title: 'Providers are engaged.',
      body: 'Vendor tasks attach to the case. Updates come back to the record, not to inboxes.',
      image: '/screenshot-provider-recommendations.png',
      imageAlt:
        'Provider recommendations ranked by match score and policy alignment.',
    },
    {
      number: '04',
      title: 'HR has full visibility.',
      body: 'Status, blockers, and deadlines across all active cases. No follow-up required.',
      image: '/screenshot-hr-assignments.png',
      imageAlt:
        'HR assignments view showing active relocations with corridors, statuses, and deadlines.',
    },
  ],

  cta: {
    headline: 'See it with your corridors.',
    primaryCta: 'Book a demo',
    trustMicrocopy: '30-minute walkthrough. No commitment.',
  },
} as const;
