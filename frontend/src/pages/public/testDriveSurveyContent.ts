/**
 * /test-drive/survey completion + 7-question survey content (TD-5 / AIQ-1423).
 * Ported verbatim from docs/test-drive-copy.md (§10 + Survey). Brand voice: no "journey".
 * Only three questions ask for typing and all are optional; the three highest-value
 * asks (testimonial, pilot, intro) sit last, on purpose.
 */
export const testDriveSurveyContent = {
  intro: {
    header: "A few quick questions, then you're done.",
    body:
      "You've run both sides of a case. Tell us how it went — most of these are one tap. If you already left detailed feedback along the way, keep the written ones short.",
  },

  // Personal confidentiality assurance, shown before any personal data is entered.
  privacy:
    "Everything you share here comes to me alone. I treat it as confidential — it's used only to improve ReloPass and to follow up with you, and it's never shared with anyone else.",
  signature: '— Romain Lecomte',

  // TD-FIX-2 (AIQ-1503): one-tap self-ID so friendly feedback can be told apart from
  // real ICP feedback. Required — the single-link model has no other way to tag it.
  segment: {
    label: 'Do you work in HR, mobility, or relocation?',
    helper: 'This tells me whether to read your feedback as an industry view or a friendly one.',
    options: [
      { value: 'prospect', label: 'Yes' },
      { value: 'internal', label: 'No' },
    ],
    required: 'Please pick one so I can weight your feedback correctly.',
  },

  aboutYou: {
    header: 'About you',
    name: { label: 'Your name' },
    email: { label: 'Your email', helper: 'For follow-up only.', invalid: 'Enter a valid email address.' },
    companyRole: { label: 'Company & role', helper: 'Optional; helps me understand whose feedback this is.' },
    sector: {
      label: 'Sector / industry',
      helper: 'Optional; pick the closest.',
      placeholder: 'Select a sector…',
      options: [
        'Energy & utilities',
        'Financial services',
        'Technology & software',
        'Manufacturing & industrial',
        'Pharmaceuticals & life sciences',
        'Healthcare',
        'Consulting & professional services',
        'Consumer goods & retail',
        'Automotive',
        'Aerospace & defence',
        'Telecommunications',
        'Construction & engineering',
        'Logistics & transportation',
        'Media & entertainment',
        'Education',
        'Government & public sector',
      ],
      otherLabel: 'Other…',
      otherPlaceholder: 'Tell us your sector',
    },
  },

  q1: { label: 'Overall, how did running this case feel?', low: '1 = rough', high: '5 = smooth' },
  q2: {
    label: 'Where did you get stuck, confused, or slowed down?',
    helper: 'Be specific — a step, a screen, a moment.',
  },
  q3: {
    label: 'Does ReloPass address a problem you recognize?',
    options: [
      { value: 'yes', label: 'Yes, clearly' },
      { value: 'somewhat', label: 'Somewhat' },
      { value: 'no', label: 'Not really' },
    ],
    whyLabel: 'Why?',
  },
  q4: { label: 'If you could change one thing, what would it be?' },

  highValueIntro: 'The next three are the ones that make this worth running. Kept last, on purpose.',

  q5: {
    label: 'In one sentence, how would you describe ReloPass to someone in your field?',
    consent: 'You can quote me — with my name and company.',
    helper: 'If it landed, a sentence in your words is worth more than any pitch of mine.',
  },
  q6: {
    label: 'Would you or your company want to run a real pilot?',
    options: [
      { value: 'yes', label: "Yes — let's talk" },
      { value: 'maybe', label: 'Maybe, tell me more' },
      { value: 'no', label: 'Not now' },
    ],
    noteLabel: 'Anything that would make it a yes?',
    helper: 'No pressure — even a "maybe" tells me who to keep close.',
  },
  q7: {
    label: 'Who else runs or oversees relocations that I should speak with?',
    name: 'Name',
    companyRole: 'Company / role',
    contact: 'How to reach them (email or LinkedIn)',
    consent: 'You can mention I referred them.',
    helper:
      'A pilot starts with one conversation. An intro to the right person is the most useful thing you can leave me with.',
  },

  submit: 'Submit',

  thankYou: {
    header: "Thanks — that's genuinely useful.",
    body:
      "I'll act on what you flagged. If you offered a pilot or an intro, expect a personal note from me shortly.",
  },
} as const;
