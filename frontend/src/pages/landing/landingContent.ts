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

  // FRIDAY-004c locked proof block — verbatim from audit/gtm/proof_block_v1.md §1.
  // Each line is ≤14 words (13/13/14) and maps to a distinct EU AI Act article
  // (Art. 12 record-keeping · Arts. 10+9 data + risk · Art. 14 human oversight).
  // Do not rephrase — these 3 lines are locked/approved copy.
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
