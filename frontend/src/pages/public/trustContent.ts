/**
 * How it works page content configuration.
 * Answers: "How does the process actually work once a team uses ReloPass?"
 * Process-led, confidence-building. Not comparison-led.
 * Edit this file to update copy without touching layout.
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
    title: 'Each relocation runs through clear steps',
    body: 'Every relocation is handled as its own case. That gives the team a stable structure for tracking requirements, documents, providers, and progress.',
    flow: ['Case', 'Requirements', 'Documents', 'Providers', 'Progress'] as const,
    supportingLine: 'The goal is not to add more process. It is to make the existing process easier to follow.',
  },

  inContext: {
    title: 'Everything stays in context',
    body: 'Your team can see what is done, what is missing, and what is holding the case up. Documents and requirements stay tied to each step, so you are not relying on side notes or separate trackers.',
    items: [
      'What has already been completed',
      'What is still missing',
      'What is holding the case up',
      'Documents and requirements tied to the right steps',
    ],
  },

  boundaries: {
    title: 'The process is guided. Judgment stays with your team.',
    body: 'ReloPass supports the work by keeping the case clear and organized. Your team still makes the call when a situation is unusual, sensitive, or needs closer review.',
  },

  cta: {
    headline: 'See it with a real case',
    microCopy: 'Walk through a relocation case with us.',
    options: {
      demo: 'Book a demo',
      seePlatform: 'See the platform',
      signIn: 'Sign in',
    },
  },
} as const;
