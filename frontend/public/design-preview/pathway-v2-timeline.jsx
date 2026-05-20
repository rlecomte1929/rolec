(function() {
const { useState, useEffect, useRef } = React;
// Pathway v2 — Timeline rail (silhouette + materialised states).

const PV2_STATUS_META = {
  active:   { label: 'Active',   variant: 'success' },
  locked:   { label: 'Locked',   variant: 'neutral' },
  waiting:  { label: 'Waiting',  variant: 'warning' },
  complete: { label: 'Complete', variant: 'info' },
};

function TimelineSilhouette() {
  return (
    <>
      <div className="skl-banner">
        <span className="row"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 16v-4M12 8h.01"/></svg></span>
        <span>Complete your intake to unlock your timeline.</span>
      </div>

      <div className="skl-totals">
        <div className="totals-item">
          <div className="totals-k">Total time</div>
          <div className="totals-v" style={{ color: '#9ca3af' }}>— weeks</div>
        </div>
        <div className="totals-item">
          <div className="totals-k">Total cost</div>
          <div className="totals-v" style={{ color: '#9ca3af' }}>—</div>
        </div>
      </div>

      <div className="tl-header">
        <h2>Timeline</h2>
        <span className="text-sm text-muted">Generates on intake confirmation</span>
      </div>

      <div>
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="skl-row">
            <div className="skl-bullet" />
            <div className="skl-lines">
              <div className="skl-line l1" />
              <div className="skl-line l2" />
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

function TimelineStep({ step, expanded, onToggle }) {
  const meta = PV2_STATUS_META[step.status] || PV2_STATUS_META.locked;
  return (
    <div className={`tl-row ${step.status}${expanded ? ' open' : ''}`}>
      <div className="tl-node"><div className="tl-node-inner" /></div>

      <div className="tl-row-head" onClick={onToggle}>
        <div className="tl-title-wrap">
          <div className="tl-meta-line">
            <span className="tl-step-num">Step {step.n}</span>
            <Pill variant={meta.variant} dot={step.status === 'active'}>{meta.label}</Pill>
            {step.cost && step.cost !== '—' && <span className="text-sm text-muted">{step.cost}</span>}
          </div>
          <h3 className="tl-title">{step.title}</h3>
          {step.line && <p className="tl-line">{step.line}</p>}
          <div className="tl-meta">
            <span><Ico name="user" size={12}/> <span className="pin">{step.owner}</span></span>
            <span><Ico name="pin" size={12}/> {step.where}</span>
            <span><Ico name="clock" size={12}/> {step.time}</span>
            {step.depends && <span><Ico name="chevron-right" size={12}/> {step.depends}</span>}
          </div>
        </div>
        <span className="tl-chev"><Ico name="chevron-down" size={16}/></span>
      </div>

      {expanded && (
        <div className="tl-body">
          {step.waitingNote && (
            <div className="tl-waiting"><Ico name="pause-circle" size={13}/> {step.waitingNote}</div>
          )}
          {step.note && (
            <div className={`tl-note ${step.note.variant}`}>
              <Ico name="info" size={15}/>
              <div>
                <strong>{step.note.title}</strong>
                <span>{step.note.body}</span>
              </div>
            </div>
          )}
          {step.subs && step.subs.length > 0 && (
            <ul className="tl-subs">
              {step.subs.map((s, i) => (
                <li key={i}>
                  <span className="dot" />
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          )}

          {/* Document upload stub — placeholder per acceptance criteria */}
          {(step.key === 'permit' || step.key === 'docs-origin' || step.key === 'housing') && (
            <button className="tl-upload-stub" disabled>
              <Ico name="upload" size={13}/>
              <span>Upload documents</span>
              <Pill variant="neutral" className="ml-8">In development</Pill>
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function FamilyLane({ lane, expanded, onToggle }) {
  const { memberName, memberInitials, memberLabel, step } = lane;
  return (
    <div className="lane">
      <div className={`lane-row${expanded ? ' open' : ''}`}>
        <div className="lane-member">
          <div className="lane-avatar">{memberInitials}</div>
          <div>
            <div className="lane-name">{memberName}</div>
            <div className="lane-label">{memberLabel}</div>
          </div>
          <span className="lane-anchor"><Ico name="chevron-right" size={11}/> after {step.anchorTo}</span>
        </div>

        <div className="tl-row-head" style={{ alignItems: 'flex-start' }} onClick={onToggle}>
          <div className="tl-title-wrap">
            <h4 className="tl-title">{step.title}</h4>
            <p className="tl-line">{step.line}</p>
            <div className="tl-meta">
              <span><Ico name="user" size={12}/> <span className="pin">{step.owner}</span></span>
              <span><Ico name="pin" size={12}/> {step.where}</span>
              <span><Ico name="clock" size={12}/> {step.time}</span>
            </div>
          </div>
          <span className="tl-chev"><Ico name="chevron-down" size={16}/></span>
        </div>

        {expanded && step.subs && (
          <ul className="tl-subs mt-16">
            {step.subs.map((s, i) => (
              <li key={i}>
                <span className="dot" />
                <span>{s}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function Timeline({ plan }) {
  const [openSteps, setOpenSteps] = useState({ 1: true });   // step 1 (active) open by default
  const [openLanes, setOpenLanes] = useState({});

  const toggleStep = (n) => setOpenSteps(o => ({ ...o, [n]: !o[n] }));
  const toggleLane = (k) => setOpenLanes(o => ({ ...o, [k]: !o[k] }));

  return (
    <>
      <div className="totals">
        <div className="totals-row">
          <div className="totals-item">
            <div className="totals-k">Total time</div>
            <div className="totals-v">{plan.totals.time}</div>
          </div>
          <div className="totals-item">
            <div className="totals-k">Total cost</div>
            <div className="totals-v">{plan.totals.cost}</div>
          </div>
          <div className="totals-item">
            <div className="totals-k">Employer</div>
            <div className="totals-v" style={{ fontSize: 14, color: '#374151', fontWeight: 500 }}>{plan.totals.employerCovers}</div>
          </div>
        </div>
        <div className="outcomes">
          {plan.outcomes.map((o, i) => (
            <span key={i} className="outcome"><Ico name="check" size={12} strokeWidth={3}/> {o}</span>
          ))}
        </div>
      </div>

      <div className="tl-header">
        <h2>Timeline</h2>
        <span className="text-sm text-muted">{plan.steps.length} steps · {plan.lanes.length} family tracks</span>
      </div>

      <div className="tl">
        {plan.steps.map((s, i) => {
          // Insert family lanes anchored to a step right AFTER that step
          const lanesAfter = plan.lanes.filter(l => l.step.anchorTo === `Step ${s.n}`);
          return (
            <React.Fragment key={s.n}>
              <TimelineStep
                step={s}
                expanded={!!openSteps[s.n]}
                onToggle={() => toggleStep(s.n)}
              />
              {lanesAfter.map(l => (
                <FamilyLane
                  key={l.memberKey}
                  lane={l}
                  expanded={!!openLanes[l.memberKey]}
                  onToggle={() => toggleLane(l.memberKey)}
                />
              ))}
            </React.Fragment>
          );
        })}
      </div>
    </>
  );
}

// Pull globals
const Ico = window.PV2_Ico;
const Pill = window.PV2_Pill;

Object.assign(window, {
  PV2_Timeline: Timeline,
  PV2_TimelineSilhouette: TimelineSilhouette,
});

})();
