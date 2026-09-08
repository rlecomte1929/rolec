// Pathway v2 — data layer.
// Mocked API functions whose signatures match the real ReloPass contracts exactly.
// Single source of truth: DEMO_CASE.

(function() {

const TARGET_START_DATE = '2026-07-25';     // TODAY (2026-05-18) + 68 days
const TARGET_START_LABEL = '25 Jul 2026';

const DEMO_CASE = {
  id: 'RLP-2026-0317',
  assignmentId: 'demo-assign-001',
  status: 'created',
  createdAt: '2026-04-14T09:12:00Z',
  updatedAt: '2026-05-18T11:03:00Z',
  hrContact: { name: 'Karoline Glad', role: 'Mobility Lead', company: 'Aurora Energy' },
  targetStartDate: TARGET_START_DATE,
  targetStartLabel: TARGET_START_LABEL,
  corridor: {
    origin:      { city: 'Lyon',      country: 'France', code: 'FR' },
    destination: { city: 'Stavanger', country: 'Norway', code: 'NO' },
  },
  reason: 'Work',
  employer: 'Aurora Energy AS',
  policy: {
    name: 'Skilled Worker — EEA Corridor',
    version: 'v2.1',
    updatedAt: '34 days ago',
    updatedBy: 'Karoline Glad',
  },
  draft: {
    relocationBasics: {
      originCountry: 'France', destCountry: 'Norway',
      originCity: 'Lyon',      destCity: 'Stavanger',
      purpose: 'Work',         targetMoveDate: TARGET_START_DATE,
      housingPreference: null, constraints: null,
    },
    employeeProfile: {
      fullName: 'Marc Bouchard',
      nationality: 'French',
      passportCountry: null,                    // asked at intake
      residenceCountry: 'France',
      email: 'marc.bouchard@aurora-energy.com',
    },
    familyMembers: {
      maritalStatus: null,                      // asked at intake
      spouse: null,
      children: [],
    },
    assignmentContext: {
      employerName: 'Aurora Energy AS',
      employerCountry: 'Norway',
      workLocation: 'Stavanger',
      contractType: 'Permanent',
      salaryBand: 'Senior',
      jobTitle: 'Senior Engineer',
      contractStartDate: TARGET_START_DATE,
    },
  },
  // Pre-known family from HR onboarding form (not yet acknowledged by employee at intake)
  knownFamily: {
    spouse: { fullName: 'Léa Bouchard', relationship: 'spouse', nationality: 'French', dateOfBirth: '1990-03-15' },
    children: [{ fullName: 'Camille Bouchard', relationship: 'child', nationality: 'French', dateOfBirth: '2019-06-22' }],
  },
};

// 12 countries used in Q1 and Q2 — matches the spec exactly.
const COUNTRIES_12 = [
  'France', 'Germany', 'United Kingdom', 'Spain', 'Italy', 'Netherlands',
  'Belgium', 'Portugal', 'Switzerland', 'United States', 'India', 'Other',
];

// ─────────────────────────────────────────────────────────────────────────────
// Mocked API (300ms latency) — signatures match real ReloPass backend
// ─────────────────────────────────────────────────────────────────────────────

const wait = (ms) => new Promise(r => setTimeout(r, ms));

// In-memory store. In production this is the backend.
let _store = JSON.parse(JSON.stringify(DEMO_CASE));

async function getCaseByAssignment(assignmentId) {
  await wait(300);
  return { assignment: { id: assignmentId }, case: JSON.parse(JSON.stringify(_store)) };
}

async function getCase(caseId) {
  await wait(300);
  return JSON.parse(JSON.stringify(_store));
}

// Deep-merge partial into _store.draft. Mirrors PATCH /api/cases/:caseId.
async function patchCase(caseId, partial) {
  await wait(300);
  const deepMerge = (a, b) => {
    if (b == null) return a;
    if (typeof b !== 'object' || Array.isArray(b)) return b;
    const out = { ...(a || {}) };
    for (const k of Object.keys(b)) out[k] = deepMerge(a?.[k], b[k]);
    return out;
  };
  _store = { ..._store, draft: deepMerge(_store.draft, partial), updatedAt: new Date().toISOString() };
  return JSON.parse(JSON.stringify(_store));
}

async function createCase(caseId) {
  await wait(300);
  _store.status = 'open';
  return { createdCaseId: caseId, requirementsSnapshotId: 'snap-demo-001' };
}

// Reset (demo helper)
function _resetStore() {
  _store = JSON.parse(JSON.stringify(DEMO_CASE));
}

// ─────────────────────────────────────────────────────────────────────────────
// Plan derivation — pure function of case draft, called on every render.
// Returns the materialised 8-step timeline + family parallel tracks.
// ─────────────────────────────────────────────────────────────────────────────

function deriveTimeline(case_) {
  const draft = case_.draft;
  const family = draft.familyMembers;
  const hasSpouse = family.maritalStatus === 'partner' || family.maritalStatus === 'partner_kids';
  const hasKids   = family.maritalStatus === 'partner_kids' || family.maritalStatus === 'kids_only';

  const steps = [
    {
      n: 1, key: 'sponsorship', title: 'Employer sponsorship letter',
      status: case_.status === 'open' ? 'active' : 'locked',
      owner: 'Employer', where: 'Origin / Remote', time: '1–2 weeks', cost: 'Covered',
      depends: null,
      line: 'Aurora Energy submits a sponsorship declaration to UDI.',
      subs: [
        'HR confirms salary threshold',
        'HR uploads employment contract',
        'Letter issued',
      ],
      waitingNote: 'No action required. Waiting on Aurora Energy.',
    },
    {
      n: 2, key: 'permit', title: 'UDI skilled worker permit application',
      status: 'locked',
      owner: 'You + Employer', where: 'Online (udi.no)', time: '3–5 weeks', cost: '€600',
      depends: 'Step 1',
      line: 'You submit the permit application on udi.no using the employer letter.',
      subs: [
        'Create UDI applicant account',
        'Upload passport copy',
        'Pay NOK 6,900 fee',
        'Submit form',
      ],
      note: {
        variant: 'warning',
        title: 'Norway salary threshold (2026)',
        body: 'Skilled workers must earn NOK 635,500/year. Aurora Energy confirms your salary meets this.',
      },
    },
    {
      n: 3, key: 'docs-origin', title: 'Document gathering — origin side',
      status: 'locked',
      owner: 'You', where: 'France (local)', time: '2–3 weeks', cost: '€80',
      depends: 'Parallel with Step 2',
      line: 'Collect apostilled French civil documents before you leave.',
      subs: [
        'Birth certificate + apostille',
        'Marriage certificate + apostille',
        'Proof of address (last 3 months)',
      ],
    },
    {
      n: 4, key: 'housing', title: 'Housing search',
      status: 'locked',
      owner: 'You', where: 'Stavanger (remote OK)', time: '2–4 weeks', cost: 'Variable',
      depends: 'Step 2 approved',
      line: 'Most landlords require a permit reference or employer letter.',
      subs: [
        'Contact Aurora Energy relocation contact',
        `Finn.no search${draft.relocationBasics.housingPreference ? ` — ${labelForHousing(draft.relocationBasics.housingPreference)} filter applied` : ''}`,
        'Sign lease',
      ],
    },
    {
      n: 5, key: 'police', title: 'Police registration — Norway arrival',
      status: 'locked',
      owner: 'You', where: 'Stavanger police station', time: '1 week', cost: '—',
      depends: 'Permit approved + arrival in Norway',
      line: 'EU/EEA citizens must register within 3 months of arrival.',
      subs: [
        'Book appointment online',
        'Bring: passport, rental contract, employer letter',
        'Receive registration certificate',
      ],
    },
    {
      n: 6, key: 'tax', title: 'Tax registration + D-number',
      status: 'locked',
      owner: 'You', where: 'Skatteetaten', time: '1–2 weeks', cost: '—',
      depends: 'Step 5',
      line: 'A D-number is required before Aurora Energy can process your first payroll.',
      subs: [
        'Submit application with police registration certificate',
        'Receive D-number by post',
        'Provide to Aurora Energy payroll',
      ],
    },
    {
      n: 7, key: 'settle', title: 'Settle-in essentials',
      status: 'locked',
      owner: 'You', where: 'Stavanger', time: 'Ongoing', cost: 'Variable',
      depends: 'Arrival',
      line: 'Practical setup: bank account, SIM, GP registration, school.',
      subs: [
        'Open DNB / SpareBank1 account (D-number required)',
        'Register with local GP',
        hasKids ? 'School enrolment (see Camille\u2019s track)' : 'Set up local services',
      ],
    },
    {
      n: 8, key: 'close', title: 'Case close-out',
      status: 'locked',
      owner: 'HR', where: 'ReloPass', time: '—', cost: '—',
      depends: 'All steps complete',
      line: 'HR marks the case as Arrived and archives the policy record.',
      subs: [],
    },
  ];

  // Family parallel tracks
  const lanes = [];
  if (hasSpouse && family.spouse) {
    lanes.push({
      memberKey: 'spouse',
      memberName: family.spouse.fullName || 'Spouse',
      memberInitials: initials(family.spouse.fullName || 'Spouse'),
      memberLabel: 'Partner',
      step: {
        title: 'Work permit eligibility check',
        anchorTo: 'Step 2',
        owner: `You + ${firstName(family.spouse.fullName)}`,
        where: 'Online', time: '1 week', cost: '—',
        line: 'Spouses of skilled workers may have right to work — confirm with UDI.',
        subs: [
          'Check UDI family reunification rules',
          'Confirm via employer HR',
        ],
      },
    });
  }
  if (hasKids && family.children && family.children.length) {
    family.children.forEach((child, i) => {
      lanes.push({
        memberKey: 'child-' + i,
        memberName: child.fullName || `Child ${i + 1}`,
        memberInitials: initials(child.fullName || `Child ${i + 1}`),
        memberLabel: `Child${ageFromDOB(child.dateOfBirth) ? `, ${ageFromDOB(child.dateOfBirth)}` : ''}`,
        step: {
          title: 'School enrolment — Stavanger international',
          anchorTo: 'Step 4',
          owner: 'You',
          where: 'Stavanger', time: '2–4 weeks', cost: 'Variable',
          line: 'International School of Stavanger (ISS) applications open year-round.',
          subs: [
            'Submit ISS application online',
            'Provide French school records',
            'Confirm start date with school',
          ],
        },
      });
    });
  }

  return {
    totals: { time: '10–14 weeks', cost: '€620', employerCovers: 'Aurora Energy covers employer steps' },
    outcomes: ['Right to live in Norway', 'Right to work', 'Family registered'],
    steps,
    lanes,
  };
}

function labelForHousing(key) {
  return {
    city_centre: 'City centre',
    suburb: 'Suburb',
    near_school: 'Near international school',
    flexible: 'Flexible',
  }[key] || key;
}

function initials(name) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map(s => s[0]).join('').toUpperCase();
}

function firstName(name) {
  return name ? name.split(/\s+/)[0] : '';
}

function ageFromDOB(dob) {
  if (!dob) return null;
  const b = new Date(dob);
  const today = new Date('2026-05-18');
  let age = today.getFullYear() - b.getFullYear();
  const m = today.getMonth() - b.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < b.getDate())) age--;
  return age;
}

Object.assign(window, {
  PATHWAY_V2: {
    DEMO_CASE,
    COUNTRIES_12,
    getCaseByAssignment, getCase, patchCase, createCase, _resetStore,
    deriveTimeline,
    helpers: { initials, firstName, ageFromDOB, labelForHousing },
  },
});

})();
