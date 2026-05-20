/**
 * Why ReloPass: problem and differentiation. No full process diagram.
 *
 * Phase 3 copy + visual upgrade — April 2026
 */

export const whyReloPassContent = {
  hero: {
    eyebrow: 'For HR and mobility teams',
    headline: 'Relocation fails in the handoffs.',
    subheadline:
      'Not because teams aren\'t capable. Because the tools aren\'t built for coordination.',
    primaryCta: 'Book a demo',
    secondaryCta: 'See the platform',
    trustMicrocopy: '30-minute walkthrough. No commitment.',
  },

  currentReality: {
    title: 'Relocation is a coordination problem first.',
    items: [
      'Most relocation failures are not policy failures. They are coordination failures. Tasks dropped between HR, employees, and vendors. Documents requested twice and never tracked. Timelines managed in threads. Status buried in inboxes.',
      'The tools that exist either own the service (agencies) or help with one part of the problem (document tools, vendor directories, HR modules). None of them are built to coordinate the whole workflow.',
      'ReloPass is the coordination layer. Not a service. Not a marketplace. The system through which HR, employees, and providers operate in one structured workflow.',
    ],
    supportingLine: 'Relocations complete. The coordination cost stays high.',
  },

  thesis:
    'ReloPass is not a better version of what exists. It is a different kind of tool — one built specifically to structure the execution of relocation, not just support it from the edges.',

  toolsFailure: {
    title: 'Why current tools fail',
    columns: [
      {
        label: 'Relocation agencies',
        body: 'Agencies own the service. They don\'t give HR visibility into what\'s happening or why. You get outcomes without control.',
      },
      {
        label: 'Spreadsheets and email',
        body: 'Manual tracking breaks at scale. Status is wherever the last email is. Nothing is auditable. Nothing is proactive.',
      },
      {
        label: 'HR platform add-ons',
        body: 'Generic workflow tools aren\'t built for relocation complexity: corridors, compliance, multi-vendor coordination, document chains.',
      },
    ],
    bridgingLine: 'ReloPass is not any of these. It is the operating layer that connects them.',
  },

  differentiation: {
    title: 'Without ReloPass vs. With ReloPass',
    categoryBoundary: {
      positive: 'One system of record for every cross-border relocation.',
      negatives: [
        'Not a relocation agency.',
        'Not a vendor marketplace.',
        'Not an HR add-on.',
      ],
    },
    contrastRows: [
      { dimension: 'Status', without: 'In inboxes, spreadsheets, and chased by phone', with: 'Visible in the case, updated by the system' },
      { dimension: 'Documents', without: 'Requested manually, tracked in email', with: 'Tied to the case with completion status' },
      { dimension: 'Providers', without: 'Operating outside HR\'s view', with: 'Assigned tasks inside the case, progress visible' },
      { dimension: 'Policy', without: 'Applied inconsistently', with: 'Encoded as operating rules at case creation' },
      { dimension: 'Compliance', without: 'Reconstructed after the fact', with: 'Logged automatically throughout the case' },
      { dimension: 'Handoffs', without: 'The main source of failure', with: 'Structured, sequenced, and tracked' },
    ],
    productAnchor:
      'When a document uploads, the case updates. HR does not need to chase the provider.',
    blocks: [
      {
        title: 'Case at the center',
        body: 'Each case has structure, status, and next steps built in.',
      },
      {
        title: 'Less chasing',
        body: 'The workflow carries the coordination. The team stops hunting updates.',
      },
    ],
  },

  categoryFraming: {
    title: 'A new category: mobility operations.',
    body: 'ReloPass is not a better version of what exists. It is a different kind of tool — one built specifically to structure the execution of relocation, not just support it from the edges.',
    positionedLine: 'For HR teams running relocation at scale, the question is no longer which vendor to use. It is whether relocation has an operating system.',
  },

  outcomes: {
    title: 'Day-to-day impact',
    items: [
      'One case view instead of four tools open at once.',
      'Move blocked cases without losing thread on the others.',
      'Updates reach HR through the case, not another email chain.',
    ],
    supportingLine: 'The case does the coordination. The team does the work.',
    image: '/screenshot-hr-assignments.png',
    imageAlt:
      'HR assignments view showing active relocations with corridors, statuses, and deadlines on one record.',
  },

  peakCta: {
    headline: 'Every relocation case is visible, compliant, on-time.',
    primaryCta: 'Book a demo',
  },

  cta: {
    headline: 'See how it changes the way relocation runs.',
    options: {
      demo: 'Book a demo',
      howItWorks: 'How it works',
      signIn: 'Sign in',
    },
  },
} as const;
