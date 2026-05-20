// Pathway — shared components.
// Built on assumption that Icon (icons.jsx) and PATHWAY_DATA (data.js) are on window.

const { useState, useEffect, useRef, useMemo } = React;
const { COUNTRIES, DESTINATIONS } = window.PATHWAY_DATA;

// ─────────────────────────────────────────────────────────────────────────────
// Header — brand + progress + edit pill
// ─────────────────────────────────────────────────────────────────────────────
function Header({ progress, screen, onEdit, accent }) {
  return (
    <div className="pw-header">
      <div className="pw-header-row">
        <div className="pw-brand">
          <img src="assets/relopass-mark.png" alt="ReloPass" className="pw-brand-mark-img" />
          <div className="pw-brand-name">
            ReloPass
            <span className="pw-brand-by"> · Pathway</span>
          </div>
          <span className="pw-brand-tag">Mobility operations</span>
        </div>
        {screen !== 'welcome' && (
          <button className="pw-edit-pill" onClick={onEdit} aria-label="Edit my answers">
            <Icon name="edit" size={13} />
            <span>Edit my answers</span>
          </button>
        )}
      </div>
      <div className="pw-progress">
        <div className="pw-progress-fill" style={{ width: `${progress}%`, background: accent }} />
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Welcome — emotional, calm, one button
// ─────────────────────────────────────────────────────────────────────────────
function Welcome({ onStart, accent }) {
  return (
    <div className="pw-welcome" key="welcome">
      <div className="pw-welcome-inner">
        <div className="pw-welcome-eyebrow">
          <span className="pw-dot" style={{ background: accent }} />
          ReloPass · Pathway
        </div>
        <h1 className="pw-welcome-h">
          You're not alone.<br/>
          <span style={{ color: accent }}>Let's build this together.</span>
        </h1>
        <p className="pw-welcome-sub">
          Pathway turns your situation into a structured relocation plan — case-based, policy-aware,
          and timed to your date. Seven short questions. About two minutes.
        </p>
        <button className="pw-cta" style={{ background: accent }} onClick={onStart}>
          <span>Begin intake</span>
          <Icon name="arrow-right" size={18} />
        </button>
        <div className="pw-welcome-chips">
          <span><Icon name="check" size={13}/> Free to explore</span>
          <span><Icon name="check" size={13}/> Nothing is submitted</span>
          <span><Icon name="check" size={13}/> No account</span>
        </div>
      </div>
      <div className="pw-welcome-aside">
        <div className="pw-welcome-card">
          <div className="pw-welcome-card-eyebrow">What you'll get</div>
          <ul className="pw-welcome-card-list">
            <li><span className="pw-wc-num" style={{ background: accent }}>1</span><span>A structured case for your relocation — origin, destination, reason, family, timing.</span></li>
            <li><span className="pw-wc-num" style={{ background: accent }}>2</span><span>A step-by-step plan with status, owner, location, time and cost on every step.</span></li>
            <li><span className="pw-wc-num" style={{ background: accent }}>3</span><span>Where ReloPass surfaces what you'd otherwise miss — thresholds, parallel tracks, gotchas.</span></li>
          </ul>
          <div className="pw-welcome-card-foot">
            <span className="pw-wc-tag">Operating layer</span>
            <span className="pw-wc-tag">Policy-aware</span>
            <span className="pw-wc-tag">Audit-ready close</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Option chips — large tappable
// ─────────────────────────────────────────────────────────────────────────────
function CountryChip({ option, selected, onSelect, accent }) {
  return (
    <button
      className={`pw-chip pw-chip-country ${selected ? 'is-selected' : ''}`}
      style={selected ? { borderColor: accent, background: `${accent}10` } : null}
      onClick={() => onSelect(option.code)}
    >
      <span className="pw-chip-flag">{option.flag}</span>
      <span className="pw-chip-name">{option.name}</span>
      {selected && (
        <span className="pw-chip-check" style={{ background: accent }}>
          <Icon name="check" size={11} strokeWidth={3} />
        </span>
      )}
    </button>
  );
}

function ChoiceChip({ option, selected, onSelect, accent }) {
  return (
    <button
      className={`pw-chip pw-chip-choice ${selected ? 'is-selected' : ''}`}
      style={selected ? { borderColor: accent, background: `${accent}12` } : null}
      onClick={() => onSelect(option.code)}
    >
      <span className="pw-chip-ico" style={{ color: selected ? accent : '#1F2421' }}>
        <Icon name={option.icon} size={20} />
      </span>
      <span className="pw-chip-name">{option.name}</span>
      {selected && (
        <span className="pw-chip-check" style={{ background: accent }}>
          <Icon name="check" size={11} strokeWidth={3} />
        </span>
      )}
    </button>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Question card — prompt + why + options + (Other for countries)
// ─────────────────────────────────────────────────────────────────────────────
function QuestionCard({ question, value, onAnswer, onBack, canBack, qIndex, totalQ, accent, direction }) {
  const [other, setOther] = useState('');
  const [showOther, setShowOther] = useState(false);

  // Slide in from right on forward, from left on back
  const animClass = direction === 'back' ? 'pw-slide-in-left' : 'pw-slide-in-right';

  return (
    <div className={`pw-qcard pw-qcard-anim`} data-anim={animClass} key={question.id}>
      <div className="pw-qmeta">
        <span className="pw-qcount">Question {qIndex + 1} of {totalQ}</span>
        {canBack && (
          <button className="pw-qback" onClick={onBack}>
            <Icon name="arrow-left" size={13} />
            <span>Back</span>
          </button>
        )}
      </div>

      <h2 className="pw-qprompt">{question.prompt}</h2>

      <div className="pw-qwhy">
        <Icon name="info" size={14} />
        <span><strong>Why I'm asking — </strong>{question.why}</span>
      </div>

      <div className={question.kind === 'country' ? 'pw-chip-grid pw-chip-grid-countries' : 'pw-chip-grid'}>
        {question.options.map(opt => (
          question.kind === 'country'
            ? <CountryChip key={opt.code} option={opt} selected={value === opt.code} onSelect={onAnswer} accent={accent} />
            : <ChoiceChip  key={opt.code} option={opt} selected={value === opt.code} onSelect={onAnswer} accent={accent} />
        ))}

        {question.kind === 'country' && (
          showOther ? (
            <div className="pw-chip pw-chip-other-input">
              <input
                autoFocus
                placeholder="Type a country…"
                value={other}
                onChange={e => setOther(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && other.trim()) onAnswer('OTHER:' + other.trim()); }}
              />
              <button onClick={() => other.trim() && onAnswer('OTHER:' + other.trim())} style={{ background: accent }}>
                <Icon name="arrow-right" size={14} />
              </button>
            </div>
          ) : (
            <button className="pw-chip pw-chip-other" onClick={() => setShowOther(true)}>
              <span className="pw-chip-flag">·</span>
              <span className="pw-chip-name" style={{ color: '#1F242188' }}>Other…</span>
            </button>
          )
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Plan silhouette — greyed skeleton that materialises during intake
// ─────────────────────────────────────────────────────────────────────────────
function PlanSilhouette({ filled, slots, accent }) {
  return (
    <div className="pw-silhouette">
      <div className="pw-sil-head">
        <div className="pw-sil-eyebrow">Your plan, taking shape</div>
        <div className="pw-sil-title">As you answer, steps lock in here.</div>
      </div>

      <div className="pw-sil-track">
        {Array.from({ length: slots }).map((_, i) => {
          const isFilled = i < filled;
          return (
            <div key={i} className={`pw-sil-step ${isFilled ? 'is-filled' : ''}`} style={{ animationDelay: `${i * 60}ms` }}>
              <div className="pw-sil-bullet" style={isFilled ? { background: accent, borderColor: accent } : null} />
              <div className="pw-sil-lines">
                <div className="pw-sil-line pw-sil-line-1" style={isFilled ? { background: '#1F242122' } : null} />
                <div className="pw-sil-line pw-sil-line-2" style={isFilled ? { background: '#1F242118' } : null} />
              </div>
            </div>
          );
        })}
      </div>

      <div className="pw-sil-foot">
        <div className="pw-sil-foot-row">
          <span>Estimated time</span>
          <span className="pw-sil-skel" />
        </div>
        <div className="pw-sil-foot-row">
          <span>Estimated cost</span>
          <span className="pw-sil-skel" />
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Plan view
// ─────────────────────────────────────────────────────────────────────────────
const STATUS_META = {
  done:    { label: 'Done',    icon: 'check-circle', tone: '#3A6B4F' },
  active:  { label: 'Active',  icon: 'play',         tone: '#3A6B4F' },
  waiting: { label: 'Waiting', icon: 'clock',        tone: '#9C7E1F' },
  locked:  { label: 'Locked',  icon: 'lock',         tone: '#6B6F6B' },
};

function StepCard({ step, accent, aiVisibility, density, onAdvisor }) {
  const [open, setOpen] = useState(step.status === 'active');
  const meta = STATUS_META[step.status] || STATUS_META.locked;
  const tone = step.status === 'active' || step.status === 'done' ? accent : meta.tone;

  const showAi = step.ai && aiVisibility !== 'off';

  return (
    <div className={`pw-step pw-step-${step.status} ${open ? 'is-open' : ''} pw-density-${density}`}>
      <div className="pw-step-rail" style={{ background: step.status === 'done' || step.status === 'active' ? accent : '#1F242122' }} />

      <button className="pw-step-head" onClick={() => setOpen(o => !o)}>
        <div className="pw-step-num" style={{ background: step.status === 'done' || step.status === 'active' ? accent : '#1F24211a', color: step.status === 'done' || step.status === 'active' ? 'white' : '#1F2421' }}>
          {step.status === 'done' ? <Icon name="check" size={14} strokeWidth={3} /> : step.n}
        </div>
        <div className="pw-step-title-wrap">
          <div className="pw-step-title-row">
            <h3 className="pw-step-title">{step.title}</h3>
            <span className="pw-step-status" style={{ color: tone, background: `${tone}14`, borderColor: `${tone}30` }}>
              <Icon name={meta.icon} size={11} />
              <span>{meta.label}</span>
            </span>
          </div>
          {density !== 'compact' && (
            <p className="pw-step-line">{step.line}</p>
          )}
          <div className="pw-step-meta">
            <span><Icon name="user" size={11}/> {step.who}</span>
            <span><Icon name="pin" size={11}/> {step.where}</span>
            <span><Icon name="clock" size={11}/> {step.time}</span>
            <span className="pw-step-cost">{step.cost}</span>
            {step.needs && <span className="pw-step-needs">Needs: {step.needs}</span>}
          </div>
        </div>
        <span className="pw-step-chev"><Icon name="chevron-down" size={16}/></span>
      </button>

      {open && (
        <div className="pw-step-body">
          {density === 'compact' && (
            <p className="pw-step-line pw-step-line-inbody">{step.line}</p>
          )}

          {step.note === 'Norway salary threshold' && (
            <div className="pw-step-note" style={{ borderColor: `${accent}44`, background: `${accent}08` }}>
              <Icon name="info" size={14} />
              <span><strong>Norway salary threshold</strong> — Skilled-worker route requires ~NOK 489k/yr (Bachelor) or NOK 448k (no degree). Check before signing.</span>
            </div>
          )}

          {showAi && (
            <div className="pw-step-ai" style={{ borderColor: `${accent}33` }}>
              <span className="pw-ai-tag" style={{ background: accent }}>
                <Icon name="sparkle" size={11} /> {aiVisibility === 'detailed' ? 'AI insight' : 'Suggested'}
              </span>
              <span>{step.ai}</span>
            </div>
          )}

          {step.subs.length > 0 && (
            <ul className="pw-step-subs">
              {step.subs.map((s, i) => (
                <li key={i}>
                  <span className="pw-step-sub-dot" style={{ background: `${accent}33` }} />
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          )}

          {step.advisor && (
            <button className="pw-step-advisor" onClick={() => onAdvisor(step)}>
              <Icon name="message" size={14} />
              <span>Talk to a licensed advisor about this step</span>
              <Icon name="chevron-right" size={14} />
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function PlanHeader({ plan, answers, accent }) {
  const origin = [...COUNTRIES, ...DESTINATIONS].find(c => c.code === answers.origin);
  const dest = DESTINATIONS.find(c => c.code === answers.destination);
  return (
    <div className="pw-plan-head">
      <div className="pw-plan-route">
        <div className="pw-plan-route-eyebrow">Your plan</div>
        <div className="pw-plan-route-row">
          <span className="pw-plan-loc">
            <span>{origin?.flag || '🌍'}</span>
            <span>{origin?.name || 'Origin'}</span>
          </span>
          <span className="pw-plan-arrow" style={{ color: accent }}>
            <Icon name="arrow-right" size={18} />
          </span>
          <span className="pw-plan-loc pw-plan-loc-dest">
            <span>{dest?.flag || '🌍'}</span>
            <span>{dest?.name || 'Destination'}</span>
          </span>
        </div>
        <div className="pw-plan-label" style={{ color: accent }}>{plan.label}</div>
      </div>

      <div className="pw-plan-totals">
        <div className="pw-plan-total">
          <div className="pw-plan-total-k">Total time</div>
          <div className="pw-plan-total-v">{plan.totalTime}</div>
        </div>
        <div className="pw-plan-total">
          <div className="pw-plan-total-k">Total cost</div>
          <div className="pw-plan-total-v">{plan.totalCost}</div>
        </div>
      </div>

      <div className="pw-outcomes" style={{ borderColor: `${accent}33`, background: `${accent}08` }}>
        <span className="pw-outcomes-k">When you finish, you'll have</span>
        <div className="pw-outcomes-list">
          {plan.outcomes.map((o, i) => (
            <span key={i} className="pw-outcome"><Icon name="check" size={12} strokeWidth={3}/> {o}</span>
          ))}
        </div>
      </div>

      {plan.banner && (
        <div className="pw-plan-banner">
          <Icon name="info" size={14}/>
          <span>{plan.banner}</span>
        </div>
      )}
    </div>
  );
}

function PlanView({ plan, answers, accent, aiVisibility, density, onRestart }) {
  const [revealed, setRevealed] = useState(0);
  useEffect(() => {
    setRevealed(0);
    let i = 0;
    const id = setInterval(() => {
      i += 1;
      setRevealed(r => r + 1);
      if (i >= plan.steps.length) clearInterval(id);
    }, 120);
    return () => clearInterval(id);
  }, [plan]);

  const onAdvisor = (step) => {
    // hard-coded — just a console alert sim
    alert(`Licensed advisor for: ${step.title}\n\n(Demo — would open advisor matching.)`);
  };

  return (
    <div className="pw-plan">
      <PlanHeader plan={plan} answers={answers} accent={accent} />

      <div className="pw-plan-list">
        {plan.steps.map((s, i) => (
          <div key={i} className="pw-step-fade" style={{
            opacity: i < revealed ? 1 : 0,
            transform: i < revealed ? 'translateY(0)' : 'translateY(8px)',
            transition: 'opacity 360ms ease, transform 360ms ease',
          }}>
            <StepCard step={s} accent={accent} aiVisibility={aiVisibility} density={density} onAdvisor={onAdvisor} />
          </div>
        ))}
      </div>

      <div className="pw-plan-foot">
        <button className="pw-plan-restart" onClick={onRestart}>
          <Icon name="arrow-left" size={14} />
          <span>Start over</span>
        </button>
        <div className="pw-plan-foot-note">
          <Icon name="info" size={12}/>
          <span>Steps marked with “Talk to an advisor” are where a human in the loop genuinely helps.</span>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, {
  PathwayHeader: Header,
  PathwayWelcome: Welcome,
  PathwayQuestion: QuestionCard,
  PathwaySilhouette: PlanSilhouette,
  PathwayPlan: PlanView,
});
