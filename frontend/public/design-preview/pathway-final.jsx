// Pathway Final — single-file React prototype.
// 5-question intake + hard-coded Path A (FR→NO) and Path B (IN→DE) outputs.

(function() {
const { useState, useEffect } = React;

// ─── Inline icon component (lucide-style) ───
const I = ({ n, s = 16, sw = 1.75 }) => {
  const p = { width: s, height: s, viewBox: '0 0 24 24', fill: 'none',
    stroke: 'currentColor', strokeWidth: sw, strokeLinecap: 'round', strokeLinejoin: 'round' };
  const M = {
    arrowR: <path d="M5 12h14M13 5l7 7-7 7"/>,
    arrowL: <path d="M19 12H5M11 5l-7 7 7 7"/>,
    check:  <path d="M20 6 9 17l-5-5"/>,
    chevD:  <path d="m6 9 6 6 6-6"/>,
    chevR:  <path d="m9 6 6 6-6 6"/>,
    info:   <><circle cx="12" cy="12" r="9"/><path d="M12 16v-4M12 8h.01"/></>,
    edit:   <><path d="M11 4H5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h13a2 2 0 0 0 2-2v-6"/><path d="M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4z"/></>,
    lock:   <><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></>,
    msg:    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>,
    play:   <polygon points="6 4 20 12 6 20 6 4" fill="currentColor"/>,
    x:      <path d="M18 6 6 18M6 6l12 12"/>,
  };
  return <svg {...p}>{M[n] || <circle cx="12" cy="12" r="3"/>}</svg>;
};

// ─── Question data ───
// Each question maps to a draft field (.section.field) per the spec.
const QUESTIONS = [
  {
    id: 'origin',
    section: 'relocationBasics', field: 'originCountry',
    title: 'Where are you moving from?',
    info: 'Used for the residency permit application.',
    summary: 'From',
    kind: 'country',
    options: [
      { code: 'FR', label: 'France',      flag: '🇫🇷' },
      { code: 'DE', label: 'Germany',     flag: '🇩🇪' },
      { code: 'GB', label: 'UK',          flag: '🇬🇧' },
      { code: 'ES', label: 'Spain',       flag: '🇪🇸' },
      { code: 'NL', label: 'Netherlands', flag: '🇳🇱' },
      { code: 'IN', label: 'India',       flag: '🇮🇳' },
      { code: 'US', label: 'USA',         flag: '🇺🇸' },
    ],
  },
  {
    id: 'destination',
    section: 'relocationBasics', field: 'destCountry',
    title: 'Where are you going?',
    info: 'Determines which visa pathway applies.',
    summary: 'To',
    kind: 'country',
    options: [
      { code: 'FR', label: 'France',      flag: '🇫🇷' },
      { code: 'DE', label: 'Germany',     flag: '🇩🇪' },
      { code: 'GB', label: 'UK',          flag: '🇬🇧' },
      { code: 'NO', label: 'Norway',      flag: '🇳🇴' },
      { code: 'NL', label: 'Netherlands', flag: '🇳🇱' },
      { code: 'CA', label: 'Canada',      flag: '🇨🇦' },
      { code: 'US', label: 'USA',         flag: '🇺🇸' },
    ],
  },
  {
    id: 'reason',
    section: 'relocationBasics', field: 'purpose',
    title: "What's bringing you there?",
    info: 'Different reasons follow different routes.',
    summary: 'Reason',
    kind: 'choice',
    options: [
      { code: 'work',    label: 'Work' },
      { code: 'study',   label: 'Study' },
      { code: 'family',  label: 'Family' },
      { code: 'longstay',label: 'Long stay / Retirement' },
    ],
  },
  {
    id: 'family',
    section: 'familyMembers', field: 'maritalStatus',
    title: "Who's moving with you?",
    info: 'Each person needs their own track and documents.',
    summary: 'With',
    kind: 'choice',
    options: [
      { code: 'solo',         label: 'Just me' },
      { code: 'partner',      label: 'Partner' },
      { code: 'partner_kids', label: 'Partner + children' },
      { code: 'kids',         label: 'Children only' },
    ],
  },
  {
    id: 'timing',
    section: 'relocationBasics', field: 'targetMoveDate',
    title: 'When do you want to arrive?',
    info: 'Sets the urgency of your timeline.',
    summary: 'When',
    kind: 'choice',
    options: [
      { code: '3mo', label: 'Within 3 months' },
      { code: '36',  label: '3–6 months' },
      { code: '612', label: '6–12 months' },
      { code: 'flex',label: 'Flexible' },
    ],
  },
];

// ─── Hard-coded plans ───

function planA() {
  return {
    label: 'France → Norway · Skilled work',
    flagFrom: '🇫🇷', from: 'France', flagTo: '🇳🇴', to: 'Norway',
    totalTime: '10–14 weeks',
    totalCost: '~€680',
    outcomes: ['Right to live', 'Right to work', 'Family settled'],
    steps: [
      {
        n: 1, status: 'active', title: 'Employer sponsorship letter',
        owner: 'Employer', time: '1–2 weeks', cost: 'Covered',
        line: 'Aurora Energy submits a declaration to UDI before you can apply.',
        subs: [
          'HR confirms salary meets NOK 635,500 threshold',
          'HR uploads contract',
        ],
      },
      {
        n: 2, status: 'locked', title: 'UDI skilled worker permit (online)',
        owner: 'You', time: '3–5 weeks', cost: '€600', needs: 'Step 1',
        line: 'Apply at udi.no with the employer letter and your passport.',
        subs: [
          'Create UDI account',
          'Upload passport',
          'Pay NOK 6,900',
          'Submit',
        ],
        advisor: true,
      },
      {
        n: 3, status: 'locked', title: 'Apostille documents — France side',
        owner: 'You', time: '2–3 weeks', cost: '€80', needs: 'Parallel with Step 2',
        line: 'Collect apostilled French civil documents before you leave.',
        subs: [
          'Birth certificate',
          'Marriage certificate',
          'Proof of address',
        ],
      },
      {
        n: 4, status: 'locked', title: 'Housing search — Stavanger',
        owner: 'You', time: '2–4 weeks', cost: 'Variable', needs: 'Step 2',
        line: 'Most landlords need your permit reference or employer letter.',
        subs: [
          'finn.no search',
          'Contact employer relocation contact',
          'Sign lease',
        ],
      },
      {
        n: 5, status: 'locked', title: 'Family documents (partner + children)',
        owner: 'You', time: '2 weeks', cost: '€120', needs: 'Parallel with Steps 2–4',
        line: 'Partner and children need their own apostilled documents.',
        subs: [
          'Partner birth certificate',
          'Children birth certificates',
          'Marriage certificate',
        ],
      },
      {
        n: 6, status: 'locked', title: 'Police registration on arrival',
        owner: 'You', time: '1 week', cost: 'Free', needs: 'Arrival',
        line: 'Register at Stavanger police station within 3 months of arrival.',
        subs: [
          'Book appointment',
          'Bring passport + rental contract + employer letter',
        ],
      },
      {
        n: 7, status: 'locked', title: 'Tax D-number registration',
        owner: 'You', time: '1–2 weeks', cost: 'Free', needs: 'Step 6',
        line: 'Required before your first payroll at Aurora Energy.',
        subs: [
          'Submit with police certificate',
          'Receive D-number by post',
        ],
      },
      {
        n: 8, status: 'locked', title: 'Settle in: bank, GP, school',
        owner: 'You', time: 'Ongoing', cost: 'Variable', needs: 'D-number',
        line: 'Practical setup once you have your D-number.',
        subs: [
          'Open bank account (DNB or SpareBank1)',
          'Register with GP',
          'Enrol children in school',
        ],
      },
    ],
  };
}

function planB() {
  return {
    label: 'India → Germany · Skilled work',
    flagFrom: '🇮🇳', from: 'India', flagTo: '🇩🇪', to: 'Germany',
    totalTime: '16–24 weeks',
    totalCost: '~€900',
    outcomes: ['Right to live', 'Right to work', 'Path to permanent residence'],
    steps: [
      {
        n: 1, status: 'active', title: 'Gather qualification documents',
        owner: 'You', time: '2–4 weeks', cost: '€50',
        line: 'Germany requires certified translations of your degree and transcripts.',
        subs: [
          'Collect originals',
          'Get certified German translations',
          'Apostille if required',
        ],
      },
      {
        n: 2, status: 'locked', title: 'Credential recognition (anabin / KMK)',
        owner: 'You', time: '4–8 weeks', cost: 'Free', needs: 'Step 1',
        line: 'Check your qualification at anabin.kmk.org — required for most work visas.',
        subs: [
          'Search your university in anabin',
          'If not listed, apply for KMK assessment',
        ],
        advisor: true,
      },
      {
        n: 3, status: 'locked', title: 'Job offer formalisation',
        owner: 'Employer + You', time: '1–2 weeks', cost: 'Free', needs: 'Step 2 in progress',
        line: 'You need a written offer referencing the job title and salary before applying.',
        subs: [
          'Confirm offer in writing',
          'Verify salary meets minimum wage threshold',
        ],
      },
      {
        n: 4, status: 'locked', title: 'German national visa application (D-visa)',
        owner: 'You', time: '2–4w appt + 8–12w processing', cost: '€75', needs: 'Steps 1–3',
        line: 'Apply at the German consulate in India with your offer letter and credentials.',
        subs: [
          'Book appointment at German consulate',
          'Prepare document pack',
          'Attend interview',
          'Pay fee',
        ],
        advisor: true,
      },
      {
        n: 5, status: 'locked', title: 'Enter Germany + register address (Anmeldung)',
        owner: 'You', time: '1 week', cost: 'Free', needs: 'Visa approved',
        line: 'Register your address within 2 weeks of arrival — required for everything else.',
        subs: [
          'Find accommodation',
          'Book Einwohnermeldeamt appointment',
          'Receive Meldebescheinigung',
        ],
      },
      {
        n: 6, status: 'locked', title: 'Tax ID + social security number',
        owner: 'Government', time: '2–4 weeks', cost: 'Free', needs: 'Step 5',
        line: 'Issued automatically after Anmeldung. Required for payroll.',
        subs: [
          'Receive Steuer-ID by post',
          'Register with health insurance (Krankenkasse)',
        ],
      },
      {
        n: 7, status: 'locked', title: 'Residence permit — Niederlassungserlaubnis track',
        owner: 'You', time: '4–8 weeks', cost: '€100', needs: 'Steps 5–6',
        line: 'Your D-visa converts to a residence permit at the Ausländerbehörde.',
        subs: [
          'Book Ausländerbehörde appointment',
          'Bring all documents',
          'Pay fee',
          'Receive permit',
        ],
      },
    ],
  };
}

function planGeneric(answers) {
  const origin = QUESTIONS[0].options.find(o => o.code === answers.origin);
  const dest   = QUESTIONS[1].options.find(o => o.code === answers.destination);
  return {
    label: 'Generic plan',
    flagFrom: origin?.flag || '🌍', from: origin?.label || 'Origin',
    flagTo: dest?.flag || '🌍',     to: dest?.label || 'Destination',
    totalTime: '~6 months',
    totalCost: '~€500',
    outcomes: ['Right to live', 'Right to work'],
    banner: 'Full route coverage coming soon. This is a preview for two demo paths.',
    steps: [
      { n: 1, status: 'active', title: 'Document gathering', owner: 'You', time: '2–4 weeks', cost: 'Variable',
        line: 'Passport, civil status, qualifications, financial proof.', subs: [] },
      { n: 2, status: 'locked', title: 'Visa application', owner: 'You', time: '4–12 weeks', cost: 'Variable', needs: 'Step 1',
        line: 'Submit at the consulate or destination embassy.', subs: [] },
      { n: 3, status: 'locked', title: 'Travel prep', owner: 'You', time: '1–2 weeks', cost: 'Variable', needs: 'Step 2',
        line: 'Insurance, accommodation, transit.', subs: [] },
      { n: 4, status: 'locked', title: 'Arrival registration', owner: 'You', time: '1 week', cost: 'Free', needs: 'Arrival',
        line: 'Register your address at the local authority.', subs: [] },
      { n: 5, status: 'locked', title: 'Tax / ID setup', owner: 'Government', time: '2–4 weeks', cost: 'Free', needs: 'Step 4',
        line: 'Receive your local tax and ID numbers.', subs: [] },
      { n: 6, status: 'locked', title: 'Settle in', owner: 'You', time: 'Ongoing', cost: 'Variable', needs: 'Step 5',
        line: 'Bank, healthcare, schooling, local services.', subs: [] },
    ],
  };
}

function buildPlan(answers) {
  // Path A — France → Norway · Work · Partner+children · Within 3 months
  if (answers.origin === 'FR' && answers.destination === 'NO' && answers.reason === 'work'
      && (answers.family === 'partner_kids' || answers.family === 'partner') && answers.timing === '3mo') {
    return planA();
  }
  // Path B — India → Germany · Work · Just me · 6–12 months
  if (answers.origin === 'IN' && answers.destination === 'DE' && answers.reason === 'work'
      && answers.family === 'solo' && answers.timing === '612') {
    return planB();
  }
  return planGeneric(answers);
}

// ─── Helpers ───
function answerLabel(qid, code) {
  if (!code) return '';
  if (typeof code === 'string' && code.startsWith('OTHER:')) return code.slice(6);
  const q = QUESTIONS.find(qq => qq.id === qid);
  return q?.options.find(o => o.code === code)?.label || code;
}

// ─── Header ───
function Header({ progress, onEdit, showEdit }) {
  return (
    <>
      <div className="hdr">
        <div className="hdr-row">
          <img src="assets/relopass-mark.png" alt="ReloPass" className="hdr-logo" />
          <span className="hdr-name">ReloPass<span className="by"> · Pathway</span></span>
          <span className="spacer"/>
          {showEdit && (
            <button className="edit-pill" onClick={onEdit}>
              <I n="edit" s={13}/> Edit my answers
            </button>
          )}
        </div>
      </div>
      <div className="progress"><div style={{ width: `${progress}%` }} /></div>
    </>
  );
}

// ─── Welcome ───
function Welcome({ onStart }) {
  return (
    <div className="welcome">
      <div className="frame" style={{ textAlign: 'left' }}>
        <h1 className="welcome-h">Let's build your relocation plan.</h1>
        <p className="welcome-sub">5 questions. A clear path. Under 2 minutes.</p>
        <button className="btn-primary" onClick={onStart}>
          Get started <I n="arrowR" s={16}/>
        </button>
      </div>
    </div>
  );
}

// ─── Question screen ───
function Question({ q, qIdx, total, value, onAnswer, onBack, canBack }) {
  const [other, setOther] = useState('');
  const [showOther, setShowOther] = useState(false);

  const isCountry = q.kind === 'country';

  const pickOther = () => { if (other.trim()) onAnswer('OTHER:' + other.trim()); };

  return (
    <div className="q-card" style={{ width: '100%' }} key={q.id}>
      <div className="q-meta">
        <span className="count">Question {qIdx + 1} of {total}</span>
        {canBack && (
          <button className="q-back" onClick={onBack}>
            <I n="arrowL" s={12}/> Back
          </button>
        )}
      </div>

      <div className="q-title-row">
        <h2 className="q-title">{q.title}</h2>
        <span className="q-info" tabIndex={0}>
          <I n="info" s={15}/>
          <span className="q-tip">{q.info}</span>
        </span>
      </div>

      <div className={`chips ${isCountry ? 'cols-3' : ''}`}>
        {q.options.map(o => (
          <button key={o.code}
            className={`chip${value === o.code ? ' selected' : ''}`}
            onClick={() => onAnswer(o.code)}>
            {o.flag && <span className="flag">{o.flag}</span>}
            <span>{o.label}</span>
            {value === o.code && <span className="chk"><I n="check" s={16} sw={3}/></span>}
          </button>
        ))}

        {isCountry && (
          showOther ? (
            <div className="other-row">
              <input autoFocus placeholder="Type a country…" value={other}
                onChange={e => setOther(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') pickOther(); }} />
              <button onClick={pickOther}><I n="arrowR" s={14}/></button>
            </div>
          ) : (
            <button className="chip" style={{ borderStyle: 'dashed', color: 'var(--muted)' }}
              onClick={() => setShowOther(true)}>
              <span>Other…</span>
            </button>
          )
        )}
      </div>
    </div>
  );
}

// ─── People profile card (Deel/Crextio-style — builds up as intake progresses) ───
function ProfileCard({ answers, onEditQ }) {
  const origin = answers.origin ? QUESTIONS[0].options.find(o => o.code === answers.origin) : null;
  const dest   = answers.destination ? QUESTIONS[1].options.find(o => o.code === answers.destination) : null;
  const reason = answers.reason ? QUESTIONS[2].options.find(o => o.code === answers.reason)?.label : null;
  const family = answers.family ? QUESTIONS[3].options.find(o => o.code === answers.family)?.label : null;
  const timing = answers.timing ? QUESTIONS[4].options.find(o => o.code === answers.timing)?.label : null;

  // Visible rows: always show 5 slots; populated ones build up with animation
  const rows = [
    { id: 'origin',      label: 'From',     flag: origin?.flag, value: origin?.label,
      qid: 'origin' },
    { id: 'destination', label: 'To',       flag: dest?.flag,   value: dest?.label,
      qid: 'destination' },
    { id: 'reason',      label: 'Purpose',  value: reason,
      qid: 'reason' },
    { id: 'family',      label: 'Household',value: family,
      qid: 'family' },
    { id: 'timing',      label: 'Target',   value: timing,
      qid: 'timing' },
  ];

  return (
    <div className="profile-card">
      <div className="profile-head">
        <div className="profile-avatar">MB</div>
        <div className="profile-name-block">
          <div className="profile-name">Marc Bouchard</div>
          <div className="profile-role">Senior Engineer · Aurora Energy</div>
        </div>
        <span className="profile-pill">Intake</span>
      </div>

      <div className="profile-rows">
        {rows.map((r, i) => (
          <div key={r.id}
            className={`profile-row${r.value ? '' : ' pending'}`}
            style={{ animationDelay: `${i * 40}ms` }}
            onClick={() => r.value && onEditQ && onEditQ(r.qid)}>
            <span className="profile-k">{r.label}</span>
            {r.value ? (
              <span className="profile-v">
                {r.flag && <span className="flag">{r.flag}</span>}
                <span>{r.value}</span>
              </span>
            ) : (
              <span className="profile-v-pending">— pending —</span>
            )}
          </div>
        ))}
      </div>

      <div className="profile-foot">
        <div className="profile-foot-row">
          <span className="profile-k">Annual salary</span>
          <span className="profile-v">€72,000</span>
        </div>
        <div className="profile-foot-row">
          <span className="profile-k">Contract start</span>
          <span className="profile-v">25 Jul 2026</span>
        </div>
      </div>
    </div>
  );
}

// ─── Sidecar widgets under the profile card ───
function DocumentsCard() {
  const docs = [
    { name: 'Passport',                  status: 'ok' },
    { name: 'Employment contract',       status: 'ok' },
    { name: 'Birth certificate',         status: 'pending' },
    { name: 'Marriage certificate',      status: 'pending' },
  ];
  const ok = docs.filter(d => d.status === 'ok').length;
  return (
    <div className="sidecar-card">
      <div className="sidecar-title">
        <span>Documents</span>
        <span className="sidecar-count">{ok}/{docs.length}</span>
      </div>
      <div className="sidecar-rows">
        {docs.map(d => (
          <div key={d.name} className="sidecar-doc">
            <span className={`dot${d.status === 'ok' ? ' ok' : ''}`}/>
            <span className="label">{d.name}</span>
            <span className={`status${d.status === 'ok' ? ' ok' : ''}`}>
              {d.status === 'ok' ? 'on file' : 'needed'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function CompensationCard() {
  return (
    <div className="sidecar-card">
      <div className="sidecar-title"><span>Compensation</span></div>
      <div className="sidecar-rows">
        <div className="sidecar-row"><span className="k">Annual salary</span><span className="v">€72,000</span></div>
        <div className="sidecar-row"><span className="k">Sign-on bonus</span><span className="v">€8,000</span></div>
        <div className="sidecar-row"><span className="k">Housing allowance</span><span className="v">€1,200 / mo</span></div>
        <div className="sidecar-row"><span className="k">Visa fees</span><span className="v">Covered</span></div>
      </div>
    </div>
  );
}

// Mini calendar — July 2026, with 25th = arrival milestone, 18th = consulate appt
function CalendarCard() {
  // July 2026: 1st = Wednesday (per real calendar)
  const days = [];
  // 2 lead days from June (Mon, Tue dim)
  for (let i = 29; i <= 30; i++) days.push({ d: i, dim: true });
  // 31 days of July
  for (let i = 1; i <= 31; i++) {
    let cls = '';
    if (i === 19) cls = 'today';          // demo: pretend today is July 19
    else if ([2, 10, 25, 28].includes(i)) cls = 'milestone';
    days.push({ d: i, cls });
  }
  // trailing days (Aug 1, 2)
  for (let i = 1; i <= 2; i++) days.push({ d: i, dim: true });

  return (
    <div className="sidecar-card">
      <div className="sidecar-title">
        <span>July 2026</span>
        <span className="sidecar-count">4 milestones</span>
      </div>
      <div className="calendar">
        {['M','T','W','T','F','S','S'].map((h, i) => <div key={i} className="cal-h">{h}</div>)}
        {days.map((d, i) => (
          <div key={i} className={`cal-day ${d.dim ? 'dim' : ''} ${d.cls || ''}`}>{d.d}</div>
        ))}
      </div>
      <div className="cal-legend">
        <span className="item"><span className="dot today"/> Today</span>
        <span className="item"><span className="dot mile"/> Milestone</span>
      </div>
    </div>
  );
}
function SummaryPanel({ answers, onEditQ }) {
  // Build labelled rows for each question. Empty-state shows pending.
  const rows = QUESTIONS.map(q => {
    const v = answers[q.id];
    const opt = v ? q.options.find(o => o.code === v) : null;
    const isOther = typeof v === 'string' && v.startsWith('OTHER:');
    return {
      id: q.id,
      label: q.summary,
      hasValue: v != null,
      flag: opt?.flag,
      value: isOther ? v.slice(6) : (opt?.label || ''),
    };
  });

  // Avatar = origin code → dest code (uppercase). If neither, use "RP".
  const origin = answers.origin && QUESTIONS[0].options.find(o => o.code === answers.origin);
  const dest   = answers.destination && QUESTIONS[1].options.find(o => o.code === answers.destination);
  const avatar = origin && dest ? `${origin.code}→${dest.code}` : (origin?.code || dest?.code || 'RP');
  const avatarShort = avatar.length > 5 ? avatar.slice(0, 5) : avatar;

  return (
    <div className="summary-card">
      <div className="summary-head">
        <div className="summary-avatar" style={{ fontSize: avatarShort.length > 2 ? 10 : 13 }}>
          {avatarShort}
        </div>
        <div>
          <div className="summary-title">Your move</div>
          <div className="summary-sub">Plan details build here</div>
        </div>
      </div>

      <div className="summary-rows">
        {rows.map(r => (
          <div key={r.id} className="summary-row">
            <span className="summary-k">{r.label}</span>
            {r.hasValue ? (
              <span className="summary-v">
                {r.flag && <span className="flag">{r.flag}</span>}
                <span>{r.value}</span>
                <button className="summary-edit" onClick={() => onEditQ(r.id)} title="Edit">
                  edit
                </button>
              </span>
            ) : (
              <span className="summary-v pending">Pending</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Edit popover (when user clicks an answer badge) ───
function EditPopover({ qid, answers, onPick, onClose }) {
  const q = QUESTIONS.find(qq => qq.id === qid);
  if (!q) return null;
  return (
    <>
      <div className="popover-overlay" onClick={onClose} />
      <div className="popover">
        <h4>Edit: {q.summary}</h4>
        <div className="opt-list">
          {q.options.map(o => (
            <button key={o.code}
              className={`opt-mini${answers[qid] === o.code ? ' selected' : ''}`}
              onClick={() => { onPick(qid, o.code); onClose(); }}>
              {o.flag && <span>{o.flag}</span>}
              <span>{o.label}</span>
            </button>
          ))}
        </div>
      </div>
    </>
  );
}

// ─── Plan step ───
function StepCard({ step, expanded, onToggle, index }) {
  return (
    <div className={`step ${step.status}${expanded ? ' open' : ''}`}
         onClick={onToggle}
         style={{ animationDelay: `${index * 160}ms` }}>
      <div className="step-body">
        <div className="step-head-row">
          <span className="step-title">Step {step.n} — {step.title}</span>
          <span className={`step-pill ${step.owner.toLowerCase().split(/\s|\+/)[0]}`}>{step.owner}</span>
        </div>

        {expanded && (
          <div className="step-detail">
            <div className="step-meta">
              <span>{step.time}</span>
              <span className="cost">{step.cost}</span>
              {step.needs && <span className="step-needs">Needs: {step.needs}</span>}
            </div>
            <p className="step-line">{step.line}</p>

            {step.subs.length > 0 && (
              <ul className="step-subs">
                {step.subs.map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            )}

            {step.advisor && (
              <button className="step-advisor" onClick={(e) => { e.stopPropagation(); alert('Advisor matching (demo).'); }}>
                <span className="ico"><I n="msg" s={14}/></span>
                <span>Talk to a licensed advisor</span>
                <span className="arrow"><I n="chevR" s={14}/></span>
              </button>
            )}
          </div>
        )}
      </div>

      <span className="step-chev" style={{ transition: 'transform 180ms ease', transform: expanded ? 'rotate(180deg)' : 'none' }}>
        <I n="chevD" s={14}/>
      </span>

      <div className="step-icon">
        {step.status === 'active' ? <I n="play" s={11}/> : <I n="lock" s={12}/>}
      </div>
    </div>
  );
}

// ─── Plan view ───
function Plan({ answers, onRestart }) {
  const plan = buildPlan(answers);
  const isGeneric = !!plan.banner;
  const [open, setOpen] = useState({});                 // no step expanded by default — clean list

  return (
    <div className={`frame ${isGeneric ? 'frame-wider' : 'frame-wide'}`}>
      <div className="plan-header">
        <div className="plan-eyebrow">Your plan</div>
        <h2 className="plan-h">{plan.label}</h2>
        <div className="plan-route">
          <span className="flag">{plan.flagFrom}</span>
          <span>{plan.from}</span>
          <I n="arrowR" s={14}/>
          <span className="flag">{plan.flagTo}</span>
          <span>{plan.to}</span>
        </div>

        <div className="plan-totals">
          <div>
            <div className="k">Total time</div>
            <div className="v">{plan.totalTime}</div>
          </div>
          <div>
            <div className="k">Total cost</div>
            <div className="v">{plan.totalCost}</div>
          </div>
        </div>

        <div className="outcomes">
          <span style={{ fontSize: 13, color: 'var(--muted)', alignSelf: 'center', marginRight: 4 }}>
            When you're done:
          </span>
          {plan.outcomes.map((o, i) => (
            <span key={i} className="outcome"><I n="check" s={12} sw={3}/> {o}</span>
          ))}
        </div>

        {plan.banner && (
          <div className="plan-banner">
            <I n="info" s={14}/>
            <span>{plan.banner}</span>
          </div>
        )}
      </div>

      <div className="plan-steps">
        {plan.steps.map((s, i) => (
          <StepCard key={s.n} step={s} index={i}
            expanded={!!open[s.n]}
            onToggle={() => setOpen(o => ({ ...o, [s.n]: !o[s.n] }))} />
        ))}
      </div>

      <div className="foot">
        <span className="meta">Plan re-generates if you change your answers.</span>
        <button onClick={onRestart}><I n="arrowL" s={12}/>&nbsp; Start over</button>
      </div>
    </div>
  );
}

// ─── App ───
function App() {
  const [screen, setScreen] = useState('welcome');
  const [answers, setAnswers] = useState({});
  const [qIdx, setQIdx] = useState(0);
  const [editingQid, setEditingQid] = useState(null);

  const total = QUESTIONS.length;
  const captured = QUESTIONS.filter(q => answers[q.id] != null).length;
  const progress = screen === 'welcome' ? 0
    : screen === 'plan' ? 100
    : Math.round((captured / total) * 95);

  const start = () => { setScreen('intake'); setQIdx(0); };
  const restart = () => { setScreen('welcome'); setAnswers({}); setQIdx(0); };
  const edit = () => { setScreen('intake'); setQIdx(0); };

  const onAnswer = (val) => {
    const id = QUESTIONS[qIdx].id;
    const next = { ...answers, [id]: val };
    setAnswers(next);
    setTimeout(() => {
      if (qIdx + 1 < total) setQIdx(qIdx + 1);
      else setScreen('plan');
    }, 200);
  };

  const back = () => { if (qIdx > 0) setQIdx(qIdx - 1); };

  const onJumpToQ = (qid) => setEditingQid(qid);

  const onEditPick = (qid, val) => {
    setAnswers(prev => ({ ...prev, [qid]: val }));
  };

  // Demo loaders
  const loadDemo = (which) => {
    if (which === 'A') setAnswers({ origin: 'FR', destination: 'NO', reason: 'work', family: 'partner_kids', timing: '3mo' });
    if (which === 'B') setAnswers({ origin: 'IN', destination: 'DE', reason: 'work', family: 'solo', timing: '612' });
    if (which === 'X') setAnswers({ origin: 'ES', destination: 'CA', reason: 'study', family: 'solo', timing: '36' });
    setScreen('plan');
  };

  return (
    <>
      <Header progress={progress} onEdit={edit} showEdit={screen !== 'welcome'} />
      <div className="shell">
        {screen === 'welcome' && <Welcome onStart={start} />}
        {screen === 'intake' && (
          <div className="intake-split">
            <div className="intake-left">
              <ProfileCard answers={answers} onEditQ={onJumpToQ} />
            </div>
            <div className="intake-right">
              <Question
                q={QUESTIONS[qIdx]} qIdx={qIdx} total={total}
                value={answers[QUESTIONS[qIdx].id]}
                onAnswer={onAnswer} onBack={back} canBack={qIdx > 0}
              />
            </div>
          </div>
        )}
        {screen === 'plan' && (
          <div className="intake-split plan-split">
            <div className="intake-left">
              <ProfileCard answers={answers} onEditQ={onJumpToQ} />
              <div className="sidecar">
                <CalendarCard />
                <DocumentsCard />
                <CompensationCard />
              </div>
            </div>
            <div className="intake-right">
              <Plan answers={answers} onRestart={restart} />
            </div>
          </div>
        )}
      </div>

      {editingQid && (
        <EditPopover
          qid={editingQid} answers={answers}
          onPick={onEditPick}
          onClose={() => setEditingQid(null)}
        />
      )}

      <TweaksPanel>
        <TweakSection label="Demo" />
        <TweakButton label="Path A · FR → NO" onClick={() => loadDemo('A')} />
        <TweakButton label="Path B · IN → DE" onClick={() => loadDemo('B')} />
        <TweakButton label="Generic preview" onClick={() => loadDemo('X')} />
        <TweakButton label="Reset to welcome" onClick={restart} />
      </TweaksPanel>
    </>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
})();
