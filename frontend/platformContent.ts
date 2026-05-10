/**
 * Platform page: what the product is. No competitor story.
 *
 * Phase 1 copy update — April 2026
 * Source: Brand Audit (Phase 0-2) + Branding Blueprint V02
 */

export const platformContent = {
  hero: {
    eyebrow: 'For HR and mobility teams',
    headline: 'Every relocation on one system of record.',
    subheadline:
      'Cases, documents, providers, and progress on one record. No inboxes, no spreadsheets, no vendor portals.',
    primaryCta: 'Book a demo',
    secondaryCta: 'How it works',
    trustMicrocopy: '30-minute walkthrough. No commitment.',
  },

  productDefinition: {
    title: 'Case-based relocation system',
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
    headline: 'See how it works with your cases',
    options: {
      demo: 'Book a demo',
      howItWorks: 'How it works',
      signIn: 'Sign in',
    },
  },
} as const;
