/**
 * Why ReloPass: problem and differentiation. No full process diagram.
 *
 * Phase 3 copy + visual upgrade — April 2026
 */

export const whyReloPassContent = {
  hero: {
    eyebrow: 'For HR and mobility teams',
    headline: 'Relocation fails in the handoffs.',
    subheadline:
      'Inboxes, spreadsheets, and vendor portals each hold a piece of the case. ReloPass puts them on one record.',
    primaryCta: 'Book a demo',
    secondaryCta: 'See the platform',
    trustMicrocopy: '30-minute walkthrough. No commitment.',
  },

  currentReality: {
    title: 'What teams still fight',
    items: [
      'Visa status lives in the provider\'s inbox, not the case.',
      'HR fields the same questions because employees cannot see their own progress.',
      'No single view shows which cases are on track and which are blocked.',
      'Chasing updates becomes a job of its own.',
    ],
    supportingLine: 'Relocations complete. The coordination cost stays high.',
  },

  thesis:
    'Fragmented coordination breaks relocation. ReloPass puts everything on one case.',

  differentiation: {
    title: 'What is different',
    categoryBoundary: {
      positive: 'One system of record for every cross-border relocation.',
      negatives: [
        'Not a relocation agency.',
        'Not a vendor marketplace.',
        'Not an HR add-on.',
      ],
    },
    productAnchor:
      'When a document uploads, the case updates. HR does not need to chase the provider.',
    blocks: [
      {
        title: 'Case at the center',
        body: 'Each case has structure, status, and next steps built in.',
      },
      {
        title: 'Less chasing',
        body: 'The workflow carries the coordination. The team stops hunting updates.',
      },
    ],
  },

  outcomes: {
    title: 'Day-to-day impact',
    items: [
      'One case view instead of four tools open at once.',
      'Move blocked cases without losing thread on the others.',
      'Updates reach HR through the case, not another email chain.',
    ],
    supportingLine: 'The case does the coordination. The team does the work.',
    image: '/screenshot-hr-assignments.png',
    imageAlt:
      'HR assignments view showing active relocations with corridors, statuses, and deadlines on one record.',
  },

  peakCta: {
    headline: 'Every relocation case is visible, compliant, on-time.',
    primaryCta: 'Book a demo',
  },

  cta: {
    headline: 'Tell us how your relocations run today.',
    options: {
      demo: 'Book a demo',
      howItWorks: 'How it works',
      signIn: 'Sign in',
    },
  },
} as const;
