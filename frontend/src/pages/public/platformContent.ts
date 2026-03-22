/**
 * Platform page: what the product is. No competitor story.
 */

export const platformContent = {
  hero: {
    headline: 'Every relocation in one workspace',
    subheadline: 'Case, documents, providers, and progress in one view.',
    primaryCta: 'Book a demo',
    secondaryCta: 'How it works',
  },

  productDefinition: {
    title: 'Case-based relocation workspace',
    body: 'Each move is its own case. Stops updates living only in email, sheets, and vendor threads.',
  },

  insideProduct: {
    blocks: [
      {
        title: 'Case overview',
        body: 'Status, dates, and open work in one place.',
      },
      {
        title: 'Documents',
        body: 'Requirements and files tied to the case.',
      },
      {
        title: 'Service providers',
        body: 'Vendor steps stay linked to the same case.',
      },
    ],
  },

  cta: {
    headline: 'See it with your workflow in mind',
    options: {
      demo: 'Book a demo',
      howItWorks: 'How it works',
      signIn: 'Sign in',
    },
  },
} as const;
