// platform-s9-admin.jsx — Admin section (ReloPass superuser)
(function() {
const { useState } = React;
const I = window.PlatformIcon;
const D = window.PlatformData;

// ── Mock data ──────────────────────────────────────
const REVIEW_QUEUE = [
  { id: 'rq-1041', kind: 'Vendor approval',  what: 'EuroLingua Stavanger',     org: 'Aurora Energy', age: '2h',  prio: 'high',   owner: 'Romain' },
  { id: 'rq-1040', kind: 'Resource publish', what: 'NO · TB test minors',      org: 'Internal',      age: '4h',  prio: 'high',   owner: 'Unassigned' },
  { id: 'rq-1039', kind: 'Policy exception', what: 'Marc B. · school',         org: 'Aurora Energy', age: '6h',  prio: 'medium', owner: 'Sofia' },
  { id: 'rq-1038', kind: 'Vendor approval',  what: 'Skole Match',              org: 'Aurora Energy', age: '11h', prio: 'medium', owner: 'Romain' },
  { id: 'rq-1037', kind: 'Form template',    what: 'UDI · UTL-2011 (v2026.4)', org: 'Internal',      age: '1d',  prio: 'medium', owner: 'Sofia' },
  { id: 'rq-1036', kind: 'Source refresh',   what: 'anabin.kmk.org',           org: 'Internal',      age: '1d',  prio: 'low',    owner: 'Unassigned' },
  { id: 'rq-1035', kind: 'Tax rule',         what: 'DE Bundessteuer 2026 Q3',  org: 'Internal',      age: '2d',  prio: 'low',    owner: 'Linnea' },
  { id: 'rq-1034', kind: 'Tenant onboarding',what: 'Veritas Manufacturing',    org: 'Sales',         age: '3d',  prio: 'high',   owner: 'Marcus' },
];

const ADMIN_TOOLS = [
  { id: 's9a', t: 'Review queue',       sub: '24 items · 8 awaiting assignment', ico: 'check2',  count: 24, tone: 'warning',
    breakdown: [ ['Vendor approvals', 9], ['Policy exceptions', 6], ['Form templates', 4], ['Source refreshes', 3], ['Tenant onboarding', 2] ] },
  { id: 's9b', t: 'Ops analytics',      sub: 'SLA, bottlenecks, reviewer load',   ico: 'pulse',   count: 96, tone: 'success', suffix: '%',
    breakdown: [ ['SLA met (last 30d)', '96%'], ['Reviewer load avg', '14/wk'], ['p95 ack', '38m'], ['Bottleneck', 'apostille intake'] ] },
  { id: 's9c', t: 'Workflow analytics', sub: 'Recommendations, RFQ conversion',   ico: 'network', count: 4127, tone: 'accent',
    breakdown: [ ['Recommendations served', '4,127'], ['RFQ conversion', '32%'], ['Supplier engagement', '78%'], ['Drop-off · S1→S3', '6%'] ] },
  { id: 's9d', t: 'Resources CMS',      sub: 'Guides, requirements, taxonomy',    ico: 'book',    count: 318, tone: 'teal',
    breakdown: [ ['Published resources', 248], ['Drafts', 42], ['Categories', 18], ['Tags', 124] ] },
  { id: 's9e', t: 'Prospects',          sub: 'HR pipeline · ICP-scored',          ico: 'users',   count: 184, tone: 'accent',
    breakdown: [ ['ICP A-tier', 28], ['ICP B-tier', 64], ['Discovery booked', 12], ['Won this quarter', 4] ] },
  { id: 's9f', t: 'Integrations',       sub: 'Personio, BambooHR, Supabase auth', ico: 'layers',  count: 7,  tone: 'success',
    breakdown: [ ['Personio webhooks', '12k/day'], ['BambooHR · live', 'OK'], ['Supabase auth p95', '180ms'], ['Last incident', '14d ago'] ] },
  { id: 's9g', t: 'Companies & users',  sub: 'Tenants, allowlists, roles',        ico: 'globe',   count: 42, tone: 'teal',
    breakdown: [ ['Tenants', 42], ['HR users', 168], ['Employees · active', '1,204'], ['Admin allowlist', '@relopass.com'] ] },
];

// ── Admin overview (s9) ────────────────────────────
function AdminOverviewScreen({ setRoute }) {
  return (
    <div className="page wide">
      <div className="page-hd">
        <div className="page-eyebrow">ReloPass · internal superuser console</div>
        <div className="split-row" style={{ alignItems: 'flex-end' }}>
          <h1 className="page-h">Admin overview</h1>
          <div className="spacer"></div>
          <span className="pill warning"><I n="shield" s={11}/> admin scope · @relopass.com</span>
          <button className="btn"><I n="filter" s={12}/> All tenants</button>
        </div>
        <div className="page-sub">
          Everything ReloPass operators see. Tenant data is read-write; tenant-private fields are masked unless you escalate via the review queue.
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 18 }}>
        <AdminStat k="Active tenants"     v="42"     sub="+ 3 this quarter"  tone="accent"/>
        <AdminStat k="Cases in flight"    v="1,204"  sub="across 4 corridors top" tone="teal"/>
        <AdminStat k="Open review items"  v="24"     sub="8 awaiting assignment"   tone="warning"/>
        <AdminStat k="System SLA (30d)"   v="96%"    sub="target 95%"        tone="success"/>
      </div>

      <div className="adm-grid">
        {ADMIN_TOOLS.map(tool => (
          <div key={tool.id} className="card adm-card" onClick={() => setRoute(tool.id)}>
            <div className="adm-card-hd">
              <div className={`adm-ico ${tool.tone}`}><I n={tool.ico} s={16}/></div>
              <div>
                <div className="t">{tool.t}</div>
                <div className="s">{tool.sub}</div>
              </div>
              <div className="adm-count tabular">{tool.count}{tool.suffix || ''}</div>
            </div>
            <div className="adm-card-bd">
              {tool.breakdown.map(([k, v], i) => (
                <div key={i} className="adm-row">
                  <span className="k">{k}</span>
                  <span className="v">{v}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="card card-pad" style={{ marginTop: 18, display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ width: 28, height: 28, borderRadius: 7, background: 'var(--accent-soft)', color: 'var(--accent)', display: 'grid', placeItems: 'center' }}><I n="sparkles" s={14}/></div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600, fontSize: 13 }}>What you see vs. what tenants see</div>
          <div style={{ fontSize: 12.5, color: 'var(--text-2)', marginTop: 4, lineHeight: 1.6 }}>
            Tenants on <strong>Basic</strong> see intake + documents. <strong>Standard</strong> adds roadmap, marketplace, and AI discovery. <strong>Premium</strong> unlocks the full dossier & forms. <strong>HR</strong> tier exposes the mobility control center and the policy engine. Switch role in the Tweaks panel to preview what each tier sees.
          </div>
        </div>
      </div>
    </div>
  );
}

function AdminStat({ k, v, sub, tone }) {
  return (
    <div className="card card-pad">
      <div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-3)', fontWeight: 600 }}>{k}</div>
      <div className="tabular" style={{ fontSize: 26, fontWeight: 700, marginTop: 4, letterSpacing: '-0.02em' }}>{v}</div>
      <div style={{ fontSize: 11.5, color: 'var(--text-3)', marginTop: 2 }}>{sub}</div>
    </div>
  );
}

// ── Review queue (s9a) ─────────────────────────────
function ReviewQueueScreen() {
  return (
    <div className="page wide">
      <div className="page-hd">
        <div className="page-eyebrow">Admin · /review-queue</div>
        <div className="split-row" style={{ alignItems: 'flex-end' }}>
          <h1 className="page-h">Review queue</h1>
          <div className="spacer"></div>
          <button className="btn"><I n="filter" s={12}/> Filters</button>
          <button className="btn"><I n="users" s={12}/> Assign batch</button>
          <button className="btn primary"><I n="plus" s={12}/> New review item</button>
        </div>
        <div className="page-sub">Vendor approvals, policy exceptions, source refreshes, and tenant onboarding all funnel here. Claim or assign before the SLA timer runs out.</div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 14 }}>
        <AdminStat k="Open"     v={REVIEW_QUEUE.length} sub="across 8 categories" tone="accent"/>
        <AdminStat k="High priority"   v="3" sub="SLA breach risk" tone="danger"/>
        <AdminStat k="Unassigned"      v="2" sub="auto-route after 30m" tone="warning"/>
        <AdminStat k="Closed today"    v="18" sub="median 47m" tone="success"/>
      </div>

      <div className="card movable-tbl-wrap" style={{ padding: 0 }}>
        <ReviewQueueTable rows={REVIEW_QUEUE}/>
      </div>
    </div>
  );
}

function ReviewQueueTable({ rows }) {
  const DEFAULT_ORDER  = ['id','kind','what','org','age','prio','owner','act'];
  const DEFAULT_WIDTHS = { id: 90, kind: 130, what: 240, org: 140, age: 70, prio: 100, owner: 150, act: 90 };
  const MIN_W          = { id: 70, kind: 90,  what: 160, org: 100, age: 56, prio: 80,  owner: 110, act: 80 };
  const LABELS         = { id: 'ID', kind: 'Type', what: 'Item', org: 'Tenant', age: 'Age', prio: 'Priority', owner: 'Owner', act: '' };
  const cols = useMovableColumns({ storageKey: 'reviewQueue', defaultOrder: DEFAULT_ORDER, defaultWidths: DEFAULT_WIDTHS, minWidths: MIN_W });

  const renderCell = (r, id) => {
    switch (id) {
      case 'id':    return <span className="mono" style={{ color: 'var(--text-3)', fontSize: 11.5 }}>{r.id}</span>;
      case 'kind':  return <span className="pill ghost" style={{ fontSize: 10.5 }}>{r.kind}</span>;
      case 'what':  return <span style={{ fontWeight: 550 }}>{r.what}</span>;
      case 'org':   return r.org;
      case 'age':   return <span className="tabular" style={{ color: 'var(--text-3)' }}>{r.age}</span>;
      case 'prio':  return r.prio === 'high' ? <span className="pill danger">High</span>
                          : r.prio === 'medium' ? <span className="pill warning">Medium</span>
                          : <span className="pill ghost">Low</span>;
      case 'owner': return r.owner === 'Unassigned'
                          ? <span style={{ color: 'var(--text-3)', fontStyle: 'italic' }}>Unassigned</span>
                          : <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                              <div className="avatar" style={{ width: 22, height: 22, fontSize: 9 }}>{r.owner.slice(0,2).toUpperCase()}</div>
                              {r.owner}
                            </span>;
      case 'act':   return <button className="btn sm" style={{ float:'right' }}>Open</button>;
      default: return null;
    }
  };

  return (
    <>
      <table className="tbl movable-tbl">
        <thead>
          <tr>
            {cols.order.map(id => (
              <MovableTh key={id} colId={id} ctx={cols} label={LABELS[id]} sortable={id !== 'act'}/>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.id}>
              {cols.order.map(id => (
                <td key={id} style={cols.cellStyle(id)}>{renderCell(r, id)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {cols.dirty && (
        <div style={{ padding: '8px 14px', borderTop: '1px solid var(--divider)', textAlign: 'right' }}>
          <span className="mt-reset" onClick={cols.reset}>↺ Reset columns</span>
        </div>
      )}
    </>
  );
}

// ── Ops analytics (s9b) ────────────────────────────
function OpsAnalyticsScreen() {
  return (
    <div className="page wide">
      <div className="page-hd">
        <div className="page-eyebrow">Admin · /ops</div>
        <div className="split-row" style={{ alignItems: 'flex-end' }}>
          <h1 className="page-h">Ops analytics</h1>
          <div className="spacer"></div>
          <button className="btn"><I n="cal" s={12}/> Last 30 days</button>
          <button className="btn"><I n="download" s={12}/> Export</button>
        </div>
        <div className="page-sub">SLA performance, reviewer workload, top destinations, and operational bottlenecks across all tenants.</div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 14 }}>
        <AdminStat k="SLA met"          v="96%"  sub="target 95%"    tone="success"/>
        <AdminStat k="Median ack time"  v="11m"  sub="p95 38m"       tone="accent"/>
        <AdminStat k="Reviewer load"    v="14/wk" sub="avg per FTE"   tone="teal"/>
        <AdminStat k="Open bottleneck"  v="Apostille intake" sub="42% of delays"  tone="warning"/>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <div className="card card-pad">
          <h4 style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-3)', marginBottom: 12 }}>SLA performance · last 30 days</h4>
          <FauxChart bars={[78, 84, 92, 88, 96, 98, 94, 96, 99, 97, 95, 96, 100, 98, 96, 94, 97, 99, 96, 95, 97, 98, 96, 99, 98, 96, 95, 94, 97, 96]}/>
        </div>
        <div className="card card-pad">
          <h4 style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-3)', marginBottom: 12 }}>Top destinations · this quarter</h4>
          <CorridorRow flag="🇳🇴" lbl="Norway"  cnt={142} pct={92}/>
          <CorridorRow flag="🇩🇪" lbl="Germany" cnt={118} pct={78}/>
          <CorridorRow flag="🇺🇸" lbl="USA"     cnt={86}  pct={62}/>
          <CorridorRow flag="🇸🇬" lbl="Singapore" cnt={64} pct={48}/>
          <CorridorRow flag="🇨🇦" lbl="Canada"  cnt={47}  pct={36}/>
        </div>
      </div>

      <div className="card card-pad" style={{ marginTop: 14 }}>
        <h4 style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-3)', marginBottom: 12 }}>Reviewer workload</h4>
        <ReviewerWorkloadTable/>
      </div>
    </div>
  );
}

function ReviewerWorkloadTable() {
  const ROWS = [
    { id: 'romain', name: 'Romain (admin)', init: 'RP', active: 8,  closed: 42, ack: '7m',  sla: 98 },
    { id: 'sofia',  name: 'Sofia O.',       init: 'SO', active: 14, closed: 68, ack: '12m', sla: 96 },
    { id: 'marcus', name: 'Marcus L.',      init: 'ML', active: 11, closed: 54, ack: '14m', sla: 95 },
    { id: 'linnea', name: 'Linnea K.',      init: 'LK', active: 6,  closed: 38, ack: '9m',  sla: 99 },
  ];
  const ORDER  = ['name','active','closed','ack','sla'];
  const W      = { name: 220, active: 100, closed: 110, ack: 100, sla: 100 };
  const MIN    = { name: 140, active: 80,  closed: 90,  ack: 80,  sla: 80 };
  const LBL    = { name: 'Reviewer', active: 'Active items', closed: 'Closed (30d)', ack: 'Median ack', sla: 'SLA met' };
  const cols = useMovableColumns({ storageKey: 'reviewerWorkload', defaultOrder: ORDER, defaultWidths: W, minWidths: MIN });

  const cell = (r, id) => {
    if (id === 'name') return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <div className="avatar" style={{ width: 22, height: 22, fontSize: 9 }}>{r.init}</div>{r.name}
    </span>;
    if (id === 'sla') return <span className="pill success">{r.sla}%</span>;
    return <span className="tabular">{r[id]}</span>;
  };

  return (
    <div className="movable-tbl-wrap">
      <table className="tbl movable-tbl">
        <thead><tr>
          {cols.order.map(id => <MovableTh key={id} colId={id} ctx={cols} label={LBL[id]} sortable/>)}
        </tr></thead>
        <tbody>
          {ROWS.map(r => (
            <tr key={r.id}>
              {cols.order.map(id => <td key={id} style={cols.cellStyle(id)}>{cell(r, id)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FauxChart({ bars }) {
  const max = Math.max(...bars);
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 100 }}>
      {bars.map((v, i) => (
        <div key={i} title={`${v}%`}
          style={{
            flex: 1,
            height: `${(v / max) * 100}%`,
            background: v >= 95 ? 'var(--success)' : v >= 85 ? 'var(--accent)' : 'var(--warning)',
            borderRadius: '2px 2px 0 0',
            opacity: 0.85,
          }}/>
      ))}
    </div>
  );
}

function CorridorRow({ flag, lbl, cnt, pct }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', borderBottom: '1px solid var(--divider)' }}>
      <span style={{ fontSize: 16, width: 22 }}>{flag}</span>
      <span style={{ fontSize: 13, fontWeight: 550, flex: 1 }}>{lbl}</span>
      <div className="prog-bar" style={{ width: 120 }}><div style={{ width: `${pct}%` }}/></div>
      <span className="mono tabular" style={{ fontSize: 12, width: 36, textAlign: 'right', color: 'var(--text-2)', fontWeight: 600 }}>{cnt}</span>
    </div>
  );
}

// ── Stub for the remaining admin pages ─────────────
function AdminStubScreen({ title, eyebrow, ico, desc, kvs }) {
  return (
    <div className="page wide">
      <div className="page-hd">
        <div className="page-eyebrow">{eyebrow}</div>
        <div className="split-row" style={{ alignItems: 'flex-end' }}>
          <h1 className="page-h">{title}</h1>
          <div className="spacer"></div>
          <button className="btn"><I n="filter" s={12}/> Filters</button>
          <button className="btn primary"><I n="plus" s={12}/> New</button>
        </div>
        <div className="page-sub">{desc}</div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 16 }}>
        {kvs.map(([k, v, tone], i) => <AdminStat key={i} k={k} v={v} sub="" tone={tone || 'accent'}/>)}
      </div>

      <div className="card card-pad" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 320, gap: 12, flexDirection: 'column' }}>
        <div style={{ width: 56, height: 56, borderRadius: 14, background: 'var(--accent-soft)', color: 'var(--accent)', display: 'grid', placeItems: 'center' }}>
          <I n={ico} s={24}/>
        </div>
        <div style={{ fontSize: 14, fontWeight: 600 }}>Detailed view coming up</div>
        <div style={{ fontSize: 12.5, color: 'var(--text-3)', maxWidth: 460, textAlign: 'center' }}>
          The endpoints are live in the backend ({eyebrow.split('·')[1]?.trim() || 'admin scope'}). This view will render the full table/editor next.
        </div>
      </div>
    </div>
  );
}

function WorkflowAnalyticsScreen() {
  return <AdminStubScreen
    eyebrow="Admin · /workflow"
    title="Workflow analytics"
    ico="network"
    desc="Observability for user workflows: recommendations served, supplier engagement, RFQ conversion, drop-off."
    kvs={[['Recommendations', '4,127', 'accent'], ['RFQ conversion', '32%', 'success'], ['Supplier eng.', '78%', 'teal'], ['Drop-off · S1→S3', '6%', 'warning']]}/>;
}
function ResourcesCMSScreen() {
  return <AdminStubScreen
    eyebrow="Admin · /resources"
    title="Resources CMS"
    ico="book"
    desc="Edit destination guides, requirement rules, taxonomy, categories, tags, and sources used by the AI engine."
    kvs={[['Published', '248', 'success'], ['Drafts', '42', 'warning'], ['Categories', '18', 'accent'], ['Tags', '124', 'teal']]}/>;
}
function ProspectsScreen() {
  return <AdminStubScreen
    eyebrow="Admin · /prospects"
    title="HR prospect pipeline"
    ico="users"
    desc="ICP-scored HR contacts, outreach status, discovery bookings, and won/lost deals."
    kvs={[['ICP A-tier', '28', 'success'], ['ICP B-tier', '64', 'accent'], ['Discovery booked', '12', 'teal'], ['Won (Q3)', '4', 'warning']]}/>;
}
function IntegrationsScreen() {
  return <AdminStubScreen
    eyebrow="Admin · /integrations"
    title="Integrations"
    ico="layers"
    desc="Personio sync, BambooHR live, Supabase auth, Stripe billing, Slack notifications."
    kvs={[['Personio (24h)', '12k events', 'success'], ['BambooHR', 'OK', 'success'], ['Supabase p95', '180ms', 'teal'], ['Last incident', '14d', 'accent']]}/>;
}
function CompaniesScreen() {
  return <AdminStubScreen
    eyebrow="Admin · /tenants"
    title="Companies & users"
    ico="globe"
    desc="Tenant directory, HR users, admin allowlists, role assignments."
    kvs={[['Tenants', '42', 'teal'], ['HR users', '168', 'accent'], ['Employees', '1,204', 'success'], ['Admin allowlist', '@relopass.com', 'warning']]}/>;
}

window.AdminOverviewScreen = AdminOverviewScreen;
window.ReviewQueueScreen = ReviewQueueScreen;
window.OpsAnalyticsScreen = OpsAnalyticsScreen;
window.WorkflowAnalyticsScreen = WorkflowAnalyticsScreen;
window.ResourcesCMSScreen = ResourcesCMSScreen;
window.ProspectsScreen = ProspectsScreen;
window.IntegrationsScreen = IntegrationsScreen;
window.CompaniesScreen = CompaniesScreen;
})();
