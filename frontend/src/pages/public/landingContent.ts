/**
 * Homepage content. Edit here to change marketing copy without layout changes.
 */

export const landingContent = {
  hero: {
    eyebrow: 'For HR and mobility teams',
    headline: 'Run relocation as one process',
    subheadline:
      'Cases, documents, providers, and status in one place. Less thread-chasing and spreadsheet glue work.',
    // 'Get started', not 'Book a demo'. This CTA LINKS to /access, a hub whose own
    // first option is another "Book a demo" that opens the modal — so the same label
    // meant "open a modal" in the header and "go to a page and click it again" here.
    // /access is now consistently "Get started" in header, footer and hero, and
    // "Book a demo" means exactly one thing everywhere: it opens the modal.
    primaryCta: 'Get started',
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
        title: 'No single view',
        body: 'Hard to see what moved, what is blocked, and who owns the next step.',
      },
      {
        title: 'Follow-up becomes the work',
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
    title: 'Built for mobility operators.',
    body: 'Workflow, policy-aware guidance, and execution in one system.',
    checklist: [
      'Workflow-first, not chat-first',
      'Policy-aware, not generic tasks',
      'For HR and mobility operators',
      'Built for visibility and follow-through',
    ],
  },

  finalCta: {
    headline: 'Three ways in.',
    microCopy: 'Book a demo, sign in, or create an account.',
    options: {
      demo: 'Book a demo',
      platform: 'See the platform',
      signIn: 'Sign in',
    },
  },
} as const;
