// platform-shell.jsx — Sidebar, Topbar, AI panel
(function() {
const { useState, useEffect, useRef } = React;
const I = window.PlatformIcon;

// ── Sidebar ──────────────────────────────────────────
// Tier hierarchy: basic < standard < premium < hr < admin
const TIER_RANK = { basic: 0, standard: 1, premium: 2, hr: 3, admin: 4 };
const TIER_LABEL = { basic: 'Basic', standard: 'Standard', premium: 'Premium', hr: 'HR', admin: 'Admin' };

function Sidebar({ route, setRoute, collapsed, onToggleCollapse, role = 'admin' }) {
  const sectionsDef = [
    { label: 'Employee', tier: 'basic', items: [
      { id: 's1', name: 'Intake',           ico: 'sparkles',  tier: 'basic',    badge: null },
      { id: 's1p',name: 'Detailed intake', ico: 'user',      tier: 'basic',    badge: 'NEW' },
      { id: 's3', name: 'Roadmap',          ico: 'pulse',     tier: 'standard', badge: '3' },
      { id: 's10', name: 'Inbox',           ico: 'msg',       tier: 'basic',    badge: '3' },
      { id: 's8', name: 'Documents',        ico: 'upload',    tier: 'basic',    badge: null },
      { id: 's4', name: 'Dossier & forms',  ico: 'files',     tier: 'premium',  badge: null },
      { id: 's6', name: 'Service providers',ico: 'briefcase', tier: 'standard', badge: null },
    ]},
    { label: 'AI Engine', tier: 'hr', items: [
      { id: 's2', name: 'Requirements discovery', ico: 'network', tier: 'hr', badge: 'LIVE' },
    ]},
    { label: 'HR Operations', tier: 'hr', items: [
      { id: 's7', name: 'Mobility control', ico: 'globe',  tier: 'hr', badge: '12' },
      { id: 's7e',name: 'Exceptions',       ico: 'alert', tier: 'hr', badge: null },
      { id: 's7p',name: 'Company profile',  ico: 'briefcase', tier: 'hr', badge: null },
      { id: 's5', name: 'Policy & benefits',ico: 'shield', tier: 'hr', badge: null },
      { id: 's5b',name: 'Policy Builder',   ico: 'edit',  tier: 'hr', badge: 'NEW' },
      { id: 's5c',name: 'Policy vs. Reality',ico: 'pulse', tier: 'hr', badge: 'NEW' },
    ]},
    { label: 'Admin · ReloPass', tier: 'admin', items: [
      { id: 's9',   name: 'Admin overview',   ico: 'home',     tier: 'admin', badge: null },
      { id: 's9a',  name: 'Review queue',     ico: 'check2',   tier: 'admin', badge: '24' },
      { id: 's9b',  name: 'Ops analytics',    ico: 'pulse',    tier: 'admin', badge: null },
      { id: 's9c',  name: 'Workflow analytics',ico: 'network', tier: 'admin', badge: null },
      { id: 's9d',  name: 'Resources CMS',    ico: 'book',     tier: 'admin', badge: null },
      { id: 's9e',  name: 'Prospects',        ico: 'users',    tier: 'admin', badge: null },
      { id: 's9f',  name: 'Integrations',     ico: 'layers',   tier: 'admin', badge: null },
      { id: 's9g',  name: 'Companies',         ico: 'globe',    tier: 'admin', badge: null },
    ]},
  ];

  // Persisted custom order per section (drag-to-reorder)
  const [order, setOrder] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('sb_order') || '{}');
      return typeof saved === 'object' && saved ? saved : {};
    } catch (e) { return {}; }
  });
  useEffect(() => {
    try { localStorage.setItem('sb_order', JSON.stringify(order)); } catch (e) {}
  }, [order]);

  // Apply persisted order to a section, preserving items the user hasn't reordered
  const orderedItems = (sec) => {
    const savedIds = order[sec.label];
    const all = sec.items;
    if (!savedIds || !Array.isArray(savedIds)) return all;
    const known = new Set(all.map(i => i.id));
    const inSaved = savedIds.filter(id => known.has(id));
    const seen = new Set(inSaved);
    const tail = all.filter(i => !seen.has(i.id));
    return [...inSaved.map(id => all.find(i => i.id === id)), ...tail];
  };

  // Drag state
  const [dragId, setDragId] = useState(null);
  const [overId, setOverId] = useState(null);
  const [dragSide, setDragSide] = useState(null); // 'before' | 'after'

  const moveItem = (secLabel, fromId, toId, side) => {
    const sec = sectionsDef.find(s => s.label === secLabel);
    if (!sec) return;
    const list = orderedItems(sec).map(i => i.id);
    const fromIdx = list.indexOf(fromId);
    if (fromIdx < 0) return;
    list.splice(fromIdx, 1);
    const toIdx = list.indexOf(toId);
    const insertAt = toIdx + (side === 'after' ? 1 : 0);
    list.splice(insertAt, 0, fromId);
    setOrder(o => ({ ...o, [secLabel]: list }));
  };

  const resetOrder = (label) => setOrder(o => {
    const n = { ...o };
    delete n[label];
    return n;
  });

  const userRank = TIER_RANK[role] ?? 4;
  const isCustomized = (label) => !!order[label] && order[label].length > 0;

  return (
    <aside className="sb">
      <button className="sb-collapse" onClick={onToggleCollapse} title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
        <I n="chevR" s={12}/>
      </button>
      <div className="sb-brand">
        <img src="assets/relopass-mark.png" alt="" />
        <div className="sb-brand-name">ReloPass <span className="sub">/ Platform</span></div>
      </div>

      <div className="sb-org" title="Workspace">
        <div className="sb-org-avatar">AE</div>
        <div className="sb-org-name">Aurora Energy</div>
        <I n="chevUD" s={12} className="chev"/>
      </div>

      <div className="sb-search">
        <I n="search" s={13}/>
        <input placeholder="Search cases, vendors, requirements…" />
        <span className="kbd">⌘K</span>
      </div>

      {sectionsDef.map(sec => {
        const secLocked = TIER_RANK[sec.tier] > userRank;
        if (secLocked) return null;
        const items = orderedItems(sec);
        return (
          <React.Fragment key={sec.label}>
            <div className="sb-section">
              <span style={{ flex: 1 }}>{sec.label}</span>
              {isCustomized(sec.label) && (
                <span
                  onClick={() => resetOrder(sec.label)}
                  title="Reset to default order"
                  style={{ cursor: 'pointer', fontSize: 9, fontWeight: 600, color: 'var(--text-3)', padding: '1px 6px', borderRadius: 4 }}
                  onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--accent)'; e.currentTarget.style.background = 'var(--accent-soft)'; }}
                  onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-3)'; e.currentTarget.style.background = 'transparent'; }}
                >↺</span>
              )}
            </div>
            <div className="sb-nav">
              {items.map(item => {
                const locked = TIER_RANK[item.tier] > userRank;
                const isDragging = dragId === item.id;
                const isOver = overId === item.id && dragId !== item.id;
                return (
                  <div key={item.id}
                    className={`sb-item${route === item.id ? ' active' : ''}${locked ? ' locked' : ''}${isDragging ? ' sb-dragging' : ''}${isOver ? ` sb-drop-${dragSide}` : ''}`}
                    draggable={!locked && !collapsed}
                    onClick={() => !locked && setRoute(item.id)}
                    onDragStart={(e) => {
                      if (locked) return;
                      setDragId(item.id);
                      try { e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', item.id); } catch (err) {}
                    }}
                    onDragOver={(e) => {
                      if (!dragId || dragId === item.id) return;
                      // only allow dropping within same section
                      const sameSection = sec.items.some(i => i.id === dragId);
                      if (!sameSection) return;
                      e.preventDefault();
                      const rect = e.currentTarget.getBoundingClientRect();
                      const side = (e.clientY - rect.top) < rect.height / 2 ? 'before' : 'after';
                      setOverId(item.id);
                      setDragSide(side);
                    }}
                    onDrop={(e) => {
                      e.preventDefault();
                      if (!dragId || dragId === item.id) {
                        setDragId(null); setOverId(null); setDragSide(null); return;
                      }
                      moveItem(sec.label, dragId, item.id, dragSide);
                      setDragId(null); setOverId(null); setDragSide(null);
                    }}
                    onDragEnd={() => { setDragId(null); setOverId(null); setDragSide(null); }}
                    title={collapsed ? item.name : (locked ? `Requires ${TIER_LABEL[item.tier]} plan` : 'Drag to reorder')}>
                    <I n={item.ico} s={15} className="ico"/>
                    <span>{item.name}</span>
                    {locked
                      ? <span className="badge tier">{TIER_LABEL[item.tier]}</span>
                      : item.badge && <span className="badge">{item.badge}</span>
                    }
                    {collapsed && <span className="sb-item-tip">{item.name}{locked ? ` · ${TIER_LABEL[item.tier]}` : ''}</span>}
                  </div>
                );
              })}
            </div>
          </React.Fragment>
        );
      })}

      <div className="sb-foot">
        <div className="sb-user">
          <div className="sb-user-avatar">{role === 'admin' ? 'RP' : role === 'hr' ? 'HM' : 'MB'}</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="sb-user-name">{role === 'admin' ? 'Romain · ReloPass' : role === 'hr' ? 'Helena Müller' : 'Marc Bouchard'}</div>
            <div className="sb-user-role">{role === 'admin' ? 'Admin · superuser' : role === 'hr' ? 'Global Mobility · HR' : `${TIER_LABEL[role]} plan`}</div>
          </div>
          <I n="chevR" s={13} style={{ color: 'var(--text-3)' }}/>
        </div>
      </div>
    </aside>
  );
}

// ── Top bar ──────────────────────────────────────────
function TopBar({ route, role, onOpenAI, onToggleTheme, dark }) {
  const TITLES = {
    s1: ['Employee', 'Intake'],
    s1n:['Employee', 'Detailed Intake'],
    s1p:['Employee', 'Detailed intake'],
    s1f:['Employee', 'Intake flow'],
    s2: ['AI Engine', 'Requirements discovery'],
    s3: ['Employee', 'Roadmap'],
    s4: ['Employee', 'Dossier & forms'],
    s5: ['HR Operations', 'Policy & benefits'],
    s5b:['HR Operations', 'Policy Builder'],
    s5c:['HR Operations', 'Policy vs. Reality'],
    s6: ['Employee', 'Service providers'],
    s7: ['HR Operations', 'Mobility control'],
    s7e:['HR Operations', 'Policy exceptions'],
    s7p:['HR Operations', 'Company profile'],
    s8: ['Employee', 'Documents'],
    s10:['Employee', 'Inbox'],
    s9: ['Admin', 'Overview'],
    s9a:['Admin', 'Review queue'],
    s9b:['Admin', 'Ops analytics'],
    s9c:['Admin', 'Workflow analytics'],
    s9d:['Admin', 'Resources CMS'],
    s9e:['Admin', 'Prospects'],
    s9f:['Admin', 'Integrations'],
    s9g:['Admin', 'Companies'],
  };
  const [section, page] = TITLES[route] || ['', ''];
  const isAdminRoute = typeof route === 'string' && route.startsWith('s9');
  return (
    <div className="topbar">
      <div className="crumbs">
        {isAdminRoute ? (
          <>
            <span className="crumb">
              <I n="shield" s={11} style={{ verticalAlign: -1, marginRight: 5, color: 'var(--warning)' }}/>
              ReloPass admin
            </span>
            <span className="sep">/</span>
            <span className="crumb current">{page}</span>
          </>
        ) : (
          <>
            <span className="crumb">Aurora Energy</span>
            <span className="sep">/</span>
            <span className="crumb">{section}</span>
            <span className="sep">/</span>
            <span className="crumb current">{page}</span>
          </>
        )}
      </div>

      {(route === 's2' || route === 's3') && (
        <span className="topbar-status">
          <span className="dot"></span>
          {route === 's2' ? 'AI engine · 6 sources live' : 'Case on track'}
        </span>
      )}

      <div className="topbar-spacer"></div>

      <button className="topbar-btn" onClick={onToggleTheme} title="Theme">
        <I n={dark ? 'sun' : 'moon'} s={14}/>
      </button>
      <button className="topbar-btn" title="Notifications">
        <I n="bell" s={14}/>
      </button>
      <button className="topbar-btn ai" onClick={onOpenAI}>
        <I n="sparkles" s={13}/>
        Ask ReloPass AI
        <span className="kbd" style={{ background: 'rgba(255,255,255,0.2)', borderColor: 'transparent', color: 'inherit' }}>⌘J</span>
      </button>
    </div>
  );
}

// ── AI panel (right rail) ────────────────────────────
// Route → human-readable label + on-screen policy data + employee case context.
// These are read from real platform data where available; everything else is
// the realistic fixture used elsewhere in the prototype so the answers stay
// grounded in what the user can actually see on the page.
function getAIContext(route) {
  const ROUTE_LABELS = {
    s0: 'Sign-in / Create account',
    s1: 'Intake — relocation basics',
    s1n: 'Detailed Intake — 6-step wizard',
    s1p: 'Profile & preferences — 7 editable sections',
    s1u: 'Intake (unified accordion)',
    s2: 'Requirements discovery — AI-extracted requirements from official sources',
    s3: 'Roadmap — case timeline, stages, parallel tracks',
    s4: 'Dossier & forms — auto-filled visa forms',
    s5: 'Policy & benefits — employee estimate review with exception requests',
    s5b: 'Policy Builder — HR creating/editing the company\'s tiered policy',
    s5c: 'Policy vs. Reality — compliance heatmap vs employee selections',
    s6: 'Service marketplace — vetted providers',
    s7: 'Mobility control — HR view of all active cases',
    s7e: 'Policy Exceptions inbox — HR review of employee requests',
    s7p: 'Company profile — HR setup',
    s8: 'Documents — employee uploads + OCR',
    s9: 'Admin overview', s9a: 'Admin · Review queue', s9b: 'Admin · Ops analytics',
    s9c: 'Admin · Workflow analytics', s9d: 'Admin · Resources CMS',
    s9e: 'Admin · Prospects', s9f: 'Admin · Integrations', s9g: 'Admin · Companies',
    s10: 'Inbox — case-related messages',
  };

  // Marc Bouchard's case — used across the prototype as the demo employee
  const caseContext = `Employee: Marc Bouchard
Corridor: France → Norway (Stavanger)
Employer: Aurora Energy
Tier: Tier 2 · Director-level package
Cost cap: €68,000 · Committed: €38,580 (57%)
Household: Partner (Camille) + 2 children (Léo 8, Élise 5)
Move date: target Sep 1, 2026
Visa: Skilled Worker Residence Permit (UDI)
Current stage: 4 of 8 stages done; UDI form awaiting employee approval (due Jul 10)
Known risks: International school for kids is excluded under Tier 2 (exception pending)`;

  // Policy data visible on the Policy & benefits / Estimate screens (s5)
  const POLICY_CONTEXT = {
    s5: `Tier 2 benefits (Marc):
- Temporary housing: COVERED €2,400/mo · 90 days (committed €7,200)
- International shipping: COVERED 40ft container (committed €8,500)
- Immigration fees: COVERED full (committed €680)
- Tax equalization: COVERED Year 1 only (committed €12,000)
- Language tuition: PARTIAL €1,500 cap (employee requested €2,800, APPROVED as exception with note from Helena)
- Spouse career coach: PARTIAL 5 sessions cap (employee requested 12, REJECTED — HR suggests using ReloPass free 1:1 coaching credits)
- International school: EXCLUDED — employee requested €18,000/yr, PENDING HR review
- Settling-in concierge: COVERED 20 hours (committed €1,400)
73% of similar director-level school-exception requests at Aurora were approved in the past 24 months.`,
    s3: `Roadmap: 8 stages, 4 done. Next 4 unblocked: UDI form approval (due Jul 10), partner Camille's dependent track (in motion), lease e-sign with Stavanger Relocation Co. (Jul 14 viewings), police registration prep. SLA: 94% of Aurora UDI applications approved within 4 weeks.`,
    s2: `47 requirements compiled from 6 official sources (UDI, Skatteetaten, EU/EEA portal, France Diplomatie, Arbeidstilsynet, Aurora HR policy engine). 12 doc requirements, 10–14 wks estimate, €680 cost. AI confidence: lowest item 84% (human-reviewed if <85%).`,
    s4: `Dossier: 23 of 28 fields auto-filled from passport + contract + civil documents. 5 remaining personal-history fields (previous addresses, last 5 years).`,
    s7: `HR Mobility Control: 12 active cases. 2 at-risk today — Yuki Tanaka (JP→DE, anabin credential recognition 8-day delay) and Lucas Reyes (MX→US, L-1A visa appt). Q3 budget: 74% spent at 67% of quarter (€40k under plan). Norwegian processing capacity: 78% (2 more FR→NO cases would push to risk-of-delay).`,
    s5b: `HR Policy Builder: editing the company's tiered policy. Tiers configurable from templates (Standard / Tech / Banking / Short-term). Each tier has 31 canonical benefits across 6 categories with category-caps or lump-sum budget modes.`,
    s5c: `Policy vs. Reality dashboard: 14 active assignments, 83% policy compliance rate. Most exceeded benefit: Host housing cap (6 of 14 cases). Recommendation: housing cap in Germany (€2,500/mo) covers only 58% of selections — consider raising to €2,900.`,
    s7e: `Policy Exceptions inbox: 3 pending requests for HR review (International school for Marc Bouchard's kids; spouse career coach for Priya Nair; temporary housing extension for Lucas Reyes).`,
  };

  return {
    label: ROUTE_LABELS[route] || route,
    policyContext: POLICY_CONTEXT[route] || `(no policy data visible on this screen)`,
    caseContext,
  };
}

function AIPanel({ route, onClose }) {
  const ctx = getAIContext(route);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([
    { role: 'assistant', text: getOpeningLine(route) },
  ]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);
  const bodyRef = useRef(null);

  // Auto-scroll the conversation to the bottom on new content
  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const QUICK = [
    'What\u2019s blocking my case?',
    'Is anything urgent this week?',
    'Translate this to French',
    'Why was this benefit excluded?',
  ];

  const fillQuick = (text) => {
    setInput(text);
    inputRef.current?.focus();
  };

  const send = async (text) => {
    const userText = (text ?? input).trim();
    if (!userText || loading) return;

    setInput('');
    setMessages((m) => [...m, { role: 'user', text: userText }]);
    setLoading(true);
    setError(null);

    const prompt = `You are ReloPass AI, a relocation policy advisor inside the ReloPass platform. You only answer based on the policy and case data visible on screen.

Rules:
(1) Lead with a direct YES / NO / CONDITIONAL answer on the first line.
(2) Cite the specific policy rule, benefit cap, or visible data point that supports the answer.
(3) Maximum 4 sentences total.
(4) Never speculate — if the visible data does not cover the question, say: "Recommend checking with your advisor."
(5) No apologies, no hedging. Plain, confident, helpful.
(6) Plain text only — no markdown, no headers.

CURRENT SCREEN: ${route} — ${ctx.label}

POLICY DATA VISIBLE ON SCREEN:
${ctx.policyContext}

EMPLOYEE CASE:
${ctx.caseContext}

USER QUESTION: ${userText}

Answer:`;

    try {
      if (!window.claude || typeof window.claude.complete !== 'function') {
        throw new Error('Claude API not available in this environment.');
      }
      const reply = await window.claude.complete(prompt);
      const finalText = (reply || '').toString().trim();

      // Add an empty assistant message we\u2019ll progressively fill (client-side
      // streaming feel for an otherwise non-streaming API).
      setMessages((m) => [...m, { role: 'assistant', text: '', streaming: true }]);
      await streamInto(setMessages, finalText);
    } catch (e) {
      setError(e?.message || 'Could not reach ReloPass AI. Try again in a moment.');
    } finally {
      setLoading(false);
    }
  };

  const onKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <aside className="ai-panel">
      <div className="ai-hd">
        <div className="glyph"><img src="assets/relopass-mark.png" alt=""/></div>
        <div>
          <div className="name">ReloPass AI</div>
          <div className="sub">{loading ? 'Thinking…' : `Live · grounded in this screen`}</div>
        </div>
        <button className="close" onClick={onClose} title="Close"><I n="x" s={14}/></button>
      </div>

      <div className="ai-body" ref={bodyRef}>
        {messages.map((m, i) => (
          <div key={i} className={m.role === 'user' ? 'ai-msg-user' : 'ai-status'}
               style={m.role === 'user' ? {
                 background: 'var(--surface-3)',
                 padding: '10px 12px',
                 borderRadius: 8,
                 marginBottom: 10,
                 fontSize: 12.5,
                 color: 'var(--text)',
                 lineHeight: 1.45,
               } : { marginBottom: 12 }}>
            {m.role === 'assistant' ? (
              <>
                <div className="b" style={{ marginTop: 0, whiteSpace: 'pre-wrap' }}>{m.text}{m.streaming ? '\u258C' : ''}</div>
              </>
            ) : (
              <div>{m.text}</div>
            )}
          </div>
        ))}

        {loading && messages[messages.length - 1]?.role === 'user' && (
          <div className="ai-status" style={{ marginBottom: 12 }}>
            <div className="b" style={{ marginTop: 0, display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              <span className="ai-typing"><i/><i/><i/></span>
              <span style={{ fontSize: 11.5, color: 'var(--text-3)' }}>ReloPass AI is reading the policy on screen…</span>
            </div>
          </div>
        )}

        {error && (
          <div className="ai-status" style={{ marginBottom: 12, borderLeftColor: 'var(--danger)' }}>
            <div className="t" style={{ color: 'var(--danger)' }}>Couldn't get a response</div>
            <div className="b">{error}</div>
          </div>
        )}
      </div>

      <div className="ai-foot">
        <div className="ai-quick">
          {QUICK.map((q) => (
            <button key={q} onClick={() => fillQuick(q)} disabled={loading}>{q}</button>
          ))}
        </div>
        <div className="ai-input">
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKey}
            placeholder={loading ? 'Waiting on a response…' : 'Ask anything about your case…'}
            disabled={loading}
          />
          <button className="send" onClick={() => send()} disabled={loading || !input.trim()}>
            <I n="send" s={11}/>
          </button>
        </div>
      </div>
    </aside>
  );
}

function getOpeningLine(route) {
  const OPEN = {
    s5: 'Ask me anything about your policy. I read the cap, coverage, and exception history visible on this page.',
    s5b: 'I can compare benefit caps to market data, summarise tier differences, and explain what a rule actually means in practice.',
    s5c: 'I can read the heatmap. Ask which benefit is most often exceeded, or which cases are at risk of going over budget.',
    s3: 'I can explain any milestone, what\u2019s blocking, or what to do next on your roadmap.',
    s7: 'I see all 12 active cases. Ask what needs attention today, or about any specific employee.',
    s7e: 'I can summarise an exception request, look up Aurora\u2019s approval history for similar cases, or draft a response.',
  };
  return OPEN[route] || 'Ask me anything about what\u2019s on this screen — your case, your policy, or your next step.';
}

// Client-side "streaming" — progressively reveals the response so the UI feels
// live, even though window.claude.complete() returns the full string at once.
async function streamInto(setMessages, text) {
  const chunks = text.match(/.{1,4}/g) || [];
  for (let i = 0; i < chunks.length; i++) {
    await new Promise((r) => setTimeout(r, 14));
    setMessages((prev) => {
      const next = prev.slice();
      const last = next[next.length - 1];
      if (last && last.role === 'assistant') {
        next[next.length - 1] = { ...last, text: last.text + chunks[i] };
      }
      return next;
    });
  }
  setMessages((prev) => {
    const next = prev.slice();
    const last = next[next.length - 1];
    if (last && last.role === 'assistant') {
      next[next.length - 1] = { ...last, streaming: false };
    }
    return next;
  });
}

// ── Floating AI fab ─────────────────────────────────
function AIFab({ onClick }) {
  return (
    <button className="ai-fab" onClick={onClick}>
      <span className="glyph"><img src="assets/relopass-mark.png" alt="" style={{ width: '100%', height: '100%', objectFit: 'contain' }}/></span>
      Ask ReloPass AI
      <span className="badge">3</span>
    </button>
  );
}

window.Sidebar = Sidebar;
window.TopBar = TopBar;
window.AIPanel = AIPanel;
window.AIFab = AIFab;
})();
