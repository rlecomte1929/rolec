// platform-s2-discovery.jsx — AI Requirements Discovery Engine
(function() {
const { useState, useEffect, useRef } = React;
const I = window.PlatformIcon;
const D = window.PlatformData;

const DISC = D.DISCOVERY;

function DiscoveryScreen() {
  const [tab, setTab] = useState('graph'); // graph | timeline | sources
  const [revealedReqs, setRevealedReqs] = useState(DISC.requirements.length);
  const [activeReq, setActiveReq] = useState(null);

  return (
    <div className="page wide">
      <div className="page-hd">
        <div className="page-eyebrow">AI Engine</div>
        <div className="split-row" style={{ alignItems: 'flex-end' }}>
          <h1 className="page-h">Requirements discovery</h1>
          <div className="spacer"></div>
          <button className="btn"><I n="filter" s={12}/> Corridor: <strong style={{ fontWeight: 600 }}>FR → NO</strong></button>
          <button className="btn primary"><I n="bolt" s={12}/> Re-run discovery</button>
        </div>
        <div className="page-sub">
          ReloPass cross-references official sources, employer policy, and bilateral agreements to compile the requirement graph for each case. Every node carries its source, confidence, and dependencies.
        </div>
      </div>

      <DiscoveryBanner />

      <div className="disc-toolbar">
        <div className="tabs">
          <button className={`tab${tab === 'graph' ? ' active' : ''}`} onClick={() => setTab('graph')}>Requirements</button>
          <button className={`tab${tab === 'timeline' ? ' active' : ''}`} onClick={() => setTab('timeline')}>Timeline</button>
          <button className={`tab${tab === 'sources' ? ' active' : ''}`} onClick={() => setTab('sources')}>Sources</button>
        </div>
        <div className="spacer"></div>
        <span className="pill ghost"><I n="clock" s={11}/> Last run · 14:02 · 38s</span>
        <span className="pill success"><I n="check2" s={11}/> All sources verified</span>
      </div>

      {tab === 'graph' && <GraphView revealedReqs={revealedReqs} activeReq={activeReq} setActiveReq={setActiveReq} onShowSources={() => setTab('sources')}/>}
      {tab === 'timeline' && <TimelineView/>}
      {tab === 'sources' && <SourceAuditView/>}
    </div>
  );
}

function DiscoveryBanner() {
  return (
    <div className="disc-banner">
      <div className="ico"><I n="sparkles" s={16}/></div>
      <div className="body">
        <div className="t">Compiling requirement plan for <strong>{DISC.employee}</strong> · <strong>{DISC.from} → {DISC.to}</strong> · {DISC.visa}</div>
        <div className="s">Sponsored by {DISC.employer}. Plan derived from {DISC.stats.authorities} authorities across 2 jurisdictions.</div>
      </div>
      <div className="stats">
        <div className="stat"><div className="k">Requirements</div><div className="v tabular">{DISC.stats.reqs}</div></div>
        <div className="stat"><div className="k">Documents</div><div className="v tabular">{DISC.stats.docs}</div></div>
        <div className="stat"><div className="k">Est. time</div><div className="v tabular">{DISC.stats.weeks}<span style={{ fontSize: 11, color: 'var(--text-3)', fontWeight: 500 }}> wks</span></div></div>
        <div className="stat"><div className="k">Est. cost</div><div className="v tabular">{DISC.stats.cost}</div></div>
      </div>
    </div>
  );
}

function GraphView({ revealedReqs, activeReq, setActiveReq, onShowSources }) {
  return (
    <RequirementsColumn activeReq={activeReq} setActiveReq={setActiveReq} revealed={revealedReqs} onShowSources={onShowSources}/>
  );
}

function SourcesColumn() {
  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
      <div className="disc-col-hd">
        <div className="step">1</div>
        <div>
          <div className="t">Official sources</div>
          <div className="s">Retrieved & verified</div>
        </div>
      </div>
      <div className="src-list">
        {DISC.sources.map(s => (
          <div key={s.id} className={`src${s.live ? ' live' : ''}`}>
            <div className="logo">{s.init}</div>
            <div className="body">
              <div className="nm">{s.name}</div>
              <div className="url">{s.url} · {s.items} items · {s.fetched}</div>
            </div>
            {s.verified && <I n="check2" s={14} className="ok"/>}
          </div>
        ))}
      </div>
      <div style={{ padding: '10px 12px', borderTop: '1px solid var(--divider)', fontSize: 11.5, color: 'var(--text-3)', display: 'flex', alignItems: 'center', gap: 6 }}>
        <I n="shield" s={12}/> Sources cached daily · last sync 03:14
      </div>
    </div>
  );
}

function RequirementsColumn({ activeReq, setActiveReq, revealed, onShowSources }) {
  const reqs = DISC.requirements.slice(0, revealed);
  return (
    <div className="req-section">
      <div className="disc-col-hd sticky">
        <div>
          <div className="t">Extracted requirements</div>
          <div className="s">{reqs.length} nodes · cross-referenced from 6 official sources</div>
        </div>
        <div className="right" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button className="btn sm" onClick={onShowSources}><I n="db" s={11}/> View sources</button>
          <span className="pill accent" style={{ fontSize: 10 }}><I n="sparkles" s={10}/> Live</span>
        </div>
      </div>
      <div className="req-list req-list-grid">
        {reqs.map((r, i) => {
          const src = DISC.sources.find(s => s.id === r.src);
          return (
            <div key={r.id} className="req"
              style={{ animationDelay: `${i * 50}ms`, borderColor: activeReq === r.id ? 'var(--accent)' : '' }}
              onClick={() => setActiveReq(activeReq === r.id ? null : r.id)}>
              <div className="num">{String(r.id).padStart(2, '0')}</div>
              <div className="body">
                <div className="t">{r.t}</div>
                <div className="meta">
                  <span><span style={{ color: 'var(--text-2)', fontWeight: 600 }}>{r.cat}</span></span>
                  <span><I n="user" s={10}/> {r.owner}</span>
                  <span><I n="clock" s={10}/> {r.time}</span>
                  {r.deps.length > 0 && <span>depends on #{r.deps.map(d => String(d).padStart(2,'0')).join(', #')}</span>}
                  {r.conditional && <span className="pill warning" style={{ padding: '0 6px', fontSize: 9.5 }}>conditional · {r.conditional}</span>}
                  <span style={{ color: 'var(--text-3)' }}>· {src?.init}</span>
                </div>
              </div>
              <div className="conf">
                <span className="pct">{r.conf}%</span>
                <span>confidence</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ActivityLogColumn() {
  const logEnd = useRef(null);
  return (
    <div className="card log-card">
      <div className="disc-col-hd">
        <div className="step">3</div>
        <div>
          <div className="t">AI activity</div>
          <div className="s">orchestration log</div>
        </div>
        <div className="right"><span className="pill success" style={{ fontSize: 10 }}><span className="dot"></span> compiled</span></div>
      </div>
      <div className="log-list">
        {DISC.log.map((row, i) => (
          <div key={i} className={`log-row${i === DISC.log.length - 1 ? ' active' : ''}`}>
            <span className="ts">{row.ts}</span>
            <span className="msg">
              {row.msg.map((part, j) => {
                if (typeof part === 'string') return <React.Fragment key={j}>{part}</React.Fragment>;
                if (part.h) return <span key={j} className="h">{part.h}</span>;
                if (part.ok) return <span key={j} className="ok">{part.ok}</span>;
                if (part.warn) return <span key={j} className="warn">{part.warn}</span>;
                return null;
              })}
            </span>
          </div>
        ))}
        <div ref={logEnd}></div>
      </div>
      <div style={{ padding: '10px 12px', borderTop: '1px solid var(--divider)', display: 'flex', alignItems: 'center', gap: 8, fontSize: 11.5, color: 'var(--text-3)' }}>
        <I n="db" s={12}/>
        <span>graph compiled · 47 edges · 12 documents</span>
      </div>
    </div>
  );
}

// ── Timeline (alt view) ───────────────────────────
function TimelineView() {
  const phases = [
    { wk: 'wk 1–2',  t: 'Document gathering & employer sponsorship',  reqs: [1, 3, 4, 12], color: 'accent' },
    { wk: 'wk 2–4',  t: 'Civil document apostille & translation',     reqs: [3, 4, 5],    color: 'teal' },
    { wk: 'wk 3–7',  t: 'UDI permit application',                      reqs: [2],           color: 'accent' },
    { wk: 'wk 6–9',  t: 'Housing search & confirmation',               reqs: [6],           color: 'teal' },
    { wk: 'wk 8–10', t: 'Health & TB checks (dependents)',             reqs: [7, 10],      color: 'warning' },
    { wk: 'wk 9–11', t: 'Arrival, police registration, tax setup',     reqs: [8, 9, 11],   color: 'success' },
  ];

  return (
    <div className="card card-pad">
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <h3 style={{ fontSize: 14 }}>Compiled plan timeline</h3>
        <span className="pill ghost">10–14 weeks · 12 documents</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {phases.map((p, i) => (
          <div key={i} style={{ display: 'grid', gridTemplateColumns: '90px 1fr auto', gap: 12, alignItems: 'center', padding: '10px 0', borderBottom: i < phases.length - 1 ? '1px solid var(--divider)' : 'none' }}>
            <span className="mono" style={{ fontSize: 11, color: 'var(--text-3)', fontWeight: 600 }}>{p.wk}</span>
            <div>
              <div style={{ fontWeight: 600, fontSize: 13.5 }}>{p.t}</div>
              <div style={{ fontSize: 11.5, color: 'var(--text-3)', marginTop: 3 }}>
                Requirements: {p.reqs.map(r => `#${String(r).padStart(2, '0')}`).join(', ')}
              </div>
            </div>
            <div style={{ width: 140 }}>
              <div className="prog-bar" style={{ width: '100%', height: 5 }}>
                <div style={{ width: `${(i + 1) * 16}%`, height: '100%', borderRadius: 999, background: `var(--${p.color === 'accent' ? 'accent' : p.color === 'teal' ? 'teal' : p.color === 'warning' ? 'warning' : 'success'})` }}/>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Source audit (alt view) ────────────────────────
function SourceAuditView() {
  const ORDER = ['authority','domain','fetched','items','status'];
  const W     = { authority: 240, domain: 240, fetched: 140, items: 90, status: 130 };
  const MIN   = { authority: 160, domain: 160, fetched: 110, items: 70, status: 100 };
  const LBL   = { authority: 'Authority', domain: 'Domain', fetched: 'Last fetched', items: 'Items', status: 'Status' };
  const cols  = window.useMovableColumns({ storageKey: 's2sources', defaultOrder: ORDER, defaultWidths: W, minWidths: MIN });
  const MovableTh = window.MovableTh;

  const cell = (s, id) => {
    switch (id) {
      case 'authority': return (
        <div className="row-emp">
          <div className="avatar sq" style={{ width: 26, height: 26, fontSize: 10 }}>{s.init}</div>
          <div><div className="nm" style={{ fontSize: 12.5 }}>{s.name}</div></div>
        </div>
      );
      case 'domain':  return <span className="mono">{s.url}</span>;
      case 'fetched': return s.fetched;
      case 'items':   return <span className="tabular">{s.items}</span>;
      case 'status':  return <span className="pill success" style={{ fontSize: 10 }}><I n="check2" s={10}/> Verified</span>;
      default: return null;
    }
  };

  return (
    <div className="card movable-tbl-wrap" style={{ padding: 0 }}>
      <table className="tbl movable-tbl">
        <thead><tr>
          {cols.order.map(id => <MovableTh key={id} colId={id} ctx={cols} label={LBL[id]} sortable/>)}
        </tr></thead>
        <tbody>
          {DISC.sources.map(s => (
            <tr key={s.id}>
              {cols.order.map(id => <td key={id} style={cols.cellStyle(id)}>{cell(s, id)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

window.DiscoveryScreen = DiscoveryScreen;
})();
