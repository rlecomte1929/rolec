/**
 * Security page — minimal trust signal for HR and procurement buyers.
 * Phase 3 — April 2026
 */

export const securityContent = {
  hero: {
    eyebrow: 'Security',
    headline: 'Built to handle sensitive relocation data.',
    subheadline:
      'Relocation cases contain personal and legal information. Here is how we protect it.',
  },

  points: [
    {
      title: 'Data hosting',
      body: 'Hosted in the EU (Frankfurt) on AWS infrastructure via Supabase. Your data does not leave the European Union.',
    },
    {
      title: 'Encryption',
      body: 'All data is encrypted in transit using TLS 1.2 and at rest using AES-256.',
    },
    {
      title: 'Access controls',
      body: 'Role-based access throughout. HR sees all active cases. Employees see only their own record.',
    },
    {
      title: 'Authentication',
      body: 'Secure login with session management and protected routes on every page.',
    },
    {
      title: 'Data use',
      body: 'Your relocation data is used only to run your cases. It is never sold or shared with third parties.',
    },
    {
      title: 'Questions',
      body: 'Security questions or procurement requirements? Email contact@relopass.com.',
    },
  ],
} as const;
