/**
 * Platform page: what the product is. No competitor story.
 *
 * Phase 1 copy update — April 2026
 * Source: Brand Audit (Phase 0-2) + Branding Blueprint V02
 */

export const platformContent = {
  hero: {
    eyebrow: 'The platform',
    headline: 'Every part of the relocation workflow. One connected system.',
    subheadline:
      'Cases, timelines, documents, providers, and policy controls — structured into a single operating layer.',
    primaryCta: 'Book a demo',
    secondaryCta: 'Sign in',
    trustMicrocopy: '30-minute walkthrough. No commitment.',
  },

  productDefinition: {
    title: 'Built around the case.',
    body: 'The case is the unit of work. Everything else — policy, tasks, documents, providers — connects to it.',
  },

  insideProduct: {
    blocks: [
      {
        title: 'Cases',
        body: 'Every relocation case in one place, from open to close. The case holds the policy, the timeline, the documents, the providers, and the evidence.',
        image: '/screenshot-service-package.png',
        imageAlt: 'ReloPass case detail view showing status, timeline, documents, and provider activity',
      },
      {
        title: 'Timelines',
        body: 'Structured task sequences, policy-applied at creation. Nothing is manually assembled. Nothing is forgotten.',
        image: '/screenshot-employee-plan.png',
        imageAlt: 'Timeline view showing task states: complete, in progress, blocked, upcoming',
      },
      {
        title: 'Documents',
        body: 'Required documents tracked to the case. Uploads are matched to the case. Nothing lives in email. Nothing is chased manually.',
        image: '/screenshot-destination-intelligence.png',
        imageAlt: 'Document tracker panel within a case showing completion status per document type',
      },
      {
        title: 'Providers',
        body: 'Vendor tasks inside the case, not outside it. Their actions are logged. Their status is visible. No separate inboxes.',
        image: '/screenshot-provider-recommendations.png',
        imageAlt: 'Provider task view within the case showing multiple providers and status per task',
      },
      {
        title: 'Policy controls',
        body: 'Your relocation policy becomes the system\'s operating rules. Define what is required for each relocation type and corridor.',
        image: '/screenshot-hr-assignments.png',
        imageAlt: 'Policy configuration view showing corridor, tier, and required steps',
      },
      {
        title: 'Visibility',
        body: 'Live case status across every open case. Open items, upcoming milestones, exceptions, and overdue tasks — surfaced automatically.',
        image: '/screenshot-service-package.png',
        imageAlt: 'Portfolio dashboard showing multiple cases in different states',
      },
    ],
  },

  splitSection: {
    title: 'Same case. Two structured views.',
    subtitle: 'HR sees the full portfolio. Employees see their own case.',
    hrView: {
      label: 'What HR sees',
      image: '/screenshot-hr-assignments.png',
      caption: 'Case portfolio, policy adherence, exception flags, compliance status, provider progress.',
    },
    employeeView: {
      label: 'What the employee sees',
      image: '/screenshot-employee-plan.png',
      caption: 'Their own case timeline, document requirements, next steps, provider contacts.',
    },
  },

  cta: {
    headline: 'See the platform in a 30-minute walkthrough.',
    subtext: 'We\'ll walk through your specific relocation types and show you how ReloPass structures them.',
    options: {
      demo: 'Book a demo',
      howItWorks: 'How it works',
      signIn: 'Sign in',
    },
  },
} as const;
