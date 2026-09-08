// platform-s10-inbox.jsx — Apple-mail-style coordination inbox
(function() {
const { useState } = React;
const I = window.PlatformIcon;

const FOLDERS = [
  { id: 'inbox',  nm: 'Inbox',         ico: 'msg',     count: 9 },
  { id: 'hr',     nm: 'From HR',       ico: 'shield',  count: 2 },
  { id: 'vendor', nm: 'Vendors',       ico: 'briefcase', count: 4 },
  { id: 'auth',   nm: 'Authorities',   ico: 'flag',    count: 2 },
  { id: 'family', nm: 'Family',        ico: 'users',   count: 1 },
  { id: 'sent',   nm: 'Sent',          ico: 'send',    count: null },
  { id: 'archive',nm: 'Archive',       ico: 'download',count: null },
];

const THREADS = [
  {
    id: 't1', cat: 'hr', unread: true, starred: true,
    fromName: 'Helena Müller', fromInit: 'HM', fromRole: 'HR · Aurora Energy',
    subject: 'Re: Contract amendment for UDI submission',
    preview: 'Approved on my side — I added the salary uplift to clear the NOK 635,500 threshold cleanly. Pls forward to UDI together with…',
    when: '14:42',
    cnt: 4,
    messages: [
      { from: 'You',           fromInit: 'MB', when: 'Yesterday 11:20', body: 'Hi Helena — to lock down the UDI submission I need the signed amendment showing the relocation premium. Can you push it through today?' },
      { from: 'Helena Müller', fromInit: 'HM', when: 'Yesterday 16:48', body: 'Yes — Marcus is countersigning by end of day. I\u2019ll attach it to this thread.' },
      { from: 'Helena Müller', fromInit: 'HM', when: 'Today 09:14',     body: 'Attached. Also added the housing allowance line as a separate addendum so it doesn\u2019t complicate UDI\u2019s salary calc.', attach: ['Amendment_Bouchard_v3.pdf', 'Addendum_Housing.pdf'] },
      { from: 'Helena Müller', fromInit: 'HM', when: '14:42',           body: 'Approved on my side — I added the salary uplift to clear the NOK 635,500 threshold cleanly. Please forward to UDI together with the sponsorship declaration. Let me know if Jens wants me on the call with the consulate.' },
    ],
  },
  {
    id: 't2', cat: 'vendor', unread: true, starred: false,
    fromName: 'Jens Ødegård', fromInit: 'JØ', fromRole: 'Nordic Mobility Law',
    subject: 'UTL-2010 form — final review before submission',
    preview: 'I\u2019ve reviewed the UDI form ReloPass prepared. Two small items I\u2019d adjust before submitting: section 4.b should reference…',
    when: '13:07',
    cnt: 2,
    messages: [
      { from: 'Jens Ødegård', fromInit: 'JØ', when: '11:18', body: 'Hi Marc — I\u2019ve reviewed the UDI form ReloPass prepared. Two small items I\u2019d adjust before submitting: section 4.b should reference your full position title from the contract (not the short version), and the salary breakdown needs the housing allowance separated. I\u2019ll mark the changes inline in the PDF and send back this afternoon.' },
      { from: 'Jens Ødegård', fromInit: 'JØ', when: '13:07', body: 'Annotated PDF attached. Once you accept the changes in ReloPass I\u2019m happy to do the consulate hand-over directly.', attach: ['UTL-2010_review_JO.pdf'] },
    ],
  },
  {
    id: 't3', cat: 'vendor', unread: true, starred: false,
    fromName: 'Ingrid Solberg', fromInit: 'IS', fromRole: 'Stavanger Relocation Co.',
    subject: '3 properties shortlisted — viewings Jul 14',
    preview: 'Booked three viewings for next Monday: Hillevåg (3-bed, sea view), Storhaug (4-bed townhouse close to the French school), and…',
    when: '11:55',
    cnt: 3,
    messages: [
      { from: 'Ingrid Solberg', fromInit: 'IS', when: 'Jul 4 08:30', body: 'Hi Marc — based on Helena\u2019s housing brief and what you marked as priorities (close to the international school, max 25 min commute, family-friendly area), I\u2019ve filtered the long list to 7. I\u2019m booking viewings for the top 3 on Jul 14.' },
      { from: 'You',            fromInit: 'MB', when: 'Jul 4 19:02', body: 'Sounds great. Could you avoid anywhere in Madlamark? Helena flagged the commute as too risky for Camille\u2019s start date.' },
      { from: 'Ingrid Solberg', fromInit: 'IS', when: '11:55',       body: 'Done. Booked three viewings for next Monday: Hillevåg (3-bed, sea view), Storhaug (4-bed townhouse close to the French school), and Eiganes (3-bed near the lakes). I\u2019ll meet you at Hillevåg at 09:30.' },
    ],
  },
  {
    id: 't4', cat: 'auth', unread: false, starred: false,
    fromName: 'UDI — Norwegian Directorate of Immigration', fromInit: 'UDI', fromRole: 'Authority',
    subject: 'Application received — case ref. 2026-0042-7',
    preview: 'We have received your application for a residence permit as a skilled worker. Estimated processing time: 14–28 days. You will…',
    when: 'Jul 3',
    cnt: 1,
    messages: [
      { from: 'UDI', fromInit: 'UDI', when: 'Jul 3 14:22', body: 'We have received your application for a residence permit as a skilled worker.\n\nCase reference: 2026-0042-7\nEstimated processing time: 14–28 days\nYou will be contacted if additional information is required. Once a decision is made, you will receive an email with instructions.\n\nDo not reply to this address.' },
    ],
  },
  {
    id: 't5', cat: 'auth', unread: false, starred: false,
    fromName: 'Préfecture du Rhône', fromInit: 'PR', fromRole: 'Authority · France',
    subject: 'Apostille — Léa & Hugo birth certificates · ready Jul 11',
    preview: 'Your apostille request for the two minor birth certificates is being processed. Pickup window: Jul 11 between 09:00 and 12:00…',
    when: 'Jul 2',
    cnt: 1,
    messages: [
      { from: 'Préfecture du Rhône', fromInit: 'PR', when: 'Jul 2 17:04', body: 'Madame, Monsieur,\n\nYour apostille request for the two minor birth certificates is being processed.\n\nPickup window: Jul 11 between 09:00 and 12:00, counter 4.\n\nPresent your ID and the original receipt.' },
    ],
  },
  {
    id: 't6', cat: 'vendor', unread: false, starred: true,
    fromName: 'Elsa Berg', fromInit: 'EB', fromRole: 'Skole Match',
    subject: 'School consultation — confirmed Jul 16',
    preview: 'Looking forward to our call. I\u2019ll cover three options for both Léa and Hugo: French international school (Stavanger), British…',
    when: 'Jul 1',
    cnt: 2,
    messages: [
      { from: 'Elsa Berg', fromInit: 'EB', when: 'Jun 28', body: 'Hi Marc — Helena flagged your case. Let\u2019s book a 45-min consultation. I have slots Jul 16 between 13:00 and 16:00.' },
      { from: 'Elsa Berg', fromInit: 'EB', when: 'Jul 1',  body: 'Confirmed for Jul 16 14:00. I\u2019ll cover three options for both Léa and Hugo: French international school (Stavanger), British school, and the bilingual Norwegian-French stream. Bring their last school reports if you have them.' },
    ],
  },
  {
    id: 't7', cat: 'hr', unread: false, starred: false,
    fromName: 'Aurora HR Operations', fromInit: 'AE', fromRole: 'HR · Aurora Energy',
    subject: 'Sponsorship declaration sent to UDI · confirmation',
    preview: 'The sponsorship declaration was sent to UDI this morning. Reference 2026-0042-7-SP. No action required from you — this is for…',
    when: 'Jun 24',
    cnt: 1,
    messages: [
      { from: 'Aurora HR Operations', fromInit: 'AE', when: 'Jun 24 10:15', body: 'The sponsorship declaration was sent to UDI this morning. Reference 2026-0042-7-SP. No action required from you — this is for your records.' },
    ],
  },
  {
    id: 't8', cat: 'family', unread: false, starred: false,
    fromName: 'Camille Lefèvre', fromInit: 'CL', fromRole: 'Partner',
    subject: 'Doctor\u2019s note for the kids\u2019 TB tests',
    preview: 'Dr Renault confirmed she can run the TB tests next Thursday at 14:00 for both kids. Should I just book it or do we need to clear…',
    when: 'Jun 22',
    cnt: 1,
    messages: [
      { from: 'Camille Lefèvre', fromInit: 'CL', when: 'Jun 22 19:33', body: 'Dr Renault confirmed she can run the TB tests next Thursday at 14:00 for both kids. Should I just book it or do we need to clear it with ReloPass first?' },
    ],
  },
  {
    id: 't9', cat: 'vendor', unread: false, starred: false,
    fromName: 'FjordTax Advisory', fromInit: 'FT', fromRole: 'Tax advisor',
    subject: 'Initial tax briefing — pre-arrival',
    preview: 'I\u2019ve drafted a one-pager covering Norwegian residency rules, the 183-day test, and tax equalization mechanics specific to…',
    when: 'Jun 20',
    cnt: 1,
    messages: [
      { from: 'FjordTax Advisory', fromInit: 'FT', when: 'Jun 20 11:42', body: 'I\u2019ve drafted a one-pager covering Norwegian residency rules, the 183-day test, and tax equalization mechanics specific to your case. Happy to walk through it once your D-number is issued.' },
    ],
  },
];

function InboxScreen() {
  const [folder, setFolder] = useState('inbox');
  const [selectedId, setSelectedId] = useState(THREADS[0].id);
  const [reply, setReply] = useState('');

  const filtered = folder === 'inbox' ? THREADS
    : folder === 'sent' || folder === 'archive' ? []
    : THREADS.filter(t => t.cat === folder);

  const selected = THREADS.find(t => t.id === selectedId);

  return (
    <div className="inbox">
      {/* Folders */}
      <div className="inbox-folders">
        <div className="inbox-folders-hd">Mailboxes</div>
        {FOLDERS.map(f => (
          <div key={f.id}
            className={`inbox-folder${folder === f.id ? ' active' : ''}`}
            onClick={() => setFolder(f.id)}>
            <I n={f.ico} s={14} className="ico"/>
            <span>{f.nm}</span>
            {f.count != null && <span className="cnt">{f.count}</span>}
          </div>
        ))}

        <div className="inbox-folders-hd" style={{ marginTop: 18 }}>Stakeholders</div>
        <StakeholderRow init="HM" nm="Helena Müller" role="HR · Aurora"/>
        <StakeholderRow init="JØ" nm="Jens Ødegård"  role="Nordic Mobility"/>
        <StakeholderRow init="IS" nm="Ingrid Solberg" role="Stavanger Reloc."/>
        <StakeholderRow init="EB" nm="Elsa Berg"     role="Skole Match"/>
        <StakeholderRow init="FT" nm="FjordTax"      role="Tax advisor"/>
      </div>

      {/* Message list */}
      <div className="inbox-list">
        <div className="inbox-list-hd">
          <div className="t">{FOLDERS.find(f => f.id === folder)?.nm}</div>
          <div className="s">{filtered.length} {filtered.length === 1 ? 'thread' : 'threads'}</div>
          <div className="spacer"></div>
          <button className="btn sm"><I n="edit" s={12}/> New</button>
        </div>
        <div className="inbox-list-body">
          {filtered.length === 0 && (
            <div style={{ padding: 28, textAlign: 'center', color: 'var(--text-3)', fontSize: 13 }}>
              <I n="msg" s={20} style={{ display: 'block', margin: '0 auto 8px' }}/>
              No messages here yet.
            </div>
          )}
          {filtered.map(t => (
            <div key={t.id}
              className={`inbox-row${selectedId === t.id ? ' active' : ''}${t.unread ? ' unread' : ''}`}
              onClick={() => setSelectedId(t.id)}>
              <div className="unread-dot"></div>
              <div className="row-body">
                <div className="row-1">
                  <span className="from">{t.fromName}</span>
                  <span className="when">{t.when}</span>
                </div>
                <div className="row-2">
                  <span className="subj">{t.subject}</span>
                  {t.cnt > 1 && <span className="thread-cnt">{t.cnt}</span>}
                </div>
                <div className="row-3">{t.preview}</div>
              </div>
              {t.starred && <I n="starF" s={11} style={{ color: 'var(--warning)' }}/>}
            </div>
          ))}
        </div>
      </div>

      {/* Detail */}
      <div className="inbox-detail">
        {!selected ? (
          <div style={{ flex: 1, display: 'grid', placeItems: 'center', color: 'var(--text-3)', fontSize: 13 }}>
            Select a message
          </div>
        ) : (
          <>
            <div className="inbox-detail-hd">
              <div>
                <h2 className="subj">{selected.subject}</h2>
                <div className="meta">
                  <CategoryTag cat={selected.cat}/>
                  <span>{selected.cnt} {selected.cnt === 1 ? 'message' : 'messages'}</span>
                  <span>·</span>
                  <span>Case MB-2026-0042</span>
                </div>
              </div>
              <div className="spacer"></div>
              <button className="btn sm"><I n="star" s={12}/></button>
              <button className="btn sm"><I n="download" s={12}/> Archive</button>
              <button className="btn sm primary"><I n="msg" s={12}/> Reply</button>
            </div>

            <div className="inbox-thread">
              {selected.messages.map((m, i) => (
                <div key={i} className={`msg${m.from === 'You' ? ' me' : ''}`}>
                  <div className="msg-hd">
                    <div className="avatar" style={{ width: 30, height: 30, fontSize: 11 }}>{m.fromInit}</div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className="from">{m.from}</div>
                      <div className="to">{m.from === 'You' ? `to ${selected.fromName}` : 'to You'}</div>
                    </div>
                    <div className="when">{m.when}</div>
                  </div>
                  <div className="msg-body">{m.body}</div>
                  {m.attach && (
                    <div className="msg-attach">
                      {m.attach.map((a, j) => (
                        <div key={j} className="attach">
                          <div className="doc-ico" style={{ width: 28, height: 28 }}><span className="ext">PDF</span></div>
                          <span>{a}</span>
                          <I n="download" s={12} style={{ marginLeft: 'auto', color: 'var(--text-3)' }}/>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>

            <div className="inbox-reply">
              <div className="reply-hd">
                <span style={{ color: 'var(--text-3)' }}>Reply to <strong style={{ color: 'var(--text)' }}>{selected.fromName}</strong></span>
                <div className="spacer"></div>
                <button className="btn sm"><I n="sparkles" s={11}/> Draft with AI</button>
              </div>
              <textarea placeholder="Write a reply…"
                value={reply}
                onChange={(e) => setReply(e.target.value)}/>
              <div className="reply-foot">
                <button className="btn sm"><I n="upload" s={11}/> Attach</button>
                <span className="spacer"></span>
                <button className="btn sm">Save draft</button>
                <button className="btn sm primary"><I n="send" s={11}/> Send</button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function CategoryTag({ cat }) {
  const M = {
    hr:     { lbl: 'HR',         tone: 'accent' },
    vendor: { lbl: 'Vendor',     tone: 'teal' },
    auth:   { lbl: 'Authority',  tone: 'warning' },
    family: { lbl: 'Family',     tone: 'success' },
    sent:   { lbl: 'Sent',       tone: 'ghost' },
  };
  const m = M[cat] || M.sent;
  return <span className={`pill ${m.tone}`}>{m.lbl}</span>;
}

function StakeholderRow({ init, nm, role }) {
  return (
    <div className="inbox-stakeholder">
      <div className="avatar" style={{ width: 22, height: 22, fontSize: 9 }}>{init}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="nm">{nm}</div>
        <div className="role">{role}</div>
      </div>
    </div>
  );
}

window.InboxScreen = InboxScreen;
})();
