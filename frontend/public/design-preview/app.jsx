// Pathway — main app
const PW_QUESTIONS  = window.PATHWAY_DATA.QUESTIONS;
const buildPlan     = window.PATHWAY_DATA.buildPlan;
const planSilhouette= window.PATHWAY_DATA.planSilhouette;
const computeProgress = window.PATHWAY_DATA.computeProgress;

const ACCENT_OPTIONS = [
  { name: 'Teal',       hex: '#197b78' }, // marketing-accent (default)
  { name: 'Seafoam',    hex: '#2a9d99' }, // marketing-accent-muted — lighter swoosh
  { name: 'Navy',       hex: '#0c1929' }, // marketing-primary
  { name: 'Deep Blue',  hex: '#1e3a52' }, // marketing-primary-muted
];

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accent": "#197b78",
  "intakeLayout": "twocol",
  "planDensity": "regular",
  "aiVisibility": "subtle",
  "showDemoBar": true
}/*EDITMODE-END*/;

function visibleQuestions(answers) {
  return PW_QUESTIONS.filter(q => !q.showIf || q.showIf(answers));
}

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);

  const [screen, setScreen]   = useState('welcome'); // welcome | intake | plan
  const [qIndex, setQIndex]   = useState(0);
  const [answers, setAnswers] = useState({});
  const [direction, setDirection] = useState('forward');

  // Sync CSS accent
  useEffect(() => {
    document.documentElement.style.setProperty('--pw-accent', t.accent);
  }, [t.accent]);

  const accent = t.accent;
  const qs     = visibleQuestions(answers);
  const totalQ = qs.length;
  const q      = qs[qIndex];

  const progress = computeProgress(answers, screen);
  const silhouette = planSilhouette(answers);

  const start = () => { setScreen('intake'); setQIndex(0); setDirection('forward'); };

  const handleAnswer = (val) => {
    const newAnswers = { ...answers, [q.id]: val };
    setAnswers(newAnswers);
    setDirection('forward');
    const newQs = visibleQuestions(newAnswers);
    // small delay to let user see the selection
    setTimeout(() => {
      if (qIndex + 1 < newQs.length) {
        setQIndex(qIndex + 1);
      } else {
        setScreen('plan');
      }
    }, 220);
  };

  const handleBack = () => {
    setDirection('back');
    if (qIndex > 0) setQIndex(qIndex - 1);
  };

  const handleEdit = () => {
    setDirection('back');
    setScreen('intake');
    setQIndex(0);
  };

  const handleRestart = () => {
    setScreen('welcome');
    setAnswers({});
    setQIndex(0);
  };

  // Demo shortcuts — preload an answer set
  const loadDemo = (which) => {
    let a = {};
    if (which === 'A') {
      a = { origin: 'FR', destination: 'NO', passport: 'FR', reason: 'work', offer: 'signed', family: 'partner_kids', timing: '3mo' };
    } else if (which === 'B') {
      a = { origin: 'IN', destination: 'DE', passport: 'IN', reason: 'work', offer: 'looking', family: 'solo', timing: '612' };
    } else if (which === 'EU') {
      a = { origin: 'ES', destination: 'PT', passport: 'ES', reason: 'work', offer: 'signed', family: 'solo', timing: 'flex' };
    } else if (which === 'generic') {
      a = { origin: 'BR', destination: 'CA', passport: 'BR', reason: 'study', family: 'solo', timing: '612' };
    } else if (which === 'welcome') {
      handleRestart();
      return;
    }
    setAnswers(a);
    setScreen('plan');
  };

  // ────────── Render ──────────
  const plan = screen === 'plan' ? buildPlan(answers) : null;

  return (
    <div className="pw-app">
      <PathwayHeader
        progress={progress}
        screen={screen}
        onEdit={handleEdit}
        accent={accent}
      />

      {t.showDemoBar && (
        <div className="pw-demo-bar">
          <span className="pw-demo-bar-label"><Icon name="sparkle" size={12}/> Demo paths</span>
          <button onClick={() => loadDemo('welcome')}>Welcome</button>
          <button onClick={() => loadDemo('A')}>Path A · 🇫🇷 → 🇳🇴</button>
          <button onClick={() => loadDemo('B')}>Path B · 🇮🇳 → 🇩🇪</button>
          <button onClick={() => loadDemo('EU')}>EU → EU</button>
          <button onClick={() => loadDemo('generic')}>Generic</button>
        </div>
      )}

      {screen === 'welcome' && (
        <PathwayWelcome onStart={start} accent={accent} />
      )}

      {screen === 'intake' && t.intakeLayout === 'twocol' && (
        <div className="pw-cols">
          <div className="pw-col-left">
            {q && (
              <PathwayQuestion
                question={q}
                value={answers[q.id]}
                onAnswer={handleAnswer}
                onBack={handleBack}
                canBack={qIndex > 0}
                qIndex={qIndex}
                totalQ={totalQ}
                accent={accent}
                direction={direction}
              />
            )}
          </div>
          <div className="pw-col-right">
            <PathwaySilhouette filled={silhouette.filled} slots={silhouette.slots} accent={accent} />
          </div>
        </div>
      )}

      {screen === 'intake' && t.intakeLayout === 'focus' && (
        <div className="pw-focus">
          {q && (
            <PathwayQuestion
              question={q}
              value={answers[q.id]}
              onAnswer={handleAnswer}
              onBack={handleBack}
              canBack={qIndex > 0}
              qIndex={qIndex}
              totalQ={totalQ}
              accent={accent}
              direction={direction}
            />
          )}
        </div>
      )}

      {screen === 'plan' && plan && (
        <PathwayPlan
          plan={plan}
          answers={answers}
          accent={accent}
          aiVisibility={t.aiVisibility}
          density={t.planDensity}
          onRestart={handleRestart}
        />
      )}

      <TweaksPanel>
        <TweakSection label="Layout" />
        <TweakRadio label="Intake layout" value={t.intakeLayout}
          options={[{value:'twocol',label:'Two-col'},{value:'focus',label:'Focus'}]}
          onChange={v => setTweak('intakeLayout', v)} />
        <TweakRadio label="Plan density" value={t.planDensity}
          options={[{value:'compact',label:'Compact'},{value:'regular',label:'Card'}]}
          onChange={v => setTweak('planDensity', v)} />

        <TweakSection label="AI" />
        <TweakRadio label="Insight visibility" value={t.aiVisibility}
          options={[{value:'off',label:'Off'},{value:'subtle',label:'Subtle'},{value:'detailed',label:'Detail'}]}
          onChange={v => setTweak('aiVisibility', v)} />

        <TweakSection label="Brand" />
        <TweakColor label="Accent" value={t.accent}
          options={ACCENT_OPTIONS.map(a => a.hex)}
          onChange={v => setTweak('accent', v)} />

        <TweakSection label="Demo" />
        <TweakToggle label="Show demo path bar" value={t.showDemoBar}
          onChange={v => setTweak('showDemoBar', v)} />
        <TweakButton label="Reset to welcome" onClick={handleRestart} />
      </TweaksPanel>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
