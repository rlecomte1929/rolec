/**
 * Why ReloPass page content configuration.
 * Answers: "Why should a HR or global mobility team change from how they manage relocation today?"
 * Differentiation page — comparison-led, not process-led.
 * Edit this file to update copy without touching layout.
 */

export const whyReloPassContent = {
  hero: {
    headline: 'Why teams move away from the usual relocation mess',
    subheadline:
      'Most relocation work is still held together through inboxes, spreadsheets, provider updates, and repeated follow-up. ReloPass gives teams a cleaner way to stay on top of it.',
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
        body: 'Relocation is not treated like a generic task list. Each case has its own structure, status, and next steps.',
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
      'Better visibility when a case starts to stall, with requirements and documents tied to the case',
      'A process that is easier to manage under pressure',
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
