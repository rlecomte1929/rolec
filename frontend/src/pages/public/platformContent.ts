/**
 * Platform page content configuration.
 * Role: What the product is. No comparison, no process flow, no trust sections.
 */

export const platformContent = {
  hero: {
    headline: 'Run every relocation in one place',
    subheadline:
      'ReloPass brings the case, the documents, the service providers, and the progress into one working view.',
    primaryCta: 'Book a demo',
    secondaryCta: 'How it works',
  },

  productDefinition: {
    title: 'A case-based workspace for relocation',
    body: 'Each relocation is managed as its own case, so your team is not piecing updates together across email, spreadsheets, and service-provider threads.',
  },

  insideProduct: {
    blocks: [
      {
        title: 'Case overview',
        body: 'See the current status, key dates, and what still needs attention.',
      },
      {
        title: 'Documents',
        body: 'Keep required documents tied to the case instead of scattered across folders and threads.',
      },
      {
        title: 'Service providers',
        body: 'Track service-provider activity without losing the broader case context.',
      },
    ],
  },

  cta: {
    headline: 'See the product in context',
    options: {
      demo: 'Book a demo',
      howItWorks: 'How it works',
      signIn: 'Sign in',
    },
  },
} as const;
