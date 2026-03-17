/**
 * Homepage content configuration.
 * B2B positioning for HR, relocation, and global mobility teams.
 * Edit this file to update copy without touching layout.
 */

export const landingContent = {
  hero: {
    eyebrow: 'For HR, relocation, and global mobility teams',
    headline: 'Relocation infrastructure for globally mobile teams',
    subheadline:
      'ReloPass helps HR and mobility teams manage relocation through structured workflows, clear steps, and better visibility.',
    primaryCta: 'Book a demo',
    secondaryCta: 'Explore the platform',
  },

  problem: {
    title: 'Relocation is still fragmented',
    cards: [
      {
        title: 'Scattered coordination',
        body: 'Cases are handled across emails, spreadsheets, and external providers.',
      },
      {
        title: 'Limited visibility',
        body: "It's difficult to see status, ownership, and next steps across cases.",
      },
      {
        title: 'Repeated follow-ups',
        body: 'Teams spend time chasing documents, updates, and confirmations.',
      },
    ],
  },

  solution: {
    title: 'A more structured way to manage relocation',
    blocks: [
      {
        title: 'Case-based workflow',
        body: 'Each relocation is handled as a clear, trackable case.',
      },
      {
        title: 'Guided steps',
        body: 'Employees know what to do and when.',
      },
      {
        title: 'Policy alignment',
        body: 'Actions follow company rules and requirements.',
      },
      {
        title: 'Centralized coordination',
        body: 'Documents, services, and progress are managed in one place.',
      },
    ],
  },

  trust: {
    title: 'Designed for teams managing real relocation cases',
    body: 'ReloPass combines structured workflows, policy-aware guidance, and coordinated execution in one system.',
    checklist: [
      'Workflow-based, not chat-based',
      'Policy-aware, not generic task tracking',
      'Built for HR and mobility teams',
      'Structured for visibility and follow-through',
    ],
  },

  finalCta: {
    headline: 'Start structuring your relocation process',
    microCopy: 'Start with a single relocation case.',
    options: {
      demo: 'Book a demo',
      platform: 'Explore the platform',
      signIn: 'Sign in',
    },
  },
} as const;
