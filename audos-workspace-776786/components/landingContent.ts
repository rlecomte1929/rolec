/**
 * ReloPass homepage copy — ported from imported-source landingContent.ts
 */

export const landingContent = {
  hero: {
    eyebrow: 'Global mobility infrastructure',
    headline: 'Cut the cost of every cross-border move.',
    subheadline:
      'One system for cases, documents, providers, and deadlines — so HR runs relocation on less budget, without dropping a move.',
    brandPromise:
      'The coordination layer across HR, employees, and providers.',
    primaryCta: 'Structure how you run relocation. Start with one case.',
    secondaryCta: 'Book a demo',
    trustMicrocopy: '30-minute walkthrough. No commitment.',
  },
  proofBlock: {
    items: [
      {
        icon: 'FileSearch',
        article: 'EU AI Act · Article 12',
        text: 'Every AI decision is logged, timestamped, and tied to the source document it read.',
      },
      {
        icon: 'ScanLine',
        article: 'EU AI Act · Articles 10 & 9',
        text: 'Shadow-run every extraction against a second model — disagreements surface, never hide.',
      },
      {
        icon: 'UserCheck',
        article: 'EU AI Act · Article 14',
        text: 'No AI ships a single value to a form without a person confirming it.',
      },
    ],
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
    ],
  },
  solution: {
    sectionHeader: 'One system for cases, timelines, documents, providers, and status.',
    title: 'One system for cases, timelines, documents, providers, and status.',
    blocks: [
      { title: 'Cases', body: 'Every relocation case in one place, from open to close.' },
      { title: 'Timelines', body: 'Structured task sequences, policy-applied at creation.' },
      { title: 'Documents', body: 'Required documents tracked to the case, not to inboxes.' },
      { title: 'Providers', body: 'Vendor tasks assigned and monitored inside the case.' },
      { title: 'Policy controls', body: "Your relocation policy becomes the system's operating rules." },
      { title: 'Visibility', body: 'Live case status across every open case and provider.' },
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
    microCopy: "Tell us how your relocations run today. We'll show you what changes.",
    options: {
      demo: 'Book a demo',
      platform: 'See the platform walkthrough',
      signIn: 'Sign in',
    },
  },
} as const;

export const CONFIG_ID = '776786';

export const assetUrl = (filename: string) => `/site/${CONFIG_ID}/assets/${filename}`;
