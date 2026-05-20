// platform-s5c-policy-reality.jsx — Policy vs. Reality comparison dashboard
(function() {
const { useState, useMemo } = React;
const I = window.PlatformIcon;

// ── Mock data ──────────────────────────────────────────────────────
const BENEFITS = [
  { cat: 'Pre-assignment', k: 'visa_work_permit',     lbl: 'Visa & work permit assistance' },
  { cat: 'Pre-assignment', k: 'language_training',     lbl: 'Language training' },
  { cat: 'Pre-assignment', k: 'cultural_training',     lbl: 'Cultural training' },
  { cat: 'Relocation',     k: 'removal_expenses',      lbl: 'Removal & shipping' },
  { cat: 'Relocation',     k: 'temporary_living',      lbl: 'Temporary living' },
  { cat: 'Relocation',     k: 'settling_in',            lbl: 'Settling-in services' },
  { cat: 'Compensation',   k: 'mobility_premium',      lbl: 'Mobility premium' },
  { cat: 'Compensation',   k: 'host_housing_cap',      lbl: 'Host country housing cap' },
  { cat: 'Compensation',   k: 'host_transportation',   lbl: 'Host country transportation' },
  { cat: 'Family',         k: 'child_education',       lbl: 'Child education support' },
  { cat: 'Family',         k: 'spouse_assistance',     lbl: 'Spouse / partner assistance' },
  { cat: 'Leave',          k: 'home_leave_trips',      lbl: 'Home leave trips' },
  { cat: 'Tax',            k: 'tax_equalisation',      lbl: 'Tax equalisation' },
];

// 14 active cases with per-benefit status. Status: 'green' (within), 'amber' (soft over), 'red' (hard over), 'grey' (n/a), 'blue' (pending)
const CASES = [
  { id: 'c1', name: 'Marc Bouchard',  init: 'MB', dest: 'FR→NO', flag: '🇳🇴', tier: 'Manager',  type: 'long_term', start: '2026-06-12', budget: 22000, spend: 23400, status: 'Active',  cells: { visa_work_permit:'green', language_training:'green', cultural_training:'green', removal_expenses:'green', temporary_living:'amber', settling_in:'green', mobility_premium:'green', host_housing_cap:'amber', host_transportation:'green', child_education:'red', spouse_assistance:'green', home_leave_trips:'green', tax_equalisation:'grey' } },
  { id: 'c2', name: 'Priya Nair',     init: 'PN', dest: 'IN→DE', flag: '🇩🇪', tier: 'Director', type: 'long_term', start: '2026-04-22', budget: 38000, spend: 41200, status: 'Active',  cells: { visa_work_permit:'green', language_training:'green', cultural_training:'green', removal_expenses:'amber', temporary_living:'green', settling_in:'green', mobility_premium:'green', host_housing_cap:'red', host_transportation:'green', child_education:'grey', spouse_assistance:'red', home_leave_trips:'green', tax_equalisation:'green' } },
  { id: 'c3', name: 'Yuki Tanaka',    init: 'YT', dest: 'JP→DE', flag: '🇩🇪', tier: 'Manager',  type: 'long_term', start: '2026-03-08', budget: 22000, spend: 21100, status: 'Active',  cells: { visa_work_permit:'red',   language_training:'green', cultural_training:'green', removal_expenses:'green', temporary_living:'green', settling_in:'green', mobility_premium:'grey',  host_housing_cap:'green', host_transportation:'amber', child_education:'grey', spouse_assistance:'grey',  home_leave_trips:'green', tax_equalisation:'grey' } },
  { id: 'c4', name: 'Lucas Reyes',    init: 'LR', dest: 'MX→US', flag: '🇺🇸', tier: 'Director', type: 'long_term', start: '2026-04-30', budget: 38000, spend: 39800, status: 'Active',  cells: { visa_work_permit:'amber', language_training:'grey',  cultural_training:'green', removal_expenses:'green', temporary_living:'amber', settling_in:'green', mobility_premium:'green', host_housing_cap:'amber', host_transportation:'green', child_education:'green', spouse_assistance:'green', home_leave_trips:'green', tax_equalisation:'green' } },
  { id: 'c5', name: 'Aïcha Idrissi',  init: 'AI', dest: 'ES→CA', flag: '🇨🇦', tier: 'Manager',  type: 'long_term', start: '2026-02-14', budget: 22000, spend: 19800, status: 'Active',  cells: { visa_work_permit:'green', language_training:'green', cultural_training:'green', removal_expenses:'red',   temporary_living:'green', settling_in:'green', mobility_premium:'grey',  host_housing_cap:'green', host_transportation:'grey',  child_education:'grey', spouse_assistance:'grey',  home_leave_trips:'green', tax_equalisation:'grey' } },
  { id: 'c6', name: 'Tomás Weber',    init: 'TW', dest: 'BR→NL', flag: '🇳🇱', tier: 'Manager',  type: 'long_term', start: '2026-01-12', budget: 22000, spend: 24600, status: 'Active',  cells: { visa_work_permit:'green', language_training:'red',   cultural_training:'green', removal_expenses:'green', temporary_living:'amber', settling_in:'green', mobility_premium:'grey',  host_housing_cap:'amber', host_transportation:'green', child_education:'grey', spouse_assistance:'green', home_leave_trips:'blue',  tax_equalisation:'green' } },
  { id: 'c7', name: 'Sarah Kim',      init: 'SK', dest: 'US→JP', flag: '🇯🇵', tier: 'Director', type: 'long_term', start: '2025-12-04', budget: 38000, spend: 36400, status: 'Active',  cells: { visa_work_permit:'green', language_training:'amber', cultural_training:'green', removal_expenses:'green', temporary_living:'green', settling_in:'green', mobility_premium:'green', host_housing_cap:'green', host_transportation:'green', child_education:'grey', spouse_assistance:'grey',  home_leave_trips:'green', tax_equalisation:'green' } },
  { id: 'c8', name: 'James Holt',     init: 'JH', dest: 'GB→AU', flag: '🇦🇺', tier: 'VP',       type: 'permanent', start: '2025-11-08', budget: 68000, spend: 64200, status: 'Active',  cells: { visa_work_permit:'green', language_training:'grey',  cultural_training:'green', removal_expenses:'green', temporary_living:'green', settling_in:'green', mobility_premium:'green', host_housing_cap:'green', host_transportation:'green', child_education:'amber', spouse_assistance:'green', home_leave_trips:'green', tax_equalisation:'green' } },
  { id: 'c9', name: 'Saanvi Mehra',   init: 'SM', dest: 'IN→SG', flag: '🇸🇬', tier: 'Manager',  type: 'short_term', start: '2026-03-22', budget: 14000, spend: 15800, status: 'Active',  cells: { visa_work_permit:'green', language_training:'grey',  cultural_training:'green', removal_expenses:'amber', temporary_living:'red',   settling_in:'green', mobility_premium:'grey',  host_housing_cap:'red',   host_transportation:'green', child_education:'grey', spouse_assistance:'grey',  home_leave_trips:'blue',  tax_equalisation:'grey' } },
  { id: 'c10', name: 'Camille Fontaine', init: 'CF', dest: 'FR→US', flag: '🇺🇸', tier: 'Manager', type: 'long_term', start: '2026-05-01', budget: 22000, spend: 18200, status: 'Pending', cells: { visa_work_permit:'green', language_training:'grey',  cultural_training:'blue',  removal_expenses:'blue',  temporary_living:'blue',  settling_in:'blue',  mobility_premium:'green', host_housing_cap:'blue',  host_transportation:'blue',  child_education:'grey', spouse_assistance:'blue',  home_leave_trips:'blue',  tax_equalisation:'grey' } },
];

const STATUS_CHAR = { green: '✓', amber: '~', red: '!', grey: '—', blue: '○' };

function PolicyRealityScreen({ currency = 'EUR' }) {
  const [period, setPeriod] = useState('12mo');
  const [destFilter, setDestFilter] = useState('all');
  const [tierFilter, setTierFilter] = useState('all');
  const [activeCaseId, setActiveCaseId] = useState(null);
  const [privacy, setPrivacy] = useState(false);

  const cases = useMemo(() => {
    return CASES.filter(c =>
      (destFilter === 'all' || c.dest.endsWith(destFilter)) &&
      (tierFilter === 'all' || c.tier === tierFilter)
    );
  }, [destFilter, tierFilter]);

  // KPIs
  const kpis = useMemo(() => {
    let total = 0, withinCap = 0, overageSum = 0, overageCount = 0;
    const benefitOverages = {};
    cases.forEach(c => {
      Object.entries(c.cells).forEach(([k, s]) => {
        if (s === 'grey' || s === 'blue') return;
        total++;
        if (s === 'green') withinCap++;
        if (s === 'amber' || s === 'red') {
          benefitOverages[k] = (benefitOverages[k] || 0) + 1;
        }
      });
      const variance = c.spend - c.budget;
      if (variance > 0) {
        overageSum += variance;
        overageCount++;
      }
    });
    const mostOver = Object.entries(benefitOverages).sort((a, b) => b[1] - a[1])[0];
    return {
      compliance: total > 0 ? Math.round((withinCap / total) * 100) : 0,
      active: cases.length,
      avgOverage: overageCount > 0 ? Math.round(overageSum / overageCount) : 0,
      mostOver: mostOver ? { k: mostOver[0], count: mostOver[1], total: cases.length } : null,
    };
  }, [cases]);

  const cur = ['EUR','USD','GBP','CHF'].includes(currency) ? { EUR: '€', USD: '$', GBP: '£', CHF: 'CHF' }[currency] : '€';

  const complianceTone = kpis.compliance >= 80 ? 'green' : kpis.compliance >= 60 ? 'amber' : 'red';

  // Per-case stats
  const caseStats = (c) => {
    const cells = Object.values(c.cells);
    const ok = cells.filter(x => x === 'green').length;
    const total = cells.filter(x => x !== 'grey' && x !== 'blue').length;
    const over = cells.filter(x => x === 'amber' || x === 'red').length;
    return { pct: total > 0 ? Math.round((ok / total) * 100) : 0, over };
  };

  const benefitsByCategory = useMemo(() => {
    const out = {};
    BENEFITS.forEach(b => { (out[b.cat] = out[b.cat] || []).push(b); });
    return out;
  }, []);

  const activeCase = activeCaseId ? CASES.find(c => c.id === activeCaseId) : null;
  const activeIdx = activeCase ? CASES.findIndex(c => c.id === activeCaseId) : -1;

  return (
    <div className="page wide pvr-page">
      {window.ProfileSubNav && <window.ProfileSubNav active="reality"/>}

      <div className="page-hd">
        <div className="page-eyebrow">HR · /hr/policy-vs-reality</div>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 12 }}>
          <h1 className="page-h">Policy vs. Reality</h1>
          <div style={{ flex: 1 }}/>
          <button className="btn"><I n="download" s={12}/> Export CSV</button>
        </div>
        <div className="page-sub">
          Compare your company's policy commitments against what employees are actually selecting from service providers.
        </div>
      </div>

      {/* Filters */}
      <div className="pvr-filters">
        <div className="pvr-filter">
          <span className="lbl">Period:</span>
          <select value={period} onChange={(e) => setPeriod(e.target.value)}>
            <option value="3mo">Last 3 months</option>
            <option value="12mo">Last 12 months</option>
            <option value="all">All time</option>
          </select>
        </div>
        <div className="pvr-filter">
          <span className="lbl">Destination:</span>
          <select value={destFilter} onChange={(e) => setDestFilter(e.target.value)}>
            <option value="all">All countries</option>
            <option value="NO">Norway</option>
            <option value="DE">Germany</option>
            <option value="US">United States</option>
            <option value="JP">Japan</option>
            <option value="SG">Singapore</option>
            <option value="CA">Canada</option>
            <option value="NL">Netherlands</option>
            <option value="AU">Australia</option>
          </select>
        </div>
        <div className="pvr-filter">
          <span className="lbl">Tier:</span>
          <select value={tierFilter} onChange={(e) => setTierFilter(e.target.value)}>
            <option value="all">All tiers</option>
            <option>Manager</option>
            <option>Director</option>
            <option>VP</option>
          </select>
        </div>
        <div style={{ flex: 1 }}/>
        <label style={{ fontSize: 11.5, color: 'var(--text-3)', display: 'inline-flex', gap: 6, alignItems: 'center', cursor: 'pointer' }}>
          <input type="checkbox" checked={privacy} onChange={(e) => setPrivacy(e.target.checked)} style={{ margin: 0 }}/>
          Privacy mode
        </label>
      </div>

      {/* KPI strip */}
      <div className="pvr-kpis">
        <div className={`pvr-kpi ${complianceTone}`}>
          <div className="k">Policy compliance</div>
          <div className="v">{kpis.compliance}<span className="unit">%</span></div>
          <div className="trend up">↑ 4% vs last quarter</div>
        </div>
        <div className="pvr-kpi">
          <div className="k">Active relocations</div>
          <div className="v">{kpis.active}</div>
          <div className="s">{cases.filter(c => c.type === 'long_term').length} long-term · {cases.filter(c => c.type === 'short_term').length} short-term · {cases.filter(c => c.type === 'permanent').length} permanent</div>
        </div>
        <div className="pvr-kpi amber">
          <div className="k">Avg overage / case</div>
          <div className="v">{cur}{kpis.avgOverage.toLocaleString()}</div>
          <div className="s">Across cases with at least one overage</div>
        </div>
        <div className="pvr-kpi red">
          <div className="k">Most exceeded benefit</div>
          <div className="v" style={{ fontSize: 14, color: 'var(--text)' }}>
            {kpis.mostOver ? BENEFITS.find(b => b.k === kpis.mostOver.k)?.lbl : '—'}
          </div>
          <div className="s">
            {kpis.mostOver ? `Exceeded in ${kpis.mostOver.count} of ${kpis.mostOver.total} cases` : 'No overages'}
          </div>
        </div>
      </div>

      {/* Heatmap */}
      <div className="pvr-section">
        <div className="pvr-section-hd">
          <div>
            <div className="t">Compliance heatmap</div>
            <div className="s">Each cell = one benefit × one case. Hover for details.</div>
          </div>
        </div>
        <div className="pvr-section-bd">
          <div className="pvr-heatmap-wrap">
            <table className="pvr-heatmap">
              <thead>
                <tr>
                  <th className="row-hd" style={{ borderRight: '1px solid var(--border)' }}>Benefit</th>
                  {cases.map((c, i) => (
                    <th key={c.id} title={c.name}>
                      <div className="pvr-col-sum">{privacy ? `#${i + 1}` : c.init}</div>
                    </th>
                  ))}
                  <th>Summary</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(benefitsByCategory).map(([cat, blist]) => (
                  <React.Fragment key={cat}>
                    <tr className="pvr-cat-row"><td colSpan={cases.length + 2}>{cat}</td></tr>
                    {blist.map(b => {
                      const rowVals = cases.map(c => c.cells[b.k]);
                      const exceeded = rowVals.filter(v => v === 'amber' || v === 'red').length;
                      return (
                        <tr key={b.k}>
                          <td className="row-hd">{b.lbl}</td>
                          {cases.map(c => {
                            const s = c.cells[b.k] || 'grey';
                            return (
                              <td key={c.id} title={`${b.lbl} · ${c.name} · ${s === 'green' ? 'within cap' : s === 'amber' ? 'soft overage' : s === 'red' ? 'hard overage' : s === 'blue' ? 'pending' : 'n/a'}`}>
                                <span className={`pvr-cell ${s}`}>{STATUS_CHAR[s]}</span>
                              </td>
                            );
                          })}
                          <td><span className="pvr-row-sum" style={{ color: exceeded > 3 ? 'var(--danger)' : exceeded > 0 ? 'var(--warning)' : 'var(--text-3)' }}>{exceeded}/{cases.length} {exceeded > 0 ? 'exceeded' : 'ok'}</span></td>
                        </tr>
                      );
                    })}
                  </React.Fragment>
                ))}
                {/* Column compliance summary */}
                <tr className="pvr-col-sum-row">
                  <td className="row-hd">Compliance</td>
                  {cases.map(c => {
                    const cs = caseStats(c);
                    const tone = cs.pct >= 80 ? 'green' : cs.pct >= 60 ? 'amber' : 'red';
                    return <td key={c.id}><span className="pvr-col-sum" style={{ color: `var(--${tone === 'green' ? 'success' : tone === 'amber' ? 'warning' : 'danger'})` }}>{cs.pct}%</span></td>;
                  })}
                  <td/>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Category charts */}
      <div className="pvr-section">
        <div className="pvr-section-hd">
          <div>
            <div className="t">Category overage breakdown</div>
            <div className="s">Average % overage per benefit, grouped by category. Green = under budget.</div>
          </div>
        </div>
        <div className="pvr-section-bd">
          <div className="pvr-cat-charts">
            {Object.entries(benefitsByCategory).map(([cat, blist]) => (
              <div key={cat} className="pvr-cat-chart">
                <div className="t">{cat}</div>
                <div className="pvr-cat-chart-bars">
                  {blist.map(b => {
                    const rowVals = cases.map(c => c.cells[b.k]);
                    const overs = rowVals.filter(v => v === 'amber' || v === 'red').length;
                    const unders = rowVals.filter(v => v === 'green').length;
                    const total = rowVals.filter(v => v !== 'grey' && v !== 'blue').length || 1;
                    const pct = Math.round(((overs - unders * 0.1) / total) * 100);
                    const isOver = pct > 0;
                    return (
                      <div key={b.k} className="pvr-cat-chart-row">
                        <span className="lbl">{b.lbl}</span>
                        <div className="b">
                          {isOver
                            ? <div className="pos" style={{ width: Math.min(50, Math.abs(pct) / 2) + '%' }}/>
                            : <div className="neg" style={{ width: Math.min(50, Math.abs(pct) / 2) + '%' }}/>}
                          <div className="zero" />
                        </div>
                        <span className={`v ${isOver ? 'over' : 'under'}`}>{isOver ? '+' : ''}{pct}%</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Per-case list */}
      <div className="pvr-section">
        <div className="pvr-section-hd">
          <div>
            <div className="t">Per-case detail</div>
            <div className="s">{cases.length} active assignment{cases.length === 1 ? '' : 's'} — click any row for a side-by-side breakdown.</div>
          </div>
        </div>
        <table className="pvr-cases">
          <thead>
            <tr>
              <th>Case</th>
              <th>Destination</th>
              <th>Tier</th>
              <th>Type</th>
              <th>Compliance</th>
              <th>Overages</th>
              <th>Policy budget</th>
              <th>Actual spend</th>
              <th>Variance</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {cases.map((c, i) => {
              const cs = caseStats(c);
              const tone = cs.pct >= 80 ? 'green' : cs.pct >= 60 ? 'amber' : 'red';
              const variance = c.spend - c.budget;
              const varTone = variance > 0 ? 'over' : 'under';
              return (
                <tr key={c.id} onClick={() => setActiveCaseId(c.id)}>
                  <td>
                    <div className="nm">
                      <div className="av">{privacy ? `#${i + 1}` : c.init}</div>
                      {privacy ? `Case #${i + 1}` : c.name}
                    </div>
                  </td>
                  <td>{c.flag} {c.dest}</td>
                  <td><span className="cos-badge accent">{c.tier}</span></td>
                  <td><span className="cos-badge neutral">{c.type.replace('_', '-')}</span></td>
                  <td>
                    <div className="pvr-compliance-bar">
                      <div className="bar"><div className={tone} style={{ width: cs.pct + '%' }}/></div>
                      <span className="pct">{cs.pct}%</span>
                    </div>
                  </td>
                  <td>{cs.over > 0 ? <span className="cos-badge danger">{cs.over}</span> : <span style={{ color: 'var(--text-3)' }}>0</span>}</td>
                  <td style={{ fontFamily: 'var(--mono)' }}>{cur}{c.budget.toLocaleString()}</td>
                  <td style={{ fontFamily: 'var(--mono)' }}>{cur}{c.spend.toLocaleString()}</td>
                  <td><span className={`pvr-variance ${varTone}`}>{variance > 0 ? '+' : ''}{cur}{Math.abs(variance).toLocaleString()}</span></td>
                  <td>{c.status}</td>
                  <td><span style={{ color: 'var(--accent)', fontSize: 11.5, fontWeight: 600 }}>View details →</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Policy calibration */}
      <div className="pvr-section">
        <div className="pvr-section-hd">
          <div>
            <div className="t">Policy calibration</div>
            <div className="s">Strategic view — is the policy set correctly for the market?</div>
          </div>
        </div>
        <div className="pvr-calibration">
          <div className="pvr-cal-chart">
            <div className="t">Cap adequacy by benefit (top 6)</div>
            <div className="pvr-cat-chart-bars">
              {BENEFITS.slice(0, 6).map(b => {
                const exceed = Math.round(Math.random() * 60 + 10);
                return (
                  <div key={b.k} className="pvr-cat-chart-row">
                    <span className="lbl">{b.lbl}</span>
                    <div className="b">
                      <div className="pos" style={{ width: (exceed / 2) + '%' }}/>
                      <div className="zero"/>
                    </div>
                    <span className="v over">{exceed}%</span>
                  </div>
                );
              })}
            </div>
          </div>
          <div className="pvr-cal-chart">
            <div className="t">Housing cap vs actual spend · 12mo</div>
            <svg viewBox="0 0 300 120" style={{ width: '100%', height: 120 }}>
              <path d="M 10 60 L 60 60 L 60 50 L 120 50 L 120 50 L 180 45 L 240 45 L 290 45" stroke="var(--accent)" strokeWidth="2" fill="none"/>
              <path d="M 10 78 Q 50 75 90 70 T 170 64 T 250 56 T 290 52" stroke="var(--danger)" strokeWidth="2" fill="none" strokeDasharray="3 3"/>
              <path d="M 10 60 L 60 60 L 60 50 L 120 50 L 120 50 L 180 45 L 240 45 L 290 45 L 290 52 L 250 56 L 170 64 L 90 70 Q 50 75 10 78 Z" fill="var(--danger-soft)" opacity="0.6"/>
              <text x="10" y="14" fontSize="9" fill="var(--text-3)" fontWeight="600">Policy cap</text>
              <text x="200" y="14" fontSize="9" fill="var(--danger)" fontWeight="600">— Actual spend</text>
              <text x="0" y="115" fontSize="8" fill="var(--text-3)">Jan</text>
              <text x="270" y="115" fontSize="8" fill="var(--text-3)">Dec</text>
            </svg>
          </div>
        </div>
        <div style={{ padding: '0 16px 16px' }}>
          <div className="pvr-cal-recommend">
            <strong>Your housing cap in Germany ({cur}2,500/mo)</strong> covers only 58% of actual selections over the last 12 months. The market has moved — consider revising to {cur}2,900/mo to align with current provider pricing.
            <br/><button>Update policy →</button>
          </div>
        </div>
      </div>

      {/* Per-case drawer */}
      {activeCase && <CaseDrawer caseRow={activeCase} caseIdx={activeIdx} cur={cur} privacy={privacy} onClose={() => setActiveCaseId(null)} onNav={(d) => setActiveCaseId(CASES[Math.max(0, Math.min(CASES.length - 1, activeIdx + d))].id)}/>}
    </div>
  );
}

function CaseDrawer({ caseRow: c, caseIdx, cur, privacy, onClose, onNav }) {
  const cells = Object.entries(c.cells);
  const ok = cells.filter(([, s]) => s === 'green').length;
  const total = cells.filter(([, s]) => s !== 'grey' && s !== 'blue').length;
  const pct = total > 0 ? Math.round((ok / total) * 100) : 0;
  const tone = pct >= 80 ? 'green' : pct >= 60 ? 'amber' : 'red';

  // Fake policy / actual values per benefit
  const valueFor = (k, state, ix) => {
    const seed = (c.id.charCodeAt(1) + ix * 17) % 100;
    const base = 200 + seed * 30;
    const overPct = state === 'red' ? 1.32 : state === 'amber' ? 1.12 : state === 'green' ? 0.88 : 1.0;
    return { policy: base, actual: state === 'grey' || state === 'blue' ? null : Math.round(base * overPct) };
  };

  return (
    <>
      <div className="pvr-drawer-bd" onClick={onClose}/>
      <aside className="pvr-drawer">
        <div className="pvr-drawer-hd">
          <div className="av-lg">{privacy ? `#${caseIdx + 1}` : c.init}</div>
          <div>
            <div className="nm">{privacy ? `Case #${caseIdx + 1}` : c.name}</div>
            <div className="meta">
              <span>{c.flag} {c.dest}</span>
              <span>·</span>
              <span>{c.tier}</span>
              <span>·</span>
              <span>{c.type.replace('_', '-')}</span>
              <span>·</span>
              <span>Started {c.start}</span>
            </div>
          </div>
          <div style={{ marginLeft: 'auto' }}>
            <span className={`pvr-score-pill ${tone}`}>{pct}% compliant</span>
          </div>
          <button className="x" onClick={onClose}><I n="x" s={14}/></button>
        </div>

        <div className="pvr-drawer-body">
          {BENEFITS.map((b, ix) => {
            const s = c.cells[b.k] || 'grey';
            const { policy, actual } = valueFor(b.k, s, ix);
            const variance = actual ? actual - policy : 0;
            const varPct = policy > 0 && actual ? Math.round((variance / policy) * 100) : 0;
            return (
              <div key={b.k} className="pvr-benefit-line">
                <div className="nm">{b.lbl}</div>
                <div className="col">
                  <div className="lbl">Policy says</div>
                  <div className="val">{s === 'grey' ? '— N/A' : `${cur}${policy.toLocaleString()}/mo`}</div>
                </div>
                <div className="col sel">
                  <div className="lbl">Employee selected</div>
                  <div className="val">{actual ? `${cur}${actual.toLocaleString()}/mo` : '— Pending'}</div>
                  {actual && <div className="supplier">Supplier: {['NestPick', 'Lodgis', 'Crown', 'Bolig Direkte', 'WeFly'][ix % 5]}</div>}
                </div>
                <div className="status">
                  {s === 'green' && <span className="pill under">✓ Within cap</span>}
                  {s === 'amber' && <span className="pill soft">~ Soft overage · +{cur}{variance.toLocaleString()} ({varPct}%)</span>}
                  {s === 'red'   && <span className="pill over">⚠ Hard overage · +{cur}{variance.toLocaleString()} ({varPct}%)</span>}
                  {s === 'blue'  && <span className="pill pending">○ Awaiting selection</span>}
                  {s === 'grey'  && <span style={{ color: 'var(--text-3)', fontSize: 11.5 }}>Not applicable</span>}
                  {(s === 'amber' || s === 'red') && (
                    <div className="actions">
                      <button className="approve">Approve overage</button>
                      <button>Flag</button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <div className="pvr-drawer-foot">
          <button className="nav-arrow" onClick={() => onNav(-1)} title="Previous case">←</button>
          <button className="nav-arrow" onClick={() => onNav(1)} title="Next case">→</button>
          <div className="spc"/>
          <button><I n="download" s={12}/> Download report</button>
          <button><I n="msg" s={12}/> Email summary</button>
        </div>
      </aside>
    </>
  );
}

window.PolicyRealityScreen = PolicyRealityScreen;
})();
