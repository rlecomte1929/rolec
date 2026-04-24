/**
 * Homepage content. Edit here to change marketing copy without layout changes.
 *
 * Phase 1 copy update — April 2026
 * Source: Brand Audit (Phase 0-2) + Branding Blueprint V02
 */

export const landingContent = {
  hero: {
    eyebrow: 'For HR and mobility teams',
    headline: 'The operating layer for cross-border relocation.',
    subheadline:
      'Cases, documents, providers, and status on one record. No chased threads, no parallel spreadsheets.',
    brandPromise: 'Every relocation case is visible, compliant, on-time.',
    primaryCta: 'Book a demo',
    secondaryCta: 'See the platform',
    trustMicrocopy: '30-minute walkthrough. No commitment.',
  },

  problem: {
    title: 'Relocation still runs on emails and spreadsheets.',
    cards: [
      {
        title: 'Scattered coordination',
        body: 'Email, spreadsheets, and vendor threads do not share one case view.',
      },
      {
        title: 'No single view',
        body: 'Hard to see what moved, what is blocked, and who owns the next step.',
      },
      {
        title: 'Follow-up becomes the work',
        body: 'Too much time on documents, pings, and status checks.',
      },
    ],
  },

  solution: {
    sectionHeader: 'Global mobility. Structured.',
    title: 'One structured way to run it',
    blocks: [
      {
        title: 'Case-based workflow',
        body: 'Each move is one trackable case.',
      },
      {
        title: 'Guided steps',
        body: 'Employees see what to do next.',
      },
      {
        title: 'Policy alignment',
        body: 'Work follows company rules and caps.',
      },
      {
        title: 'Provider work in context',
        body: 'Vendor tasks stay tied to the case, not lost in inboxes.',
      },
    ],
  },

  productStrip: {
    blocks: [
      { title: 'Cases', body: 'One case per relocation' },
      { title: 'Service providers', body: 'Tasks and updates stay on the case, not in inboxes.' },
      { title: 'Progress', body: "See what's done, pending, and blocked." },
    ],
  },

  trust: {
    categoryBoundary: {
      positive: 'One system of record for every cross-border relocation.',
      negatives: [
        'Not a relocation agency.',
        'Not a vendor marketplace.',
        'Not an HR add-on.',
      ],
    },
    title: 'Built for mobility operators.',
    body: 'Workflow, policy-aware guidance, and execution in one system.',
    checklist: [
      'Workflow-first, not chat-first',
      'Policy-aware, not generic tasks',
      'For HR and mobility operators',
      'Built for visibility and follow-through',
    ],
  },

  finalCta: {
    headline: 'Three ways in.',
    microCopy: 'Book a demo, sign in, or create an account.',
    options: {
      demo: 'Book a demo',
      platform: 'See the platform',
      signIn: 'Sign in',
    },
  },
} as const;
