/**
 * Why ReloPass page content configuration.
 * Role: Why a team should change. No process flow, no workflow diagram, no "walk through a real case".
 */

export const whyReloPassContent = {
  hero: {
    headline: 'Relocation breaks in the gaps',
    subheadline:
      'Most teams are still holding the process together through inboxes, spreadsheets, provider updates, and repeated follow-up. ReloPass cuts through that coordination mess.',
    primaryCta: 'Book a demo',
    secondaryCta: 'See the platform',
  },

  currentReality: {
    title: 'What teams are still dealing with',
    items: [
      'Updates live in too many places',
      'Employees ask the same questions more than once',
      'Cases drift when no one has the full picture',
      'Follow-up becomes its own workload',
    ],
    supportingLine: 'The work gets done, but it takes more effort than it should.',
  },

  differentiation: {
    title: 'Why ReloPass feels different',
    blocks: [
      {
        title: 'Built around the case',
        body: 'Relocation is not treated like a generic task list. Each case has its own structure, status, and next step.',
      },
      {
        title: 'Less chasing',
        body: 'The process carries more of the coordination load, so your team spends less time hunting for updates.',
      },
    ],
  },

  outcomes: {
    title: 'What that changes day to day',
    items: [
      'Fewer moving parts to keep track of',
      'Cases are easier to keep moving when pressure builds',
      'The team spends less time chasing the same updates twice',
    ],
    supportingLine: 'The goal is not more software. It is less friction in the work.',
  },

  cta: {
    headline: 'See why teams make the switch',
    options: {
      demo: 'Book a demo',
      howItWorks: 'How it works',
      signIn: 'Sign in',
    },
  },
} as const;
