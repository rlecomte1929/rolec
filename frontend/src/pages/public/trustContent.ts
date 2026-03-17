/**
 * How it works page content configuration.
 * Role: How the process runs once adopted. No why-switch, no comparison.
 */

export const trustContent = {
  hero: {
    headline: 'How the work stays clear',
    subheadline:
      'ReloPass gives your team a clear case view, so you can see what is done, what is missing, and what needs attention next.',
    primaryCta: 'Book a demo',
    secondaryCta: 'See the platform',
  },

  process: {
    title: 'Each relocation moves through clear steps',
    body: 'Every relocation is handled as its own case. That gives the team a stable structure for tracking requirements, documents, service providers, and progress.',
    supportingLine: 'The goal is not to add more process. It is to make the existing process easier to follow.',
    steps: [
      { title: 'Case Creation', description: 'Start and structure the relocation case' },
      { title: 'Requirements Verification', description: 'Check requirements based on destination and profile' },
      { title: 'Relocation Documentation Pack', description: 'Gather and validate all required documents' },
      { title: 'Service Providers', description: 'Coordinate with the right partners' },
      { title: 'Monitor Progress', description: 'Track status and keep the case moving' },
    ],
  },

  inContext: {
    title: 'Everything stays in context',
    body: 'Country requirements, case documents, service-provider activity, and case progress stay tied to the same workflow instead of being split across separate tools, inboxes, and side notes.',
    items: [
      'See what has already been completed',
      'Spot what is still missing',
      'Track what is holding the case up',
      'Keep documents and activity tied to the right step',
    ],
  },

  boundaries: {
    title: 'The process is guided. Judgment stays human.',
    body: 'ReloPass keeps the case clear and organized, but your team still makes the call when a situation is unusual, sensitive, or needs closer review.',
  },

  cta: {
    headline: 'Walk through a real case',
    options: {
      demo: 'Book a demo',
      getStarted: 'Get started',
      signIn: 'Sign in',
    },
  },
} as const;
