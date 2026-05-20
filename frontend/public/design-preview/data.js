// Pathway — intake questions, options, plan generators.
// All hard-coded; no logic actually runs against real immigration rules.

(function() {

const COUNTRIES = [
  { code: 'FR', name: 'France',         flag: '🇫🇷', eu: true  },
  { code: 'DE', name: 'Germany',        flag: '🇩🇪', eu: true  },
  { code: 'ES', name: 'Spain',          flag: '🇪🇸', eu: true  },
  { code: 'IT', name: 'Italy',          flag: '🇮🇹', eu: true  },
  { code: 'PT', name: 'Portugal',       flag: '🇵🇹', eu: true  },
  { code: 'NL', name: 'Netherlands',    flag: '🇳🇱', eu: true  },
  { code: 'GB', name: 'United Kingdom', flag: '🇬🇧', eu: false },
  { code: 'US', name: 'United States',  flag: '🇺🇸', eu: false },
  { code: 'CA', name: 'Canada',         flag: '🇨🇦', eu: false },
  { code: 'IN', name: 'India',          flag: '🇮🇳', eu: false },
  { code: 'BR', name: 'Brazil',         flag: '🇧🇷', eu: false },
  { code: 'NG', name: 'Nigeria',        flag: '🇳🇬', eu: false },
];

const DESTINATIONS = [
  { code: 'NO', name: 'Norway',         flag: '🇳🇴', eu: false /* EEA */ },
  { code: 'DE', name: 'Germany',        flag: '🇩🇪', eu: true  },
  { code: 'FR', name: 'France',         flag: '🇫🇷', eu: true  },
  { code: 'ES', name: 'Spain',          flag: '🇪🇸', eu: true  },
  { code: 'PT', name: 'Portugal',       flag: '🇵🇹', eu: true  },
  { code: 'NL', name: 'Netherlands',    flag: '🇳🇱', eu: true  },
  { code: 'SE', name: 'Sweden',         flag: '🇸🇪', eu: true  },
  { code: 'IE', name: 'Ireland',        flag: '🇮🇪', eu: true  },
  { code: 'CH', name: 'Switzerland',    flag: '🇨🇭', eu: false },
  { code: 'GB', name: 'United Kingdom', flag: '🇬🇧', eu: false },
  { code: 'CA', name: 'Canada',         flag: '🇨🇦', eu: false },
  { code: 'AU', name: 'Australia',      flag: '🇦🇺', eu: false },
];

const QUESTIONS = [
  {
    id: 'origin',
    prompt: "Where do you live today?",
    why: "I need this to know what papers you'll need before you move.",
    kind: 'country',
    options: COUNTRIES,
  },
  {
    id: 'destination',
    prompt: "Where do you want to go?",
    why: "This is where your new life starts.",
    kind: 'country',
    options: DESTINATIONS,
  },
  {
    id: 'passport',
    prompt: "What's your passport country?",
    why: "Some passports unlock easier paths.",
    kind: 'country',
    options: COUNTRIES,
  },
  {
    id: 'reason',
    prompt: "What's bringing you there?",
    why: "Different reasons follow different roads.",
    kind: 'choice',
    options: [
      { code: 'work',       name: 'Work',                   icon: 'briefcase' },
      { code: 'study',      name: 'Study',                  icon: 'book' },
      { code: 'family',     name: 'Family',                 icon: 'heart' },
      { code: 'investment', name: 'Investment',             icon: 'trending' },
      { code: 'longstay',   name: 'Long-stay / Retirement', icon: 'sun' },
      { code: 'asylum',     name: 'Asylum',                 icon: 'shield' },
    ],
  },
  {
    id: 'offer',
    prompt: "Do you have a job offer yet?",
    why: "Most work permits are anchored to an employer.",
    kind: 'choice',
    showIf: (a) => a.reason === 'work',
    options: [
      { code: 'signed',  name: 'Yes, signed',  icon: 'check'   },
      { code: 'verbal',  name: 'Yes, verbal',  icon: 'handshake' },
      { code: 'looking', name: 'Looking',      icon: 'search'  },
      { code: 'notyet',  name: 'Not yet',      icon: 'clock'   },
    ],
  },
  {
    id: 'family',
    prompt: "Anyone joining you?",
    why: "Family follows a parallel track — I'll add it to your plan.",
    kind: 'choice',
    options: [
      { code: 'solo',         name: 'Just me',        icon: 'user'   },
      { code: 'partner',      name: 'Partner',        icon: 'users'  },
      { code: 'partner_kids', name: 'Partner + kids', icon: 'family' },
      { code: 'kids',         name: 'Kids only',      icon: 'baby'   },
    ],
  },
  {
    id: 'timing',
    prompt: "When do you want to be there?",
    why: "Helps me tell you what to start today vs next month.",
    kind: 'choice',
    options: [
      { code: '3mo',  name: 'Within 3 months', icon: 'fast'    },
      { code: '36',   name: '3–6 months',      icon: 'mid'     },
      { code: '612',  name: '6–12 months',     icon: 'slow'    },
      { code: 'flex', name: 'Flexible',        icon: 'flex'    },
    ],
  },
];

// ─────────────────────────────────────────────────────────────────────────────
// Plan helpers
// ─────────────────────────────────────────────────────────────────────────────

// Status: 'locked' | 'active' | 'waiting' | 'done'
// Who: 'You' | 'Employer' | 'Government' | 'Lawyer'
// Where: 'Origin' | 'Destination' | 'Online'

function makeStep(s) {
  return Object.assign({
    status: 'locked',
    who: 'You',
    where: 'Online',
    time: '1–2 weeks',
    cost: '€0',
    needs: null,
    line: '',
    subs: [],
    advisor: false,
    ai: null,
    note: null,
  }, s);
}

// Path A — France → Norway, Work + signed offer, partner + 1 kid, within 3 mo
function planPathA(answers) {
  return {
    label: 'Path A · EU → EEA · Skilled work',
    totalTime: '10–14 weeks',
    totalCost: '€640',
    outcomes: ['right to live', 'right to work', 'family with you'],
    banner: null,
    steps: [
      makeStep({
        n: 1, title: 'Confirm signed offer with employer',
        status: 'done',
        who: 'Employer', where: 'Online',
        time: 'Done', cost: '€0',
        line: "Your contract is your anchor — everything else hangs off it.",
        subs: [
          'Keep a PDF copy of the signed contract',
          'Confirm start date is at least 8 weeks out',
        ],
        ai: 'Detected: signed offer above the skilled-worker salary threshold.',
      }),
      makeStep({
        n: 2, title: 'Verify Norwegian salary threshold',
        status: 'active',
        who: 'You', where: 'Online',
        time: '2–3 days', cost: '€0',
        needs: 'Step 1',
        line: "Norway requires a minimum salary for skilled workers — quick check, big impact.",
        subs: [
          'Skilled-worker minimum: ~NOK 489,000/yr (Bachelor) or 448,000 (no degree)',
          'Ask HR to confirm gross annual figure in writing',
        ],
        note: 'Norway salary threshold',
        ai: "Your offer (NOK 612k) clears the threshold by 25%.",
      }),
      makeStep({
        n: 3, title: 'Register as EU/EEA citizen online',
        status: 'waiting',
        who: 'You', where: 'Online',
        time: '30 minutes', cost: '€0',
        needs: 'Step 2',
        line: "Your French passport skips the residence-permit queue — you register, you don't apply.",
        subs: [
          'Use UDI online portal (udi.no)',
          'Upload passport scan + employment contract',
          'You can move before this is finalised',
        ],
        ai: 'EU/EEA route saves ~6 weeks vs. third-country work permit.',
      }),
      makeStep({
        n: 4, title: 'Move to Norway',
        status: 'waiting',
        who: 'You', where: 'Origin → Destination',
        time: 'Travel day', cost: '€200–400',
        needs: 'Step 3',
        line: "Bring originals of everything — Norway likes paper.",
        subs: [
          'Passport, marriage certificate, child birth certificate (apostilled)',
          'Print Step 3 registration receipt',
        ],
      }),
      makeStep({
        n: 5, title: 'Police registration (within 3 months of arrival)',
        status: 'locked',
        who: 'Government', where: 'Destination',
        time: '1 appointment', cost: '€0',
        needs: 'Step 4',
        line: "Book the slot the day you land — they fill up fast in Oslo.",
        subs: [
          'Book at politiet.no',
          'Bring passport + employment contract + registration receipt',
        ],
      }),
      makeStep({
        n: 6, title: 'Get D-number / national ID',
        status: 'locked',
        who: 'Government', where: 'Destination',
        time: '2–4 weeks', cost: '€0',
        needs: 'Step 5',
        line: "This unlocks everything: bank, doctor, tax, salary.",
        subs: [
          'Tax office (Skatteetaten) appointment',
          'Bring police registration certificate',
        ],
      }),
      makeStep({
        n: 7, title: 'Family registration — partner + child',
        status: 'locked',
        who: 'You', where: 'Online + Destination',
        time: '3–5 weeks', cost: '€240',
        needs: 'Step 3',
        line: "Parallel track — your family can register the same day you do.",
        subs: [
          'Marriage certificate (apostille + translation)',
          'Child birth certificate (apostille + translation)',
          'Proof of shared accommodation',
        ],
        advisor: true,
        ai: 'Apostille typically takes 2 weeks in France — start this in parallel with Step 2.',
      }),
      makeStep({
        n: 8, title: 'Tax card + bank account',
        status: 'locked',
        who: 'You', where: 'Destination',
        time: '1–2 weeks', cost: '€0',
        needs: 'Step 6',
        line: "Without a tax card, your first paycheck withholds 50%. Don't skip.",
        subs: [
          'Request skattekort online (Skatteetaten)',
          'Open bank account with D-number + employment contract',
        ],
      }),
    ],
  };
}

// Path B — India → Germany, Work looking, just me, 6–12 months
function planPathB(answers) {
  return {
    label: 'Path B · Third-country · Job-seeker → Work',
    totalTime: '6–10 months',
    totalCost: '€820',
    outcomes: ['right to live', 'right to work', 'path to permanent residence'],
    banner: null,
    steps: [
      makeStep({
        n: 1, title: 'Find a qualifying employer',
        status: 'active',
        who: 'You', where: 'Origin',
        time: '8–16 weeks', cost: '€0',
        line: "Without an offer, your timeline starts the day you sign — let's get you there.",
        subs: [
          'Target Blue Card-eligible roles (€45,300+ for STEM)',
          'Apply via LinkedIn DE, StepStone, Make-it-in-Germany',
          'Optional: Job Seeker Visa (6 months in Germany to job-hunt)',
        ],
        ai: 'Your degree (Computer Science, IIT) typically clears Blue Card minimum.',
      }),
      makeStep({
        n: 2, title: 'Recognise your qualifications (anabin / ZAB)',
        status: 'active',
        who: 'You', where: 'Online',
        time: '4–6 weeks', cost: '€200',
        line: "Germany wants proof your degree is equivalent — start this today, it runs in parallel.",
        subs: [
          'Check anabin database (free, instant)',
          'If not listed: ZAB Statement of Comparability (€200, 4–6w)',
          'Order from kmk.org',
        ],
        ai: 'IIT degrees are H+/+ rated — likely no ZAB statement needed.',
      }),
      makeStep({
        n: 3, title: 'Receive signed offer',
        status: 'waiting',
        who: 'Employer', where: 'Origin',
        time: 'Variable', cost: '€0',
        needs: 'Step 1',
        line: "Don't sign until salary clears the Blue Card threshold for your field.",
        advisor: true,
      }),
      makeStep({
        n: 4, title: 'Employer files pre-approval (if needed)',
        status: 'locked',
        who: 'Employer', where: 'Origin',
        time: '2–4 weeks', cost: '€0',
        needs: 'Step 3',
        line: "Most STEM Blue Card roles skip this — your employer will confirm.",
        subs: [
          'BA (Bundesagentur für Arbeit) consent if required',
        ],
      }),
      makeStep({
        n: 5, title: 'Apply for D-visa at German consulate (Mumbai/Delhi)',
        status: 'locked',
        who: 'You', where: 'Origin',
        time: '6–12 weeks', cost: '€75',
        needs: 'Step 3',
        line: "Book the slot the moment you have the signed offer — appointments are 8+ weeks out.",
        subs: [
          'Documents: passport, offer letter, anabin/ZAB, CV, photos',
          'Biometrics at appointment',
          'Health insurance certificate',
        ],
        advisor: true,
      }),
      makeStep({
        n: 6, title: 'Travel to Germany',
        status: 'locked',
        who: 'You', where: 'Origin → Destination',
        time: 'Travel day', cost: '€500–800',
        needs: 'Step 5',
        line: "Arrive at least 2 weeks before your start date — you'll need that buffer.",
      }),
      makeStep({
        n: 7, title: 'Anmeldung — register your address',
        status: 'locked',
        who: 'Government', where: 'Destination',
        time: '1 appointment', cost: '€0',
        needs: 'Step 6',
        line: "Within 2 weeks of moving in. No Anmeldung = no bank, no contract, no anything.",
        subs: [
          'Bürgeramt appointment (book before you land)',
          'Landlord confirmation (Wohnungsgeberbestätigung)',
        ],
      }),
      makeStep({
        n: 8, title: 'Apply for residence permit at Ausländerbehörde',
        status: 'locked',
        who: 'Government', where: 'Destination',
        time: '4–8 weeks', cost: '€100',
        needs: 'Step 7',
        line: "Your D-visa converts to a residence permit (or Blue Card) here.",
        subs: [
          'Bring Anmeldung, contract, passport, photos',
          'Blue Card → 33 months → permanent residence',
        ],
      }),
      makeStep({
        n: 9, title: 'Health insurance + Tax ID',
        status: 'locked',
        who: 'You', where: 'Destination',
        time: '1–2 weeks', cost: '€0',
        needs: 'Step 7',
        line: "Tax ID arrives by post after Anmeldung — health insurance you choose yourself.",
        subs: [
          'TK, AOK, or Barmer for statutory (gesetzlich)',
          'First salary deducts ~14.6% for health',
        ],
      }),
    ],
  };
}

// EU → EU short plan (3 steps)
function planEUtoEU(answers) {
  return {
    label: 'EU citizen · Free movement',
    totalTime: '4–8 weeks',
    totalCost: '€20',
    outcomes: ['right to live', 'right to work', 'no permit needed'],
    banner: 'As an EU citizen moving inside the EU, you don\'t need a visa or permit — only registration.',
    steps: [
      makeStep({
        n: 1, title: 'Move when you\'re ready',
        status: 'active',
        who: 'You', where: 'Origin → Destination',
        time: 'Whenever', cost: '€200–500',
        line: "Your passport is your visa. You can start work the day you arrive.",
      }),
      makeStep({
        n: 2, title: 'Register your residence locally',
        status: 'waiting',
        who: 'Government', where: 'Destination',
        time: '1 appointment', cost: '€20',
        needs: 'Step 1',
        line: "Usually within 3 months of arrival — town hall or equivalent.",
        subs: [
          'Bring passport + proof of address',
          'Proof of work or sufficient resources',
        ],
      }),
      makeStep({
        n: 3, title: 'Get your tax number + healthcare',
        status: 'locked',
        who: 'You', where: 'Destination',
        time: '1–2 weeks', cost: '€0',
        needs: 'Step 2',
        line: "Unlocks salary, bank, doctor.",
      }),
    ],
  };
}

function planGeneric(answers) {
  return {
    label: 'Generic plan',
    totalTime: '~6 months',
    totalCost: '~€500',
    outcomes: ['right to live', 'right to work'],
    banner: 'Demo limited to two paths (France→Norway, India→Germany). Production covers all routes — this is a generic skeleton.',
    steps: [
      makeStep({ n: 1, title: 'Gather core documents', status: 'active', who: 'You', where: 'Origin', time: '1–2 weeks', cost: '€50', line: 'Passport, civil status, qualifications, financial proof.' }),
      makeStep({ n: 2, title: 'Choose visa category', status: 'waiting', who: 'You', where: 'Online', time: '2–3 days', cost: '€0', needs: 'Step 1', line: 'Match your reason to the right route.', advisor: true }),
      makeStep({ n: 3, title: 'Submit application at consulate', status: 'locked', who: 'You', where: 'Origin', time: '2–4 weeks', cost: '€100–300', needs: 'Step 2', line: 'Biometrics + interview.' }),
      makeStep({ n: 4, title: 'Wait for decision', status: 'locked', who: 'Government', where: 'Online', time: '4–12 weeks', cost: '€0', needs: 'Step 3', line: 'Most outcomes arrive by post or portal.' }),
      makeStep({ n: 5, title: 'Travel + arrival', status: 'locked', who: 'You', where: 'Origin → Destination', time: 'Travel day', cost: '€500+', needs: 'Step 4', line: 'Carry originals.' }),
      makeStep({ n: 6, title: 'Local registration', status: 'locked', who: 'Government', where: 'Destination', time: '1–2 weeks', cost: '€0', needs: 'Step 5', line: 'Address, tax ID, residence card.' }),
    ],
  };
}

// Identify which demo path the answers match
function classifyAnswers(a) {
  if (!a.origin || !a.destination || !a.passport || !a.reason || !a.family || !a.timing) return 'incomplete';
  if (a.reason === 'work' && !a.offer) return 'incomplete';

  const passportEU = COUNTRIES.find(c => c.code === a.passport)?.eu;
  const destEU     = DESTINATIONS.find(c => c.code === a.destination)?.eu;

  if (a.origin === 'FR' && a.destination === 'NO' && a.reason === 'work' && a.offer === 'signed'
      && (a.family === 'partner_kids' || a.family === 'partner') && a.timing === '3mo') return 'A';
  if (a.origin === 'IN' && a.destination === 'DE' && a.reason === 'work' && a.offer === 'looking'
      && a.family === 'solo' && a.timing === '612') return 'B';

  if (passportEU && destEU) return 'EU';
  return 'generic';
}

function buildPlan(answers) {
  const c = classifyAnswers(answers);
  if (c === 'A')  return planPathA(answers);
  if (c === 'B')  return planPathB(answers);
  if (c === 'EU') return planEUtoEU(answers);
  return planGeneric(answers);
}

// Materialise a partial plan during intake — shows steps that have "locked in" based on answers
function planSilhouette(answers) {
  const captured = ['origin', 'destination', 'passport', 'reason', 'offer', 'family', 'timing']
    .filter(k => answers[k] != null).length;
  // 8 silhouette slots; reveal as we go
  const slots = 8;
  const filled = Math.min(slots, Math.round((captured / 7) * slots));
  return { slots, filled };
}

// Compute progress 0..100 from answers — meaningful info captured, not clicks
function computeProgress(answers, screen) {
  if (screen === 'welcome') return 0;
  if (screen === 'plan')    return 100;
  const fields = ['origin', 'destination', 'passport', 'reason', 'family', 'timing'];
  const needOffer = answers.reason === 'work';
  if (needOffer) fields.push('offer');
  const captured = fields.filter(f => answers[f] != null).length;
  return Math.round((captured / fields.length) * 95); // cap at 95 until plan generated
}

Object.assign(window, {
  PATHWAY_DATA: {
    COUNTRIES, DESTINATIONS, QUESTIONS,
    buildPlan, classifyAnswers, planSilhouette, computeProgress,
  },
});

})(); // end IIFE
