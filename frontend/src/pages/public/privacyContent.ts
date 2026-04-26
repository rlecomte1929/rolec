/**
 * Privacy Policy page.
 * Last updated: April 2026
 */

export const privacyContent = {
  hero: {
    eyebrow: 'Legal',
    headline: 'Privacy Policy',
    subheadline: 'Last updated: April 2026',
  },

  intro:
    'ReloPass helps HR and mobility teams coordinate cross-border employee relocation. This policy explains what data we collect, why we collect it, and your rights over it.',

  sections: [
    {
      title: 'Who we are',
      body: 'ReloPass is operated by ReloPass. For questions about this policy or your data, email contact@relopass.com.',
    },
    {
      title: 'What we collect and why',
      body: 'When you request a demo, we collect your name, work email address, company name, and optionally your primary relocation corridor or annual case volume. We use this information only to schedule and run your demo walkthrough, and to follow up with relevant product information. We do not collect this information for marketing campaigns.',
    },
    {
      title: 'When you create an account',
      body: 'We collect your email address and any profile information you provide to operate your account and deliver the product. This data is used solely to run your cases and coordinate your relocations.',
    },
    {
      title: 'How we store your data',
      body: 'All data is stored in the EU (Frankfurt, Germany) on AWS infrastructure via Supabase. Data is encrypted in transit using TLS 1.2 and at rest using AES-256.',
    },
    {
      title: 'Sub-processors',
      body: 'We use Resend to send transactional emails (demo confirmations, auto-replies). Resend receives your email address for this purpose only. We do not share your data with any other third parties, and we do not sell your data.',
    },
    {
      title: 'How long we keep your data',
      body: 'Demo request data is retained for 12 months. Account data is retained for the duration of your account and deleted within 90 days of account closure.',
    },
    {
      title: 'Cookies',
      body: 'We use only essential cookies required to operate the application, including session management and authentication. We do not use advertising, tracking, or analytics cookies.',
    },
    {
      title: 'Your rights',
      body: 'If you are in the European Economic Area, you have the right to access, correct, or delete the data we hold about you, to object to or restrict processing, and to data portability. To exercise any of these rights, email contact@relopass.com. We will respond within 30 days.',
    },
    {
      title: 'Changes to this policy',
      body: 'If we make material changes to this policy, we will update the date above and notify active users by email.',
    },
  ],
} as const;
