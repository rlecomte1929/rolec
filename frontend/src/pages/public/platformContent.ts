/**
 * Platform page content configuration.
 * Answers: "What is the product, in practical terms?"
 * For HR, global mobility, and relocation professionals.
 * Edit this file to update copy without touching layout.
 */

export const platformContent = {
  hero: {
    headline: 'A better way to run relocation',
    subheadline:
      'Keep each move on track, know what is missing, and stop piecing updates together across email, spreadsheets, and outside providers.',
    primaryCta: 'Book a demo',
    secondaryCta: 'Why ReloPass',
  },

  system: {
    title: 'Each relocation runs as a case',
    body: 'Each relocation is managed as a structured case, so your team can follow progress without piecing updates together.',
  },

  cta: {
    headline: 'See how it would fit your process',
    options: {
      demo: 'Book a demo',
      whyReloPass: 'Why ReloPass',
      signIn: 'Sign in',
    },
  },
} as const;
