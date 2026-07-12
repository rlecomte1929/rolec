/**
 * TestDriveTab — admin dashboard for the INSEAD Test-Drive campaign (TD-10 / AIQ-1428).
 *
 * Read-only. Reads /api/admin/test-drive/overview and renders a scorecard + funnel +
 * pilot leads + consented testimonials, sliceable by corridor/segment, with a contact
 * CSV export. Mirrors FeedbackTab's load-hook + grid-table conventions.
 */
import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { Mail } from 'lucide-react';
import { Button } from '../antigravity/Button';
import { Badge } from '../antigravity/Badge';
import { getAuthItem } from '../../utils/demo';
import {
  getTestDriveOverview,
  testDriveContactsCsvUrl,
  recordInvitesSent,
  type TestDriveOverview,
  type InviteChannel,
} from '../../api/adminTestDrive';
import { TEST_DRIVE_CORRIDORS } from '../../pages/public/testDriveContent';

const CORRIDOR_IDS = Object.keys(TEST_DRIVE_CORRIDORS);

// TD-12: one-click thank-you from Romain's own mailbox (client-side mailto — no platform send).
// Copy must stay in sync with backend test_drive_emails._thank_you_copy.
const THANK_YOU_SUBJECT = 'Thank you — that really helps';
function thankYouMailto(email: string, name: string | null): string {
  const who = name || 'there';
  const body =
    `Hi ${who},\n\n` +
    'Thanks for test-driving ReloPass — running a full relocation and telling me where ' +
    "it held and where it broke is genuinely useful. I'll act on what you flagged.\n\n" +
    '— Romain';
  return `mailto:${email}?subject=${encodeURIComponent(THANK_YOU_SUBJECT)}&body=${encodeURIComponent(body)}`;
}

function corridorLabel(id: string | null): string {
  if (!id) return '—';
  const c = TEST_DRIVE_CORRIDORS[id];
  return c ? `${c.origin} → ${c.destination}` : id;
}

const FUNNEL_STAGES: { key: keyof TestDriveOverview['funnel']; label: string }[] = [
  { key: 'invited', label: 'Invited' },
  { key: 'clicked', label: 'Clicked' },
  { key: 'provisioned', label: 'Provisioned' },
  // TD-FIX-4 (AIQ-1505): mid-journey stages reveal where testers drop off.
  { key: 'hr_handoff', label: 'HR case created' },
  { key: 'intake_start', label: 'Intake started' },
  { key: 'intake_completed', label: 'Intake completed' },
  { key: 'roadmap_reached', label: 'Roadmap reached' },
  { key: 'vendor_selected', label: 'Vendor selected' },
  { key: 'completed', label: 'Completed' },
  { key: 'surveyed', label: 'Surveyed' },
  { key: 'pilot', label: 'Pilot interest' },
  { key: 'intro', label: 'Intros' },
];

export function TestDriveTab() {
  const [data, setData] = useState<TestDriveOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [corridor, setCorridor] = useState<string>('');
  const [segment, setSegment] = useState<string>('');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const slice = { corridor: corridor || undefined, segment: segment || undefined };
      setData(await getTestDriveOverview(slice));
    } catch {
      setError('Failed to load the Test-Drive dashboard.');
    } finally {
      setLoading(false);
    }
  }, [corridor, segment]);

  useEffect(() => {
    void load();
  }, [load]);

  const exportContacts = async () => {
    const token = getAuthItem('relopass_token') || '';
    try {
      const resp = await fetch(testDriveContactsCsvUrl({ corridor: corridor || undefined, segment: segment || undefined }), {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      if (!resp.ok) {
        setError(`Export failed (HTTP ${resp.status})`);
        return;
      }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `test_drive_contacts_${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError((err as Error)?.message || 'Export failed');
    }
  };

  const funnel = data?.funnel;
  const funnelMax = funnel ? Math.max(1, ...FUNNEL_STAGES.map((st) => funnel[st.key])) : 1;

  return (
    <div className="space-y-6">
      {/* Slice controls + export */}
      <div className="flex flex-wrap items-center gap-4">
        <FilterRow label="Corridor" options={[{ v: '', l: 'All' }, ...CORRIDOR_IDS.map((id) => ({ v: id, l: corridorLabel(id) }))]}
          value={corridor} onChange={setCorridor} />
        <FilterRow label="Segment" options={[{ v: '', l: 'All' }, { v: 'prospect', l: 'Prospect' }, { v: 'internal', l: 'Internal' }]}
          value={segment} onChange={setSegment} />
        <div className="ml-auto">
          <Button unstyled onClick={exportContacts}
            className="rounded-lg border border-[#0b2b43] px-3 py-1.5 text-sm font-semibold text-[#0b2b43] hover:bg-[#0b2b43] hover:text-white transition-colors">
            Export contacts CSV
          </Button>
        </div>
      </div>

      {/* TD-FIX-3 (AIQ-1504): record invites sent — gives the funnel a denominator. */}
      <RecordInvitesForm onRecorded={() => void load()} />

      {loading && <p className="text-sm text-gray-400">Loading…</p>}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3">
          <p className="text-sm text-red-700">{error}</p>
          <Button unstyled onClick={() => void load()} className="mt-2 text-xs font-semibold text-red-700 underline">Retry</Button>
        </div>
      )}

      {data && !loading && !error && (
        <>
          {/* Scorecard */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {([
              { label: 'Provisioned', value: funnel?.provisioned ?? 0, color: 'text-[#0b2b43]' },
              { label: 'Completed', value: funnel?.completed ?? 0, color: 'text-green-600' },
              { label: 'Surveyed', value: funnel?.surveyed ?? 0, color: 'text-[#1f8e8b]' },
              { label: 'Pilot interest', value: funnel?.pilot ?? 0, color: 'text-amber-600' },
            ] as const).map(({ label, value, color }) => (
              <div key={label} className="rounded-lg border border-gray-200 px-4 py-3 bg-white">
                <p className={`text-2xl font-bold ${color}`}>{value}</p>
                <p className="text-xs text-gray-400 mt-0.5">{label}</p>
              </div>
            ))}
          </div>
          <div className="flex flex-wrap gap-6 text-sm text-gray-600">
            <span>Avg experience: <strong className="text-gray-900">{data.scorecard.avg_overall ?? '—'}</strong> / 5</span>
            <span>Problem fit: {(['yes', 'somewhat', 'no'] as const).map((k) => (
              <span key={k} className="ml-2">{k} <strong className="text-gray-900">{data.scorecard.problem_fit?.[k] ?? 0}</strong></span>
            ))}</span>
          </div>

          {/* Funnel */}
          <Section title="Funnel">
            {funnel && funnel.invited > 0 && (
              <p className="mb-2 text-sm text-gray-600">
                Click-through:{' '}
                <strong className="text-gray-900">
                  {Math.round((funnel.clicked / funnel.invited) * 100)}%
                </strong>{' '}
                <span className="text-gray-400">
                  ({funnel.clicked} clicked / {funnel.invited} invited)
                </span>
              </p>
            )}
            <div className="space-y-1.5">
              {FUNNEL_STAGES.map((st) => {
                const v = funnel ? funnel[st.key] : 0;
                return (
                  <div key={st.key} className="flex items-center gap-3">
                    <span className="w-32 shrink-0 text-xs text-gray-500">{st.label}</span>
                    <div className="flex-1 h-5 rounded bg-gray-100 overflow-hidden">
                      <div className="h-full bg-[#1f8e8b]/80" style={{ width: `${Math.round((v / funnelMax) * 100)}%` }} />
                    </div>
                    <span className="w-10 shrink-0 text-right text-sm font-semibold text-gray-900">{v}</span>
                  </div>
                );
              })}
            </div>
          </Section>

          {/* Pilot leads */}
          <Section title={`Pilot leads (${data.pilot_leads.length})`}>
            {data.pilot_leads.length === 0 ? (
              <EmptyRow text="No pilot interest yet." />
            ) : (
              <div className="rounded-lg border border-gray-200 overflow-hidden">
                <div className="grid grid-cols-[1fr_1.4fr_1fr_90px_130px] bg-gray-50 px-3 py-2 text-[11px] uppercase tracking-wide text-gray-400">
                  <span>Name</span><span>Company / role</span><span>Corridor</span><span>Interest</span><span>Thank-you</span>
                </div>
                <div className="divide-y divide-gray-100">
                  {data.pilot_leads.map((r, i) => (
                    <div key={i} className="grid grid-cols-[1fr_1.4fr_1fr_90px_130px] px-3 py-2 text-sm items-center">
                      <span className="text-gray-900">{r.tester_name || '—'}<span className="block text-[11px] text-gray-400">{r.tester_email}</span></span>
                      <span className="text-gray-600">{r.tester_company_role || '—'}{r.tester_sector ? ` · ${r.tester_sector}` : ''}</span>
                      <span className="text-gray-600">{corridorLabel(r.corridor_id)}</span>
                      <Badge variant={r.pilot_interest === 'yes' ? 'success' : 'warning'} size="sm">{r.pilot_interest}</Badge>
                      <ThankYouButton email={r.tester_email} name={r.tester_name} />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Section>

          {/* Survey responses — every surveyed tester with a contact email (TD-12).
              TD-FIX-5 (AIQ-1506): labelled by what it actually lists (survey responses),
              not "Completions" — that conflicted with the 'Completed' funnel counter. */}
          <Section title={`Survey responses (${data.completions.length})`}>
            {data.completions.length === 0 ? (
              <EmptyRow text="No survey responses yet." />
            ) : (
              <div className="rounded-lg border border-gray-200 overflow-hidden">
                <div className="grid grid-cols-[1fr_1.4fr_1fr_70px_130px] bg-gray-50 px-3 py-2 text-[11px] uppercase tracking-wide text-gray-400">
                  <span>Name</span><span>Company / role</span><span>Corridor</span><span>Q1</span><span>Thank-you</span>
                </div>
                <div className="divide-y divide-gray-100">
                  {data.completions.map((r, i) => (
                    <div key={i} className="grid grid-cols-[1fr_1.4fr_1fr_70px_130px] px-3 py-2 text-sm items-center">
                      <span className="text-gray-900">{r.tester_name || '—'}<span className="block text-[11px] text-gray-400">{r.tester_email}</span></span>
                      <span className="text-gray-600">{r.tester_company_role || '—'}{r.tester_sector ? ` · ${r.tester_sector}` : ''}</span>
                      <span className="text-gray-600">{corridorLabel(r.corridor_id)}</span>
                      <span className="text-gray-600">{r.q1_overall ?? '—'}</span>
                      <ThankYouButton email={r.tester_email} name={r.tester_name} />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Section>

          {/* Testimonials (consented only) */}
          <Section title={`Testimonials (${data.testimonials.length})`}>
            {data.testimonials.length === 0 ? (
              <EmptyRow text="No consented testimonials yet." />
            ) : (
              <div className="space-y-2">
                {data.testimonials.map((t, i) => (
                  <div key={i} className="rounded-lg border border-gray-200 bg-white px-4 py-3">
                    <p className="text-sm text-gray-900">“{t.testimonial}”</p>
                    <p className="mt-1 text-xs text-gray-400">{t.tester_name || 'Anonymous'}{t.tester_company_role ? ` · ${t.tester_company_role}` : ''} · {corridorLabel(t.corridor_id)}</p>
                  </div>
                ))}
              </div>
            )}
          </Section>
        </>
      )}
    </div>
  );
}

function FilterRow({ label, options, value, onChange }: {
  label: string;
  options: { v: string; l: string }[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs font-medium text-gray-500">{label}</span>
      <div className="flex flex-wrap gap-1 rounded-lg border border-gray-200 p-0.5 bg-gray-50">
        {options.map((o) => (
          <button key={o.v} type="button" onClick={() => onChange(o.v)}
            className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
              value === o.v ? 'bg-[#0b2b43] text-white' : 'text-gray-600 hover:bg-gray-100'
            }`}>
            {o.l}
          </button>
        ))}
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold text-[#0b2b43]">{title}</h3>
      {children}
    </div>
  );
}

// TD-12: one-click thank-you from Romain's own mailbox. Renders a mailto link when the
// tester left an email, else a dash. Shared by the Pilot leads + Completions tables.
function ThankYouButton({ email, name }: { email: string | null; name: string | null }) {
  if (!email) return <span className="text-[11px] text-gray-300">—</span>;
  return (
    <a
      href={thankYouMailto(email, name)}
      className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 px-2.5 py-1.5 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-50 hover:text-gray-900"
      title="Open your mail client with a thank-you prefilled to this tester"
    >
      <Mail size={13} aria-hidden="true" /> Send thank-you
    </a>
  );
}

function EmptyRow({ text }: { text: string }) {
  return (
    <div className="rounded-lg border border-dashed border-gray-200 px-4 py-6 text-center">
      <p className="text-sm text-gray-500">{text}</p>
    </div>
  );
}

// TD-FIX-3 (AIQ-1504): record invites sent (count + segment + channel) so the funnel has a
// denominator. Persists into funnel_events; the 'Invited' tile + click-through read from it.
const INVITE_SELECT_CLASS =
  'mt-1 rounded-md border border-gray-200 px-2 py-1.5 text-sm text-gray-700 focus:border-[#1f8e8b] focus:outline-none focus:ring-2 focus:ring-[#1f8e8b]/30';

function RecordInvitesForm({ onRecorded }: { onRecorded: () => void }) {
  const [count, setCount] = useState('');
  const [segment, setSegment] = useState<'' | 'internal' | 'prospect'>('');
  const [channel, setChannel] = useState<InviteChannel>('whatsapp');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setMsg(null);
    setErr(null);
    const n = Number.parseInt(count, 10);
    if (!Number.isFinite(n) || n < 1) {
      setErr('Enter how many invites you sent (1 or more).');
      return;
    }
    setBusy(true);
    try {
      const res = await recordInvitesSent({ count: n, channel, ...(segment ? { segment } : {}) });
      setMsg(`Recorded ${res.recorded} invite${res.recorded === 1 ? '' : 's'}.`);
      setCount('');
      onRecorded();
    } catch {
      setErr('Could not record invites. Try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-3 rounded-lg border border-gray-200 bg-white px-4 py-3">
      <div>
        <label htmlFor="td-invite-count" className="block text-xs font-medium text-gray-500">Invites sent</label>
        <input
          id="td-invite-count"
          type="number"
          min={1}
          value={count}
          onChange={(e) => setCount(e.target.value)}
          placeholder="e.g. 25"
          className="mt-1 w-24 rounded-md border border-gray-200 px-2 py-1.5 text-sm text-gray-700 focus:border-[#1f8e8b] focus:outline-none focus:ring-2 focus:ring-[#1f8e8b]/30"
        />
      </div>
      <div>
        <label htmlFor="td-invite-segment" className="block text-xs font-medium text-gray-500">Segment</label>
        <select
          id="td-invite-segment"
          value={segment}
          onChange={(e) => setSegment(e.target.value as '' | 'internal' | 'prospect')}
          className={INVITE_SELECT_CLASS}
        >
          <option value="">Unspecified</option>
          <option value="prospect">Prospect</option>
          <option value="internal">Internal</option>
        </select>
      </div>
      <div>
        <label htmlFor="td-invite-channel" className="block text-xs font-medium text-gray-500">Channel</label>
        <select
          id="td-invite-channel"
          value={channel}
          onChange={(e) => setChannel(e.target.value as InviteChannel)}
          className={INVITE_SELECT_CLASS}
        >
          <option value="whatsapp">WhatsApp</option>
          <option value="email">Email</option>
          <option value="other">Other</option>
        </select>
      </div>
      <Button
        unstyled
        type="submit"
        disabled={busy}
        className="rounded-lg bg-[#0b2b43] px-3 py-1.5 text-sm font-semibold text-white transition-colors hover:bg-[#0b2b43]/90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {busy ? 'Recording…' : 'Record invites sent'}
      </Button>
      {msg && <span className="text-xs font-medium text-green-600">{msg}</span>}
      {err && <span className="text-xs font-medium text-red-600">{err}</span>}
    </form>
  );
}
