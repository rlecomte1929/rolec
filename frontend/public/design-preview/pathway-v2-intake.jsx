(function() {
const { useState, useEffect, useRef } = React;
// Pathway v2 — Intake side panel.
// Reads/writes a local draftAnswers; on confirm patches the case + calls createCase.

const { DEMO_CASE, COUNTRIES_12, patchCase, createCase, helpers } = window.PATHWAY_V2;
const { initials, firstName } = helpers;

const HOUSING_OPTIONS = [
  { code: 'city_centre', label: 'City centre' },
  { code: 'suburb',      label: 'Suburb' },
  { code: 'near_school', label: 'Near international school' },
  { code: 'flexible',    label: 'Flexible' },
];

const FAMILY_OPTIONS = [
  { code: 'solo',        label: 'Just me' },
  { code: 'partner',     label: 'Partner' },
  { code: 'partner_kids',label: 'Partner + children' },
  { code: 'kids_only',   label: 'Children only' },
];

const COUNTRIES_FULL = [
  'France', 'Germany', 'United Kingdom', 'Spain', 'Italy', 'Netherlands',
  'Belgium', 'Portugal', 'Switzerland', 'United States', 'India',
];

// ─── Question definitions ───
// Each question knows: id, title, info, kind, options (if any), validate, draftPath.
const QUESTIONS = [
  {
    id: 'origin',
    section: 'relocationBasics',
    title: 'Where are you currently registered?',
    info: 'Used for the residency permit application.',
    kind: 'country',
    locked: true,
    lockedValue: 'France',
    lockedReason: 'Set from your assignment record',
  },
  {
    id: 'passport',
    section: 'employeeProfile',
    title: 'Which passport will you travel on?',
    info: 'Determines which visa pathway applies.',
    kind: 'country',
  },
  {
    id: 'family',
    section: 'familyMembers',
    title: 'Who is moving with you?',
    info: 'Each person needs their own track and documents.',
    kind: 'single',
    options: FAMILY_OPTIONS,
  },
  {
    id: 'targetMove',
    section: 'relocationBasics',
    title: 'What is your earliest available move date?',
    info: 'Sets the start of your timeline. Can be updated later.',
    kind: 'date',
    referenceLabel: 'Target start date (set by HR)',
    referenceValue: window.PATHWAY_V2.DEMO_CASE.targetStartLabel,
  },
  {
    id: 'housing',
    section: 'relocationBasics',
    title: 'Preferred area in Stavanger?',
    info: 'Used to filter housing options in your plan.',
    kind: 'single',
    options: HOUSING_OPTIONS,
  },
  {
    id: 'constraints',
    section: 'relocationBasics',
    title: 'Any constraints we should know about?',
    info: 'Examples: school year end, lease expiry, medical, pet.',
    kind: 'text',
    optional: true,
    placeholder: 'e.g. Lease ends June 30, daughter\u2019s school year ends July 4',
  },
];

// ─── Question card body ───
function QView({ q, value, onChange, onAutoAdvance, draft, lockedFamilyDefaults, onFamilyChange }) {
  const tipRef = useRef(null);

  // Country chip grid
  if (q.kind === 'country') {
    if (q.locked) {
      return (
        <div className="q">
          <QHead q={q} />
          <ContextRow draft={draft} />
          <div className="chips" style={{ gridTemplateColumns: '1fr' }}>
            <Chip label={q.lockedValue} selected locked badge={<LockBadge />} />
          </div>
          <p className="text-sm text-muted mt-16">{q.lockedReason}. Required by policy.</p>
        </div>
      );
    }
    return (
      <div className="q">
        <QHead q={q} />
        <ContextRow draft={draft} />
        <div className="chips cols-3">
          {COUNTRIES_12.map(c => (
            <Chip key={c} label={c} selected={value === c} onClick={() => { onChange(c); onAutoAdvance && onAutoAdvance(); }} />
          ))}
        </div>
      </div>
    );
  }

  if (q.kind === 'single') {
    const cols = q.options.length >= 4 ? 2 : 3;
    return (
      <div className="q">
        <QHead q={q} />
        <ContextRow draft={draft} />
        <div className={`chips cols-${cols}`}>
          {q.options.map(o => (
            <Chip key={o.code} label={o.label} selected={value === o.code} onClick={() => { onChange(o.code); onAutoAdvance && onAutoAdvance(o.code); }} />
          ))}
        </div>

        {/* Family sub-panel — inline on Q3 */}
        {q.id === 'family' && (value === 'partner' || value === 'partner_kids' || value === 'kids_only') && (
          <FamilyEditor familyKind={value} onChange={onFamilyChange} />
        )}
      </div>
    );
  }

  if (q.kind === 'date') {
    return (
      <div className="q">
        <QHead q={q} />
        <ContextRow draft={draft} />
        <div className="q-context">
          <div className="q-context-row"><strong>{q.referenceLabel}:</strong> <span>{q.referenceValue}</span></div>
          <div className="q-context-row text-muted">You can match this or propose an earlier date.</div>
        </div>
        <input type="date" className="date-input"
          value={value || ''}
          min="2026-05-18"
          onChange={(e) => onChange(e.target.value)} />
      </div>
    );
  }

  if (q.kind === 'text') {
    return (
      <div className="q">
        <QHead q={q} />
        <ContextRow draft={draft} />
        <textarea className="tx-input" placeholder={q.placeholder}
          value={value || ''} onChange={(e) => onChange(e.target.value)} />
        {q.optional && <p className="text-sm text-muted mt-8">Optional. Leave blank to skip.</p>}
      </div>
    );
  }

  return null;
}

function QHead({ q }) {
  return (
    <div className="q-title-row">
      <h3 className="q-title">{q.title}</h3>
      <span className="q-info">
        <Ico name="info" size={15} />
        <span className="q-tip">{q.info}</span>
      </span>
    </div>
  );
}

function ContextRow({ draft }) {
  // Show the locked context for every question — destination, reason, employer.
  return (
    <div className="q-context">
      <div className="q-context-row">
        <strong>Destination:</strong>
        <span>{draft.relocationBasics.destCity}, {draft.relocationBasics.destCountry}</span>
      </div>
      <div className="q-context-row">
        <strong>Reason:</strong>
        <span>{draft.relocationBasics.purpose}</span>
      </div>
      <div className="q-context-row">
        <strong>Employer:</strong>
        <span>{draft.assignmentContext.employerName}</span>
      </div>
    </div>
  );
}

// ─── Family editor ───
function FamilyEditor({ familyKind, onChange }) {
  const known = window.PATHWAY_V2.DEMO_CASE.knownFamily;
  const hasSpouse = familyKind === 'partner' || familyKind === 'partner_kids';
  const hasKids   = familyKind === 'partner_kids' || familyKind === 'kids_only';

  const [spouse, setSpouse] = useState(hasSpouse ? known.spouse : null);
  const [children, setChildren] = useState(hasKids ? [...known.children] : []);

  // sync state when familyKind changes
  useEffect(() => {
    setSpouse(hasSpouse ? known.spouse : null);
    setChildren(hasKids ? [...known.children] : []);
  }, [familyKind]);

  // push up
  useEffect(() => { onChange && onChange({ spouse, children }); }, [spouse, children]);

  const updateSpouse = (patch) => setSpouse(s => ({ ...(s || {}), ...patch }));
  const updateChild = (i, patch) => setChildren(cs => cs.map((c, idx) => idx === i ? { ...c, ...patch } : c));
  const removeChild = (i) => setChildren(cs => cs.filter((_, idx) => idx !== i));
  const addChild = () => setChildren(cs => [...cs, { fullName: '', relationship: 'child', nationality: 'French', dateOfBirth: '' }]);

  return (
    <div className="mt-24">
      <div className="row mb-12" style={{ justifyContent: 'space-between' }}>
        <div>
          <div className="review-k">Family members</div>
          <div className="text-sm text-muted">Each person gets their own track in the timeline.</div>
        </div>
      </div>

      {hasSpouse && spouse && (
        <MemberRow
          member={spouse}
          relation="Partner"
          onChange={updateSpouse}
        />
      )}

      {hasKids && children.map((c, i) => (
        <MemberRow key={i}
          member={c}
          relation="Child"
          onChange={(patch) => updateChild(i, patch)}
          onRemove={() => removeChild(i)}
        />
      ))}

      {hasKids && (
        <button className="add-child" onClick={addChild}>
          <Ico name="plus" size={14}/> Add another child
        </button>
      )}
    </div>
  );
}

function MemberRow({ member, relation, onChange, onRemove }) {
  return (
    <div className="member-row">
      <div className="member-avatar">{initials(member.fullName || relation)}</div>
      <div className="member-fields">
        <div className="row">
          <input className="name-input" value={member.fullName || ''}
            placeholder="Full name" onChange={(e) => onChange({ fullName: e.target.value })} />
          <span className="relation-chip">{relation}</span>
        </div>
        <div className="row">
          <input type="date" className="dob-input" value={member.dateOfBirth || ''}
            onChange={(e) => onChange({ dateOfBirth: e.target.value })} />
          <select className="nat-select" value={member.nationality || 'French'}
            onChange={(e) => onChange({ nationality: e.target.value })}>
            {COUNTRIES_FULL.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          <span className="badge neutral" style={{ fontSize: 11 }}>Pending</span>
        </div>
      </div>
      {onRemove && (
        <button className="member-remove" onClick={onRemove} aria-label="Remove">
          <Ico name="x" size={14}/>
        </button>
      )}
    </div>
  );
}

// ─── Review summary ───
function ReviewSummary({ draftAnswers, onJump }) {
  const items = [
    { k: 'Origin country',  v: draftAnswers.origin,  qIndex: 0 },
    { k: 'Passport',        v: draftAnswers.passport, qIndex: 1 },
    { k: 'Travelling with', v: labelForFamily(draftAnswers.family), qIndex: 2 },
    { k: 'Move date',       v: draftAnswers.targetMove, qIndex: 3 },
    { k: 'Stavanger area',  v: labelForHousing(draftAnswers.housing), qIndex: 4 },
    { k: 'Constraints',     v: draftAnswers.constraints || 'None given', qIndex: 5 },
  ];
  return (
    <div className="review">
      {items.map((it, i) => (
        <div key={i} className="review-row">
          <div>
            <div className="review-k">{it.k}</div>
            <div className="review-v">{it.v}</div>
          </div>
          <button className="review-edit" onClick={() => onJump(it.qIndex)}>
            Edit
          </button>
        </div>
      ))}
    </div>
  );
}

function labelForFamily(code) {
  return { solo: 'Just me', partner: 'Partner', partner_kids: 'Partner + children', kids_only: 'Children only' }[code] || '—';
}
function labelForHousing(code) {
  return { city_centre: 'City centre', suburb: 'Suburb', near_school: 'Near international school', flexible: 'Flexible' }[code] || '—';
}

// ─── Main panel ───
function IntakePanel({ open, onClose, case_, onConfirm }) {
  const [qIdx, setQIdx] = useState(0);
  const [reviewing, setReviewing] = useState(false);
  // local draft answers; Q1 is locked to France, pre-fill
  const [ans, setAns] = useState({
    origin: 'France',
    passport: null,
    family: null,
    targetMove: case_.targetStartDate,
    housing: null,
    constraints: '',
  });
  const [familyDetail, setFamilyDetail] = useState(null);
  const [saving, setSaving] = useState(false);

  // Reset on each open
  useEffect(() => {
    if (open) {
      setQIdx(0);
      setReviewing(false);
    }
  }, [open]);

  const total = QUESTIONS.length;
  const captured = Object.entries(ans).filter(([k, v]) => {
    if (k === 'constraints') return false; // optional doesn't count
    return v != null && v !== '';
  }).length;
  // 5 required (constraints optional)
  const progress = reviewing ? 100 : Math.round((captured / 5) * 95);

  const q = QUESTIONS[qIdx];
  const value = ans[q.id];
  const canContinue = q.optional || (q.locked) || (value != null && value !== '');

  const goNext = () => {
    if (qIdx + 1 < total) setQIdx(qIdx + 1);
    else setReviewing(true);
  };
  const goBack = () => {
    if (reviewing) { setReviewing(false); setQIdx(total - 1); return; }
    if (qIdx > 0) setQIdx(qIdx - 1);
  };

  const onChangeAns = (val) => setAns(prev => ({ ...prev, [q.id]: val }));

  const confirm = async () => {
    setSaving(true);
    // Build patch matching CaseDraftDTO structure
    const patch = {
      relocationBasics: {
        originCountry: ans.origin,
        targetMoveDate: ans.targetMove,
        housingPreference: ans.housing,
        constraints: ans.constraints || null,
      },
      employeeProfile: { passportCountry: ans.passport },
      familyMembers: {
        maritalStatus: ans.family,
        spouse: (ans.family === 'partner' || ans.family === 'partner_kids') ? (familyDetail?.spouse || window.PATHWAY_V2.DEMO_CASE.knownFamily.spouse) : null,
        children: (ans.family === 'partner_kids' || ans.family === 'kids_only') ? (familyDetail?.children || window.PATHWAY_V2.DEMO_CASE.knownFamily.children) : [],
      },
    };
    const updated = await patchCase(case_.id, patch);
    await createCase(case_.id);
    setSaving(false);
    onConfirm(updated);
  };

  return (
    <>
      <div className={`panel-overlay${open ? ' open' : ''}`} onClick={onClose} />
      <aside className={`panel${open ? ' open' : ''}`} aria-hidden={!open}>
        <div className="panel-hd">
          <div className="panel-hd-row">
            <div className="panel-title">{reviewing ? 'Review your intake' : 'Your intake'}</div>
            <button className="panel-close" onClick={onClose}>
              <Ico name="x" size={14}/> Close
            </button>
          </div>
          <div className="panel-progress">
            <Prog value={progress} />
            <span className="panel-q-count">
              {reviewing ? 'Review' : `Question ${qIdx + 1} of ${total}`}
            </span>
          </div>
        </div>

        <div className="panel-body">
          {!reviewing && (
            <>
              {qIdx > 0 && (
                <button className="btn ghost sm" onClick={goBack} style={{ marginBottom: 12, marginLeft: -8 }}>
                  <Ico name="arrow-left" size={14}/> Back
                </button>
              )}
              <QView
                q={q}
                value={value}
                onChange={onChangeAns}
                onAutoAdvance={(picked) => {
                  // For 'family', do NOT auto-advance if user picks a non-solo option (they need to fill members)
                  if (q.id === 'family' && picked && picked !== 'solo') return;
                  // Auto-advance for country + single-select (other than family)
                  if (q.kind === 'country' || q.kind === 'single') {
                    setTimeout(() => goNext(), 220);
                  }
                }}
                draft={case_.draft}
                onFamilyChange={setFamilyDetail}
              />
            </>
          )}

          {reviewing && (
            <ReviewSummary
              draftAnswers={ans}
              onJump={(i) => { setReviewing(false); setQIdx(i); }}
            />
          )}
        </div>

        <div className="panel-foot">
          {!reviewing && (
            <>
              <div className="left">
                <Ico name="shield-check" size={14}/>
                <span>Required by policy</span>
              </div>
              <Btn variant="primary" size="md" onClick={goNext} disabled={!canContinue}>
                {qIdx + 1 === total ? 'Review' : 'Continue'} <Ico name="arrow-right" size={14}/>
              </Btn>
            </>
          )}
          {reviewing && (
            <>
              <Btn variant="ghost" size="md" onClick={goBack}>
                <Ico name="arrow-left" size={14}/> Back to edit
              </Btn>
              <Btn variant="primary" size="md" onClick={confirm} disabled={saving}>
                {saving ? 'Confirming…' : 'Confirm intake'} <Ico name="check" size={14}/>
              </Btn>
            </>
          )}
        </div>
      </aside>
    </>
  );
}

// Pull globals
const Ico = window.PV2_Ico;
const Btn = window.PV2_Btn;
const Prog = window.PV2_Prog;
const Chip = window.PV2_Chip;
const LockBadge = window.PV2_LockBadge;

Object.assign(window, { PV2_IntakePanel: IntakePanel });

})();
