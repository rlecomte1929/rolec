/**
 * Homepage content. Edit here to change marketing copy without layout changes.
 *
 * Phase 1 copy update — April 2026
 * Source: Brand Audit (Phase 0-2) + Branding Blueprint V02
 */

export const landingContent = {
  hero: {
    eyebrow: 'EU AI Act–ready mobility',
    headline: 'Mobility AI your auditor will trust.',
    subheadline:
      "Every step in your employee's relocation — every document, every decision — logged, cited, and EU AI Act–ready.",
    brandPromise:
      'The audit trail your compliance team needs — and the experience your employees actually want.',
    primaryCta: 'Book a demo',
    secondaryCta: 'See the platform',
    trustMicrocopy: '30-minute walkthrough. No commitment.',
  },

  problem: {
    title: 'Relocation still runs on email and spreadsheets.',
    cards: [
      {
        title: 'HR is accountable for outcomes they cannot see.',
        body: 'Status lives in inboxes, not in systems.',
      },
      {
        title: 'Vendors operate outside the case, not inside it.',
        body: 'Provider progress is invisible until something goes wrong.',
      },
      {
        title: 'Every delay is a compliance, cost, or employee risk.',
        body: 'Handoffs are untracked. Deadlines are missed before anyone notices.',
      },
      {
        title: 'Status lives in inboxes, not in systems.',
        body: 'Nothing is auditable. Nothing is proactive.',
      },
    ],
  },

  solution: {
    sectionHeader: 'One system for cases, timelines, documents, providers, and status.',
    title: 'One system for cases, timelines, documents, providers, and status.',
    blocks: [
      {
        title: 'Cases',
        body: 'Every relocation case in one place, from open to close.',
      },
      {
        title: 'Timelines',
        body: 'Structured task sequences, policy-applied at creation.',
      },
      {
        title: 'Documents',
        body: 'Required documents tracked to the case, not to inboxes.',
      },
      {
        title: 'Providers',
        body: 'Vendor tasks assigned and monitored inside the case.',
      },
      {
        title: 'Policy controls',
        body: 'Your relocation policy becomes the system\'s operating rules.',
      },
      {
        title: 'Visibility',
        body: 'Live case status across every open case and provider.',
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
    headline: 'Ready to run relocation as a system?',
    microCopy: 'Tell us how your relocations run today. We\'ll show you what changes.',
    options: {
      demo: 'Book a demo',
      platform: 'See the platform walkthrough',
      signIn: 'Sign in',
    },
  },
} as const;
