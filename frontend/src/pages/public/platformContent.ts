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
        image: '/screenshot-service-package.png',
        imageAlt: 'Service package estimate showing three selected providers with costs',
      },
      {
        title: 'Corridor resources',
        body: 'Visa steps, housing options, and school guides. Matched to the corridor.',
        image: '/screenshot-destination-intelligence.png',
        imageAlt: 'Destination intelligence for Singapore: visa, housing, and school resources',
      },
      {
        title: 'Service providers',
        body: 'Vendor steps stay linked to the same case.',
        image: '/screenshot-provider-recommendations.png',
        imageAlt: 'Provider recommendations ranked by match score and policy alignment',
      },
    ],
  },

  splitSection: {
    title: 'One record. Two views.',
    subtitle: 'HR sees every case. Employees see their own.',
    hrView: {
      label: 'HR view',
      image: '/screenshot-hr-assignments.png',
      caption: 'All cases, corridors, and status across the team.',
    },
    employeeView: {
      label: 'Employee view',
      image: '/screenshot-employee-plan.png',
      caption: 'Each step, sequenced. The next action is always clear.',
    },
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
