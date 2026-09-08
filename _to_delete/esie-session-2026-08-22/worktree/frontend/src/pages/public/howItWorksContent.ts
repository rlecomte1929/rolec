/**
 * How it works page — 4-step operational sequence.
 * Phase 3 — April 2026
 */

export const howItWorksContent = {
  hero: {
    eyebrow: 'For HR and mobility teams',
    headline: 'Four steps from fragmented to structured.',
    subheadline:
      'ReloPass is configured to your policy and corridors, then runs every case through the same structured workflow.',
    trustMicrocopy: '30-minute walkthrough. No commitment.',
  },

  steps: [
    {
      number: '01',
      title: 'Configure your policy and corridors.',
      body: 'Define the relocation types you run, the steps required for each, the documents needed, and the providers assigned. This becomes the operating rulebook.',
      image: '/screenshot-hr-assignments.png',
      imageAlt:
        'Policy configuration screen showing corridor selector and required steps list.',
    },
    {
      number: '02',
      title: 'Open a case and apply the policy.',
      body: 'When a relocation begins, create the case, assign the corridor, and let the system generate the structured workflow automatically. No manual assembly.',
      image: '/screenshot-hero-case-card.png',
      imageAlt:
        'Case creation modal showing corridor applied and timeline preview generated.',
    },
    {
      number: '03',
      title: 'Coordinate tasks across HR, employees, and providers.',
      body: 'Tasks route to the right party at the right time. Documents are requested and tracked. Vendors receive structured assignments inside the case.',
      image: '/screenshot-provider-recommendations.png',
      imageAlt:
        'Task assignment view showing multi-party task routing and status per task.',
    },
    {
      number: '04',
      title: 'Track progress to compliant close.',
      body: 'Monitor open items, exceptions, and milestones. Every case closes with a complete evidence log. Audit-ready on day one.',
      image: '/screenshot-employee-plan.png',
      imageAlt:
        'Case timeline at completion showing completed states, evidence log, and close status.',
    },
  ],

  setupTimeline: [
    {
      phase: 'Week 1',
      label: 'Policy configuration',
      description: 'Your relocation types, corridors, and operating rules are configured with your team.',
    },
    {
      phase: 'Week 2',
      label: 'First cases',
      description: 'Run live cases through the system. Validate workflows against your existing process.',
    },
    {
      phase: 'Ongoing',
      label: 'Full operation',
      description: 'Every new case opens in ReloPass. HR has visibility. Providers are coordinated. Cases close with evidence.',
    },
  ],

  cta: {
    headline: 'Start with one corridor. Run it in ReloPass.',
    subtext: 'Most teams are fully operational within two weeks.',
    primaryCta: 'Book a demo',
    secondaryCta: 'See the platform',
    trustMicrocopy: '30-minute walkthrough. No commitment.',
  },
} as const;
