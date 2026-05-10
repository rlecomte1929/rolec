/**
 * Access / get-started paths.
 *
 * Phase 1 copy update — April 2026
 * Source: Brand Audit (Phase 0-2) + Branding Blueprint V02
 */

export const accessContent = {
  hero: {
    eyebrow: 'For HR and mobility teams',
    headline: 'Three ways in.',
    subheadline: 'Book a demo, sign in, or create an account.',
    trustMicrocopy: '30-minute walkthrough. No commitment.',
  },

  options: {
    bookDemo: {
      label: 'Book a demo',
      description: 'See your corridor and case volume on a live case view.',
      cta: 'Book a demo',
    },
    signIn: {
      label: 'Sign in',
      description: 'See your cases and next actions',
      cta: 'Sign in',
    },
    createAccount: {
      label: 'Create account',
      description: 'Start with one case, no credit card required',
      cta: 'Create account',
    },
  },

  closingCta: 'Structure how you run relocation. Start with one case.',

  reassurance: 'You can start with one case.',

  demoCover: {
    title: 'What the demo covers',
    bullets: [
      'Your corridors and case volume on a live case view.',
      'How policy rules, documents, and provider tasks stay on one record.',
      'What switching from email and spreadsheets looks like in week one.',
    ],
  },

  bookingForm: {
    title: 'Book a demo',
    fields: {
      name: { label: 'Name', placeholder: 'Your name' },
      email: { label: 'Work email', placeholder: 'name@company.com' },
      company: { label: 'Company', placeholder: 'Company name' },
      corridor: {
        label: 'Primary corridor or annual volume',
        placeholder: 'e.g. France to Singapore, ~15 moves/year',
      },
    },
    submitLabel: 'Request a demo',
    submitMicrocopy: 'Someone from our team will confirm a time within the next business days.',
    success: {
      title: 'Request received.',
      body: 'We will be in touch within the next business days to confirm your walkthrough.',
    },
    errorFallback: 'Something went wrong. Email us at contact@relopass.com.',
  },
} as const;
