/**
 * Homepage content configuration.
 * B2B positioning for HR, relocation, and global mobility teams.
 * Edit this file to update copy without touching layout.
 */

export const landingContent = {
  hero: {
    eyebrow: 'For HR, relocation, and global mobility teams',
    headline: 'Run relocation as one coordinated process',
    subheadline:
      'ReloPass helps HR and mobility teams manage relocation across cases, documents, service providers, and progress — without piecing updates together manually.',
    primaryCta: 'Book a demo',
    secondaryCta: 'See the platform',
  },

  problem: {
    title: 'Relocation is still fragmented',
    cards: [
      {
        title: 'Scattered coordination',
        body: 'Cases are handled across email, spreadsheets, and outside providers.',
      },
      {
        title: 'Limited visibility',
        body: 'It is hard to see what is moving, what is blocked, and who owns the next step.',
      },
      {
        title: 'Repeated follow-up',
        body: 'Teams spend too much time chasing documents, updates, and confirmations.',
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
        title: 'Service-provider coordination',
        body: 'Keep service-provider work tied to the case instead of scattered across threads.',
      },
    ],
  },

  productStrip: {
    blocks: [
      { title: 'Cases', body: 'Track each relocation as a single case' },
      { title: 'Service providers', body: 'Keep provider work tied to the case' },
      { title: 'Progress', body: 'See what is moving, missing, or blocked' },
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
      platform: 'See the platform',
      signIn: 'Sign in',
    },
  },
} as const;
