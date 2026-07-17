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

  // TD-FIX-6 (AIQ-1509): newcomer-facing intro. Romain-approved copy, validated
  // 2026-07-12. HARD RULE — plain text only: no bold/emphasis/<strong>/font-weight
  // on any word in either block (including "service providers"). Rendered as plain
  // <p> paragraphs in TestDrivePage.tsx.
  whatReloPassIs: {
    header: 'What ReloPass is',
    paragraphs: [
      "A cross-border move never lives in one place. HR chases documents, the employee guesses what's next, and a dozen service providers — immigration, movers, housing, banking, tax — each work from their own inbox.",
      'ReloPass puts the whole relocation in one place: HR sees exactly where the case stands, the employee gets a clear roadmap, and every service provider stays attached to the case instead of an email thread.',
    ],
  },

  whatWeTest: {
    header: "What we're testing",
    paragraphs: [
      "You're seeing this early, on purpose. Some of you have heard me talk about ReloPass — what I don't know is whether it makes sense to someone opening it cold.",
      'So: run one relocation from both sides — the HR manager who sets it up, and the employee who goes through it. Made-up data, about 20 minutes.',
      "I'm not after polite feedback. Tell me where you got lost, what you expected and didn't get, and whether you'd trust this with a real move. A clear \"no\" is the most useful thing you can give me — better now than after launch.",
    ],
  },

  howItWorks: {
    header: 'How it works',
    steps: [
      { title: 'Enter your first name.', body: 'We generate your HR and employee test accounts from it.' },
      { title: 'Run the HR side.', body: 'Configure the case and hand it to the employee.' },
      { title: 'Run the employee side.', body: 'Complete intake and reach the roadmap.' },
      { title: 'Flag anything, anytime.', body: 'The feedback button stays with you the whole way.' },
      { title: 'Mark it complete.', body: "Answer a few short questions and you're done." },
    ],
    // TD-FIX-5 (AIQ-1506): shown inside the HR step once a corridor is assigned, so the
    // case can't drift off the route we measure. Tokenised — one page serves all corridors.
    // TD-FIX-7 (AIQ-1510): the route is now pre-set and locked on the case (server-side),
    // so this states the fact instead of asking the tester to set a route they have no
    // field for. Plain text.
    corridorInstruction: 'Your route is already set: {origin} → {destination}.',
  },

  aboutData: {
    header: 'About the data',
    // AIQ-1556 correction: the campaign's promise is that the tester enters nothing real,
    // and it must stay literally true. The email is OPTIONAL and consent-based — the only
    // reason to leave it is so Romain can come back to you about your feedback. Nothing is
    // ever emailed to the tester (the logins render on screen), so don't claim otherwise.
    body:
      "Every account, company and case here is synthetic — nothing you enter about the move is personal data, and nothing connects to a live relocation. Use the sample details provided; there's nothing to protect, and nothing to clean up afterward. The email field is optional: leave it only if you're happy for Romain to contact you about your feedback and anything that didn't work. It's used for nothing else, and it never touches the sample relocation data.",
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
      'Once you start the test, the feedback button sits bottom-right the whole way through. Good or bad, one sentence is enough — attach a screenshot if it helps. Everything routes straight to Romain.',
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
    emailLabel: 'Email (optional)',
    emailPlaceholder: 'e.g. alex@company.com',
    emailHelper:
      "Only if you're happy for Romain to come back to you about your feedback and what didn't work. Your two logins appear on this page either way.",
    button: 'Start the test',
    legal: 'Sample data only, apart from your email — kept solely so Romain can follow up on your feedback, and only if you choose to leave one.',
  },

  credentials: {
    header: 'Your two test logins',
    // Authored (not in the copy doc) — the two-login UX risk. Brand-voice compliant (no "journey").
    note:
      "Two logins, one relocation. Start with the HR account to set up the case, then switch to the employee account to run their side. You'll switch between these as you go.",
    hr: { title: 'HR account', caption: 'Start here — configure the case and hand it off.' },
    employee: { title: 'Employee account', caption: 'Then switch to this — complete intake and reach the roadmap.' },
    // TD-FIX-7 (AIQ-1510): restate the assigned route at the moment the tester is about
    // to act, so nobody goes looking for a route to choose. Tokenised; plain text.
    corridorNote: 'Your test: {origin} → {destination} — already set for you.',
    // Testers sign in with the email (login accepts email or username); showing the
    // email keeps the identifier consistent with the sign-in field.
    emailLabel: 'Email',
    passwordLabel: 'Password',
    // AIQ-1539: the credentials block had no way to actually reach the login page — the
    // only sign-in affordance was the top nav, screens away. Give testers a direct link,
    // and one plain line stating where the test ends and that the survey is required.
    signInCta: 'Sign in →',
    signInHref: '/auth?mode=login',
    // AIQ-1569 (TD-BUG-2): the page assumed a logged-out visitor. Anyone with an active
    // ReloPass session — Romain demoing it, or a tester who already has an account —
    // clicked 'Sign in' and dropped straight into their OWN account, not the test HR
    // login. Tokenised {email} so the guard names the account they're actually in.
    signedInNotice:
      "You're already signed in as {email}. The two test logins above are separate accounts — "
      + "signing in now would just drop you back into your own. Sign out first.",
    signedInCta: 'Sign out and use my test account',
    signedOutBusy: 'Signing out…',
    doneNote:
      "You're done when the employee reaches the roadmap. Then mark your test complete below and fill in the short survey — it's required, and it's how your feedback reaches me.",
    completeCta: "I've completed my test",
  },

  errors: {
    firstNameRequired: 'Please enter your first name.',
    // No emailRequired: the email is optional by design (AIQ-1556 correction). Only a
    // malformed address that was actually typed is an error.
    emailInvalid: 'Please enter a valid email address.',
  },
} as const;
