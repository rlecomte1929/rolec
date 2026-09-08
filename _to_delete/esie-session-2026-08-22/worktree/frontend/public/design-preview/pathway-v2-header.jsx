(function() {
const { useState, useEffect, useRef } = React;
// Pathway v2 — Case Header + Next Action Card

function CaseHeader({ case_, onReply }) {
  const c = case_.corridor;
  const target = new Date(case_.targetStartDate);
  const today = new Date('2026-05-18');
  const daysLeft = Math.round((target - today) / (1000 * 60 * 60 * 24));
  const urgent = daysLeft < 30;

  return (
    <div className="ch-bar">
      <div className="ch-inner">
        <div className="ch-left">
          <img src="assets/relopass-mark.png" alt="ReloPass" className="ch-logo" />
          <div className="ch-divider" />
          <div className="ch-id">
            Case <span className="mono">{case_.id}</span>
          </div>
          <Pill variant="info">Intake</Pill>
        </div>

        <div className="ch-mid">
          <span className="ch-corridor">
            <span>{c.origin.city}</span>
            <span className="code">{c.origin.code}</span>
            <span className="ch-arrow"><Ico name="arrow-right" size={14}/></span>
            <span>{c.destination.city}</span>
            <span className="code">{c.destination.code}</span>
          </span>
        </div>

        <div className="ch-right">
          <Pill variant={urgent ? 'warning' : 'neutral'}>
            Start in {daysLeft} days · {case_.targetStartLabel}
          </Pill>
          <div className="ch-hr">
            <div className="ch-hr-avatar">{initials(case_.hrContact.name)}</div>
            <div className="ch-hr-info">
              <span className="ch-hr-name">{case_.hrContact.name}</span>
              <span className="ch-hr-role">{case_.hrContact.role}</span>
            </div>
            <button className="ch-hr-reply" onClick={onReply}>
              <Ico name="message" size={12}/> Reply
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function NextActionCard({ case_, intakeComplete, onOpenIntake, plan }) {
  if (!intakeComplete) {
    return (
      <Crd className="next" pad="md">
        <div className="next-eyebrow">
          <Pill variant="info">Step 1 of 2 · Your input required</Pill>
        </div>
        <h2 className="next-h">Complete your intake</h2>
        <p className="next-sub">6 questions · ~3 minutes</p>
        <div className="next-cta-row">
          <Btn variant="primary" size="lg" onClick={onOpenIntake}>
            Complete intake <Ico name="arrow-right" size={14}/>
          </Btn>
          <span className="next-helper">This unlocks your relocation timeline.</span>
        </div>
      </Crd>
    );
  }

  // intake complete — show first active step
  const active = plan.steps.find(s => s.status === 'active') || plan.steps[0];
  return (
    <Crd className="next" pad="md">
      <div className="next-eyebrow">
        <Pill variant="success" dot>Active · Step {active.n}</Pill>
      </div>
      <h2 className="next-h">{active.title}</h2>
      <p className="next-sub">{active.line}</p>
      <div className="next-row">
        <Pill variant="neutral"><Ico name="user" size={11}/>&nbsp; {active.owner}</Pill>
        <Pill variant="neutral"><Ico name="pin" size={11}/>&nbsp; {active.where}</Pill>
        <Pill variant="neutral"><Ico name="clock" size={11}/>&nbsp; {active.time}</Pill>
      </div>
      <div className="next-cta-row">
        {active.waitingNote ? (
          <span className="next-helper">{active.waitingNote}</span>
        ) : (
          <Btn variant="primary" size="md">
            View step details <Ico name="arrow-right" size={14}/>
          </Btn>
        )}
      </div>
    </Crd>
  );
}

const Ico = window.PV2_Ico;
const Btn = window.PV2_Btn;
const Crd = window.PV2_Crd;
const Pill = window.PV2_Pill;
const { initials } = window.PATHWAY_V2.helpers;

Object.assign(window, {
  PV2_CaseHeader: CaseHeader,
  PV2_NextActionCard: NextActionCard,
});

})();
