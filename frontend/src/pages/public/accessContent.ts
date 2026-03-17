/**
 * Access page content configuration.
 * Decision page — answers "What is my next step?"
 * Edit this file to update copy without touching layout.
 */

export const accessContent = {
  hero: {
    headline: 'Get started the right way',
    subheadline: 'Choose the path that fits where you are.',
  },

  options: {
    bookDemo: {
      label: 'Book a demo',
      description: 'See how ReloPass would work for your team',
      cta: 'Book a demo',
    },
    signIn: {
      label: 'Sign in',
      description: 'Go to your workspace',
      cta: 'Sign in',
    },
    createAccount: {
      label: 'Create account',
      description: 'Set up your first case',
      cta: 'Create account',
    },
  },

  reassurance: 'Start small and build from there.',
} as const;
