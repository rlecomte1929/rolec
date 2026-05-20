// platform-s1-intake.jsx — Employee Intake Wizard
(function() {
const { useState, useEffect, useMemo } = React;
const I = window.PlatformIcon;
const D = window.PlatformData;

const COUNTRIES = D.COUNTRIES;
const QUESTIONS = D.INTAKE_QUESTIONS;

function IntakeScreen({ presetAnswers, onComplete }) {
  const [qi, setQi] = useState(0);
  const [answers, setAnswers] = useState(presetAnswers || {});

  // Update preset when prop changes (allows tweaks panel to seed answers)
  useEffect(() => {
    if (presetAnswers) {
      setAnswers(presetAnswers);
      setQi(QUESTIONS.length - 1);
    }
  }, [presetAnswers]);

  const q = QUESTIONS[qi];
  const total = QUESTIONS.length;
  const captured = QUESTIONS.filter(qq => answers[qq.id] != null).length;
  const pct = Math.round((captured / total) * 100);

  const pick = (val) => {
    const next = { ...answers, [q.id]: val };
    setAnswers(next);
    setTimeout(() => {
      if (qi + 1 < total) setQi(qi + 1);
      else if (onComplete) onComplete(next);
    }, 220);
  };

  const back = () => qi > 0 && setQi(qi - 1);
  const value = answers[q.id];

  // Animate options & summary on question change
  return (
    <div className="page wide">
      <div className="page-hd">
        <div className="page-eyebrow">Employee intake · ReloPass</div>
        <div className="split-row" style={{ alignItems: 'flex-end' }}>
          <h1 className="page-h">Build your relocation plan</h1>
          <div className="spacer"></div>
          <span className="pill teal"><I n="clock" s={11}/> est. 90 seconds</span>
        </div>
        <div className="page-sub">
          ReloPass adapts its questions to your situation. The plan on the right rebuilds as you answer.
        </div>
      </div>

      <div className="intake-grid">
        <div className="card intake-card">
          <div className="intake-progress">
            <div className="intake-stepper" style={{ '--steps': total, '--progress': (() => {
              let filled = qi;
              QUESTIONS.forEach((qq, i) => { if (answers[qq.id] != null) filled = Math.max(filled, i); });
              return total > 1 ? Math.max(0, (filled / (total - 1)) * 100) : 0;
            })() }}>
              {QUESTIONS.map((qq, i) => {
                const done = answers[qq.id] != null;
                const active = i === qi;
                return (
                  <div key={qq.id}
                       className={`intake-step ${done ? 'done' : ''} ${active ? 'active' : ''}`}
                       onClick={() => { if (done || i < qi) setQi(i); }}
                       title={qq.title}>
                    <div className="step-dot">{done ? '✓' : i + 1}</div>
                    <div className="step-lbl">{qq.summary || `Step ${i + 1}`}</div>
                  </div>
                );
              })}
            </div>
          </div>

          <div key={q.id} style={{ animation: 'fade-in 220ms ease both' }}>
            <h2 className="intake-q">{q.title}</h2>
            <p className="intake-hint">{q.hint}</p>

            {q.ai && (
              <div className="intake-ai-nudge">
                <span className="glyph"><img src="assets/relopass-mark.png" alt=""/></span>
                <span>{q.ai}</span>
              </div>
            )}

            {q.kind === 'country' ? <CountryGrid value={value} onPick={pick} /> : <ChoiceGrid options={q.options} value={value} onPick={pick} />}
          </div>

          <div className="intake-foot">
            <button className="btn ghost" onClick={back} disabled={qi === 0} style={qi === 0 ? { opacity: 0.4, cursor: 'default' } : {}}>
              <I n="arrowL" s={13}/> Back
            </button>
            <div className="spacer"></div>
            <span className="meta">
              <I n="lock" s={11}/> Encrypted · GDPR · SOC 2
            </span>
          </div>
        </div>

        <IntakeSummary answers={answers} />
      </div>

      <style>{`
        @keyframes fade-in { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
        .opt { animation: fade-in 220ms ease both; }
        .opt:nth-child(1) { animation-delay: 0ms; } .opt:nth-child(2) { animation-delay: 40ms; }
        .opt:nth-child(3) { animation-delay: 80ms; } .opt:nth-child(4) { animation-delay: 120ms; }
        .opt:nth-child(5) { animation-delay: 160ms; } .opt:nth-child(6) { animation-delay: 200ms; }
        .opt:nth-child(7) { animation-delay: 240ms; } .opt:nth-child(8) { animation-delay: 280ms; }
      `}</style>
    </div>
  );
}

function CountryGrid({ value, onPick }) {
  return (
    <div className="opt-grid">
      {COUNTRIES.slice(0, 12).map(c => (
        <button key={c.code} className={`opt${value === c.code ? ' selected' : ''}`} onClick={() => onPick(c.code)}>
          <span className="flag">{c.flag}</span>
          <span>{c.label}</span>
          <I n="check" s={14} sw={3} className="check" />
        </button>
      ))}
    </div>
  );
}

function ChoiceGrid({ options, value, onPick }) {
  const cols = options.length <= 2 ? 'cols-2' : '';
  return (
    <div className={`opt-grid ${cols}`}>
      {options.map(o => (
        <button key={o.code} className={`opt${value === o.code ? ' selected' : ''}`}
          onClick={() => onPick(o.code)} style={{ padding: '14px 16px', alignItems: 'flex-start', minHeight: 64 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600 }}>{o.label}</div>
            {o.sub && <div className="sub">{o.sub}</div>}
          </div>
          <I n="check" s={14} sw={3} className="check" />
        </button>
      ))}
    </div>
  );
}

function IntakeSummary({ answers }) {
  const origin = answers.origin && COUNTRIES.find(c => c.code === answers.origin);
  const dest   = answers.destination && COUNTRIES.find(c => c.code === answers.destination);

  const rows = QUESTIONS.map(q => {
    const v = answers[q.id];
    let display = null, flag = null;
    if (v != null) {
      if (q.kind === 'country') {
        const c = COUNTRIES.find(c => c.code === v);
        display = c?.label; flag = c?.flag;
      } else {
        display = q.options.find(o => o.code === v)?.label;
      }
    }
    return { id: q.id, label: q.summary, value: display, flag };
  });

  // Adaptive: more answers → more confident estimate
  const captured = rows.filter(r => r.value).length;
  const conf = captured === 0 ? 0 : Math.min(95, 35 + captured * 12);
  const time = captured >= 5 ? '10–14 weeks' : captured >= 3 ? '~12 weeks' : captured >= 1 ? '8–18 weeks' : '—';
  const cost = captured >= 5 ? '€680' : captured >= 3 ? '~€700' : captured >= 1 ? '€500–€900' : '—';
  const visa = answers.origin === 'FR' && answers.destination === 'NO' ? 'Skilled Worker Permit (UDI)'
             : answers.origin === 'IN' && answers.destination === 'DE' ? 'EU Blue Card (Germany)'
             : captured >= 2 ? 'Detecting…' : '—';

  return (
    <div className="card summary-card">
      <div className="summary-hd">
        <div style={{ minWidth: 0, flex: 1 }}>
          <div className="summary-route">
            {origin ? <><span className="flag">{origin.flag}</span><span>{origin.code}</span></> : <span style={{ color: 'var(--text-3)' }}>Origin</span>}
            <I n="arrowR" s={13} className="arrow"/>
            {dest ? <><span className="flag">{dest.flag}</span><span>{dest.code}</span></> : <span style={{ color: 'var(--text-3)' }}>Destination</span>}
          </div>
          <div className="summary-sub">Live relocation profile · Marc Bouchard</div>
        </div>
      </div>

      <div className="summary-rows">
        {rows.map(r => (
          <div key={r.id} className={`summary-row${r.value ? '' : ' pending'}`}>
            <span className="k">{r.label}</span>
            <span className="v">
              {r.flag && <span className="flag">{r.flag}</span>}
              {r.value || 'Pending'}
            </span>
          </div>
        ))}
      </div>

      <div className="summary-est">
        <div className="lbl">AI prediction</div>
        <div className="stat"><span style={{ color: 'var(--text-3)' }}>Likely visa route</span><span className="v">{visa}</span></div>
        <div className="stat"><span style={{ color: 'var(--text-3)' }}>Estimated time</span><span className="v tabular">{time}</span></div>
        <div className="stat"><span style={{ color: 'var(--text-3)' }}>Est. processing cost</span><span className="v tabular">{cost}</span></div>
        <div className="conf">
          <span>Confidence</span>
          <div className="bar"><div style={{ width: `${conf}%` }}/></div>
          <span className="tabular" style={{ color: 'var(--text)', fontWeight: 600 }}>{conf}%</span>
        </div>
      </div>
    </div>
  );
}

window.IntakeScreen = IntakeScreen;
})();
