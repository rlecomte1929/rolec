/**
 * /test-drive page content (TD-3 / AIQ-1421).
 *
 * Copy ported verbatim from docs/test-drive-copy.md (brand voice: no "journey").
 * Corridor model from docs/beta-test-campaign-spec.md §2 — canonical underscore ids
 * (matches backend corridor_registry.normalize_corridor_id + test_sessions.corridor_id).
 * One page serves all five corridors via the `?corridor=` token; the Tier-B
 * early-coverage note renders only for the three Tier-B ids.
 */

export type CorridorTier = 'A' | 'B';

export interface CorridorMeta {
  origin: string;
  destination: string;
  tier: CorridorTier;
}

const FR_NO: CorridorMeta = { origin: 'Paris', destination: 'Oslo', tier: 'A' };

export const TEST_DRIVE_CORRIDORS: Record<string, CorridorMeta> = {
  FR_NO,
  IN_DE: { origin: 'India', destination: 'Munich', tier: 'A' },
  GB_US: { origin: 'London', destination: 'New York', tier: 'B' },
  NL_SG: { origin: 'Amsterdam', destination: 'Singapore', tier: 'B' },
  ES_AE: { origin: 'Madrid', destination: 'Dubai', tier: 'B' },
};

export const DEFAULT_CORRIDOR_ID = 'FR_NO';
export const DEFAULT_CORRIDOR: CorridorMeta = FR_NO;

export const testDriveContent = {
  hero: {
    // Rendered as `Beta test · {origin} → {destination}`.
    eyebrowPrefix: 'Beta test',
    headline: 'Run one relocation, end to end.',
    subhead:
      "You'll act as both the HR manager and the relocating employee on a single corridor — from case setup to the employee's roadmap. About 20 minutes, on sample data.",
  },

  corridorLabel: {
    prefix: 'Your corridor:',
    tierBNote:
      "This corridor is in early coverage. Expect gaps in the guidance — flagging them is exactly what we're testing.",
  },

  whatWeTest: {
    header: "What we're testing",
    body:
      "ReloPass is the coordination layer across HR, employees, and providers. This test checks one thing: does a case stay visible, compliant, and on-time from the first HR action to the employee's roadmap? Run it, and tell us where it holds and where it breaks.",
  },

  howItWorks: {
    header: 'How it works',
    steps: [
      { title: 'Enter your first name.', body: 'We generate your HR and employee test accounts from it.' },
      { title: 'Run the HR side.', body: 'Configure the case and hand it to the employee.' },
      { title: 'Run the employee side.', body: 'Complete intake and reach the roadmap.' },
      { title: 'Flag anything, anytime.', body: 'The feedback button stays with you the whole way.' },
      { title: 'Mark it complete.', body: "Answer five short questions and you're done." },
    ],
  },

  aboutData: {
    header: 'About the data',
    body:
      "Every account and case here is synthetic. Nothing you enter is personal data, and nothing connects to a live relocation. Use the sample details provided — there's nothing to protect, and nothing to clean up afterward.",
  },

  videos: {
    header: 'Before you start',
    intro:
      'Three short clips. Watch them or skip them — the flow is self-explanatory either way.',
    // file/poster live in frontend/public/test-drive/ (TD-11). A clip with no `file`
    // renders the static placeholder (graceful degrade).
    clips: [
      { label: 'Getting started — 40 sec', description: 'Enter your name, get your two logins, and where to sign in.', file: '/test-drive/start.mp4', poster: '/test-drive/start.jpg' },
      { label: 'The HR side — 65 sec', description: 'Open a case and hand it to the employee.', file: '/test-drive/hr.mp4', poster: '/test-drive/hr.jpg' },
      { label: 'The employee side — 95 sec', description: 'Sign in, complete intake, and reach the roadmap.', file: '/test-drive/employee.mp4', poster: '/test-drive/employee.jpg' },
    ],
  },

  feedback: {
    header: 'See something off?',
    body:
      'The feedback button sits bottom-right the whole time. Good or bad, one sentence is enough — attach a screenshot if it helps. Everything routes straight to Romain.',
  },

  // Dedicated, always-available exit to the survey (TD-5). Rendered on /test-drive
  // only once a session exists, so testers can stop and give feedback at any point.
  wrapUp: {
    header: 'Finish with the survey',
    body:
      "Every test ends with a short survey — a few quick questions, about three minutes. It's how your feedback actually reaches me, so I'm counting on you to complete it. Open it anytime: whether you ran the whole case or had to stop early, your answers are just as useful.",
    button: 'Take the survey',
    note: 'This carries your session so I know which run the feedback is about.',
  },

  startBlock: {
    header: 'Start the test',
    fieldLabel: 'First name',
    placeholder: 'e.g. Alex',
    helper: "We'll generate your HR and employee test accounts from this.",
    button: 'Start the test',
    legal: 'Sample data only. No personal data is stored from this test.',
  },

  credentials: {
    header: 'Your two test logins',
    // Authored (not in the copy doc) — the two-login UX risk. Brand-voice compliant (no "journey").
    note:
      "Two logins, one relocation. Start with the HR account to set up the case, then switch to the employee account to run their side. You'll switch between these as you go.",
    hr: { title: 'HR account', caption: 'Start here — configure the case and hand it off.' },
    employee: { title: 'Employee account', caption: 'Then switch to this — complete intake and reach the roadmap.' },
    // Testers sign in with the email (login accepts email or username); showing the
    // email keeps the identifier consistent with the sign-in field.
    emailLabel: 'Email',
    passwordLabel: 'Password',
    completeCta: "I've completed my test",
  },

  errors: {
    firstNameRequired: 'Please enter your first name.',
  },
} as const;
