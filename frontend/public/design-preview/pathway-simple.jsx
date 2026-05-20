// Pathway Simple — minimal intake-first prototype.
// Reuses window.PATHWAY_DATA (questions + plan logic from v1).

(function() {
const { useState, useEffect } = React;
const { QUESTIONS, buildPlan, computeProgress } = window.PATHWAY_DATA;
const Ico = window.Icon;

// Simple Tweak defaults
const SIMPLE_DEFAULTS = /*EDITMODE-BEGIN*/{
  "showDevPaths": false,
  "compactCountries": true
}/*EDITMODE-END*/;

// Status meta
const STATUS = {
  done:    { label: 'Done',    cls: 'done' },
  active:  { label: 'Active',  cls: 'active' },
  locked:  { label: 'Locked',  cls: 'locked' },
  waiting: { label: 'Waiting', cls: 'locked' },
};

// Filter visible questions based on answers
function visible(answers) {
  return QUESTIONS.filter(q => !q.showIf || q.showIf(answers));
}

// ─── Welcome ───
function Welcome({ onStart }) {
  return (
    <div className="welcome frame">
      <div>
        <h1 className="welcome-h">Let's map your move.<br/><span className="accent">Seven quick questions.</span></h1>
        <p className="welcome-sub">
          We'll turn your answers into a clear, step-by-step plan with timing and costs. About two minutes.
        </p>
        <button className="welcome-cta" onClick={onStart}>
          Begin <Ico name="arrow-right" size={18}/>
        </button>
      </div>
    </div>
  );
}

// ─── Big chip ───
function Opt({ option, selected, onSelect, isCountry }) {
  return (
    <button className={`opt${selected ? ' selected' : ''}`} onClick={() => onSelect(option.code)}>
      {isCountry && option.flag && <span className="flag">{option.flag}</span>}
      <span>{option.name}</span>
      {selected && <span className="check"><Ico name="check" size={18} strokeWidth={3}/></span>}
    </button>
  );
}

// ─── Question screen ───
function Question({ q, value, onAnswer, onBack, canBack, qIndex, totalQ, compactCountries }) {
  const [other, setOther] = useState('');
  const [showOther, setShowOther] = useState(false);
  const [expandedCountries, setExpandedCountries] = useState(false);

  // For countries with compact mode: show 6 + "Show all"
  let options = q.options;
  let showMore = false;
  if (q.kind === 'country' && compactCountries && !expandedCountries) {
    options = q.options.slice(0, 6);
    showMore = true;
  }

  const cols = q.kind === 'country' ? 'cols-2' : (q.options && q.options.length >= 4 ? 'cols-2' : 'cols-1');

  return (
    <div className="qstep frame">
      <div className="qnum">
        <span>Question {qIndex + 1}</span> <span className="of">of {totalQ}</span>
        {canBack && (
          <button className="back" onClick={onBack}>
            <Ico name="arrow-left" size={12}/> Back
          </button>
        )}
      </div>

      <h2 className="qprompt">{q.prompt}</h2>
      <p className="qwhy">{q.why}</p>

      <div className={`opts ${cols}`}>
        {options.map(o => (
          <Opt key={o.code} option={o} selected={value === o.code} onSelect={onAnswer} isCountry={q.kind === 'country'} />
        ))}

        {showMore && (
          <button className="opt-more" onClick={() => setExpandedCountries(true)}>
            <Ico name="chevron-down" size={14}/> Show all countries
          </button>
        )}

        {q.kind === 'country' && (expandedCountries || !compactCountries) && (
          showOther ? (
            <div className="other-row">
              <input autoFocus placeholder="Type a country…" value={other}
                onChange={e => setOther(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && other.trim()) onAnswer('OTHER:' + other.trim()); }} />
              <button onClick={() => other.trim() && onAnswer('OTHER:' + other.trim())}>
                <Ico name="arrow-right" size={14}/>
              </button>
            </div>
          ) : (
            <button className="opt-more" onClick={() => setShowOther(true)}>
              Other country…
            </button>
          )
        )}
      </div>
    </div>
  );
}

// ─── Plan step ───
function Step({ step, expanded, onToggle }) {
  const meta = STATUS[step.status] || STATUS.locked;
  return (
    <div className={`step ${meta.cls}${expanded ? ' open' : ''}`} onClick={onToggle}>
      <div className="step-num">
        {step.status === 'done' ? <Ico name="check" size={14} strokeWidth={3}/> : step.n}
      </div>
      <div className="step-body">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
          <span className={`pill ${meta.cls}`}>{meta.label}</span>
          {step.cost && step.cost !== '€0' && <span style={{ fontSize: 12.5, color: 'var(--muted)', whiteSpace: 'nowrap' }}>{step.cost}</span>}
        </div>
        <div className="step-title">{step.title}</div>
        <div className="step-line">{step.line}</div>
        <div className="step-meta">
          <span>{step.who}</span>
          <span>·</span>
          <span>{step.where}</span>
          <span>·</span>
          <span>{step.time}</span>
        </div>

        {expanded && (
          <div className="step-detail">
            {step.note === 'Norway salary threshold' && (
              <div className="step-note">
                <Ico name="info" size={14}/>
                <span><strong>Heads up — </strong>Norway requires NOK ~635k/yr for skilled workers. Confirm with your employer before signing.</span>
              </div>
            )}
            {step.subs && step.subs.length > 0 && (
              <ul>
                {step.subs.map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            )}
          </div>
        )}
      </div>
      <span className="step-chev"><Ico name="chevron-down" size={16}/></span>
    </div>
  );
}

// ─── Plan view ───
function Plan({ answers, onRestart }) {
  const plan = buildPlan(answers);
  const [openIdx, setOpenIdx] = useState(plan.steps.findIndex(s => s.status === 'active'));

  const COUNTRIES = window.PATHWAY_DATA.COUNTRIES;
  const DESTS = window.PATHWAY_DATA.DESTINATIONS;
  const origin = [...COUNTRIES, ...DESTS].find(c => c.code === answers.origin);
  const dest = DESTS.find(c => c.code === answers.destination);

  return (
    <div className="qstep frame">
      <div className="plan-eyebrow">Your plan</div>
      <h2 className="plan-h">{plan.label}</h2>
      <div className="plan-route">
        <span className="flag">{origin?.flag || '🌍'}</span>
        <span>{origin?.name || 'Origin'}</span>
        <Ico name="arrow-right" size={16}/>
        <span className="flag">{dest?.flag || '🌍'}</span>
        <span>{dest?.name || 'Destination'}</span>
      </div>

      <div className="plan-totals">
        <div>
          <div className="plan-total-k">Total time</div>
          <div className="plan-total-v">{plan.totalTime}</div>
        </div>
        <div>
          <div className="plan-total-k">Total cost</div>
          <div className="plan-total-v">{plan.totalCost}</div>
        </div>
        <div>
          <div className="plan-total-k">Outcome</div>
          <div className="plan-total-v" style={{ fontSize: 14, fontWeight: 500, color: 'var(--text)' }}>
            {plan.outcomes.slice(0, 2).join(' · ')}
          </div>
        </div>
      </div>

      <div className="plan-steps">
        {plan.steps.map((s, i) => (
          <Step key={i} step={s}
            expanded={openIdx === i}
            onToggle={() => setOpenIdx(openIdx === i ? -1 : i)} />
        ))}
      </div>

      <div className="foot-row">
        <span className="meta">Tap any step to see the details.</span>
        <button onClick={onRestart}>
          <Ico name="arrow-left" size={12}/>&nbsp; Start over
        </button>
      </div>
    </div>
  );
}

// ─── Header ───
function Header({ progress, screen, onEdit }) {
  return (
    <>
      <div className="hdr">
        <div className="hdr-inner">
          <img src="assets/relopass-mark.png" alt="ReloPass" className="hdr-logo" />
          <span className="hdr-name">ReloPass<span className="hdr-by"> · Pathway</span></span>
          <span className="hdr-spacer"/>
          {screen !== 'welcome' && (
            <button className="hdr-edit" onClick={onEdit}>
              <Ico name="edit" size={13}/> Edit answers
            </button>
          )}
        </div>
      </div>
      <div className="progress">
        <div style={{ width: `${progress}%` }} />
      </div>
    </>
  );
}

// ─── Main App ───
function App() {
  const [t, setTweak] = useTweaks(SIMPLE_DEFAULTS);
  const [screen, setScreen] = useState('welcome');
  const [qIndex, setQIndex] = useState(0);
  const [answers, setAnswers] = useState({});

  const qs = visible(answers);
  const q = qs[qIndex];
  const progress = computeProgress(answers, screen);

  const start = () => { setScreen('intake'); setQIndex(0); };
  const restart = () => { setScreen('welcome'); setAnswers({}); setQIndex(0); };
  const edit = () => { setScreen('intake'); setQIndex(0); };

  const onAnswer = (val) => {
    const newAns = { ...answers, [q.id]: val };
    setAnswers(newAns);
    const newQs = visible(newAns);
    setTimeout(() => {
      if (qIndex + 1 < newQs.length) setQIndex(qIndex + 1);
      else setScreen('plan');
    }, 220);
  };

  const back = () => { if (qIndex > 0) setQIndex(qIndex - 1); };

  // Demo loader for tweaks
  const loadDemo = (which) => {
    const sets = {
      A: { origin: 'FR', destination: 'NO', passport: 'FR', reason: 'work', offer: 'signed', family: 'partner_kids', timing: '3mo' },
      B: { origin: 'IN', destination: 'DE', passport: 'IN', reason: 'work', offer: 'looking', family: 'solo', timing: '612' },
      EU: { origin: 'ES', destination: 'PT', passport: 'ES', reason: 'work', offer: 'signed', family: 'solo', timing: 'flex' },
    };
    setAnswers(sets[which] || {});
    setScreen('plan');
  };

  return (
    <>
      <Header progress={progress} screen={screen} onEdit={edit} />

      <div className="shell">
        {screen === 'welcome' && <Welcome onStart={start} />}
        {screen === 'intake' && q && (
          <Question
            q={q}
            value={answers[q.id]}
            onAnswer={onAnswer}
            onBack={back}
            canBack={qIndex > 0}
            qIndex={qIndex}
            totalQ={qs.length}
            compactCountries={t.compactCountries}
          />
        )}
        {screen === 'plan' && <Plan answers={answers} onRestart={restart} />}
      </div>

      <TweaksPanel>
        <TweakSection label="Display" />
        <TweakToggle label="Show 6 countries first" value={t.compactCountries}
          onChange={v => setTweak('compactCountries', v)} />
        <TweakSection label="Demo" />
        <TweakButton label="Path A · FR → NO" onClick={() => loadDemo('A')} />
        <TweakButton label="Path B · IN → DE" onClick={() => loadDemo('B')} />
        <TweakButton label="EU → EU"          onClick={() => loadDemo('EU')} />
        <TweakButton label="Reset to welcome" onClick={restart} />
      </TweaksPanel>
    </>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
})();
