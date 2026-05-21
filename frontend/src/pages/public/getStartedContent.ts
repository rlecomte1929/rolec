/**
 * Get started page — three conversion paths: book a demo, sign in, see the platform.
 * Source: relopass-figma-spec.md Page 5.
 */

export const getStartedContent = {
  hero: {
    eyebrow: 'Get started',
    headline: 'Three ways in. Book a demo, sign in, or create an account.',
    subheadline:
      "Tell us how your relocations run today. We'll show you what changes.",
  },

  form: {
    title: 'Book a demo',
    fields: {
      firstName: { label: 'First name', placeholder: 'First name' },
      lastName: { label: 'Last name', placeholder: 'Last name' },
      email: { label: 'Work email', placeholder: 'name@company.com' },
      company: { label: 'Company', placeholder: 'Company name' },
      volume: {
        label: 'Number of relocations per year',
        options: [
          { value: '1-10', label: '1–10' },
          { value: '10-50', label: '10–50' },
          { value: '50-200', label: '50–200' },
          { value: '200+', label: '200+' },
        ],
        placeholder: 'Select a range',
      },
      challenge: {
        label: "What's the main challenge you're trying to solve?",
        placeholder: 'Optional',
      },
    },
    submitLabel: 'Book a demo',
    trustMicrocopy: [
      '30-minute walkthrough, tailored to your process.',
      'No commitment required.',
      'We typically respond within one business day.',
    ],
  },

  demoCovers: {
    title: 'What the demo covers',
    items: [
      'How ReloPass structures your specific relocation types',
      'The case, timeline, and document workflow in practice',
      'How providers are coordinated inside the system',
      'How your policy becomes the system’s operating rules',
      'What implementation looks like for your team',
    ],
  },

  secondaryPaths: {
    signIn: {
      headline: 'Already have an account?',
      body: 'Access your cases and workflows.',
      cta: 'Sign in',
      to: '/auth',
    },
    seePlatform: {
      headline: 'Not ready to talk yet?',
      body: 'Walk through the platform at your own pace.',
      cta: 'See the platform',
      to: '/platform',
    },
  },

  trustRow: [
    'Built for HR and mobility teams running 10 to 500+ relocations per year.',
    'Configured to your corridors and policy — not a generic template.',
    'Your data stays in your system. No vendor lock-in on provider relationships.',
  ],
} as const;
