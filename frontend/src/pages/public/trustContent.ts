/**
 * How it works: process once you use ReloPass.
 */

export const trustContent = {
  hero: {
    headline: 'Clear case view end to end',
    subheadline: 'See done work, gaps, and the next action in one place.',
    primaryCta: 'Book a demo',
    secondaryCta: 'See the platform',
  },

  process: {
    title: 'Each relocation follows clear steps',
    body: 'One case holds requirements, documents, providers, and status.',
    supportingLine: 'Same process, easier to run.',
    steps: [
      { title: 'Case setup', description: 'Open and structure the case' },
      { title: 'Requirements', description: 'Check destination and profile rules' },
      { title: 'Documents', description: 'Collect and validate files' },
      { title: 'Service providers', description: 'Coordinate partners on the case' },
      { title: 'Progress', description: 'Track status and unblock work' },
    ],
  },

  inContext: {
    title: 'Context stays on the case',
    body: 'Requirements, files, provider activity, and milestones stay on one workflow instead of split tools and notes.',
    items: [
      'See completed steps',
      'See missing items',
      'See blockers',
      'Keep files and activity on the right step',
    ],
  },

  boundaries: {
    title: 'Guided process, human decisions',
    body: 'ReloPass organizes the case. Your team still decides edge cases and sensitive calls.',
  },

  cta: {
    headline: 'Walk through a case',
    options: {
      demo: 'Book a demo',
      getStarted: 'Get started',
      signIn: 'Sign in',
    },
  },
} as const;
