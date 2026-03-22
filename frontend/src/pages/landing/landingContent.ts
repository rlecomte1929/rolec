/**
 * Homepage content. Edit here to change marketing copy without layout changes.
 */

export const landingContent = {
  hero: {
    eyebrow: 'For HR and mobility teams',
    headline: 'Run relocation as one process',
    subheadline:
      'Cases, documents, providers, and status in one place. Less thread-chasing and spreadsheet glue work.',
    primaryCta: 'Book a demo',
    secondaryCta: 'See the platform',
  },

  problem: {
    title: 'Relocation still splits across tools',
    cards: [
      {
        title: 'Scattered coordination',
        body: 'Email, spreadsheets, and vendor threads do not share one case view.',
      },
      {
        title: 'Weak visibility',
        body: 'Hard to see what moved, what is blocked, and who owns the next step.',
      },
      {
        title: 'Heavy follow-up',
        body: 'Too much time on documents, pings, and status checks.',
      },
    ],
  },

  solution: {
    title: 'One structured way to run it',
    blocks: [
      {
        title: 'Case-based workflow',
        body: 'Each move is one trackable case.',
      },
      {
        title: 'Guided steps',
        body: 'Employees see what to do next.',
      },
      {
        title: 'Policy alignment',
        body: 'Work follows company rules and caps.',
      },
      {
        title: 'Provider work in context',
        body: 'Vendor tasks stay tied to the case, not lost in inboxes.',
      },
    ],
  },

  productStrip: {
    blocks: [
      { title: 'Cases', body: 'One case per relocation' },
      { title: 'Service providers', body: 'Activity tied to the case' },
      { title: 'Progress', body: 'See moving, missing, and blocked work' },
    ],
  },

  trust: {
    title: 'Built for teams running real relocations',
    body: 'Workflow, policy-aware guidance, and execution in one system.',
    checklist: [
      'Workflow-first, not chat-first',
      'Policy-aware, not generic tasks',
      'For HR and mobility operators',
      'Built for visibility and follow-through',
    ],
  },

  finalCta: {
    headline: 'Structure how you run relocation',
    microCopy: 'Start with one case.',
    options: {
      demo: 'Book a demo',
      platform: 'See the platform',
      signIn: 'Sign in',
    },
  },
} as const;
