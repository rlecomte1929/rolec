import { useState, useMemo, type ReactNode } from 'react';
import {
  Shield, Scale, TrendingUp, AlertTriangle, X, Plus, ChevronRight, ChevronLeft,
  Clock, CheckCircle2, XCircle, FileText, LayoutGrid, ExternalLink,
  AlertCircle, Lock, Gavel, RefreshCw,
} from 'lucide-react';
import { tw } from '../../lib/colors';

// ─── WorkspaceDB globals (auto-injected SDK) ────────────────────────────────

declare global {
  function useWorkspaceDB<T = unknown>(
    table: string,
    options?: {
      shared?: boolean;
      limit?: number;
      offset?: number;
      orderBy?: { column: string; direction: 'asc' | 'desc' };
      filters?: Array<{ column: string; operator: string; value: unknown }>;
    },
  ): { data: T[]; loading: boolean; error: Error | null; total: number; refresh: () => void };

  interface Window {
    __workspaceDb: {
      from: (table: string, opts?: { shared?: boolean }) => {
        insert: (row: Record<string, unknown>) => Promise<void>;
        bulkInsert: (rows: Record<string, unknown>[]) => Promise<void>;
        update: (id: number, row: Record<string, unknown>) => Promise<void>;
        delete: (id: number) => Promise<void>;
      };
    };
  }
}

// ─── Types (mirror WorkspaceDB tables) ───────────────────────────────────────

interface Corridor {
  id: number;
  origin_country: string;
  destination_country: string;
  employee_types_in_scope: string[] | null;
  authoring_status: 'backlog' | 'authoring' | 'authored';
  assurance_status: 'not_started' | 'counsel_engaged' | 'signed_off' | 'sellable';
  demand_score: string | number | null;
  notes: string | null;
}

interface Lawyer {
  id: number;
  name: string;
  firm: string | null;
  jurisdiction: string;
  specialty: string | null;
  engagement_types_covered: string[] | null;
  contact: string | null;
  status: 'prospect' | 'engaged' | 'active' | 'inactive';
}

interface Engagement {
  id: number;
  corridor_id: number;
  lawyer_id: number;
  engagement_type: string;
  fee: string | number | null;
  status: 'proposed' | 'active' | 'completed';
  date_engaged: string | null;
  date_completed: string | null;
}

interface SignOff {
  id: number;
  corridor_id: number;
  lawyer_id: number;
  date_signed: string;
  scope: string | null;
  reverification_due_date: string | null;
  artifact_link: string | null;
}

interface VerificationItem {
  id: number;
  corridor_id: number;
  item: string;
  last_verified_date: string | null;
  next_due_date: string | null;
  source: string | null;
  status: 'current' | 'stale' | 'needs_review';
  notes: string | null;
}

// ─── Pipeline model ──────────────────────────────────────────────────────────

const STAGES = ['Backlog', 'Authoring', 'Authored', 'Counsel Engaged', 'Signed Off', 'Sellable'] as const;
type Stage = (typeof STAGES)[number];

/** Map a pipeline stage back to the two underlying status columns. */
const STAGE_WRITES: Record<Stage, { authoring_status: Corridor['authoring_status']; assurance_status: Corridor['assurance_status'] }> = {
  Backlog: { authoring_status: 'backlog', assurance_status: 'not_started' },
  Authoring: { authoring_status: 'authoring', assurance_status: 'not_started' },
  Authored: { authoring_status: 'authored', assurance_status: 'not_started' },
  'Counsel Engaged': { authoring_status: 'authored', assurance_status: 'counsel_engaged' },
  'Signed Off': { authoring_status: 'authored', assurance_status: 'signed_off' },
  Sellable: { authoring_status: 'authored', assurance_status: 'sellable' },
};

function corridorStage(c: Corridor): Stage {
  if (c.assurance_status === 'sellable') return 'Sellable';
  if (c.assurance_status === 'signed_off') return 'Signed Off';
  if (c.assurance_status === 'counsel_engaged') return 'Counsel Engaged';
  if (c.authoring_status === 'authored') return 'Authored';
  if (c.authoring_status === 'authoring') return 'Authoring';
  return 'Backlog';
}

const ENGAGEMENT_TYPES = ['launch_signoff', 'periodic_reverification', 'per_dossier_escalation'] as const;
const ENGAGEMENT_TYPE_LABELS: Record<string, string> = {
  launch_signoff: 'Launch sign-off',
  periodic_reverification: 'Periodic re-verification',
  per_dossier_escalation: 'Per-dossier escalation',
};

const COUNTRY_CODES: Record<string, string> = {
  france: 'FR', norway: 'NO', germany: 'DE', spain: 'ES', italy: 'IT', sweden: 'SE',
  denmark: 'DK', netherlands: 'NL', poland: 'PL', portugal: 'PT', belgium: 'BE',
  'united kingdom': 'GB', uk: 'GB', ireland: 'IE', switzerland: 'CH', austria: 'AT',
  finland: 'FI', 'united states': 'US', usa: 'US', singapore: 'SG', india: 'IN',
};
function countryCode(name: string): string {
  const n = (name || '').trim();
  if (n.length === 2) return n.toUpperCase();
  return COUNTRY_CODES[n.toLowerCase()] || n.slice(0, 2).toUpperCase();
}

// ─── Date helpers ────────────────────────────────────────────────────────────

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}
function addDaysISO(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}
function daysUntil(dateStr: string | null): number | null {
  if (!dateStr) return null;
  const target = new Date(dateStr);
  if (isNaN(target.getTime())) return null;
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  target.setHours(0, 0, 0, 0);
  return Math.round((target.getTime() - now.getTime()) / 86400000);
}
function fmtDate(dateStr: string | null): string {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

/** THE HARD RULE: a sign-off is valid only if its reverification_due_date is in the future. */
function isValidSignOff(s: SignOff): boolean {
  const d = daysUntil(s.reverification_due_date);
  return d !== null && d > 0;
}

// ─── Small UI atoms ──────────────────────────────────────────────────────────

const STAGE_STYLE: Record<Stage, { dot: string; badge: string }> = {
  Backlog: { dot: 'bg-[var(--space-text-muted)]', badge: 'bg-[var(--space-surface-muted)] text-[var(--space-text-secondary)]' },
  Authoring: { dot: 'bg-[var(--space-brand-primary-500)]', badge: 'bg-[var(--space-brand-primary-50)] text-[var(--space-text-brand)]' },
  Authored: { dot: 'bg-[var(--space-brand-primary)]', badge: 'bg-[var(--space-brand-primary-100)] text-[var(--space-text-brand)]' },
  'Counsel Engaged': { dot: 'bg-amber-400', badge: 'bg-amber-500/15 text-amber-300' },
  'Signed Off': { dot: 'bg-[var(--space-brand-highlight)]', badge: 'bg-[var(--space-brand-highlight-100)] text-[var(--space-text-accent)]' },
  Sellable: { dot: 'bg-[var(--space-semantic-success)]', badge: 'bg-green-500/15 text-green-300' },
};

function CorridorPair({ origin, destination, size = 'sm' }: { origin: string; destination: string; size?: 'sm' | 'lg' }) {
  return (
    <span className={`inline-flex items-center gap-1.5 ${size === 'lg' ? 'text-base' : 'text-xs'} font-bold text-[var(--space-text-primary)]`}>
      <span className={`px-1.5 py-0.5 rounded border border-[var(--space-border-strong)] bg-[var(--space-surface-muted)] ${size === 'lg' ? 'text-sm' : 'text-[10px]'}`}>
        {countryCode(origin)}
      </span>
      <ChevronRight className={size === 'lg' ? 'w-4 h-4' : 'w-3 h-3'} />
      <span className={`px-1.5 py-0.5 rounded border border-[var(--space-border-strong)] bg-[var(--space-surface-muted)] ${size === 'lg' ? 'text-sm' : 'text-[10px]'}`}>
        {countryCode(destination)}
      </span>
    </span>
  );
}

function SectionTitle({ icon: Icon, children }: { icon: typeof Shield; children: ReactNode }) {
  return (
    <h4 className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-[var(--space-text-secondary)] mb-2">
      <Icon className="w-3.5 h-3.5" /> {children}
    </h4>
  );
}

// ─── Main app ────────────────────────────────────────────────────────────────

export default function AssuranceOps() {
  const corridorsQ = useWorkspaceDB<Corridor>('corridors', { shared: true, limit: 100, orderBy: { column: 'id', direction: 'asc' } });
  const lawyersQ = useWorkspaceDB<Lawyer>('lawyers', { shared: true, limit: 100, orderBy: { column: 'id', direction: 'asc' } });
  const engagementsQ = useWorkspaceDB<Engagement>('engagements', { shared: true, limit: 100, orderBy: { column: 'id', direction: 'asc' } });
  const signOffsQ = useWorkspaceDB<SignOff>('sign_offs', { shared: true, limit: 100, orderBy: { column: 'id', direction: 'asc' } });
  const verificationQ = useWorkspaceDB<VerificationItem>('verification_log', { shared: true, limit: 100, orderBy: { column: 'id', direction: 'asc' } });

  const [tab, setTab] = useState<'pipeline' | 'roster' | 'demand'>('pipeline');
  const [detailId, setDetailId] = useState<number | null>(null);
  const [blockedMsg, setBlockedMsg] = useState<{ corridorId: number; message: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const corridors = corridorsQ.data || [];
  const lawyers = lawyersQ.data || [];
  const engagements = engagementsQ.data || [];
  const signOffs = signOffsQ.data || [];
  const verification = verificationQ.data || [];

  const loading = corridorsQ.loading || lawyersQ.loading || engagementsQ.loading || signOffsQ.loading || verificationQ.loading;
  const loadError = corridorsQ.error || lawyersQ.error || engagementsQ.error || signOffsQ.error || verificationQ.error;

  const refreshAll = () => {
    corridorsQ.refresh();
    lawyersQ.refresh();
    engagementsQ.refresh();
    signOffsQ.refresh();
    verificationQ.refresh();
  };

  const lawyerById = useMemo(() => {
    const m: Record<number, Lawyer> = {};
    lawyers.forEach((l) => { m[l.id] = l; });
    return m;
  }, [lawyers]);

  const signOffsByCorridor = useMemo(() => {
    const m: Record<number, SignOff[]> = {};
    signOffs.forEach((s) => { (m[s.corridor_id] = m[s.corridor_id] || []).push(s); });
    return m;
  }, [signOffs]);

  const engagementsByCorridor = useMemo(() => {
    const m: Record<number, Engagement[]> = {};
    engagements.forEach((e) => { (m[e.corridor_id] = m[e.corridor_id] || []).push(e); });
    return m;
  }, [engagements]);

  const verificationByCorridor = useMemo(() => {
    const m: Record<number, VerificationItem[]> = {};
    verification.forEach((v) => { (m[v.corridor_id] = m[v.corridor_id] || []).push(v); });
    return m;
  }, [verification]);

  // Re-verification alerts: sign-offs past or within 30 days of reverification_due_date
  const alerts = useMemo(() => {
    const list: Array<{ corridor: Corridor; signOff: SignOff; days: number }> = [];
    corridors.forEach((c) => {
      (signOffsByCorridor[c.id] || []).forEach((s) => {
        const d = daysUntil(s.reverification_due_date);
        if (d !== null && d <= 30) list.push({ corridor: c, signOff: s, days: d });
      });
    });
    return list.sort((a, b) => a.days - b.days);
  }, [corridors, signOffsByCorridor]);

  const staleItemCount = useMemo(
    () => verification.filter((v) => v.status === 'stale' || (v.next_due_date && (daysUntil(v.next_due_date) ?? 1) <= 0)).length,
    [verification],
  );

  // ── Stage transition with the hard Sellable gate ──
  const handleStageChange = async (corridor: Corridor, target: Stage) => {
    setBlockedMsg(null);
    if (target === 'Sellable') {
      const offs = signOffsByCorridor[corridor.id] || [];
      const valid = offs.filter(isValidSignOff);
      if (valid.length === 0) {
        let why: string;
        if (offs.length === 0) {
          why = 'No sign-off record exists for this corridor. A regulated lawyer must sign off the content before it can be sold.';
        } else if (offs.some((s) => !s.reverification_due_date)) {
          why = 'A sign-off exists but has no re-verification due date. Set a future re-verification date on the sign-off record first.';
        } else {
          why = 'Every sign-off on this corridor is past its re-verification due date. Rules decay — counsel must re-verify before this corridor can be sold.';
        }
        setBlockedMsg({ corridorId: corridor.id, message: `Blocked: cannot mark Sellable. ${why}` });
        return;
      }
    }
    setBusy(true);
    try {
      await window.__workspaceDb.from('corridors', { shared: true }).update(corridor.id, STAGE_WRITES[target]);
      corridorsQ.refresh();
    } finally {
      setBusy(false);
    }
  };

  const detailCorridor = detailId !== null ? corridors.find((c) => c.id === detailId) || null : null;

  return (
    <div className="min-h-full flex flex-col w-full bg-transparent">
      {/* Header */}
      <div className="px-5 py-4 border-b border-[var(--space-border-default)] bg-[var(--space-surface-card)]">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-9 h-9 rounded-xl bg-[var(--space-brand-primary-50)] flex items-center justify-center flex-shrink-0">
              <Shield className={`w-5 h-5 ${tw.icon.primary}`} />
            </div>
            <div className="min-w-0">
              <h2 className="font-semibold text-base text-[var(--space-text-primary)] flex items-center gap-2">
                Assurance Ops
                <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-[var(--space-surface-muted)] text-[var(--space-text-muted)] border border-[var(--space-border-default)]">Internal</span>
              </h2>
              <p className="text-xs text-[var(--space-text-secondary)] truncate">
                System of record: corridor pipeline authored → legally assured → sellable, and the regulated-lawyer network
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1 rounded-lg border border-[var(--space-border-default)] overflow-hidden">
            {([
              { id: 'pipeline', label: 'Pipeline', icon: LayoutGrid },
              { id: 'roster', label: 'Lawyer Roster', icon: Scale },
              { id: 'demand', label: 'Demand Sensor', icon: TrendingUp },
            ] as const).map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`px-3 py-1.5 text-xs font-medium flex items-center gap-1.5 transition-all ${
                  tab === t.id ? tw.button.primary : 'bg-[var(--space-surface-card)] text-[var(--space-text-secondary)] hover:bg-[var(--space-surface-muted)]'
                }`}
              >
                <t.icon className="w-3.5 h-3.5" /> <span className="hidden sm:inline">{t.label}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Re-verification alerts strip — rules decay is the moat cost */}
      {(alerts.length > 0 || staleItemCount > 0) && (
        <div className="px-5 py-2.5 border-b border-red-500/30 bg-red-500/10">
          <div className="flex items-center gap-2 flex-wrap">
            <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
            <p className="text-xs font-semibold text-red-300 uppercase tracking-wider">Re-verification</p>
            {alerts.map((a) => (
              <button
                key={a.signOff.id}
                onClick={() => setDetailId(a.corridor.id)}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium border flex items-center gap-1.5 transition-colors ${
                  a.days <= 0
                    ? 'border-red-500/40 bg-red-500/15 text-red-200 hover:border-red-400'
                    : 'border-amber-500/40 bg-amber-500/15 text-amber-200 hover:border-amber-400'
                }`}
              >
                {countryCode(a.corridor.origin_country)}→{countryCode(a.corridor.destination_country)}
                {a.days <= 0 ? ` sign-off overdue ${Math.abs(a.days)}d` : ` due in ${a.days}d`}
              </button>
            ))}
            {staleItemCount > 0 && (
              <span className="text-xs text-red-200">{staleItemCount} verification item{staleItemCount !== 1 ? 's' : ''} stale or past due</span>
            )}
          </div>
        </div>
      )}

      {/* Body */}
      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="text-center py-16">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--space-brand-primary)] mx-auto" />
            <p className="text-sm text-[var(--space-text-muted)] mt-3">Loading assurance pipeline…</p>
          </div>
        ) : loadError ? (
          <div className="text-center py-16 text-red-400 text-sm">Error: {loadError.message}</div>
        ) : tab === 'pipeline' ? (
          <PipelineBoard
            corridors={corridors}
            signOffsByCorridor={signOffsByCorridor}
            engagementsByCorridor={engagementsByCorridor}
            verificationByCorridor={verificationByCorridor}
            blockedMsg={blockedMsg}
            busy={busy}
            onStageChange={handleStageChange}
            onOpenDetail={setDetailId}
            onCreated={refreshAll}
          />
        ) : tab === 'roster' ? (
          <LawyerRoster lawyers={lawyers} signOffs={signOffs} engagements={engagements} corridors={corridors} onCreated={refreshAll} />
        ) : (
          <DemandSensor
            corridors={corridors}
            signOffsByCorridor={signOffsByCorridor}
            verificationByCorridor={verificationByCorridor}
            onOpenDetail={setDetailId}
          />
        )}
      </div>

      {/* Detail drawer */}
      {detailCorridor && (
        <CorridorDetail
          corridor={detailCorridor}
          stage={corridorStage(detailCorridor)}
          engagements={engagementsByCorridor[detailCorridor.id] || []}
          signOffs={signOffsByCorridor[detailCorridor.id] || []}
          verification={verificationByCorridor[detailCorridor.id] || []}
          lawyers={lawyers}
          lawyerById={lawyerById}
          onClose={() => setDetailId(null)}
          onChanged={refreshAll}
        />
      )}
    </div>
  );
}

// ─── 1. Pipeline board ───────────────────────────────────────────────────────

function PipelineBoard({
  corridors, signOffsByCorridor, engagementsByCorridor, verificationByCorridor,
  blockedMsg, busy, onStageChange, onOpenDetail, onCreated,
}: {
  corridors: Corridor[];
  signOffsByCorridor: Record<number, SignOff[]>;
  engagementsByCorridor: Record<number, Engagement[]>;
  verificationByCorridor: Record<number, VerificationItem[]>;
  blockedMsg: { corridorId: number; message: string } | null;
  busy: boolean;
  onStageChange: (c: Corridor, s: Stage) => void;
  onOpenDetail: (id: number) => void;
  onCreated: () => void;
}) {
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ origin: '', destination: '', demand: '', notes: '' });
  const [saving, setSaving] = useState(false);

  const byStage = useMemo(() => {
    const m: Record<Stage, Corridor[]> = {
      Backlog: [], Authoring: [], Authored: [], 'Counsel Engaged': [], 'Signed Off': [], Sellable: [],
    };
    corridors.forEach((c) => m[corridorStage(c)].push(c));
    return m;
  }, [corridors]);

  const handleAdd = async () => {
    if (!form.origin.trim() || !form.destination.trim()) return;
    setSaving(true);
    try {
      await window.__workspaceDb.from('corridors', { shared: true }).insert({
        origin_country: form.origin.trim(),
        destination_country: form.destination.trim(),
        authoring_status: 'backlog',
        assurance_status: 'not_started',
        demand_score: form.demand.trim() === '' ? null : Number(form.demand),
        notes: form.notes.trim() || null,
        employee_types_in_scope: null,
      });
      setForm({ origin: '', destination: '', demand: '', notes: '' });
      setShowAdd(false);
      onCreated();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-4 sm:p-5">
      <div className="flex items-center justify-between gap-2 mb-3">
        <p className="text-xs text-[var(--space-text-secondary)]">
          {corridors.length} corridor{corridors.length !== 1 ? 's' : ''} · a corridor can only be <span className="font-semibold text-[var(--space-text-primary)]">Sellable</span> with a valid, unexpired lawyer sign-off
        </p>
        <button onClick={() => setShowAdd(!showAdd)} className={`px-3 py-1.5 text-xs rounded-lg flex items-center gap-1 ${tw.button.accent}`}>
          {showAdd ? <X className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />} {showAdd ? 'Cancel' : 'Add corridor'}
        </button>
      </div>

      {showAdd && (
        <div className="mb-4 p-4 rounded-xl border border-[var(--space-border-default)] bg-[var(--space-brand-highlight-50)]">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--space-text-secondary)] mb-3">New corridor (enters Backlog)</p>
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
            <input type="text" placeholder="Origin country (e.g. France)" value={form.origin}
              onChange={(e) => setForm({ ...form, origin: e.target.value })}
              className={tw.input.default + ' text-sm px-3 py-2 rounded-lg border'} />
            <input type="text" placeholder="Destination country" value={form.destination}
              onChange={(e) => setForm({ ...form, destination: e.target.value })}
              className={tw.input.default + ' text-sm px-3 py-2 rounded-lg border'} />
            <input type="number" placeholder="Demand score (optional)" value={form.demand}
              onChange={(e) => setForm({ ...form, demand: e.target.value })}
              className={tw.input.default + ' text-sm px-3 py-2 rounded-lg border'} />
            <input type="text" placeholder="Notes (optional)" value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              className={tw.input.default + ' text-sm px-3 py-2 rounded-lg border'} />
          </div>
          <button onClick={handleAdd} disabled={saving || !form.origin.trim() || !form.destination.trim()}
            className={`mt-3 px-4 py-2 text-sm rounded-lg ${tw.button.primary} disabled:opacity-50`}>
            Add to backlog
          </button>
        </div>
      )}

      <div className="flex gap-3 overflow-x-auto pb-2 min-h-[420px]">
        {STAGES.map((stage, idx) => {
          const cards = byStage[stage];
          const style = STAGE_STYLE[stage];
          return (
            <div key={stage} className="flex flex-col min-w-[230px] w-[230px] flex-shrink-0">
              <div className="px-3 py-2 rounded-t-xl border border-b-0 border-[var(--space-border-default)] bg-[var(--space-surface-muted)]">
                <div className="flex items-center justify-between">
                  <h3 className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-[var(--space-text-secondary)]">
                    <span className={`w-2 h-2 rounded-full ${style.dot}`} />
                    {stage}
                    {stage === 'Sellable' && <Lock className="w-3 h-3 text-[var(--space-text-muted)]" />}
                  </h3>
                  <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold ${style.badge}`}>{cards.length}</span>
                </div>
                <p className="text-[9px] text-[var(--space-text-muted)] mt-0.5">
                  {idx < 3 ? 'Authoring stage' : 'Assurance stage'}
                </p>
              </div>
              <div className="flex-1 p-2 space-y-2 rounded-b-xl border border-[var(--space-border-default)] bg-[var(--space-surface-muted)]/40 min-h-[360px]">
                {cards.length === 0 ? (
                  <p className="text-[11px] text-[var(--space-text-muted)] text-center py-6 italic">Empty</p>
                ) : (
                  cards.map((c) => (
                    <PipelineCard
                      key={c.id}
                      corridor={c}
                      stage={stage}
                      signOffs={signOffsByCorridor[c.id] || []}
                      engagements={engagementsByCorridor[c.id] || []}
                      openQuestions={(verificationByCorridor[c.id] || []).filter((v) => v.status === 'needs_review').length}
                      blocked={blockedMsg && blockedMsg.corridorId === c.id ? blockedMsg.message : null}
                      busy={busy}
                      onStageChange={onStageChange}
                      onOpenDetail={onOpenDetail}
                    />
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function PipelineCard({
  corridor, stage, signOffs, engagements, openQuestions, blocked, busy, onStageChange, onOpenDetail,
}: {
  corridor: Corridor;
  stage: Stage;
  signOffs: SignOff[];
  engagements: Engagement[];
  openQuestions: number;
  blocked: string | null;
  busy: boolean;
  onStageChange: (c: Corridor, s: Stage) => void;
  onOpenDetail: (id: number) => void;
}) {
  const stageIdx = STAGES.indexOf(stage);
  const validOffs = signOffs.filter(isValidSignOff);
  const sellableReady = validOffs.length > 0;
  const activeEngagements = engagements.filter((e) => e.status !== 'completed').length;

  return (
    <div className="p-3 rounded-xl border border-[var(--space-border-default)] bg-[var(--space-surface-card)] shadow-sm">
      <button onClick={() => onOpenDetail(corridor.id)} className="w-full text-left group">
        <div className="flex items-center justify-between gap-2 mb-1.5">
          <CorridorPair origin={corridor.origin_country} destination={corridor.destination_country} />
          {corridor.demand_score !== null && corridor.demand_score !== undefined && (
            <span className="flex items-center gap-0.5 text-[10px] font-bold text-[var(--space-text-accent)]" title="Demand score">
              <TrendingUp className="w-3 h-3" /> {Number(corridor.demand_score)}
            </span>
          )}
        </div>
        <p className="text-[11px] text-[var(--space-text-secondary)] group-hover:text-[var(--space-text-primary)] transition-colors mb-1.5">
          {corridor.origin_country} → {corridor.destination_country}
        </p>
      </button>

      <div className="flex flex-wrap gap-1 mb-2">
        {openQuestions > 0 && (
          <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-amber-500/15 text-amber-300">
            {openQuestions} open counsel question{openQuestions !== 1 ? 's' : ''}
          </span>
        )}
        {activeEngagements > 0 && (
          <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-[var(--space-brand-primary-50)] text-[var(--space-text-brand)]">
            {activeEngagements} engagement{activeEngagements !== 1 ? 's' : ''}
          </span>
        )}
        <span className={`px-1.5 py-0.5 rounded text-[9px] font-semibold flex items-center gap-0.5 ${
          sellableReady ? 'bg-green-500/15 text-green-300' : 'bg-[var(--space-surface-muted)] text-[var(--space-text-muted)]'
        }`}>
          {sellableReady ? <CheckCircle2 className="w-2.5 h-2.5" /> : <XCircle className="w-2.5 h-2.5" />}
          {sellableReady ? 'Valid sign-off' : signOffs.length > 0 ? 'Sign-off expired' : 'No sign-off'}
        </span>
      </div>

      <div className="flex items-center justify-between gap-1">
        <button
          onClick={() => stageIdx > 0 && onStageChange(corridor, STAGES[stageIdx - 1])}
          disabled={busy || stageIdx === 0}
          className="p-1 rounded-md border border-[var(--space-border-default)] text-[var(--space-text-secondary)] hover:bg-[var(--space-surface-muted)] disabled:opacity-30 transition-colors"
          title={stageIdx > 0 ? `Move back to ${STAGES[stageIdx - 1]}` : ''}
        >
          <ChevronLeft className="w-3.5 h-3.5" />
        </button>
        <button onClick={() => onOpenDetail(corridor.id)} className="text-[10px] font-medium text-[var(--space-text-brand)] hover:underline">
          Details
        </button>
        <button
          onClick={() => stageIdx < STAGES.length - 1 && onStageChange(corridor, STAGES[stageIdx + 1])}
          disabled={busy || stageIdx === STAGES.length - 1}
          className={`p-1 rounded-md border transition-colors disabled:opacity-30 ${
            stageIdx === STAGES.length - 2 && !sellableReady
              ? 'border-red-500/40 text-red-400 hover:bg-red-500/10'
              : 'border-[var(--space-border-default)] text-[var(--space-text-secondary)] hover:bg-[var(--space-surface-muted)]'
          }`}
          title={stageIdx < STAGES.length - 1 ? `Advance to ${STAGES[stageIdx + 1]}` : ''}
        >
          <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>

      {blocked && (
        <div className="mt-2 p-2 rounded-lg border border-red-500/40 bg-red-500/10 flex items-start gap-1.5">
          <Lock className="w-3 h-3 text-red-400 flex-shrink-0 mt-0.5" />
          <p className="text-[10px] leading-snug text-red-300">{blocked}</p>
        </div>
      )}
    </div>
  );
}

// ─── 2. Lawyer roster ────────────────────────────────────────────────────────

const LAWYER_STATUS_BADGE: Record<string, string> = {
  prospect: 'bg-[var(--space-surface-muted)] text-[var(--space-text-secondary)]',
  engaged: 'bg-amber-500/15 text-amber-300',
  active: 'bg-green-500/15 text-green-300',
  inactive: 'bg-red-500/15 text-red-300',
};

function LawyerRoster({
  lawyers, signOffs, engagements, corridors, onCreated,
}: {
  lawyers: Lawyer[];
  signOffs: SignOff[];
  engagements: Engagement[];
  corridors: Corridor[];
  onCreated: () => void;
}) {
  const [showAdd, setShowAdd] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    name: '', firm: '', jurisdiction: '', specialty: '', contact: '',
    status: 'prospect' as Lawyer['status'],
    types: [] as string[],
  });

  const corridorLabel = (id: number) => {
    const c = corridors.find((x) => x.id === id);
    return c ? `${countryCode(c.origin_country)}→${countryCode(c.destination_country)}` : `#${id}`;
  };

  const jurisdictions = useMemo(() => {
    const set = new Set(lawyers.map((l) => l.jurisdiction));
    return Array.from(set).sort();
  }, [lawyers]);

  const handleAdd = async () => {
    if (!form.name.trim() || !form.jurisdiction.trim()) return;
    setSaving(true);
    try {
      await window.__workspaceDb.from('lawyers', { shared: true }).insert({
        name: form.name.trim(),
        firm: form.firm.trim() || null,
        jurisdiction: form.jurisdiction.trim(),
        specialty: form.specialty.trim() || null,
        contact: form.contact.trim() || null,
        status: form.status,
        engagement_types_covered: form.types.length > 0 ? form.types : null,
      });
      setForm({ name: '', firm: '', jurisdiction: '', specialty: '', contact: '', status: 'prospect', types: [] });
      setShowAdd(false);
      onCreated();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3 mb-4 flex-wrap">
        <div>
          <h3 className="text-sm font-semibold text-[var(--space-text-primary)] flex items-center gap-2">
            <Scale className="w-4 h-4 text-[var(--space-text-accent)]" /> Regulated lawyer network
          </h3>
          <p className="text-xs text-[var(--space-text-secondary)] mt-0.5 max-w-xl">
            The strategic asset: who can assure what. Every sellable corridor rests on a lawyer in this roster —
            jurisdiction coverage and engagement depth compound as the moat.
          </p>
        </div>
        <button onClick={() => setShowAdd(!showAdd)} className={`px-3 py-1.5 text-xs rounded-lg flex items-center gap-1 ${tw.button.accent}`}>
          {showAdd ? <X className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />} {showAdd ? 'Cancel' : 'Add lawyer'}
        </button>
      </div>

      {/* Coverage summary — only from real data */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        {[
          { label: 'Lawyers on roster', value: lawyers.length },
          { label: 'Jurisdictions covered', value: jurisdictions.length },
          { label: 'Sign-offs provided', value: signOffs.length },
          { label: 'Engagements (all time)', value: engagements.length },
        ].map((m) => (
          <div key={m.label} className="p-3 rounded-xl border border-[var(--space-border-default)] bg-[var(--space-surface-card)]">
            <p className="text-xl font-bold text-[var(--space-text-primary)]">{m.value}</p>
            <p className="text-[10px] text-[var(--space-text-secondary)]">{m.label}</p>
          </div>
        ))}
      </div>

      {showAdd && (
        <div className="mb-4 p-4 rounded-xl border border-[var(--space-border-default)] bg-[var(--space-brand-highlight-50)]">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--space-text-secondary)] mb-3">New lawyer</p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <input type="text" placeholder="Full name" value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className={tw.input.default + ' text-sm px-3 py-2 rounded-lg border'} />
            <input type="text" placeholder="Firm / chambers" value={form.firm}
              onChange={(e) => setForm({ ...form, firm: e.target.value })}
              className={tw.input.default + ' text-sm px-3 py-2 rounded-lg border'} />
            <input type="text" placeholder="Jurisdiction (e.g. France)" value={form.jurisdiction}
              onChange={(e) => setForm({ ...form, jurisdiction: e.target.value })}
              className={tw.input.default + ' text-sm px-3 py-2 rounded-lg border'} />
            <input type="text" placeholder="Specialty (e.g. consultation_juridique)" value={form.specialty}
              onChange={(e) => setForm({ ...form, specialty: e.target.value })}
              className={tw.input.default + ' text-sm px-3 py-2 rounded-lg border'} />
            <input type="text" placeholder="Contact (email / phone)" value={form.contact}
              onChange={(e) => setForm({ ...form, contact: e.target.value })}
              className={tw.input.default + ' text-sm px-3 py-2 rounded-lg border'} />
            <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as Lawyer['status'] })}
              className={tw.input.default + ' text-sm px-3 py-2 rounded-lg border'}>
              {['prospect', 'engaged', 'active', 'inactive'].map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div className="flex flex-wrap gap-2 mt-3">
            {ENGAGEMENT_TYPES.map((t) => (
              <label key={t} className="flex items-center gap-1.5 text-xs text-[var(--space-text-secondary)] cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.types.includes(t)}
                  onChange={(e) => setForm({
                    ...form,
                    types: e.target.checked ? [...form.types, t] : form.types.filter((x) => x !== t),
                  })}
                />
                {ENGAGEMENT_TYPE_LABELS[t]}
              </label>
            ))}
          </div>
          <button onClick={handleAdd} disabled={saving || !form.name.trim() || !form.jurisdiction.trim()}
            className={`mt-3 px-4 py-2 text-sm rounded-lg ${tw.button.primary} disabled:opacity-50`}>
            Add to roster
          </button>
        </div>
      )}

      <div className="rounded-xl border border-[var(--space-border-default)] bg-[var(--space-surface-card)] overflow-hidden overflow-x-auto">
        <table className="w-full min-w-[760px] text-left">
          <thead>
            <tr className="bg-[var(--space-surface-muted)] border-b border-[var(--space-border-default)]">
              {['Lawyer', 'Jurisdiction', 'Specialty', 'Engagement types covered', 'Sign-offs provided', 'Status'].map((h) => (
                <th key={h} className="px-4 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--space-text-muted)]">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {lawyers.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-10 text-center text-sm text-[var(--space-text-muted)] italic">No lawyers on the roster yet.</td></tr>
            ) : (
              lawyers.map((l) => {
                const provided = signOffs.filter((s) => s.lawyer_id === l.id);
                const isPlaceholder = l.name.toUpperCase().includes('PLACEHOLDER');
                return (
                  <tr key={l.id} className="border-b border-[var(--space-border-default)] last:border-b-0 hover:bg-[var(--space-surface-card-hover)] transition-colors align-top">
                    <td className="px-4 py-3">
                      <p className={`text-sm font-medium ${isPlaceholder ? 'text-amber-300 italic' : 'text-[var(--space-text-primary)]'}`}>
                        {isPlaceholder ? 'Placeholder — counsel not yet identified' : l.name}
                      </p>
                      {l.firm && <p className="text-[11px] text-[var(--space-text-muted)]">{l.firm}</p>}
                      {l.contact && <p className="text-[11px] text-[var(--space-text-muted)]">{l.contact}</p>}
                      {isPlaceholder && (
                        <p className="text-[10px] text-amber-400/80 mt-0.5">Slot reserved for France counsel — do not engage until confirmed.</p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-[var(--space-text-primary)]">{l.jurisdiction}</td>
                    <td className="px-4 py-3 text-xs text-[var(--space-text-secondary)]">{l.specialty || '—'}</td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {(l.engagement_types_covered || []).length === 0 ? (
                          <span className="text-xs text-[var(--space-text-muted)]">—</span>
                        ) : (
                          (l.engagement_types_covered || []).map((t) => (
                            <span key={t} className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-[var(--space-brand-primary-50)] text-[var(--space-text-brand)]">
                              {ENGAGEMENT_TYPE_LABELS[t] || t}
                            </span>
                          ))
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {provided.length === 0 ? (
                        <span className="text-xs text-[var(--space-text-muted)]">None yet</span>
                      ) : (
                        <div className="space-y-0.5">
                          {provided.map((s) => (
                            <p key={s.id} className="text-xs text-[var(--space-text-secondary)]">
                              {corridorLabel(s.corridor_id)} · {fmtDate(s.date_signed)}
                              {isValidSignOff(s)
                                ? <span className="text-green-400"> · valid</span>
                                : <span className="text-red-400"> · re-verification lapsed</span>}
                            </p>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${LAWYER_STATUS_BADGE[l.status] || LAWYER_STATUS_BADGE.prospect}`}>
                        {l.status}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── 3. Demand sensor ────────────────────────────────────────────────────────

function DemandSensor({
  corridors, signOffsByCorridor, verificationByCorridor, onOpenDetail,
}: {
  corridors: Corridor[];
  signOffsByCorridor: Record<number, SignOff[]>;
  verificationByCorridor: Record<number, VerificationItem[]>;
  onOpenDetail: (id: number) => void;
}) {
  const ranked = useMemo(() => {
    const workable = corridors.filter((c) => corridorStage(c) !== 'Sellable');
    return workable.sort((a, b) => {
      const da = a.demand_score === null || a.demand_score === undefined ? -Infinity : Number(a.demand_score);
      const db = b.demand_score === null || b.demand_score === undefined ? -Infinity : Number(b.demand_score);
      return db - da;
    });
  }, [corridors]);

  const sellable = corridors.filter((c) => corridorStage(c) === 'Sellable');

  return (
    <div className="p-4 sm:p-5 max-w-3xl">
      <h3 className="text-sm font-semibold text-[var(--space-text-primary)] flex items-center gap-2">
        <TrendingUp className="w-4 h-4 text-[var(--space-text-accent)]" /> Demand-ranked backlog
      </h3>
      <p className="text-xs text-[var(--space-text-secondary)] mt-0.5 mb-4">
        The next corridor to author or assure is decided by demand, not guesswork. Ranked by <code className="text-[10px] bg-[var(--space-surface-muted)] px-1 py-0.5 rounded">demand_score</code> (query volume); unscored corridors sink to the bottom.
      </p>

      {ranked.length === 0 ? (
        <p className="text-sm text-[var(--space-text-muted)] italic py-8 text-center">Every corridor is sellable — nothing in the work queue.</p>
      ) : (
        <div className="space-y-2">
          {ranked.map((c, idx) => {
            const stage = corridorStage(c);
            const style = STAGE_STYLE[stage];
            const openQ = (verificationByCorridor[c.id] || []).filter((v) => v.status === 'needs_review').length;
            const validOffs = (signOffsByCorridor[c.id] || []).filter(isValidSignOff);
            const blockerText =
              stage === 'Signed Off'
                ? validOffs.length > 0 ? 'Ready to mark Sellable' : 'Sign-off recorded but not valid — check re-verification date'
                : stage === 'Counsel Engaged'
                  ? `${openQ} judgment question${openQ !== 1 ? 's' : ''} open with counsel`
                  : stage === 'Authored'
                    ? 'Awaiting counsel engagement'
                    : 'Knowledge build in progress';
            return (
              <button
                key={c.id}
                onClick={() => onOpenDetail(c.id)}
                className="w-full flex items-center gap-3 p-3 rounded-xl border border-[var(--space-border-default)] bg-[var(--space-surface-card)] hover:border-[var(--space-border-strong)] transition-colors text-left"
              >
                <span className="w-7 h-7 rounded-lg bg-[var(--space-surface-muted)] flex items-center justify-center text-xs font-bold text-[var(--space-text-secondary)] flex-shrink-0">
                  {idx + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <CorridorPair origin={c.origin_country} destination={c.destination_country} />
                    <span className={`px-1.5 py-0.5 rounded text-[9px] font-semibold ${style.badge}`}>{stage}</span>
                  </div>
                  <p className="text-[11px] text-[var(--space-text-muted)] mt-0.5 truncate">{blockerText}</p>
                </div>
                <div className="text-right flex-shrink-0">
                  {c.demand_score === null || c.demand_score === undefined ? (
                    <p className="text-xs text-[var(--space-text-muted)] italic">unscored</p>
                  ) : (
                    <p className="text-lg font-bold text-[var(--space-text-accent)]">{Number(c.demand_score)}</p>
                  )}
                  <p className="text-[9px] text-[var(--space-text-muted)] uppercase tracking-wider">demand</p>
                </div>
              </button>
            );
          })}
        </div>
      )}

      <div className="mt-6 p-3 rounded-xl border border-[var(--space-border-default)] bg-[var(--space-surface-muted)]/50">
        <p className="text-[11px] text-[var(--space-text-secondary)]">
          <span className="font-semibold text-[var(--space-text-primary)]">{sellable.length}</span> corridor{sellable.length !== 1 ? 's' : ''} currently sellable ·{' '}
          <span className="font-semibold text-[var(--space-text-primary)]">{ranked.length}</span> in the authoring / assurance work queue.
          Demand scores come from corridor query volume — update a corridor's <code className="text-[10px]">demand_score</code> as demand data lands.
        </p>
      </div>
    </div>
  );
}

// ─── 4. Corridor detail drawer ───────────────────────────────────────────────

const VERIFICATION_BADGE: Record<string, string> = {
  current: 'bg-green-500/15 text-green-300',
  stale: 'bg-red-500/15 text-red-300',
  needs_review: 'bg-amber-500/15 text-amber-300',
};

function CorridorDetail({
  corridor, stage, engagements, signOffs, verification, lawyers, lawyerById, onClose, onChanged,
}: {
  corridor: Corridor;
  stage: Stage;
  engagements: Engagement[];
  signOffs: SignOff[];
  verification: VerificationItem[];
  lawyers: Lawyer[];
  lawyerById: Record<number, Lawyer>;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [showEngageForm, setShowEngageForm] = useState(false);
  const [showSignOffForm, setShowSignOffForm] = useState(false);
  const [saving, setSaving] = useState(false);

  const [engageForm, setEngageForm] = useState({
    lawyer_id: lawyers[0]?.id ?? 0,
    engagement_type: 'launch_signoff',
    fee: '',
    status: 'proposed' as Engagement['status'],
    date_engaged: todayISO(),
  });
  const [signOffForm, setSignOffForm] = useState({
    lawyer_id: lawyers[0]?.id ?? 0,
    date_signed: todayISO(),
    reverification_due_date: addDaysISO(180),
    scope: '',
    artifact_link: '',
  });

  const openQuestions = verification.filter((v) => v.status === 'needs_review');
  const otherItems = verification.filter((v) => v.status !== 'needs_review');
  const validOffs = signOffs.filter(isValidSignOff);
  const style = STAGE_STYLE[stage];

  const lawyerName = (id: number) => {
    const l = lawyerById[id];
    if (!l) return `Lawyer #${id}`;
    return l.name.toUpperCase().includes('PLACEHOLDER') ? `Placeholder (${l.jurisdiction} counsel TBC)` : l.name;
  };

  const handleAddEngagement = async () => {
    if (!engageForm.lawyer_id) return;
    setSaving(true);
    try {
      await window.__workspaceDb.from('engagements', { shared: true }).insert({
        corridor_id: corridor.id,
        lawyer_id: Number(engageForm.lawyer_id),
        engagement_type: engageForm.engagement_type,
        fee: engageForm.fee.trim() === '' ? null : Number(engageForm.fee),
        status: engageForm.status,
        date_engaged: engageForm.date_engaged || null,
        date_completed: null,
      });
      // An engagement moves an authored corridor into Counsel Engaged.
      if (corridor.assurance_status === 'not_started') {
        await window.__workspaceDb.from('corridors', { shared: true }).update(corridor.id, {
          assurance_status: 'counsel_engaged',
        });
      }
      setShowEngageForm(false);
      onChanged();
    } finally {
      setSaving(false);
    }
  };

  const handleRecordSignOff = async () => {
    if (!signOffForm.lawyer_id || !signOffForm.date_signed) return;
    setSaving(true);
    try {
      await window.__workspaceDb.from('sign_offs', { shared: true }).insert({
        corridor_id: corridor.id,
        lawyer_id: Number(signOffForm.lawyer_id),
        date_signed: signOffForm.date_signed,
        reverification_due_date: signOffForm.reverification_due_date || null,
        scope: signOffForm.scope.trim() || null,
        artifact_link: signOffForm.artifact_link.trim() || null,
      });
      // A sign-off advances assurance to signed_off (never straight to sellable — that stays a gated, explicit step).
      if (corridor.assurance_status === 'not_started' || corridor.assurance_status === 'counsel_engaged') {
        await window.__workspaceDb.from('corridors', { shared: true }).update(corridor.id, {
          assurance_status: 'signed_off',
        });
      }
      setShowSignOffForm(false);
      onChanged();
    } finally {
      setSaving(false);
    }
  };

  const handleMarkVerified = async (item: VerificationItem) => {
    setSaving(true);
    try {
      await window.__workspaceDb.from('verification_log', { shared: true }).update(item.id, {
        last_verified_date: todayISO(),
        next_due_date: addDaysISO(180),
        status: 'current',
      });
      onChanged();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/50" onClick={onClose}>
      <div
        className="w-full sm:w-[560px] h-full overflow-y-auto bg-[var(--space-surface-panel)] border-l border-[var(--space-border-default)] shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Drawer header */}
        <div className="sticky top-0 z-10 px-5 py-4 border-b border-[var(--space-border-default)] bg-[var(--space-surface-panel-strong)] flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <CorridorPair origin={corridor.origin_country} destination={corridor.destination_country} size="lg" />
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${style.badge}`}>{stage}</span>
            </div>
            <p className="text-xs text-[var(--space-text-secondary)] mt-1">
              {corridor.origin_country} → {corridor.destination_country}
              {corridor.demand_score !== null && corridor.demand_score !== undefined && ` · demand ${Number(corridor.demand_score)}`}
              {(corridor.employee_types_in_scope || []).length > 0 && ` · scope: ${(corridor.employee_types_in_scope || []).join(', ')}`}
            </p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-[var(--space-surface-muted)] text-[var(--space-text-secondary)] flex-shrink-0">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 space-y-6">
          {/* Sellable gate status */}
          <div className={`p-3 rounded-xl border flex items-start gap-2 ${
            validOffs.length > 0 ? 'border-green-500/40 bg-green-500/10' : 'border-amber-500/40 bg-amber-500/10'
          }`}>
            {validOffs.length > 0
              ? <CheckCircle2 className="w-4 h-4 text-green-400 flex-shrink-0 mt-0.5" />
              : <Lock className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />}
            <p className="text-xs leading-relaxed text-[var(--space-text-primary)]">
              {validOffs.length > 0
                ? `Sellable gate open: ${validOffs.length} valid sign-off${validOffs.length !== 1 ? 's' : ''} with a future re-verification date.`
                : signOffs.length > 0
                  ? 'Sellable gate closed: sign-off exists but its re-verification date is missing or in the past. Counsel must re-verify.'
                  : 'Sellable gate closed: no lawyer sign-off recorded. This corridor cannot be sold until a regulated lawyer signs off its content.'}
            </p>
          </div>

          {/* Open judgment questions for counsel */}
          <div>
            <SectionTitle icon={Gavel}>Residual legal-judgment questions open for counsel ({openQuestions.length})</SectionTitle>
            {openQuestions.length === 0 ? (
              <p className="text-xs text-[var(--space-text-muted)] italic">No open counsel questions.</p>
            ) : (
              <div className="space-y-2">
                {openQuestions.map((q) => (
                  <div key={q.id} className="p-3 rounded-xl border border-amber-500/30 bg-[var(--space-surface-card)]">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-xs font-semibold text-[var(--space-text-primary)] leading-snug">{q.item}</p>
                      <span className={`px-1.5 py-0.5 rounded text-[9px] font-semibold flex-shrink-0 ${VERIFICATION_BADGE[q.status]}`}>
                        {q.status.replace('_', ' ')}
                      </span>
                    </div>
                    {q.notes && <p className="text-[11px] text-[var(--space-text-secondary)] mt-1.5 leading-relaxed whitespace-pre-line">{q.notes}</p>}
                    {q.source && <p className="text-[10px] text-[var(--space-text-muted)] mt-1.5">Source: {q.source}</p>}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Engagements */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <SectionTitle icon={FileText}>Counsel engagements ({engagements.length})</SectionTitle>
              <button onClick={() => setShowEngageForm(!showEngageForm)} className="text-[10px] font-medium text-[var(--space-text-brand)] hover:underline flex items-center gap-0.5">
                <Plus className="w-3 h-3" /> {showEngageForm ? 'Cancel' : 'Add engagement'}
              </button>
            </div>
            {showEngageForm && (
              <div className="mb-3 p-3 rounded-xl border border-[var(--space-border-default)] bg-[var(--space-surface-muted)]/60 space-y-2">
                <select value={engageForm.lawyer_id} onChange={(e) => setEngageForm({ ...engageForm, lawyer_id: Number(e.target.value) })}
                  className={tw.input.default + ' w-full text-xs px-2.5 py-1.5 rounded-lg border'}>
                  {lawyers.map((l) => <option key={l.id} value={l.id}>{lawyerName(l.id)} — {l.jurisdiction}</option>)}
                </select>
                <div className="grid grid-cols-2 gap-2">
                  <select value={engageForm.engagement_type} onChange={(e) => setEngageForm({ ...engageForm, engagement_type: e.target.value })}
                    className={tw.input.default + ' text-xs px-2.5 py-1.5 rounded-lg border'}>
                    {ENGAGEMENT_TYPES.map((t) => <option key={t} value={t}>{ENGAGEMENT_TYPE_LABELS[t]}</option>)}
                  </select>
                  <input type="number" placeholder="Fee EUR (blank = TBD)" value={engageForm.fee}
                    onChange={(e) => setEngageForm({ ...engageForm, fee: e.target.value })}
                    className={tw.input.default + ' text-xs px-2.5 py-1.5 rounded-lg border'} />
                  <select value={engageForm.status} onChange={(e) => setEngageForm({ ...engageForm, status: e.target.value as Engagement['status'] })}
                    className={tw.input.default + ' text-xs px-2.5 py-1.5 rounded-lg border'}>
                    {['proposed', 'active', 'completed'].map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                  <input type="date" value={engageForm.date_engaged}
                    onChange={(e) => setEngageForm({ ...engageForm, date_engaged: e.target.value })}
                    className={tw.input.default + ' text-xs px-2.5 py-1.5 rounded-lg border'} />
                </div>
                <button onClick={handleAddEngagement} disabled={saving || lawyers.length === 0}
                  className={`px-3 py-1.5 text-xs rounded-lg ${tw.button.primary} disabled:opacity-50`}>
                  Save engagement
                </button>
              </div>
            )}
            {engagements.length === 0 ? (
              <p className="text-xs text-[var(--space-text-muted)] italic">
                No formal engagement recorded yet{stage === 'Counsel Engaged' ? ' — counsel call pending; record the engagement once terms are agreed.' : '.'}
              </p>
            ) : (
              <div className="space-y-1.5">
                {engagements.map((e) => (
                  <div key={e.id} className="flex items-center justify-between gap-2 p-2.5 rounded-lg border border-[var(--space-border-default)] bg-[var(--space-surface-card)]">
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-[var(--space-text-primary)] truncate">
                        {ENGAGEMENT_TYPE_LABELS[e.engagement_type] || e.engagement_type} — {lawyerName(e.lawyer_id)}
                      </p>
                      <p className="text-[10px] text-[var(--space-text-muted)]">
                        {e.fee === null || e.fee === undefined ? 'Fee TBD' : `€${Number(e.fee).toLocaleString()}`}
                        {e.date_engaged && ` · engaged ${fmtDate(e.date_engaged)}`}
                        {e.date_completed && ` · completed ${fmtDate(e.date_completed)}`}
                      </p>
                    </div>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold flex-shrink-0 ${
                      e.status === 'active' ? 'bg-green-500/15 text-green-300'
                        : e.status === 'completed' ? 'bg-[var(--space-surface-muted)] text-[var(--space-text-secondary)]'
                          : 'bg-amber-500/15 text-amber-300'
                    }`}>
                      {e.status}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Sign-offs */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <SectionTitle icon={CheckCircle2}>Sign-off records ({signOffs.length})</SectionTitle>
              <button onClick={() => setShowSignOffForm(!showSignOffForm)} className="text-[10px] font-medium text-[var(--space-text-brand)] hover:underline flex items-center gap-0.5">
                <Plus className="w-3 h-3" /> {showSignOffForm ? 'Cancel' : 'Record sign-off'}
              </button>
            </div>
            {showSignOffForm && (
              <div className="mb-3 p-3 rounded-xl border border-[var(--space-border-default)] bg-[var(--space-surface-muted)]/60 space-y-2">
                <select value={signOffForm.lawyer_id} onChange={(e) => setSignOffForm({ ...signOffForm, lawyer_id: Number(e.target.value) })}
                  className={tw.input.default + ' w-full text-xs px-2.5 py-1.5 rounded-lg border'}>
                  {lawyers.map((l) => <option key={l.id} value={l.id}>{lawyerName(l.id)} — {l.jurisdiction}</option>)}
                </select>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-[9px] uppercase tracking-wider text-[var(--space-text-muted)] mb-0.5">Date signed</label>
                    <input type="date" value={signOffForm.date_signed}
                      onChange={(e) => setSignOffForm({ ...signOffForm, date_signed: e.target.value })}
                      className={tw.input.default + ' w-full text-xs px-2.5 py-1.5 rounded-lg border'} />
                  </div>
                  <div>
                    <label className="block text-[9px] uppercase tracking-wider text-[var(--space-text-muted)] mb-0.5">Re-verification due (gates Sellable)</label>
                    <input type="date" value={signOffForm.reverification_due_date}
                      onChange={(e) => setSignOffForm({ ...signOffForm, reverification_due_date: e.target.value })}
                      className={tw.input.default + ' w-full text-xs px-2.5 py-1.5 rounded-lg border'} />
                  </div>
                </div>
                <input type="text" placeholder="Scope (content version, sections, exclusions)" value={signOffForm.scope}
                  onChange={(e) => setSignOffForm({ ...signOffForm, scope: e.target.value })}
                  className={tw.input.default + ' w-full text-xs px-2.5 py-1.5 rounded-lg border'} />
                <input type="text" placeholder="Artifact link (signed opinion / memo URL)" value={signOffForm.artifact_link}
                  onChange={(e) => setSignOffForm({ ...signOffForm, artifact_link: e.target.value })}
                  className={tw.input.default + ' w-full text-xs px-2.5 py-1.5 rounded-lg border'} />
                <button onClick={handleRecordSignOff} disabled={saving || lawyers.length === 0 || !signOffForm.date_signed}
                  className={`px-3 py-1.5 text-xs rounded-lg ${tw.button.primary} disabled:opacity-50`}>
                  Save sign-off
                </button>
              </div>
            )}
            {signOffs.length === 0 ? (
              <p className="text-xs text-[var(--space-text-muted)] italic">No sign-off yet — the corridor cannot reach Sellable without one.</p>
            ) : (
              <div className="space-y-1.5">
                {signOffs.map((s) => {
                  const valid = isValidSignOff(s);
                  const d = daysUntil(s.reverification_due_date);
                  return (
                    <div key={s.id} className={`p-2.5 rounded-lg border bg-[var(--space-surface-card)] ${valid ? 'border-green-500/30' : 'border-red-500/40'}`}>
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-xs font-medium text-[var(--space-text-primary)]">
                          {lawyerName(s.lawyer_id)} · signed {fmtDate(s.date_signed)}
                        </p>
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold flex-shrink-0 ${valid ? 'bg-green-500/15 text-green-300' : 'bg-red-500/15 text-red-300'}`}>
                          {valid ? 'valid' : 'lapsed'}
                        </span>
                      </div>
                      <p className="text-[10px] text-[var(--space-text-muted)] mt-0.5">
                        Re-verification due {fmtDate(s.reverification_due_date)}
                        {d !== null && (d <= 0 ? ` — overdue ${Math.abs(d)}d` : ` — in ${d}d`)}
                      </p>
                      {s.scope && <p className="text-[11px] text-[var(--space-text-secondary)] mt-1">{s.scope}</p>}
                      {s.artifact_link && (
                        <a href={s.artifact_link} target="_blank" rel="noreferrer" className="text-[10px] text-[var(--space-text-brand)] hover:underline flex items-center gap-0.5 mt-1">
                          <ExternalLink className="w-3 h-3" /> Signed artifact
                        </a>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Verification / decay log */}
          <div>
            <SectionTitle icon={RefreshCw}>Verification & decay log ({verification.length} items)</SectionTitle>
            <p className="text-[10px] text-[var(--space-text-muted)] mb-2">
              Rules decay. Each tracked regulatory item must be re-verified on a rolling basis; stale items are the cost of keeping the corridor sellable.
            </p>
            {verification.length === 0 ? (
              <p className="text-xs text-[var(--space-text-muted)] italic">No verification items tracked for this corridor yet.</p>
            ) : (
              <div className="rounded-xl border border-[var(--space-border-default)] overflow-hidden">
                {[...openQuestions, ...otherItems].map((v, i) => {
                  const d = daysUntil(v.next_due_date);
                  return (
                    <div key={v.id} className={`px-3 py-2.5 bg-[var(--space-surface-card)] ${i > 0 ? 'border-t border-[var(--space-border-default)]' : ''}`}>
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-xs font-medium text-[var(--space-text-primary)] leading-snug min-w-0">{v.item}</p>
                        <div className="flex items-center gap-1.5 flex-shrink-0">
                          <span className={`px-1.5 py-0.5 rounded text-[9px] font-semibold ${VERIFICATION_BADGE[v.status] || VERIFICATION_BADGE.needs_review}`}>
                            {v.status.replace('_', ' ')}
                          </span>
                          <button
                            onClick={() => handleMarkVerified(v)}
                            disabled={saving}
                            className="px-1.5 py-0.5 rounded text-[9px] font-semibold border border-[var(--space-border-default)] text-[var(--space-text-secondary)] hover:bg-[var(--space-surface-muted)] disabled:opacity-40 transition-colors"
                            title="Mark verified today; next due in 180 days"
                          >
                            Mark verified
                          </button>
                        </div>
                      </div>
                      <p className="text-[10px] text-[var(--space-text-muted)] mt-0.5 flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        Last verified {fmtDate(v.last_verified_date)} · next due {fmtDate(v.next_due_date)}
                        {d !== null && d <= 0 && <span className="text-red-400 font-semibold">— past due</span>}
                        {d !== null && d > 0 && d <= 30 && <span className="text-amber-400 font-semibold">— due in {d}d</span>}
                      </p>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Notes */}
          {corridor.notes && (
            <div>
              <SectionTitle icon={AlertCircle}>Operational notes</SectionTitle>
              <div className="p-3 rounded-xl border border-[var(--space-border-default)] bg-[var(--space-surface-card)]">
                <p className="text-[11px] text-[var(--space-text-secondary)] leading-relaxed whitespace-pre-line">{corridor.notes}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
