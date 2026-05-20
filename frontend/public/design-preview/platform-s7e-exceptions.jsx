// platform-s7e-exceptions.jsx — HR Policy Exceptions inbox + detail view
(function() {
const { useState, useMemo, useEffect } = React;
const I = window.PlatformIcon;

// ── Mock data ──────────────────────────────────────────────────────
// Each request: who, what benefit, the policy state vs requested, justification,
// status, timestamps, audit trail.
const EXC_REQUESTS = [
  {
    id: 'exc-1041',
    type: 'new_category',
    type_lbl: 'Add benefit',
    benefit: 'International school',
    employee: { name: 'Marc Bouchard', init: 'MB', role: 'Senior Eng · FR → NO', case: 'c-marc-no' },
    current:   { v: 'Excluded',         s: 'Not in Tier 2 package' },
    requested: { v: '€18,000 / yr',     s: 'Up to 1 academic year for 2 kids' },
    justification: 'Both kids are mid-school year (Grade 4 and Grade 7). Our move lands in late August — they\'ll need to start the Norwegian academic year at an international school to avoid losing a full year of progress. Lycée Français de Stavanger is the only fit; we\'ve already secured spots conditional on funding.',
    submitted_at: '2026-05-12T09:23:00Z',
    submitted_ago: '2h',
    status: 'pending',
    hr_note: null,
    decided_at: null, decided_by: null, decided_by_init: null,
    unread: true,
    ai_insight: '73% of director-level requests like this were approved as exceptions at Aurora in the past 24 months.',
    audit: [
      { kind: 'submit', who: 'Marc Bouchard',  what: 'Submitted exception request for International school.', when: '2h ago · 09:23 CET' },
      { kind: 'ai',     who: 'ReloPass AI',    what: 'Classified · "Tier 2 escalation · school benefit". Precedent: 73% approved.', when: '2h ago · 09:23 CET' },
    ],
  },
  {
    id: 'exc-1040',
    type: 'cap_override',
    type_lbl: 'Cap override',
    benefit: 'Spouse career coach',
    employee: { name: 'Priya Nair', init: 'PN', role: 'PM · IN → DE', case: 'c-priya-de' },
    current:   { v: '5 sessions',    s: 'Tier 1 cap' },
    requested: { v: '12 sessions',   s: 'Extended coaching package' },
    justification: 'My spouse is changing industries (architecture → product). The standard 5 sessions cover CV/networking; she also needs interview prep and a German credential bridge. Quote from Berlin Career Studio for 12-session package is €2,400 (vs €1,000 currently allowed).',
    submitted_at: '2026-05-11T14:02:00Z',
    submitted_ago: '21h',
    status: 'pending',
    hr_note: null,
    decided_at: null, decided_by: null, decided_by_init: null,
    unread: true,
    ai_insight: 'Cap overrides on spouse-career line items have an 58% historical approval rate. Within budget envelope.',
    audit: [
      { kind: 'submit', who: 'Priya Nair', what: 'Submitted cap-override request.', when: '21h ago · 14:02 CET' },
    ],
  },
  {
    id: 'exc-1038',
    type: 'timeline_extension',
    type_lbl: 'Timeline',
    benefit: 'Temporary housing',
    employee: { name: 'Lucas Reyes', init: 'LR', role: 'Director · MX → US', case: 'c-lucas-us' },
    current:   { v: '90 days',    s: 'Standard window' },
    requested: { v: '120 days',   s: 'Extended due to L-1A delay' },
    justification: 'My L-1A premium processing is now at week 9 with no decision. Family relocation paused, lease starts deferred. Need an additional 30 days on the corporate apartment to avoid double-billing.',
    submitted_at: '2026-05-09T11:10:00Z',
    submitted_ago: '3d',
    status: 'approved',
    hr_note: 'Approved — USCIS L-1A delays are well-documented this quarter. We\'ll cover the 30-day extension at the standard rate. Switch landlord to monthly invoicing.',
    decided_at: '2026-05-10T08:30:00Z',
    decided_by: 'Helena Müller',
    decided_by_init: 'HM',
    unread: false,
    audit: [
      { kind: 'submit',  who: 'Lucas Reyes',    what: 'Submitted timeline-extension request.', when: '3d ago · 11:10 PST' },
      { kind: 'ai',      who: 'ReloPass AI',    what: 'Cross-referenced USCIS processing data. L-1A premium queue at p95 = 11 weeks.', when: '3d ago · 11:11 PST' },
      { kind: 'approve', who: 'Helena Müller',  what: 'Approved with note.', quote: 'Approved — USCIS L-1A delays are well-documented this quarter. We\'ll cover the 30-day extension at the standard rate.', when: '2d ago · 08:30 CET' },
    ],
  },
  {
    id: 'exc-1036',
    type: 'additional_coverage',
    type_lbl: 'More coverage',
    benefit: 'International shipping',
    employee: { name: 'Aïcha Idrissi', init: 'AI', role: 'Senior Designer · ES → CA', case: 'c-aicha-ca' },
    current:   { v: '40ft container', s: 'Tier 2 cap' },
    requested: { v: '40ft + air-freight', s: 'Add ~80kg priority air-freight' },
    justification: 'Sea container ETA is 6 weeks. Need work-essential equipment (Cintiq, mechanical keyboard, design library) within 2 weeks of arrival to start. Quote: €1,800 air-freight via Crown Moving.',
    submitted_at: '2026-05-07T16:45:00Z',
    submitted_ago: '5d',
    status: 'rejected',
    hr_note: 'Not approved — policy excludes air-freight add-ons above the standard container. We\'ll cover a 2-week loaner workstation through ReloPass IT instead (same outcome, within band). Loop in IT@ for setup.',
    decided_at: '2026-05-08T10:15:00Z',
    decided_by: 'Helena Müller',
    decided_by_init: 'HM',
    unread: false,
    audit: [
      { kind: 'submit', who: 'Aïcha Idrissi',  what: 'Submitted additional-coverage request.', when: '5d ago · 16:45 CET' },
      { kind: 'reject', who: 'Helena Müller',  what: 'Rejected with proposed alternative.', quote: 'Not approved — policy excludes air-freight add-ons. Will provide 2-week loaner workstation via ReloPass IT instead.', when: '4d ago · 10:15 CET' },
      { kind: 'note',   who: 'Helena Müller',  what: 'Created IT ticket #IT-4421 for loaner workstation.', when: '4d ago · 10:22 CET' },
    ],
  },
  {
    id: 'exc-1034',
    type: 'cap_override',
    type_lbl: 'Cap override',
    benefit: 'Language tuition',
    employee: { name: 'Tomás Weber', init: 'TW', role: 'Data Scientist · BR → NL', case: 'c-tomas-nl' },
    current:   { v: '€1,500',    s: 'Tier 1 cap' },
    requested: { v: '€2,800',    s: 'Intensive Dutch program' },
    justification: 'My employer-side role is client-facing. Standard B1 tutoring (€1,500) won\'t get me to client-readiness. Intensive 12-week B2 program from Direct Dutch is €2,800.',
    submitted_at: '2026-05-04T08:20:00Z',
    submitted_ago: '8d',
    status: 'pending',
    hr_note: null,
    decided_at: null, decided_by: null, decided_by_init: null,
    unread: false,
    ai_insight: 'Client-facing roles in the Netherlands: 81% of cap-extensions for language tuition were approved.',
    audit: [
      { kind: 'submit', who: 'Tomás Weber', what: 'Submitted cap-override request.', when: '8d ago · 08:20 CET' },
    ],
  },
  {
    id: 'exc-1029',
    type: 'new_category',
    type_lbl: 'Add benefit',
    benefit: 'Pet relocation',
    employee: { name: 'Sarah Kim', init: 'SK', role: 'Engineering Manager · US → JP', case: 'c-sarah-jp' },
    current:   { v: 'Excluded',     s: 'Not in any tier' },
    requested: { v: '€1,400',       s: 'Cat transport via WeFly Petcare' },
    justification: 'I have a 12-year-old cat — leaving her behind isn\'t an option. Tokyo flat is pet-friendly. Quote from WeFly Petcare €1,400 (door-to-door with import certs).',
    submitted_at: '2026-04-28T13:00:00Z',
    submitted_ago: '14d',
    status: 'approved',
    hr_note: 'Approved as a goodwill exception. Setting precedent for Sarah\'s case only — broader pet-relocation policy is being scoped for 2027.',
    decided_at: '2026-04-30T09:00:00Z',
    decided_by: 'Helena Müller',
    decided_by_init: 'HM',
    unread: false,
    audit: [
      { kind: 'submit',  who: 'Sarah Kim',      what: 'Submitted new-category request.', when: '14d ago · 13:00 PST' },
      { kind: 'approve', who: 'Helena Müller',  what: 'Approved as one-off goodwill exception.', quote: 'Approved as a goodwill exception. Setting precedent for Sarah\'s case only.', when: '12d ago · 09:00 CET' },
    ],
  },
];

window.PLATFORM_EXCEPTIONS = EXC_REQUESTS;

// ── Helpers ────────────────────────────────────────────────────────
const TYPE_TONES = {
  cap_override: 'accent',
  new_category: 'teal',
  timeline_extension: 'warning',
  additional_coverage: 'accent',
};

function StatusBadge({ status }) {
  const labels = {
    pending:  'Pending review',
    approved: 'Approved',
    rejected: 'Not approved',
  };
  return (
    <span className={`exc-status ${status}`}>
      <span className="dot"/>
      {labels[status]}
    </span>
  );
}

function AuditTimeline({ items }) {
  return (
    <div className="exc-timeline">
      {items.map((it, i) => (
        <div key={i} className={`exc-timeline-item evt-${it.kind}`}>
          <div className="dot"/>
          <div className="who">{it.who}</div>
          <div className="what">{it.what}</div>
          {it.quote && <div className="what quote" style={{ marginTop: 6 }}>“{it.quote}”</div>}
          <div className="when">{it.when}</div>
        </div>
      ))}
    </div>
  );
}

// ── List row ───────────────────────────────────────────────────────
function ExcRow({ r, active, onClick }) {
  return (
    <div className={`exc-row${active ? ' active' : ''}${r.unread ? ' unread' : ''}`} onClick={onClick}>
      <div className="av">{r.employee.init}</div>
      <div className="body">
        <div className="row-1">
          <span className="who">{r.employee.name}</span>
          <span className="type-tag">{r.type_lbl}</span>
        </div>
        <div className="row-2"><strong>{r.benefit}</strong> · <span style={{ color: 'var(--text-3)' }}>{r.requested.v}</span></div>
        <div className="row-3">{r.justification}</div>
      </div>
      <div style={{ textAlign: 'right', display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
        <span className="when">{r.submitted_ago}</span>
        <StatusBadge status={r.status}/>
      </div>
    </div>
  );
}

// ── Detail pane ────────────────────────────────────────────────────
function ExcDetail({ r, onDecide }) {
  // Local state for decision flow (demo only)
  const [intent, setIntent] = useState(null); // 'approve' | 'reject' | null
  const [note, setNote] = useState('');
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => { setIntent(null); setNote(''); setSubmitted(false); }, [r?.id]);

  if (!r) {
    return (
      <div className="exc-detail">
        <div className="exc-empty-detail">
          <div className="glyph"><I n="files" s={22}/></div>
          <div className="t">Select a request</div>
          <div className="s">Choose a request from the inbox to see the full context, justification, and decision history.</div>
        </div>
      </div>
    );
  }

  const decided = r.status === 'approved' || r.status === 'rejected';

  const handleDecide = () => {
    if (!intent) return;
    onDecide?.(r.id, intent, note);
    setSubmitted(true);
  };

  return (
    <div className="exc-detail">
      <div className="exc-detail-hd">
        <div className="av-lg">{r.employee.init}</div>
        <div>
          <div className="who">{r.employee.name}</div>
          <div className="who-sub">{r.employee.role}</div>
        </div>
        <div className="right">
          <StatusBadge status={r.status}/>
          <div className="case" style={{ marginTop: 5 }}>{r.id} · case {r.employee.case}</div>
        </div>
      </div>

      <div className="exc-detail-body">
        <div className="exc-section-hd">Requested change</div>
        <div className="exc-summary">
          <div className="side">
            <div className="k">Current policy</div>
            <div className="v">{r.current.v}</div>
            <div className="s">{r.current.s}</div>
          </div>
          <div className="arrow"><I n="arrowR" s={16}/></div>
          <div className="side req">
            <div className="k">{r.type_lbl}</div>
            <div className="v">{r.requested.v}</div>
            <div className="s">{r.requested.s}</div>
          </div>
        </div>

        <div className="exc-section-hd">Employee justification</div>
        <div className="exc-justification">
          <div className="q">{r.employee.name.split(' ')[0]} wrote:</div>
          <div className="a">{r.justification}</div>
        </div>

        {r.ai_insight && !decided && (
          <div className="exc-insight">
            <div className="ico"><I n="sparkles" s={13}/></div>
            <div>
              <strong>Precedent · </strong>
              {r.ai_insight}
              <div style={{ fontSize: 11.5, color: 'var(--text-3)', marginTop: 4 }}>
                Based on similar Aurora Energy cases · last 24 months
              </div>
            </div>
          </div>
        )}

        {/* Decision panel */}
        {!decided && !submitted && (
          <>
            <div className="exc-section-hd">Your decision</div>
            <div className="exc-actions">
              <div className="top">
                <div className={`exc-decision-btn approve${intent === 'approve' ? ' active' : ''}`}
                     onClick={() => setIntent('approve')}>
                  <div className="ico"><I n="check2" s={16}/></div>
                  <div className="t">Approve</div>
                  <div className="s">Grant the requested change</div>
                </div>
                <div className={`exc-decision-btn reject${intent === 'reject' ? ' active' : ''}`}
                     onClick={() => setIntent('reject')}>
                  <div className="ico"><I n="x" s={16}/></div>
                  <div className="t">Reject</div>
                  <div className="s">Keep current policy as-is</div>
                </div>
              </div>

              {intent && (
                <>
                  <div className="exc-comment-lbl">
                    Comment to {r.employee.name.split(' ')[0]}
                    {intent === 'reject'
                      ? <span className="req">*</span>
                      : <span className="opt">(optional — but recommended)</span>}
                  </div>
                  <textarea
                    placeholder={intent === 'approve'
                      ? 'e.g. Approved. The new cap is effective for your case only — your roadmap will update automatically.'
                      : 'Explain why this can\'t be approved and propose an alternative if possible. This text is sent back to the employee.'}
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                  />
                  <div className="exc-actions-foot">
                    <span style={{ fontSize: 11.5, color: 'var(--text-3)', alignSelf: 'center' }}>
                      <I n="info" s={11} style={{ verticalAlign: -1, marginRight: 4 }}/>
                      {r.employee.name.split(' ')[0]} will be notified via in-app + email.
                    </span>
                    <div className="spc"/>
                    <button onClick={() => { setIntent(null); setNote(''); }}>Cancel</button>
                    <button
                      className={`primary ${intent}`}
                      disabled={intent === 'reject' && !note.trim()}
                      onClick={handleDecide}
                    >
                      {intent === 'approve' ? 'Confirm approval' : 'Confirm rejection'}
                    </button>
                  </div>
                </>
              )}
            </div>
          </>
        )}

        {(decided || submitted) && (
          <>
            <div className="exc-section-hd">Decision</div>
            <div className={`exc-decided ${r.status === 'approved' || (submitted && intent === 'approve') ? 'approved' : 'rejected'}`}>
              <div className="ttl">
                <I n="check2" s={14}/>
                {submitted
                  ? (intent === 'approve' ? 'Request approved' : 'Request rejected')
                  : (r.status === 'approved' ? 'Request approved' : 'Request not approved')}
              </div>
              <div className="meta">
                Decided by {submitted ? 'You (Helena Müller)' : r.decided_by} · {submitted ? 'just now' : (r.decided_at ? r.decided_at.split('T')[0] : '—')}
              </div>
              {(r.hr_note || (submitted && note)) && (
                <div className="note">{r.hr_note || note}</div>
              )}
            </div>
          </>
        )}

        <div className="exc-section-hd" style={{ marginTop: 24 }}>
          Audit trail
          <span className="right">View case</span>
        </div>
        <AuditTimeline items={
          submitted ? [
            ...r.audit,
            {
              kind: intent === 'approve' ? 'approve' : 'reject',
              who: 'Helena Müller',
              what: intent === 'approve' ? 'Approved with note.' : 'Rejected with note.',
              quote: note || undefined,
              when: 'Just now · ' + new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }),
            }
          ] : r.audit
        }/>
      </div>
    </div>
  );
}

// ── Main inbox screen ─────────────────────────────────────────────
function ExceptionsScreen({ tradeoffNotes = false }) {
  const [filter, setFilter] = useState('pending');
  const [selectedId, setSelectedId] = useState(EXC_REQUESTS[0]?.id);
  const [requests, setRequests] = useState(EXC_REQUESTS);

  const counts = useMemo(() => ({
    all:      requests.length,
    pending:  requests.filter(r => r.status === 'pending').length,
    approved: requests.filter(r => r.status === 'approved').length,
    rejected: requests.filter(r => r.status === 'rejected').length,
  }), [requests]);

  const filtered = useMemo(() => {
    if (filter === 'all') return requests;
    return requests.filter(r => r.status === filter);
  }, [filter, requests]);

  const selected = filtered.find(r => r.id === selectedId) || filtered[0] || null;

  const handleDecide = (id, intent, note) => {
    setRequests(rs => rs.map(r => r.id === id ? {
      ...r,
      status: intent === 'approve' ? 'approved' : 'rejected',
      hr_note: note,
      decided_at: new Date().toISOString(),
      decided_by: 'Helena Müller',
      decided_by_init: 'HM',
      unread: false,
    } : r));
  };

  // Mark row read on selection
  useEffect(() => {
    if (!selectedId) return;
    setRequests(rs => rs.map(r => r.id === selectedId ? { ...r, unread: false } : r));
  }, [selectedId]);

  return (
    <div className="page wide">
      {window.ProfileSubNav && <window.ProfileSubNav active="exceptions"/>}
      <div className="page-hd">
        <div className="page-eyebrow">HR · /hr/exceptions</div>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 12 }}>
          <h1 className="page-h">Policy exceptions</h1>
          <div style={{ flex: 1 }}/>
          <span className="pill warning"><I n="alert" s={11}/> {counts.pending} pending</span>
          <button className="btn"><I n="download" s={12}/> Export</button>
        </div>
        <div className="page-sub">
          Employees requested deviations from their assigned policy. Review each request, approve or reject with a note, and the decision flows back to their relocation plan.
        </div>
      </div>

      {tradeoffNotes && (
        <div className="exc-uxnote" style={{ display: 'flex', marginBottom: 14 }}>
          <span className="pin">📌</span>
          <div>
            <strong>UX tradeoff · two-pane inbox vs. modal:</strong> we chose a persistent two-pane layout instead of opening each request in a modal so HR can scan and triage the queue without context-switching. Tradeoff: less screen space for the detail (good for "decide quickly"; harder when justification is long).
          </div>
        </div>
      )}

      <div className="exc-inbox">
        <div className="exc-list">
          <div className="exc-list-hd">
            <div className="ttl">
              Exception requests
              <span className="ct">{counts.pending}</span>
            </div>
            <div className="sub">Across {counts.all} cases · live</div>
            <div className="exc-filters">
              <div className={`exc-filter${filter === 'pending' ? ' active' : ''}`} onClick={() => setFilter('pending')}>
                Pending <span className="ct">{counts.pending}</span>
              </div>
              <div className={`exc-filter${filter === 'approved' ? ' active' : ''}`} onClick={() => setFilter('approved')}>
                Approved <span className="ct">{counts.approved}</span>
              </div>
              <div className={`exc-filter${filter === 'rejected' ? ' active' : ''}`} onClick={() => setFilter('rejected')}>
                Rejected <span className="ct">{counts.rejected}</span>
              </div>
              <div className={`exc-filter${filter === 'all' ? ' active' : ''}`} onClick={() => setFilter('all')}>
                All <span className="ct">{counts.all}</span>
              </div>
            </div>
          </div>
          <div className="exc-list-body">
            {filtered.length === 0 ? (
              <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-3)', fontSize: 12.5 }}>
                <I n="check2" s={24} style={{ color: 'var(--success)', marginBottom: 8 }}/>
                <div>No {filter} requests.</div>
                <div style={{ fontSize: 11.5, marginTop: 4 }}>You're caught up.</div>
              </div>
            ) : (
              filtered.map(r => (
                <ExcRow key={r.id} r={r}
                        active={selected?.id === r.id}
                        onClick={() => setSelectedId(r.id)}/>
              ))
            )}
          </div>
        </div>

        <ExcDetail r={selected} onDecide={handleDecide}/>
      </div>

      {tradeoffNotes && (
        <div style={{ marginTop: 18, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div className="exc-uxnote row">
            <span className="pin">📌</span>
            <div>
              <strong>HR comment field is optional on approve, required on reject.</strong> Rationale: approvals don't need explanation (good news), but rejected employees deserve a reason and ideally a path forward. The required-on-reject pattern prevents "silent rejections".
            </div>
          </div>
          <div className="exc-uxnote row">
            <span className="pin">📌</span>
            <div>
              <strong>AI precedent insight</strong> appears only on pending requests. Once decided, we hide it to avoid second-guessing the human decision. Pattern borrowed from Stripe Radar — assist on the way in, don't critique on the way out.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

window.ExceptionsScreen = ExceptionsScreen;
})();
