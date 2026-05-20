// platform-screens.jsx — S3 Roadmap, S4 Dossier, S5 Policy, S6 Marketplace, S7 Control center
(function() {
const { useState } = React;
const I = window.PlatformIcon;
const D = window.PlatformData;

// ── S3 Roadmap ───────────────────────────────────────
const TRACKS = [
  {
    id: 'visa', nm: 'Visa & permit', icon: '🇳🇴',
    steps: [
      { t: 'Profile completed',                       s: 'done',      when: 'Jun 02', owner: 'Marc' },
      { t: 'Requirements identified (AI)',            s: 'done',      when: 'Jun 04', owner: 'ReloPass AI' },
      { t: 'Employer sponsorship declaration',        s: 'done',      when: 'Jun 24', owner: 'Aurora HR' },
      { t: 'UDI permit submitted',                    s: 'active',    when: 'Jul 03', owner: 'Marc', note: 'Awaiting UDI response · est. 14 days' },
      { t: 'Permit issued · ready for pickup',        s: 'waiting',   when: 'est. Jul 17', owner: 'UDI', note: 'Waiting on UDI decision' },
    ],
  },
  {
    id: 'civil', nm: 'Civil documents', icon: '📜',
    steps: [
      { t: 'Marc — birth certificate (apostille)',    s: 'done',      when: 'Jun 14', owner: 'Marc' },
      { t: 'Marriage certificate (apostille)',        s: 'done',      when: 'Jun 18', owner: 'Marc' },
      { t: 'Certified translations',                  s: 'active',    when: 'in progress', owner: 'Vendor · Trad-Office', note: '2 of 4 documents back' },
      { t: 'Police registration (on arrival)',        s: 'available', when: 'after arrival', owner: 'Marc' },
      { t: 'Tax D-number registration',               s: 'waiting',   when: '+ Aug', owner: 'Skatteetaten', note: 'Requires police registration' },
    ],
  },
  {
    id: 'family', nm: 'Family (partner + 2 kids)', icon: '👨‍👩‍👧',
    steps: [
      { t: 'Léa — birth certificate (apostille)',     s: 'active',    when: 'in progress', owner: 'Marc', note: 'Can run in parallel — does not block UDI' },
      { t: 'Hugo — birth certificate (apostille)',    s: 'active',    when: 'in progress', owner: 'Marc' },
      { t: 'TB tests for minors',                     s: 'available', when: 'any time', owner: 'Marc + family GP', note: 'No dependency — start any time' },
      { t: 'School placement · Léa & Hugo',           s: 'waiting',   when: '+ Aug', owner: 'Skole Match', note: 'Needs housing address' },
    ],
  },
  {
    id: 'settle', nm: 'Settlement · Stavanger', icon: '🏠',
    steps: [
      { t: 'Area survey & shortlist',                 s: 'done',      when: 'Jun 28', owner: 'Stavanger Relocation' },
      { t: 'Housing search & viewings',               s: 'active',    when: 'Jul 14', owner: 'Stavanger Relocation', note: '3 properties shortlisted' },
      { t: 'Lease signed',                            s: 'waiting',   when: 'est. Jul 20', owner: 'Marc', note: 'After viewings' },
      { t: 'Health insurance (HELFO)',                s: 'waiting',   when: '+ Aug', owner: 'Marc', note: 'After D-number' },
      { t: 'Bank account setup',                      s: 'waiting',   when: '+ Aug', owner: 'Marc', note: 'After D-number' },
    ],
  },
];

function RoadmapScreen() {
  const all = TRACKS.flatMap(t => t.steps);
  const doneCount = all.filter(s => s.s === 'done').length;
  const activeCount = all.filter(s => s.s === 'active').length;
  const pct = Math.round((doneCount / all.length) * 100);

  return (
    <div className="page wide">
      <div className="page-hd">
        <div className="page-eyebrow">Case · MB-2026-0042</div>
        <div className="split-row" style={{ alignItems: 'flex-end' }}>
          <h1 className="page-h">Marc Bouchard — France → Norway</h1>
          <div className="spacer"></div>
          <button className="btn"><I n="msg" s={12}/> Message Helena</button>
          <button className="btn primary"><I n="upload" s={12}/> Upload document</button>
        </div>
        <div className="page-sub">Skilled Worker permit · Aurora Energy AS · Stavanger · target arrival Jul 26. Multiple tracks run in parallel — they only block each other where ReloPass flags it.</div>
      </div>

      <div className="rm-grid">
        <div>
          <div className="card card-pad" style={{ marginBottom: 14 }}>
            <div className="split-row" style={{ marginBottom: 8 }}>
              <h3 style={{ fontSize: 13 }}>Overall progress</h3>
              <div className="spacer"></div>
              <span className="mono tabular" style={{ fontSize: 12, color: 'var(--text-2)' }}>{doneCount}/{all.length} complete · {activeCount} in progress</span>
            </div>
            <div className="prog-bar" style={{ width: '100%', height: 6 }}>
              <div style={{ width: `${pct}%`, height: '100%', background: 'linear-gradient(90deg, var(--accent), var(--teal))', borderRadius: 999 }}/>
            </div>
            <div style={{ display: 'flex', gap: 18, marginTop: 12, fontSize: 12, alignItems: 'center', flexWrap: 'wrap' }}>
              <span style={{ color: 'var(--text-3)' }}>{pct}% complete</span>
              <span style={{ color: 'var(--text-3)' }}>· est. arrival <strong style={{ color: 'var(--text)' }}>Jul 26</strong></span>
              <span className="spacer"></span>
              <span className="pill success"><I n="check2" s={11}/> On track</span>
            </div>
          </div>

          <div className="rm-tracks">
            {TRACKS.map(tr => <Track key={tr.id} {...tr}/>)}
          </div>

          <div className="card" style={{ marginTop: 14, padding: 0 }}>
            <div className="legend">
              <span className="item"><span className="dot" style={{ background: 'var(--success)' }}/> done</span>
              <span className="item"><span className="dot" style={{ background: 'var(--accent)' }}/> in progress</span>
              <span className="item"><span className="dot" style={{ background: 'var(--teal)' }}/> ready to start</span>
              <span className="item"><span className="dot" style={{ background: 'var(--warning)' }}/> waiting on a dependency</span>
              <span className="spacer"></span>
              <span style={{ color: 'var(--text-3)' }}><I n="sparkles" s={11} style={{ verticalAlign: 'middle' }}/> ReloPass AI watches all 4 tracks at once</span>
            </div>
          </div>
        </div>

        <div>
          <div className="card card-pad" style={{ marginBottom: 14 }}>
            <h4 style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-3)', marginBottom: 12 }}>What you can do now</h4>
            <NowAction t="TB tests for minors" sub="No dependency · book any time" tone="teal"/>
            <NowAction t="Sign lease (after viewings)" sub="Available once Jul 14 viewings done" tone="teal"/>
            <NowAction t="Approve school exception" sub="Awaiting Helena · HR" tone="warning"/>
          </div>

          <div className="card card-pad" style={{ marginBottom: 14 }}>
            <h4 style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-3)', marginBottom: 10 }}>Agenda · this week</h4>
            <AgendaItem date="Jul 8" t="UDI form review with advisor" who="Nordic Mobility Law"/>
            <AgendaItem date="Jul 10" t="UDI permit submission" who="Marc · self-serve"/>
            <AgendaItem date="Jul 14" t="Stavanger housing viewings (3)" who="Stavanger Relocation"/>
            <AgendaItem date="Jul 16" t="School consultation call" who="Skole Match"/>
          </div>

          <div className="card card-pad">
            <h4 style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-3)', marginBottom: 10 }}>Stakeholders</h4>
            <StakeholderRow init="MB" nm="Marc Bouchard" role="Employee"/>
            <StakeholderRow init="HM" nm="Helena Müller" role="HR · Aurora Energy"/>
            <StakeholderRow init="JØ" nm="Jens Ødegård"  role="Advisor · Nordic Mobility"/>
            <StakeholderRow init="UDI" nm="UDI"           role="Authority · Norway"/>
          </div>
        </div>
      </div>
    </div>
  );
}

function Track({ id, nm, icon, steps }) {
  const [open, setOpen] = useState(false);
  const done = steps.filter(s => s.s === 'done').length;
  const active = steps.filter(s => s.s === 'active').length;
  const pct = Math.round((done / steps.length) * 100);
  return (
    <div className={`card rm-track${open ? ' open' : ''}`}>
      <div className="rm-track-hd" onClick={() => setOpen(o => !o)} style={{ cursor: 'pointer' }}>
        <div className="icon">{icon}</div>
        <div>
          <div className="t">{nm}</div>
          <div className="s">{steps.length} steps · {active > 0 ? `${active} in progress` : 'independent track'}</div>
        </div>
        <div className="spc"></div>
        <div className="bar">
          <div className="prog-bar"><div style={{ width: `${pct}%` }}/></div>
        </div>
        <span className="count">{done}/{steps.length}</span>
        <I n="chevD" s={14} className="rm-chev" style={{ color: 'var(--text-3)', transition: 'transform 180ms ease', transform: open ? 'none' : 'rotate(-90deg)' }}/>
      </div>
      {open && (
        <div className="rm-steps">
          {steps.map((s, i) => <TrackStep key={i} {...s}/>)}
        </div>
      )}
    </div>
  );
}

function TrackStep({ t, s, when, owner, note }) {
  const [open, setOpen] = useState(false);
  const STATUS_LABEL = {
    done: 'done',
    active: 'in progress',
    available: 'ready',
    waiting: 'waiting',
  };
  return (
    <div className={`rm-step ${s}${open ? ' open' : ''}`} onClick={() => setOpen(o => !o)}>
      <div className="rm-mark">
        {s === 'done' ? <I n="check" s={11} sw={3}/>
         : s === 'active' ? <I n="dot" s={9}/>
         : s === 'available' ? <I n="play" s={9}/>
         : <I n="lock" s={10}/>}
      </div>
      <div style={{ minWidth: 0 }}>
        <div className="rm-step-row">
          <div className="t">{t}</div>
          <span className="status-pill">{STATUS_LABEL[s]}</span>
        </div>
        {open && (
          <div className="meta">
            <strong>{owner}</strong> · {when}
            {note ? <span style={{ display: 'block', marginTop: 2 }}>{note}</span> : null}
          </div>
        )}
      </div>
    </div>
  );
}

function NowAction({ t, sub, tone }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
      <div style={{ width: 6, height: 6, borderRadius: 999, background: `var(--${tone})`, marginTop: 7, flexShrink: 0 }}/>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12.5, fontWeight: 550 }}>{t}</div>
        <div style={{ fontSize: 11, color: 'var(--text-3)' }}>{sub}</div>
      </div>
    </div>
  );
}

function AgendaItem({ date, t, who }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 0', borderBottom: '1px solid var(--divider)', fontSize: 12.5 }}>
      <div style={{ width: 36, fontSize: 10.5, color: 'var(--text-3)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{date}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 550 }}>{t}</div>
        <div style={{ fontSize: 11, color: 'var(--text-3)' }}>{who}</div>
      </div>
    </div>
  );
}

function StakeholderRow({ init, nm, role }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '6px 0' }}>
      <div className="avatar" style={{ width: 24, height: 24, fontSize: 10 }}>{init}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12.5, fontWeight: 550 }}>{nm}</div>
        <div style={{ fontSize: 11, color: 'var(--text-3)' }}>{role}</div>
      </div>
    </div>
  );
}

// ── S4 Dossier ───────────────────────────────────────
const FORMS = [
  {
    id: 'utl2010', code: 'UTL-2010', nm: 'Application for residence permit — Skilled Worker',
    authority: 'UDI · Norway', for: 'Marc Bouchard',
    deadline: 'Jul 10', deadlineDays: 2, urgency: 'urgent',
    autoFilled: 23, missing: 5, total: 28,
    ai: { tone: 'good', t: 'Looks ready · 5 personal-history fields away from submission', sub: '23 fields auto-filled from your passport, contract, and civil documents. Your previous addresses are the only items the AI can\'t infer.' },
    expanded: false,
    fields: [
      ['Surname', 'BOUCHARD', 'ai'],
      ['Given names', 'Marc Étienne', 'ai'],
      ['Date of birth', '14 March 1989', 'ai'],
      ['Place of birth', 'Lyon, France', 'ai'],
      ['Nationality', 'French', 'ai'],
      ['Passport number', '22FH48291', 'ai'],
      ['Passport expires', '08 November 2031', 'ai'],
      [],
      ['Employer', 'Aurora Energy AS', 'ai'],
      ['Org. number', '918 762 401', 'ai'],
      ['Position', 'Senior Reservoir Engineer', 'ai'],
      ['Gross annual salary', 'NOK 825,400', 'ai'],
      ['Contract start', '25 July 2026', 'ai'],
      ['Norwegian address', '—', 'missing'],
      [],
      ['Previous address (2024–)', '—', 'missing'],
      ['Previous address (2021–24)', '—', 'missing'],
      ['Marital status', 'Married', 'ai'],
      ['Spouse name', 'Camille Lefèvre', 'ai'],
      ['Children', 'Léa Bouchard (8), Hugo Bouchard (5)', 'ai'],
    ],
  },
  {
    id: 'utl2011-c', code: 'UTL-2011', nm: 'Family immigration — Spouse',
    authority: 'UDI · Norway', for: 'Camille Lefèvre',
    deadline: 'Jul 25', deadlineDays: 17, urgency: 'soon',
    autoFilled: 14, missing: 8, total: 22,
    ai: { tone: 'wait', t: 'Waiting on Camille\'s apostilled birth certificate', sub: 'Currently at the translator. ETA Jul 12. The form will be 87% complete the moment it arrives.' },
    expanded: false,
  },
  {
    id: 'utl2011-l', code: 'UTL-2011', nm: 'Family immigration — Minor child',
    authority: 'UDI · Norway', for: 'Léa Bouchard (8)',
    deadline: 'Jul 25', deadlineDays: 17, urgency: 'soon',
    autoFilled: 12, missing: 9, total: 21,
    ai: { tone: 'wait', t: 'Birth certificate apostille pending at Rhône prefecture', sub: 'We\'ll pre-fill 90% of this form automatically the moment the apostille is back. Nothing more to do.' },
    expanded: false,
  },
  {
    id: 'utl2011-h', code: 'UTL-2011', nm: 'Family immigration — Minor child',
    authority: 'UDI · Norway', for: 'Hugo Bouchard (5)',
    deadline: 'Jul 25', deadlineDays: 17, urgency: 'soon',
    autoFilled: 12, missing: 9, total: 21,
    ai: { tone: 'wait', t: 'Birth certificate apostille pending at Rhône prefecture', sub: 'Same dependency as Léa — both apostilles travel together.' },
    expanded: false,
  },
  {
    id: 'rf1234', code: 'RF-1234', nm: 'Address registration — Folkeregisteret',
    authority: 'Skatteetaten · Norway', for: 'Marc + family',
    deadline: 'on arrival', deadlineDays: null, urgency: 'flexible',
    autoFilled: 18, missing: 2, total: 20,
    ai: { tone: 'good', t: 'Pre-filled · ready once you have a Norwegian address', sub: 'You\'ll submit this in Stavanger after your housing is confirmed. We\'ll remind you 1 week before arrival.' },
    expanded: false,
  },
  {
    id: 'gp7-04', code: 'GP-7-04', nm: 'D-number application',
    authority: 'Skatteetaten · Norway', for: 'Marc Bouchard',
    deadline: 'after arrival', deadlineDays: null, urgency: 'flexible',
    autoFilled: 11, missing: 1, total: 12,
    ai: { tone: 'good', t: 'Ready to submit once you arrive', sub: 'Required before your first Aurora payroll. The only manual field is your Norwegian phone number.' },
    expanded: false,
  },
  {
    id: 'helfo', code: 'HELFO-1', nm: 'Health insurance registration',
    authority: 'HELFO · Norwegian Health Authority', for: 'Marc + family',
    deadline: 'after D-number', deadlineDays: null, urgency: 'flexible',
    autoFilled: 6, missing: 8, total: 14,
    ai: { tone: 'block', t: 'Blocked — needs D-number first', sub: 'Will fill itself automatically the moment your D-number is issued. No action needed from you.' },
    expanded: false,
  },
];

function DossierScreen() {
  const [forms, setForms] = useState(FORMS);
  const toggle = (id) => setForms(fs => fs.map(f => f.id === id ? { ...f, expanded: !f.expanded } : f));

  const submitReady = forms.filter(f => f.ai.tone === 'good' && f.urgency === 'urgent').length;
  const totalAuto = forms.reduce((s, f) => s + f.autoFilled, 0);
  const totalAll  = forms.reduce((s, f) => s + f.total, 0);
  const completePct = Math.round((totalAuto / totalAll) * 100);

  return (
    <div className="page wide">
      <div className="page-hd">
        <div className="page-eyebrow">Dossier · Marc Bouchard · FR → NO</div>
        <div className="split-row" style={{ alignItems: 'flex-end' }}>
          <h1 className="page-h">Forms the AI prepared for you</h1>
          <div className="spacer"></div>
          <button className="btn"><I n="download" s={12}/> Export all</button>
          <button className="btn primary"><I n="send" s={12}/> Submit ready forms ({submitReady})</button>
        </div>
        <div className="page-sub">
          {forms.length} official forms across {new Set(forms.map(f => f.authority)).size} authorities.
          Each row tells you exactly where it stands — urgency on the right, the AI\u2019s read on the left.
        </div>
      </div>

      <div className="card card-pad" style={{ marginBottom: 14, display: 'flex', alignItems: 'center', gap: 16 }}>
        <div>
          <div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-3)', fontWeight: 600 }}>Overall dossier</div>
          <div className="tabular" style={{ fontSize: 24, fontWeight: 700, marginTop: 2 }}>{totalAuto} <span style={{ fontSize: 14, color: 'var(--text-3)' }}>/ {totalAll} fields filled</span></div>
        </div>
        <div style={{ flex: 1 }}>
          <div className="prog-bar" style={{ width: '100%', height: 6 }}>
            <div style={{ width: `${completePct}%`, height: '100%', background: 'linear-gradient(90deg, var(--accent), var(--teal))', borderRadius: 999 }}/>
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 8 }}>{completePct}% complete across all forms · {submitReady} ready to submit · {forms.filter(f => f.ai.tone === 'wait').length} waiting on documents</div>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {forms.map(f => <FormCard key={f.id} form={f} onToggle={() => toggle(f.id)}/>)}
      </div>
    </div>
  );
}

const URGENCY_META = {
  urgent:   { lbl: 'Urgent',     tone: 'danger',  sub: (d) => d?.deadline ? `due ${d.deadline}` : '' },
  soon:     { lbl: 'Due soon',   tone: 'warning', sub: (d) => d?.deadline ? `due ${d.deadline}` : '' },
  flexible: { lbl: 'No deadline',tone: 'ghost',   sub: (d) => d?.deadline ? d.deadline : '' },
};
const AI_TONE = {
  good:  { tone: 'success',  ico: 'check2' },
  wait:  { tone: 'warning',  ico: 'clock' },
  block: { tone: 'danger',   ico: 'lock' },
};

function FormCard({ form, onToggle }) {
  const { code, nm, authority, for: who, urgency, autoFilled, missing, total, ai, expanded, fields } = form;
  const urgM = URGENCY_META[urgency];
  const pct = Math.round((autoFilled / total) * 100);
  const aiM = AI_TONE[ai.tone];

  return (
    <div className={`card form-card${expanded ? ' open' : ''}`}>
      <div className="form-hd" onClick={onToggle}>
        <I n="chevD" s={14} className="form-chev" style={{ color: 'var(--text-3)', transition: 'transform 180ms ease', transform: expanded ? 'none' : 'rotate(-90deg)', flexShrink: 0 }}/>

        <div className="form-id">
          <span className="form-code">{code}</span>
          <span className="form-auth">{authority}</span>
        </div>

        <div className="form-title">
          <div className="t">{nm}</div>
          <div className="s">For <strong>{who}</strong> · {autoFilled} of {total} fields filled · {missing > 0 ? `${missing} need your input` : 'ready to submit'}</div>
        </div>

        <div className="form-progress">
          <div className="prog-bar"><div style={{ width: `${pct}%`, background: pct >= 90 ? 'var(--success)' : pct >= 60 ? 'var(--accent)' : 'var(--warning)' }}/></div>
          <span className="mono tabular">{pct}%</span>
        </div>

        <div className="form-urgency">
          <span className={`pill ${urgM.tone}`}>{urgM.lbl}</span>
          <span className="due">{urgM.sub(form)}</span>
        </div>
      </div>

      <div className={`form-ai ${ai.tone}`}>
        <I n={aiM.ico} s={14} className="ai-ico"/>
        <div>
          <div className="t">{ai.t}</div>
          <div className="s">{ai.sub}</div>
        </div>
      </div>

      {expanded && fields && (
        <div style={{ padding: '0 18px 18px' }}>
          <div className="doc-form" style={{ marginTop: 8 }}>
            <h3>Kingdom of Norway · Directorate of Immigration<br/><span style={{ fontSize: 10, fontWeight: 500, letterSpacing: 0 }}>{nm} · Form {code}</span></h3>
            {fields.map((row, i) => row.length === 0
              ? <div key={i} style={{ height: 12 }}/>
              : <DocField key={i} lab={row[0]} val={row[1]} ai={row[2] === 'ai'} missing={row[2] === 'missing'}/>
            )}
          </div>
          <div style={{ marginTop: 14, display: 'flex', gap: 8, alignItems: 'center' }}>
            {missing > 0 && <span className="pill warning"><I n="alert" s={11}/> {missing} fields need your input</span>}
            <span className="pill teal"><I n="check2" s={11}/> {autoFilled} fields auto-filled</span>
            <div className="spacer"></div>
            <button className="btn ghost">Save draft</button>
            <button className="btn primary"><I n="send" s={12}/> Submit to {authority.split('·')[0].trim()}</button>
          </div>
        </div>
      )}

      {expanded && !fields && (
        <div style={{ padding: '0 18px 18px' }}>
          <div style={{ padding: 24, textAlign: 'center', background: 'var(--surface-2)', borderRadius: 8, color: 'var(--text-3)', fontSize: 13 }}>
            <I n="lock" s={18} style={{ display: 'block', margin: '0 auto 8px' }}/>
            Form preview opens once the AI has enough information to fill it.
          </div>
        </div>
      )}
    </div>
  );
}

function DocField({ lab, val, ai, missing }) {
  return (
    <div className={`doc-field${ai ? ' ai' : ''}${missing ? ' missing' : ''}`}>
      <div className="lab">{lab}</div>
      <div className="val">{val}</div>
    </div>
  );
}

// ── S5 Policy — Employee estimate review w/ exception flow ────
const EXC_TYPES = [
  { id: 'cap_override',       t: 'Cap override',       s: 'Request a higher amount on this benefit' },
  { id: 'additional_coverage',t: 'More coverage',      s: 'Extend an existing benefit\'s scope' },
  { id: 'timeline_extension', t: 'Timeline extension', s: 'Extend a policy window or deadline' },
  { id: 'new_category',       t: 'Add a benefit',      s: 'Request something not in your tier' },
];

// Seed: 3 exceptions on Marc's policy in different states (per the brief)
const MARC_EXCEPTIONS_BY_BENEFIT = {
  'International school': { status: 'pending', note: null, requested: '€18,000 / yr', submitted_ago: '2h ago' },
  'Language tuition':     { status: 'approved', note: 'Approved. Client-facing role justifies the extended program — new cap is €2,800 for your case.', requested: '€2,800', submitted_ago: 'Approved 3d ago', decided_by: 'Helena Müller' },
  'Spouse career coach':  { status: 'rejected', note: 'Not approved — the 5-session cap is firm at Tier 2. We can revisit at the 6-month review if needed. In the meantime, ReloPass has free 1:1 coaching credits Helena can grant.', requested: '12 sessions', submitted_ago: 'Decided 5d ago', decided_by: 'Helena Müller' },
};

function PolicyScreen() {
  const benefits = D.POLICY_BENEFITS;
  const [openNoteFor, setOpenNoteFor] = useState(null);
  const [requestFor, setRequestFor] = useState(null); // benefit object being requested
  const [toast, setToast] = useState(null);
  const [exceptions, setExceptions] = useState(MARC_EXCEPTIONS_BY_BENEFIT);

  const onSubmitException = (benefit, type, requested, justification) => {
    setExceptions(e => ({
      ...e,
      [benefit.nm]: { status: 'pending', note: null, requested: requested || benefit.cap, submitted_ago: 'Just now', type },
    }));
    setRequestFor(null);
    setToast({ msg: `Exception submitted for ${benefit.nm}. HR will review.`, id: Date.now() });
    setTimeout(() => setToast(null), 3500);
  };

  const totalCommitted = '€38,580';
  const totalCap = '€68,000';

  return (
    <div className="page">
      {window.ProfileSubNav && <window.ProfileSubNav active="policy"/>}
      <div className="page-hd">
        <div className="page-eyebrow">Your relocation · Policy estimate</div>
        <div className="split-row" style={{ alignItems: 'flex-end' }}>
          <h1 className="page-h">Your policy &amp; benefits</h1>
          <div className="spacer"></div>
          <button className="btn"><I n="download" s={12}/> Download summary</button>
        </div>
        <div className="page-sub">
          This is what Aurora's mobility policy covers for your move. If something doesn't fit your situation, you can request an exception on any line — HR reviews each one personally.
        </div>
      </div>

      {/* Estimate header */}
      <div className="card card-pad" style={{ marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div className="avatar lg">MB</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600 }}>Marc Bouchard · FR → NO · Director-level package</div>
            <div style={{ fontSize: 12, color: 'var(--text-3)' }}>Tier 2 · Long-term assignment · Family · Cost cap {totalCap}</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div className="mono tabular" style={{ fontSize: 20, fontWeight: 700 }}>{totalCommitted}</div>
            <div style={{ fontSize: 11, color: 'var(--text-3)' }}>committed of {totalCap}</div>
          </div>
        </div>
        <div className="prog-bar" style={{ width: '100%', height: 5, marginTop: 14 }}>
          <div style={{ width: '57%', height: '100%', background: 'var(--accent)', borderRadius: 999 }}/>
        </div>
      </div>

      {/* Benefits table */}
      <div className="card" style={{ padding: 0, marginBottom: 14 }}>
        <div className="card-hd">
          <div className="title">Your benefits</div>
          <div className="sub">{benefits.length} line items · 3 active exception requests</div>
        </div>
        <table className="est-table">
          <tbody>
            {benefits.map(b => {
              const exc = exceptions[b.nm];
              const noteOpen = openNoteFor === b.nm;
              return (
                <React.Fragment key={b.nm}>
                  <tr className="parent-row">
                    <td style={{ width: '40%' }}>
                      <div className="est-name">
                        <div className="nm">{b.nm}</div>
                        <div className="cap">{b.status === 'excluded' ? <em style={{ fontStyle: 'normal' }}>Not in your band</em> : <>Cap: <strong>{b.cap}</strong></>}</div>
                      </div>
                    </td>
                    <td style={{ width: '20%' }}>
                      <div className="est-coverage">
                        {b.status === 'covered' &&  <span className="pill success">Covered</span>}
                        {b.status === 'partial' &&  <span className="pill warning">Partial cover</span>}
                        {b.status === 'excluded' && <span className="pill ghost" style={{ color: 'var(--text-3)' }}>Not covered</span>}
                      </div>
                    </td>
                    <td className="est-cost-cell" style={{ width: '18%' }}>
                      <div className="est-cost">
                        {b.cost.includes(' / ') ? b.cost.split(' / ')[0] : <span className="free">included</span>}
                      </div>
                      {b.cost.includes(' / ') && (
                        <div className="sub" style={{ textAlign: 'right' }}>of {b.cost.split(' / ')[1]}</div>
                      )}
                    </td>
                    <td className="est-action-cell">
                      {exc ? (
                        exc.status === 'pending' ? (
                          <span className="exc-status pending"><span className="dot"/>Exception requested</span>
                        ) : (
                          <span className={`exc-note`} onClick={() => setOpenNoteFor(noteOpen ? null : b.nm)}>
                            <span className={`exc-status ${exc.status}`}>
                              <span className="dot"/>
                              {exc.status === 'approved' ? 'Exception approved' : 'Request not approved'}
                            </span>
                            <I n={noteOpen ? 'chevD' : 'chevR'} s={11}/>
                          </span>
                        )
                      ) : (
                        <button className="exc-trigger" onClick={() => setRequestFor(b)}>
                          <I n="sparkles" s={11} className="ico"/>
                          Request an exception
                        </button>
                      )}
                    </td>
                  </tr>
                  {exc && noteOpen && (
                    <tr className="note-row">
                      <td colSpan={4}>
                        <div className={`exc-note-popout ${exc.status}`}>
                          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>
                            {exc.status === 'approved' ? 'HR approved · note from' : 'HR note from'} {exc.decided_by || 'Helena Müller'}
                          </div>
                          <div>{exc.note}</div>
                          <div className="meta">
                            <span>You requested {exc.requested}</span>
                            <span>·</span>
                            <span>{exc.submitted_ago}</span>
                            <span>·</span>
                            <span>Reference: exc-{1030 + (b.nm.length % 20)}</span>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                  {exc && exc.status === 'pending' && (
                    <tr className="note-row">
                      <td colSpan={4}>
                        <div className="exc-note-popout">
                          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>
                            Awaiting HR review
                          </div>
                          <div>
                            You requested <strong>{exc.requested}</strong> · submitted {exc.submitted_ago}.
                            HR typically responds within 1 business day.
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Help footer */}
      <div className="card card-pad" style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ width: 28, height: 28, borderRadius: 7, background: 'var(--accent-soft)', color: 'var(--accent)', display: 'grid', placeItems: 'center', flexShrink: 0 }}><I n="info" s={14}/></div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600, fontSize: 13 }}>How exceptions work</div>
          <div style={{ fontSize: 12.5, color: 'var(--text-2)', marginTop: 4, lineHeight: 1.55 }}>
            If a benefit doesn't fit your situation, request an exception — HR sees it immediately and decides personally with a note back to you. Most decisions land within 1 business day. Approved exceptions update your roadmap and estimate automatically.
          </div>
        </div>
      </div>

      {/* Slide-in request panel */}
      {requestFor && (
        <ExceptionRequestPanel
          benefit={requestFor}
          existing={exceptions[requestFor.nm]}
          onClose={() => setRequestFor(null)}
          onSubmit={onSubmitException}
        />
      )}

      {/* Toast */}
      {toast && (
        <div className="exc-toast">
          <div className="ic">✓</div>
          {toast.msg}
        </div>
      )}
    </div>
  );
}

// ── Employee Exception Request Panel ──────────────────────────────
function ExceptionRequestPanel({ benefit, existing, onClose, onSubmit }) {
  const defaultType = benefit.status === 'excluded' ? 'new_category'
                    : benefit.status === 'partial'  ? 'cap_override'
                    : 'additional_coverage';
  const [type, setType] = useState(defaultType);
  const [requested, setRequested] = useState('');
  const [justification, setJustification] = useState('');

  const canSubmit = justification.trim().length > 10;

  return (
    <>
      <div className="exc-panel-backdrop" onClick={onClose}/>
      <aside className="exc-panel" role="dialog" aria-label={`Request exception for ${benefit.nm}`}>
        <div className="exc-panel-hd">
          <div className="glyph"><I n="sparkles" s={16}/></div>
          <div style={{ flex: 1 }}>
            <div className="ttl">Request an exception</div>
            <div className="sub">For <strong>{benefit.nm}</strong> on your relocation policy.</div>
          </div>
          <button className="close" onClick={onClose}><I n="x" s={14}/></button>
        </div>

        <div className="exc-panel-body">
          {/* Pre-filled context */}
          <div className="exc-context">
            <div className="lbl"><I n="info" s={11}/>Current policy</div>
            <div className="nm">{benefit.nm}</div>
            <div className="exc-vs">
              <div className="side">
                <div className="k">Today</div>
                <div className="v">
                  {benefit.status === 'excluded' ? 'Not in your band' : benefit.cap}
                </div>
              </div>
              <div className="arrow"><I n="arrowR" s={14}/></div>
              <div className="side req">
                <div className="k">You'll request</div>
                <div className="v">{requested.trim() || 'Enter amount or scope below'}</div>
              </div>
            </div>
          </div>

          {/* Type chooser */}
          <div className="exc-form-section">
            <div className="lbl">What kind of exception?</div>
            <div className="exc-types">
              {EXC_TYPES.map(t => (
                <div key={t.id}
                     className={`exc-type-chip${type === t.id ? ' active' : ''}`}
                     onClick={() => setType(t.id)}>
                  <div className="t">{t.t}</div>
                  <div className="s">{t.s}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Amount / scope */}
          <div className="exc-form-section">
            <div className="lbl">
              What are you requesting?
              <span className="opt">(amount, duration, or scope)</span>
            </div>
            <input
              className="exc-input"
              type="text"
              placeholder={
                type === 'cap_override' ? 'e.g. €18,000'
                : type === 'timeline_extension' ? 'e.g. 30 more days'
                : type === 'additional_coverage' ? 'e.g. air-freight add-on for laptop'
                : 'e.g. International school for 2 kids'
              }
              value={requested}
              onChange={(e) => setRequested(e.target.value)}
            />
            <div className="hint">Briefly state what you'd like instead of what the policy allows. You'll explain why in the next step.</div>
          </div>

          {/* Justification */}
          <div className="exc-form-section">
            <div className="lbl">Why does this matter for your move? <span className="req">*</span></div>
            <textarea
              className="exc-textarea"
              placeholder={`Tell HR what's behind this request — context they wouldn't know from your case file. The more specific you are, the easier it is to approve.`}
              value={justification}
              onChange={(e) => setJustification(e.target.value)}
            />
            <div className="hint">{justification.trim().length} chars · aim for at least one paragraph.</div>
          </div>

          <div className="exc-next">
            <I n="info" s={13} className="ico"/>
            <div>
              <strong>What happens next:</strong> Your HR mobility lead is notified instantly.
              You'll see the status here and get an in-app notification when they respond — typically within 1 business day.
            </div>
          </div>
        </div>

        <div className="exc-panel-foot">
          <button onClick={onClose}>Cancel</button>
          <div className="spc"/>
          <button className="primary"
                  disabled={!canSubmit}
                  onClick={() => onSubmit(benefit, type, requested, justification)}>
            <I n="send" s={12} style={{ marginRight: 6 }}/>
            Send to HR
          </button>
        </div>
      </aside>
    </>
  );
}

// ── S6 Marketplace ───────────────────────────────────
function MarketplaceScreen() {
  const [cat, setCat] = useState('all');
  const cats = ['all', 'Immigration lawyer', 'Housing agent', 'International movers', 'Language tuition', 'School consultant', 'Tax advisor'];
  const vendors = cat === 'all' ? D.VENDORS : D.VENDORS.filter(v => v.cat === cat);

  return (
    <div className="page">
      <div className="page-hd">
        <div className="page-eyebrow">Service providers · Stavanger</div>
        <div className="split-row" style={{ alignItems: 'flex-end' }}>
          <h1 className="page-h">Curated provider marketplace</h1>
          <div className="spacer"></div>
          <button className="btn"><I n="filter" s={12}/> Filters</button>
          <button className="btn primary"><I n="plus" s={12}/> Request quotes</button>
        </div>
        <div className="page-sub">8 HR-approved providers in your corridor. Compare quotes, response times, and cost splits between Aurora and you.</div>
      </div>

      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 14 }}>
        {cats.map(c => (
          <button key={c} onClick={() => setCat(c)}
            className="pill" style={{
              padding: '5px 11px',
              cursor: 'pointer',
              background: cat === c ? 'var(--accent)' : 'var(--surface)',
              color: cat === c ? 'white' : 'var(--text-2)',
              borderColor: cat === c ? 'transparent' : 'var(--border)',
              fontWeight: 550,
            }}>
            {c === 'all' ? 'All categories' : c}
          </button>
        ))}
      </div>

      <div className="svc-grid">
        {vendors.map(v => (
          <div key={v.id} className="card svc-card">
            <div className="top">
              <div className="logo">{v.logo}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="nm">{v.nm}</div>
                <div className="cat">{v.cat}</div>
                <div className="stars">
                  <I n="starF" s={11}/> <span className="rate">{v.rate}</span> <span style={{ color: 'var(--text-3)' }}>· {v.ratings} ratings</span>
                </div>
              </div>
              {v.preferred && <span className="pill teal" style={{ fontSize: 9.5, padding: '1px 6px' }}>preferred</span>}
            </div>
            <div className="row"><span className="k">Price</span><span className="v">{v.price}</span></div>
            <div className="row"><span className="k">Response time</span><span>{v.sla}</span></div>
            <div className="row"><span className="k">Cost coverage</span>
              {v.covered ? <span className="pill success" style={{ fontSize: 9.5 }}>covered by Aurora</span> : <span className="pill warning" style={{ fontSize: 9.5 }}>employee pays</span>}
            </div>
            <div className="foot">
              <button className="btn sm" style={{ flex: 1, justifyContent: 'center' }}>View profile</button>
              <button className="btn sm primary" style={{ flex: 1, justifyContent: 'center' }}>Request quote</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── S7 HR Control Center ─────────────────────────────
function ControlScreen() {
  const emps = D.EMPLOYEES;
  const active = emps.filter(e => e.status !== 'completed').length;
  const blocked = emps.filter(e => e.status === 'blocked' || e.riskLvl === 'high').length;
  const completed = emps.filter(e => e.stage === 'completed').length;

  return (
    <div className="page wide">
      {window.ProfileSubNav && <window.ProfileSubNav active="control"/>}
      <div className="page-hd">
        <div className="page-eyebrow">HR · Global mobility</div>
        <div className="split-row" style={{ alignItems: 'flex-end' }}>
          <h1 className="page-h">Mobility control center</h1>
          <div className="spacer"></div>
          <button className="btn"><I n="filter" s={12}/> All corridors</button>
          <button className="btn"><I n="cal" s={12}/> Q3 2026</button>
          <button className="btn primary"><I n="plus" s={12}/> New case</button>
        </div>
        <div className="page-sub">12 active relocations · 4 corridors · Aurora Energy global team.</div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 14 }}>
        <StatCard k="Active cases"     v={active}   sub="across 4 corridors" tone="accent"/>
        <StatCard k="At risk"          v={blocked}  sub="delays > 5 days"     tone="warning"/>
        <StatCard k="Completed YTD"    v={completed + 7} sub="vs. 12 in 2025"      tone="success"/>
        <StatCard k="Mobility spend"   v="€612k"    sub="of €820k budget"     tone="teal"/>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 320px', gap: 14, alignItems: 'start' }}>
        <div className="card movable-tbl-wrap" style={{ padding: 0 }}>
          <div className="card-hd">
            <div className="title">All relocation cases</div>
            <div className="sub">{emps.length} employees</div>
            <div className="right">
              <span className="pill ghost"><I n="search" s={11}/> Search</span>
            </div>
          </div>
          <CasesTable emps={emps}/>
        </div>

        <div>
          <div className="card card-pad" style={{ marginBottom: 12 }}>
            <h4 style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-3)', marginBottom: 10 }}>Corridor mix · Q3</h4>
            <CorridorBar from="🇫🇷" to="🇳🇴" label="FR → NO" count={3} pct={70}/>
            <CorridorBar from="🇮🇳" to="🇩🇪" label="IN → DE" count={2} pct={55}/>
            <CorridorBar from="🇺🇸" to="🇯🇵" label="US → JP" count={1} pct={40}/>
            <CorridorBar from="🇲🇽" to="🇺🇸" label="MX → US" count={1} pct={28}/>
            <CorridorBar from="🇮🇹" to="🇬🇧" label="IT → GB" count={1} pct={20}/>
          </div>
          <div className="card card-pad" style={{ marginBottom: 12 }}>
            <h4 style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-3)', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
              <I n="alert" s={12} style={{ color: 'var(--warning)' }}/> Risk feed
            </h4>
            <RiskRow nm="Yuki Tanaka" what="anabin recognition pending · 8 days" tone="danger"/>
            <RiskRow nm="Lucas Reyes" what="US visa appt rescheduled · +5 days" tone="warning"/>
            <RiskRow nm="Elena Morelli" what="awaiting employer letter · +3 days" tone="warning"/>
            <RiskRow nm="Priya Nair"   what="EU Blue Card threshold review" tone="accent"/>
          </div>
          <div className="card card-pad">
            <h4 style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-3)', marginBottom: 10 }}>Pending approvals</h4>
            <ApprovalRow nm="School exception · MB" who="Tier 2 escalation"/>
            <ApprovalRow nm="Contract amendment · PN" who="Salary uplift"/>
            <ApprovalRow nm="Vendor switch · LR" who="Tax advisor swap"/>
          </div>
        </div>
      </div>
    </div>
  );
}

function Household({ value }) {
  // value is a string like 'Solo', 'Partner', 'Partner + 2 kids', etc.
  const v = (value || '').toLowerCase();
  let icon, tone, short;
  if (v === 'solo' || v === 'just me') {
    icon = 'user';   tone = 'ghost';   short = 'Solo';
  } else if (v.includes('kid') || v.includes('children') || v.includes('child')) {
    icon = 'users';  tone = 'accent';  short = value;
  } else if (v.includes('partner') || v.includes('spouse') || v.includes('couple')) {
    icon = 'users';  tone = 'teal';    short = 'Partner';
  } else {
    icon = 'users';  tone = 'ghost';   short = value || '—';
  }
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
      <I n={icon} s={12} style={{ color: 'var(--text-3)' }}/>
      <span style={{ fontWeight: 550, color: 'var(--text)' }}>{short}</span>
    </span>
  );
}

function StatCard({ k, v, sub, tone }) {
  return (
    <div className="card card-pad">
      <div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-3)', fontWeight: 600 }}>{k}</div>
      <div style={{ fontSize: 26, fontWeight: 700, marginTop: 4, letterSpacing: '-0.02em' }} className="tabular">{v}</div>
      <div style={{ fontSize: 11.5, color: 'var(--text-3)', marginTop: 2 }}>{sub}</div>
      <div style={{ height: 3, marginTop: 8, borderRadius: 999, background: `var(--${tone === 'accent' ? 'accent' : tone === 'warning' ? 'warning' : tone === 'success' ? 'success' : 'teal'}-soft)`, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: tone === 'warning' ? '30%' : '70%', background: `var(--${tone === 'accent' ? 'accent' : tone === 'warning' ? 'warning' : tone === 'success' ? 'success' : 'teal'})`, borderRadius: 999 }}/>
      </div>
    </div>
  );
}

function CorridorBar({ from, to, label, count, pct }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 0', borderBottom: '1px solid var(--divider)' }}>
      <div style={{ fontSize: 13, display: 'flex', gap: 4, alignItems: 'center', width: 84 }}>
        <span>{from}</span><span style={{ color: 'var(--text-3)' }}>→</span><span>{to}</span>
      </div>
      <div style={{ flex: 1 }}>
        <div className="prog-bar"><div style={{ width: `${pct}%` }}/></div>
      </div>
      <div className="mono tabular" style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--text-2)' }}>{count}</div>
    </div>
  );
}

function RiskRow({ nm, what, tone }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 9, padding: '7px 0', borderBottom: '1px solid var(--divider)' }}>
      <div style={{ width: 5, height: 5, borderRadius: 999, marginTop: 6, background: `var(--${tone})`, flexShrink: 0 }}/>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12.5, fontWeight: 550 }}>{nm}</div>
        <div style={{ fontSize: 11, color: 'var(--text-3)' }}>{what}</div>
      </div>
    </div>
  );
}

function ApprovalRow({ nm, who }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '7px 0', borderBottom: '1px solid var(--divider)' }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12.5, fontWeight: 550 }}>{nm}</div>
        <div style={{ fontSize: 11, color: 'var(--text-3)' }}>{who}</div>
      </div>
      <button className="btn sm">Review</button>
    </div>
  );
}

// ── S8 Documents ─────────────────────────────────────
const DOCS = [
  { id: 'd1', nm: 'Passport',                   person: 'Marc',    cat: 'Identity',  status: 'verified',   uploaded: 'Jun 02', src: 'Marc',   fields: 18, size: '2.4 MB', ext: 'PDF', expires: 'Nov 2031' },
  { id: 'd2', nm: 'Employment contract',        person: 'Marc',    cat: 'Employment',status: 'verified',   uploaded: 'Jun 04', src: 'Aurora HR', fields: 22, size: '510 KB', ext: 'PDF' },
  { id: 'd3', nm: 'Marriage certificate',       person: 'Couple',  cat: 'Civil',     status: 'verified',   uploaded: 'Jun 18', src: 'Marc',   fields: 6,  size: '780 KB', ext: 'PDF', note: 'Apostilled 2024-09-12' },
  { id: 'd4', nm: 'Birth certificate',          person: 'Marc',    cat: 'Civil',     status: 'verified',   uploaded: 'Jun 14', src: 'Marc',   fields: 5,  size: '620 KB', ext: 'PDF' },
  { id: 'd5', nm: "Master's diploma",           person: 'Marc',    cat: 'Education', status: 'verified',   uploaded: 'May 04', src: 'Marc',   fields: 9,  size: '1.1 MB', ext: 'PDF', note: 'Translated · sworn' },
  { id: 'd6', nm: 'CV / Résumé',                 person: 'Marc',    cat: 'Employment',status: 'verified',   uploaded: 'May 12', src: 'Marc',   fields: 24, size: '320 KB', ext: 'PDF' },
  { id: 'd7', nm: 'Passport',                   person: 'Camille', cat: 'Identity',  status: 'verified',   uploaded: 'Jun 06', src: 'Marc',   fields: 18, size: '2.2 MB', ext: 'PDF', expires: 'Mar 2030' },
  { id: 'd8', nm: 'Birth certificate',          person: 'Camille', cat: 'Civil',     status: 'translating',uploaded: 'Jun 20', src: 'Marc',   fields: 5,  size: '640 KB', ext: 'PDF', note: 'At translator · ETA Jul 12' },
  { id: 'd9', nm: 'Birth certificate',          person: 'Léa (8)', cat: 'Civil',     status: 'apostille',  uploaded: 'Jun 22', src: 'Marc',   fields: 5,  size: '590 KB', ext: 'PDF', note: 'Awaiting apostille · prefecture Rhône' },
  { id: 'd10', nm: 'Birth certificate',         person: 'Hugo (5)',cat: 'Civil',     status: 'apostille',  uploaded: 'Jun 22', src: 'Marc',   fields: 5,  size: '610 KB', ext: 'PDF', note: 'Awaiting apostille · prefecture Rhône' },
  { id: 'd11', nm: 'School records',            person: 'Léa (8)', cat: 'Education', status: 'verified',   uploaded: 'Jun 28', src: 'Marc',   fields: 12, size: '410 KB', ext: 'PDF' },
  { id: 'd12', nm: 'Vaccination record',        person: 'Léa (8)', cat: 'Health',    status: 'ocr',        uploaded: 'Jul 02', src: 'Marc',   fields: 0,  size: '1.8 MB', ext: 'PDF', note: 'OCR in progress · 47s remaining' },
  { id: 'd13', nm: 'Vaccination record',        person: 'Hugo (5)',cat: 'Health',    status: 'verified',   uploaded: 'Jul 02', src: 'Marc',   fields: 14, size: '1.6 MB', ext: 'PDF' },
  { id: 'd14', nm: 'Proof of address (FR)',     person: 'Marc',    cat: 'Civil',     status: 'verified',   uploaded: 'Jun 30', src: 'Marc',   fields: 4,  size: '180 KB', ext: 'PDF' },
  { id: 'd15', nm: 'Salary history (3 years)',  person: 'Marc',    cat: 'Employment',status: 'verified',   uploaded: 'Jun 04', src: 'Aurora HR', fields: 36, size: '870 KB', ext: 'PDF' },
  { id: 'd16', nm: 'TB test result',            person: 'Léa (8)', cat: 'Health',    status: 'missing',    uploaded: null,     src: null,     fields: 0,  size: null,     ext: null, note: 'Required by UDI · upload before Aug 30' },
  { id: 'd17', nm: 'TB test result',            person: 'Hugo (5)',cat: 'Health',    status: 'missing',    uploaded: null,     src: null,     fields: 0,  size: null,     ext: null, note: 'Required by UDI · upload before Aug 30' },
  { id: 'd18', nm: 'Norwegian housing proof',   person: 'Marc',    cat: 'Housing',   status: 'missing',    uploaded: null,     src: null,     fields: 0,  size: null,     ext: null, note: 'Required for UDI · lease, hotel, or employer letter' },
];

const STATUS_META = {
  verified:    { lbl: 'Verified',         tone: 'success',  ico: 'check2' },
  translating: { lbl: 'At translator',    tone: 'accent',   ico: 'clock' },
  apostille:   { lbl: 'Apostille pending',tone: 'warning',  ico: 'clock' },
  ocr:         { lbl: 'OCR in progress',  tone: 'accent',   ico: 'sparkles' },
  missing:     { lbl: 'Required · missing',tone: 'danger',  ico: 'alert' },
};

function DocumentsScreen() {
  const [person, setPerson] = useState('all');
  const [status, setStatus] = useState('all');
  const [drag, setDrag] = useState(false);

  const persons = ['all', 'Marc', 'Camille', 'Léa (8)', 'Hugo (5)', 'Couple'];
  const statuses = ['all', 'verified', 'apostille', 'translating', 'ocr', 'missing'];

  const filtered = DOCS.filter(d =>
    (person === 'all' || d.person === person) &&
    (status === 'all' || d.status === status)
  );

  const total = DOCS.length;
  const verified = DOCS.filter(d => d.status === 'verified').length;
  const action = DOCS.filter(d => ['apostille', 'translating', 'ocr'].includes(d.status)).length;
  const missing = DOCS.filter(d => d.status === 'missing').length;

  return (
    <div className="page wide">
      <div className="page-hd">
        <div className="page-eyebrow">Documents · Marc Bouchard</div>
        <div className="split-row" style={{ alignItems: 'flex-end' }}>
          <h1 className="page-h">All your documents in one place</h1>
          <div className="spacer"></div>
          <button className="btn"><I n="download" s={12}/> Export all</button>
          <button className="btn primary"><I n="upload" s={12}/> Upload</button>
        </div>
        <div className="page-sub">
          ReloPass extracts the fields from each document and reuses them across every form. Upload once, fill many.
        </div>
      </div>

      {/* Stat row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 14 }}>
        <StatCard k="Total documents"      v={total}    sub={`across ${persons.length - 1} people`}  tone="accent"/>
        <StatCard k="Verified"             v={verified} sub="ready for forms"            tone="success"/>
        <StatCard k="In progress"          v={action}   sub="apostille / translation / OCR" tone="warning"/>
        <StatCard k="Missing"              v={missing}  sub="required by UDI"            tone="danger"/>
      </div>

      {/* Drop zone */}
      <div
        className={`dropzone${drag ? ' drag' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); }}>
        <div className="dz-icon"><I n="upload" s={20}/></div>
        <div>
          <div className="dz-t">Drop documents here or <span className="dz-link">browse</span></div>
          <div className="dz-s">PDF, JPG, PNG · up to 20 MB each · we extract text automatically</div>
        </div>
        <div className="spacer"></div>
        <button className="btn primary"><I n="upload" s={12}/> Upload</button>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 16, marginTop: 18, marginBottom: 12, flexWrap: 'wrap' }}>
        <FilterChips label="Person"  value={person} options={persons}  onChange={setPerson}/>
        <FilterChips label="Status"  value={status} options={statuses} onChange={setStatus}/>
        <div className="spacer"></div>
        <div style={{ fontSize: 12, color: 'var(--text-3)', alignSelf: 'center' }}>
          Showing <strong style={{ color: 'var(--text)' }}>{filtered.length}</strong> of {total}
        </div>
      </div>

      {/* Doc table */}
      <div className="card movable-tbl-wrap" style={{ padding: 0 }}>
        <DocumentsTable rows={filtered} statusMeta={STATUS_META}/>
      </div>

      {/* Help footer */}
      <div className="card card-pad" style={{ marginTop: 14, display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ width: 28, height: 28, borderRadius: 7, background: 'var(--accent-soft)', color: 'var(--accent)', display: 'grid', placeItems: 'center' }}><I n="sparkles" s={14}/></div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600, fontSize: 13 }}>What happens after you upload?</div>
          <div style={{ fontSize: 12.5, color: 'var(--text-2)', marginTop: 4 }}>
            ReloPass extracts every field automatically (typically 30–60 seconds). Verified fields are reused across UDI forms, Skatteetaten registrations, and your housing applications. You only ever enter information once.
          </div>
        </div>
      </div>
    </div>
  );
}

function FilterChips({ label, value, options, onChange }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{ fontSize: 11, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600, marginRight: 4 }}>{label}</span>
      <div style={{ display: 'flex', gap: 4 }}>
        {options.map(o => {
          const sel = value === o;
          const lbl = o === 'all' ? 'All' : (STATUS_META[o]?.lbl || o);
          return (
            <button key={o} onClick={() => onChange(o)}
              className="pill"
              style={{
                padding: '3px 10px', cursor: 'pointer', fontSize: 11.5,
                background: sel ? 'var(--accent)' : 'var(--surface)',
                color: sel ? 'white' : 'var(--text-2)',
                borderColor: sel ? 'transparent' : 'var(--border)',
                fontWeight: 550,
              }}>
              {lbl}
            </button>
          );
        })}
      </div>
    </div>
  );
}

window.RoadmapScreen = RoadmapScreen;
window.DossierScreen = DossierScreen;
window.PolicyScreen = PolicyScreen;
window.MarketplaceScreen = MarketplaceScreen;
window.ControlScreen = ControlScreen;
window.DocumentsScreen = DocumentsScreen;

// ── CasesTable (used by ControlScreen) ─────────────────────────────
function CasesTable({ emps }) {
  const ORDER  = ['employee','corridor','visa','household','progress','owner','status'];
  const W      = { employee: 240, corridor: 140, visa: 160, household: 140, progress: 180, owner: 110, status: 150 };
  const MIN    = { employee: 180, corridor: 120, visa: 120, household: 110, progress: 140, owner: 90,  status: 120 };
  const LBL    = { employee: 'Employee', corridor: 'Corridor', visa: 'Visa', household: 'Household', progress: 'Progress', owner: 'Owner', status: 'Status' };
  const cols = window.useMovableColumns({ storageKey: 'mobilityCases', defaultOrder: ORDER, defaultWidths: W, minWidths: MIN });
  const MovableTh = window.MovableTh;

  const cell = (e, id) => {
    const from = D.COUNTRIES.find(c => c.code === e.from);
    const to   = D.COUNTRIES.find(c => c.code === e.to);
    const tone = e.riskLvl === 'high' ? 'warning' : e.riskLvl === 'medium' ? 'accent' : 'success';
    switch (id) {
      case 'employee': return (
        <div className="row-emp">
          <div className="avatar">{e.init}</div>
          <div><div className="nm">{e.name}</div><div className="role">{e.role}</div></div>
        </div>
      );
      case 'corridor': return (
        <span className="corridor">
          <span className="flag" style={{ fontSize: 14 }}>{from?.flag}</span>{e.from}
          <I n="arrowR" s={10} className="arr"/>
          <span className="flag" style={{ fontSize: 14 }}>{to?.flag}</span>{e.to}
        </span>
      );
      case 'visa': return e.visa;
      case 'household': return <Household value={e.family}/>;
      case 'progress': return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div className={`prog-bar ${tone}`}><div style={{ width: `${e.progress}%` }}/></div>
          <span className="mono tabular" style={{ fontSize: 11, color: 'var(--text-3)' }}>{e.progress}%</span>
        </div>
      );
      case 'owner': return e.owner;
      case 'status':
        return e.status === 'blocked' ? <span className="pill danger"><I n="alert" s={10}/> Blocked</span>
          : e.delay > 4 ? <span className="pill warning"><I n="clock" s={10}/> +{e.delay}d</span>
          : e.stage === 'completed' ? <span className="pill success"><I n="check2" s={10}/> Done</span>
          : <span className="pill accent"><span className="dot"></span> {e.stage.replace('_', ' ')}</span>;
      default: return null;
    }
  };

  return (
    <table className="tbl movable-tbl">
      <thead><tr>
        {cols.order.map(id => <MovableTh key={id} colId={id} ctx={cols} label={LBL[id]} sortable/>)}
      </tr></thead>
      <tbody>
        {emps.map(e => (
          <tr key={e.id}>
            {cols.order.map(id => <td key={id} style={cols.cellStyle(id)}>{cell(e, id)}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
window.CasesTable = CasesTable;

// ── DocumentsTable (used by DocumentsScreen) ───────────────────────
function DocumentsTable({ rows, statusMeta }) {
  const ORDER = ['document','person','cat','status','fields','uploaded','act'];
  const W     = { document: 280, person: 130, cat: 130, status: 130, fields: 80, uploaded: 110, act: 110 };
  const MIN   = { document: 200, person: 100, cat: 100, status: 100, fields: 64, uploaded: 90,  act: 90 };
  const LBL   = { document: 'Document', person: 'Person', cat: 'Category', status: 'Status', fields: 'Fields', uploaded: 'Uploaded', act: '' };
  const cols = window.useMovableColumns({ storageKey: 'documents', defaultOrder: ORDER, defaultWidths: W, minWidths: MIN });
  const MovableTh = window.MovableTh;

  const cell = (d, id) => {
    const meta = statusMeta[d.status];
    switch (id) {
      case 'document': return (
        <div className="row-emp">
          <div className="doc-ico">
            {d.ext ? <span className="ext">{d.ext}</span> : <I n="upload" s={13}/>}
          </div>
          <div>
            <div className="nm" style={{ fontSize: 13 }}>{d.nm}</div>
            <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 1 }}>
              {d.size ? `${d.size} · ${d.src}` : '—'}{d.note ? ` · ${d.note}` : ''}
            </div>
          </div>
        </div>
      );
      case 'person':   return <span style={{ fontWeight: 550 }}>{d.person}</span>;
      case 'cat':      return d.cat;
      case 'status':   return <span className={`pill ${meta.tone}`}><I n={meta.ico} s={10}/> {meta.lbl}</span>;
      case 'fields':   return <span className="tabular">{d.fields > 0 ? d.fields : '—'}</span>;
      case 'uploaded': return <span style={{ color: 'var(--text-3)' }}>{d.uploaded || '—'}</span>;
      case 'act':      return d.status === 'missing'
        ? <button className="btn sm primary"><I n="upload" s={11}/> Upload</button>
        : <button className="btn sm">View</button>;
      default: return null;
    }
  };

  return (
    <table className="tbl movable-tbl">
      <thead><tr>
        {cols.order.map(id => <MovableTh key={id} colId={id} ctx={cols} label={LBL[id]} sortable={id !== 'act'}/>)}
      </tr></thead>
      <tbody>
        {rows.map(d => (
          <tr key={d.id}>
            {cols.order.map(id => <td key={id} style={cols.cellStyle(id)}>{cell(d, id)}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
window.DocumentsTable = DocumentsTable;
})();
