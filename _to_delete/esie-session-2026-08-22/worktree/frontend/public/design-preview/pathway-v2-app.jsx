(function() {
const { useState, useEffect, useRef } = React;
// Pathway v2 — main app.

const PV2_TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "showDevPanel": true,
  "expandedTimeline": false
}/*EDITMODE-END*/;

function PathwayV2() {
  const [t, setTweak] = useTweaks(PV2_TWEAK_DEFAULTS);
  const [case_, setCase] = useState(null);
  const [intakeOpen, setIntakeOpen] = useState(false);
  const [intakeComplete, setIntakeComplete] = useState(false);
  const [loadingCase, setLoadingCase] = useState(true);

  // Load case on mount
  useEffect(() => {
    (async () => {
      const { case: c } = await window.PATHWAY_V2.getCaseByAssignment('demo-assign-001');
      setCase(c);
      setLoadingCase(false);
    })();
  }, []);

  const onConfirmIntake = (updatedCase) => {
    setCase({ ...updatedCase, status: 'open' });
    setIntakeComplete(true);
    setIntakeOpen(false);
  };

  const resetCase = async () => {
    window.PATHWAY_V2._resetStore();
    const c = await window.PATHWAY_V2.getCase('RLP-2026-0317');
    setCase(c);
    setIntakeComplete(false);
    setIntakeOpen(false);
  };

  const jumpToComplete = async () => {
    // Apply a complete answer set + materialise plan
    const updated = await window.PATHWAY_V2.patchCase('RLP-2026-0317', {
      relocationBasics: {
        originCountry: 'France',
        targetMoveDate: case_.targetStartDate,
        housingPreference: 'near_school',
        constraints: 'Camille\u2019s school year ends July 4',
      },
      employeeProfile: { passportCountry: 'France' },
      familyMembers: {
        maritalStatus: 'partner_kids',
        spouse: window.PATHWAY_V2.DEMO_CASE.knownFamily.spouse,
        children: window.PATHWAY_V2.DEMO_CASE.knownFamily.children,
      },
    });
    await window.PATHWAY_V2.createCase('RLP-2026-0317');
    setCase({ ...updated, status: 'open' });
    setIntakeComplete(true);
  };

  if (loadingCase || !case_) {
    return (
      <div style={{ display: 'grid', placeItems: 'center', minHeight: '100vh', color: '#6b7280' }}>
        Loading case…
      </div>
    );
  }

  const plan = intakeComplete ? window.PATHWAY_V2.deriveTimeline(case_) : null;

  return (
    <>
      <CaseHeader case_={case_} onReply={() => alert('Reply to Karoline (demo).')} />

      <div className="page">
        <div className="content">
          <NextActionCard
            case_={case_}
            intakeComplete={intakeComplete}
            onOpenIntake={() => setIntakeOpen(true)}
            plan={plan}
          />

          {!intakeComplete && <TimelineSilhouette />}
          {intakeComplete && plan && <Timeline plan={plan} />}

          <footer className="policy-foot">
            <p>
              Case follows: <span className="strong">{case_.policy.name}</span> · {case_.policy.version}
            </p>
            <p>
              Last updated {case_.policy.updatedAt} by {case_.policy.updatedBy} (Mobility Lead)
            </p>
          </footer>
        </div>
      </div>

      <IntakePanel
        open={intakeOpen}
        onClose={() => setIntakeOpen(false)}
        case_={case_}
        onConfirm={onConfirmIntake}
      />

      {t.showDevPanel && (
        <TweaksPanel>
          <TweakSection label="Demo state" />
          <TweakButton label={intakeComplete ? 'Reset to intake' : 'Skip to complete'}
            onClick={intakeComplete ? resetCase : jumpToComplete} />
          <TweakButton label="Open intake panel" onClick={() => setIntakeOpen(true)} />
        </TweaksPanel>
      )}
    </>
  );
}

const CaseHeader = window.PV2_CaseHeader;
const NextActionCard = window.PV2_NextActionCard;
const IntakePanel = window.PV2_IntakePanel;
const Timeline = window.PV2_Timeline;
const TimelineSilhouette = window.PV2_TimelineSilhouette;

const pv2Root = ReactDOM.createRoot(document.getElementById('root'));
pv2Root.render(<PathwayV2 />);

})();
