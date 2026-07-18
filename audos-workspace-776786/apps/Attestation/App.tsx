import { useState, useMemo, useEffect } from 'react';
import {
  Stamp, Scale, Shield, Lock, Unlock, ChevronRight, ChevronLeft, X, Plus,
  CheckCircle2, XCircle, AlertTriangle, AlertCircle, FileText, Clock,
  ExternalLink, Copy, Printer, Pencil, Gavel, Eye, Info, LayoutGrid,
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
}

type DbHandle = {
  from: (table: string, opts?: { shared?: boolean }) => {
    insert: (row: Record<string, unknown>) => Promise<unknown>;
    update: (id: number, row: Record<string, unknown>) => Promise<unknown>;
    eq: (column: string, value: unknown) => any;
    orderBy: (column: string, direction: 'asc' | 'desc') => any;
    limit: (n: number) => any;
    get: () => Promise<{ data: any[]; total: number }>;
  };
};
const db = (): DbHandle => (window as any).__workspaceDb;

// ─── Types (mirror WorkspaceDB tables) ───────────────────────────────────────

interface Corridor {
  id: number;
  origin_country: string;
  destination_country: string;
  authoring_status: string;
  assurance_status: 'not_started' | 'counsel_engaged' | 'signed_off' | 'sellable';
  notes: string | null;
}

interface Lawyer {
  id: number;
  name: string;
  firm: string | null;
  jurisdiction: string;
  specialty: string | null;
  status: 'prospect' | 'engaged' | 'active' | 'inactive';
}

interface Claim {
  id: number;
  corridor_id: number;
  dimension: string;
  fixture_row: string | null;
  claim_text: string;
  legal_basis: string | null;
  jurisdiction: string;
  disposition_asserted: 'INFO' | 'ROUTE';
  version: number;
  is_current_version: boolean;
  notes: string | null;
}

interface Attestation {
  id: number;
  claim_id: number;
  lawyer_id: number;
  verdict: 'CONFIRMED' | 'NEEDS_REVISION' | 'CROSSES_THE_LINE' | 'OUT_OF_SCOPE';
  verdict_note: string | null;
  attested_at: string;
  expires_at: string | null;
  superseded_by: number | null;
}

// ─── Attestation status model ────────────────────────────────────────────────

type ClaimStatus = 'UNATTESTED' | 'CONFIRMED' | 'NEEDS_REVISION' | 'CROSSES_THE_LINE' | 'OUT_OF_SCOPE' | 'EXPIRED';

const STATUS_ORDER: ClaimStatus[] = ['UNATTESTED', 'CONFIRMED', 'NEEDS_REVISION', 'CROSSES_THE_LINE', 'OUT_OF_SCOPE', 'EXPIRED'];

const STATUS_STYLE: Record<ClaimStatus, { badge: string; dot: string; label: string }> = {
  UNATTESTED: { badge: 'bg-[var(--space-surface-muted)] text-[var(--space-text-secondary)] border-[var(--space-border-default)]', dot: 'bg-[var(--space-text-muted)]', label: 'Unattested' },
  CONFIRMED: { badge: 'bg-green-500/15 text-green-300 border-green-500/30', dot: 'bg-[var(--space-semantic-success)]', label: 'Confirmed' },
  NEEDS_REVISION: { badge: 'bg-amber-500/15 text-amber-300 border-amber-500/30', dot: 'bg-amber-400', label: 'Needs revision' },
  CROSSES_THE_LINE: { badge: 'bg-red-500/15 text-red-300 border-red-500/30', dot: 'bg-red-500', label: 'Crosses the line' },
  OUT_OF_SCOPE: { badge: 'bg-[var(--space-brand-primary-50)] text-[var(--space-text-brand)] border-[var(--space-border-strong)]', dot: 'bg-[var(--space-brand-primary)]', label: 'Out of scope' },
  EXPIRED: { badge: 'bg-orange-500/15 text-orange-300 border-orange-500/30', dot: 'bg-orange-400', label: 'Expired' },
};

const DIMENSIONS: { id: string; label: string }[] = [
  { id: 'nationality_resolution', label: 'Nationality Resolution' },
  { id: 'applicable_legislation', label: 'Applicable Legislation' },
  { id: 'advice_routing', label: 'Advice Routing' },
  { id: 'tax', label: 'Tax' },
  { id: 'social_security', label: 'Social Security' },
  { id: 'posting', label: 'Posting' },
  { id: 'visa', label: 'Visa' },
  { id: 'permit', label: 'Permit' },
];
const CANONICAL_DIMS = ['nationality_resolution', 'applicable_legislation', 'advice_routing', 'tax'];
const dimLabel = (id: string) => DIMENSIONS.find((d) => d.id === id)?.label || id.replace(/_/g, ' ');

const JURISDICTIONS = ['FR', 'NO', 'EU', 'NORDIC', 'BILATERAL'];

const VERDICTS: { id: Attestation['verdict']; label: string; hint: string; noteRequired: boolean; style: string }[] = [
  { id: 'CONFIRMED', label: 'Confirmed', hint: 'Accurate as stated — disposition and legal basis are correct', noteRequired: false, style: 'border-green-500/40 bg-green-500/10 text-green-300 hover:bg-green-500/20' },
  { id: 'NEEDS_REVISION', label: 'Needs revision', hint: 'Material error or ambiguity — correction note required', noteRequired: true, style: 'border-amber-500/40 bg-amber-500/10 text-amber-300 hover:bg-amber-500/20' },
  { id: 'CROSSES_THE_LINE', label: 'Crosses the line', hint: 'As written this would be regulated advice — must ROUTE; note required', noteRequired: true, style: 'border-red-500/40 bg-red-500/10 text-red-300 hover:bg-red-500/20' },
  { id: 'OUT_OF_SCOPE', label: 'Out of scope', hint: 'Cannot opine — outside jurisdictional or subject-matter competence', noteRequired: false, style: 'border-[var(--space-border-strong)] bg-[var(--space-surface-muted)] text-[var(--space-text-secondary)] hover:bg-[var(--space-surface-card-hover)]' },
];

const EXPIRY_PRESETS: { id: string; label: string; months: number | null }[] = [
  { id: '6m', label: '6 months (fees / thresholds)', months: 6 },
  { id: '12m', label: '12 months (legislation — default)', months: 12 },
  { id: '24m', label: '24 months (stable treaty provisions)', months: 24 },
  { id: 'none', label: 'No auto-expiry (constitutional / treaty only)', months: null },
];

/** The current (non-superseded, latest) attestation on a claim, if any. */
function currentAttestation(claimId: number, attestations: Attestation[]): Attestation | null {
  const active = attestations
    .filter((a) => a.claim_id === claimId && (a.superseded_by === null || a.superseded_by === undefined))
    .sort((a, b) => String(b.attested_at || '').localeCompare(String(a.attested_at || '')) || b.id - a.id);
  return active[0] || null;
}

function attestationExpired(a: Attestation): boolean {
  if (!a.expires_at) return false;
  const t = new Date(a.expires_at).getTime();
  return !isNaN(t) && t < Date.now();
}

function claimStatus(claimId: number, attestations: Attestation[]): ClaimStatus {
  const a = currentAttestation(claimId, attestations);
  if (!a) return 'UNATTESTED';
  if (attestationExpired(a)) return 'EXPIRED';
  return a.verdict;
}

/**
 * THE SELLABILITY GATE.
 * fully_attested_and_current is true only when the corridor has at least one
 * current-version claim AND every current-version claim carries an active,
 * unexpired CONFIRMED attestation. Anything else — an unattested stub, a
 * pending revision, a crosses-the-line verdict, an out-of-scope claim, or an
 * expired attestation — holds the gate closed.
 */
function computeGate(claims: Claim[], attestations: Attestation[]): {
  fullyAttestedAndCurrent: boolean;
  counts: Record<ClaimStatus, number>;
  total: number;
} {
  const counts: Record<ClaimStatus, number> = {
    UNATTESTED: 0, CONFIRMED: 0, NEEDS_REVISION: 0, CROSSES_THE_LINE: 0, OUT_OF_SCOPE: 0, EXPIRED: 0,
  };
  claims.forEach((c) => { counts[claimStatus(c.id, attestations)] += 1; });
  const total = claims.length;
  return {
    fullyAttestedAndCurrent: total > 0 && counts.CONFIRMED === total,
    counts,
    total,
  };
}

// ─── Misc helpers ────────────────────────────────────────────────────────────

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
const corridorCode = (c: Corridor) => `${countryCode(c.origin_country)}→${countryCode(c.destination_country)}`;

function fmtDateTime(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

function addMonthsISO(months: number): string {
  const d = new Date();
  d.setMonth(d.getMonth() + months);
  return d.toISOString();
}

function isPlaceholderLawyer(l: Lawyer): boolean {
  return (l.name || '').toUpperCase().includes('PLACEHOLDER');
}

function escapeHtml(s: string | null | undefined): string {
  return String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ─── Main app ────────────────────────────────────────────────────────────────

export default function LegalAttestationInstrument() {
  const corridorsQ = useWorkspaceDB<Corridor>('corridors', { shared: true, limit: 100, orderBy: { column: 'id', direction: 'asc' } });
  const lawyersQ = useWorkspaceDB<Lawyer>('lawyers', { shared: true, limit: 100, orderBy: { column: 'id', direction: 'asc' } });
  const claimsQ = useWorkspaceDB<Claim>('attestation_claims', { shared: true, limit: 500, orderBy: { column: 'id', direction: 'asc' } });
  const attestationsQ = useWorkspaceDB<Attestation>('attestations', { shared: true, limit: 500, orderBy: { column: 'id', direction: 'asc' } });

  const [mode, setMode] = useState<'admin' | 'lawyer'>('admin');
  const [corridorId, setCorridorId] = useState<number | null>(null);

  const corridors = corridorsQ.data || [];
  const lawyers = lawyersQ.data || [];
  const allClaims = claimsQ.data || [];
  const attestations = attestationsQ.data || [];

  // Default to the first corridor once loaded (FR→NO is corridor #1 today).
  useEffect(() => {
    if (corridorId === null && corridors.length > 0) setCorridorId(corridors[0].id);
  }, [corridors, corridorId]);

  const corridor = corridors.find((c) => c.id === corridorId) || null;
  const claims = useMemo(
    () => allClaims.filter((c) => c.corridor_id === corridorId && c.is_current_version),
    [allClaims, corridorId],
  );
  const gate = useMemo(() => computeGate(claims, attestations), [claims, attestations]);

  const loading = corridorsQ.loading || lawyersQ.loading || claimsQ.loading || attestationsQ.loading;
  const loadError = corridorsQ.error || lawyersQ.error || claimsQ.error || attestationsQ.error;

  const refreshAll = () => {
    corridorsQ.refresh();
    lawyersQ.refresh();
    claimsQ.refresh();
    attestationsQ.refresh();
  };

  return (
    <div className="min-h-full flex flex-col w-full bg-transparent">
      {/* Header */}
      <div className="px-5 py-4 border-b border-[var(--space-border-default)] bg-[var(--space-surface-card)]">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-9 h-9 rounded-xl bg-[var(--space-brand-primary-50)] flex items-center justify-center flex-shrink-0">
              <Stamp className={`w-5 h-5 ${tw.icon.primary}`} />
            </div>
            <div className="min-w-0">
              <h2 className="font-semibold text-base text-[var(--space-text-primary)] flex items-center gap-2">
                Legal Attestation Instrument
                <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-[var(--space-surface-muted)] text-[var(--space-text-muted)] border border-[var(--space-border-default)]">Internal</span>
              </h2>
              <p className="text-xs text-[var(--space-text-secondary)] truncate">
                Structured, versioned lawyer sign-off at claim granularity — the system of record behind the corridor sellability gate
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {/* Corridor picker */}
            <select
              value={corridorId ?? ''}
              onChange={(e) => setCorridorId(Number(e.target.value))}
              className={tw.input.default + ' text-xs px-2.5 py-1.5 rounded-lg border'}
            >
              {corridors.length === 0 && <option value="">No corridors</option>}
              {corridors.map((c) => (
                <option key={c.id} value={c.id}>{corridorCode(c)} · {c.origin_country} → {c.destination_country}</option>
              ))}
            </select>
            <div className="flex items-center gap-1 rounded-lg border border-[var(--space-border-default)] overflow-hidden">
              {([
                { id: 'admin', label: 'Founder Console', icon: LayoutGrid },
                { id: 'lawyer', label: 'Lawyer Review', icon: Scale },
              ] as const).map((t) => (
                <button
                  key={t.id}
                  onClick={() => setMode(t.id)}
                  className={`px-3 py-1.5 text-xs font-medium flex items-center gap-1.5 transition-all ${
                    mode === t.id ? tw.button.primary : 'bg-[var(--space-surface-card)] text-[var(--space-text-secondary)] hover:bg-[var(--space-surface-muted)]'
                  }`}
                >
                  <t.icon className="w-3.5 h-3.5" /> <span className="hidden sm:inline">{t.label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="text-center py-16">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--space-brand-primary)] mx-auto" />
            <p className="text-sm text-[var(--space-text-muted)] mt-3">Loading attestation register…</p>
          </div>
        ) : loadError ? (
          <div className="text-center py-16 text-red-400 text-sm">Error: {loadError.message}</div>
        ) : !corridor ? (
          <div className="text-center py-16">
            <Shield className="w-8 h-8 mx-auto text-[var(--space-text-muted)]" />
            <p className="text-sm text-[var(--space-text-muted)] mt-3">No corridors exist yet. Add a corridor in Assurance Ops first.</p>
          </div>
        ) : mode === 'admin' ? (
          <AdminConsole
            corridor={corridor}
            claims={claims}
            attestations={attestations}
            lawyers={lawyers}
            gate={gate}
            onChanged={refreshAll}
          />
        ) : (
          <LawyerReview
            corridor={corridor}
            claims={claims}
            attestations={attestations}
            lawyers={lawyers}
            gate={gate}
            onChanged={refreshAll}
          />
        )}
      </div>
    </div>
  );
}

// ─── Corridor attestation status header (shared by both modes) ──────────────

function GateHeader({
  corridor, gate,
}: {
  corridor: Corridor;
  gate: ReturnType<typeof computeGate>;
}) {
  const open = gate.fullyAttestedAndCurrent;
  const inconsistent = corridor.assurance_status === 'sellable' && !open;
  return (
    <div className="space-y-2">
      <div className={`p-3.5 rounded-xl border flex items-start gap-3 ${
        open ? 'border-green-500/40 bg-green-500/10' : 'border-amber-500/40 bg-amber-500/10'
      }`}>
        {open
          ? <Unlock className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
          : <Lock className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-sm font-semibold text-[var(--space-text-primary)]">
              Sellability gate — <code className="text-xs bg-[var(--space-surface-muted)] px-1.5 py-0.5 rounded">fully_attested_and_current</code>
            </p>
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
              open ? 'bg-green-500/20 text-green-300' : 'bg-amber-500/20 text-amber-300'
            }`}>
              {open ? 'TRUE — gate open' : 'FALSE — gate closed'}
            </span>
          </div>
          <p className="text-xs text-[var(--space-text-secondary)] mt-1 leading-relaxed">
            {open
              ? `Every one of the ${gate.total} current claim${gate.total !== 1 ? 's' : ''} on ${corridor.origin_country} → ${corridor.destination_country} carries an active, unexpired CONFIRMED attestation. The corridor is eligible to be marked sellable in Assurance Ops.`
              : gate.total === 0
                ? `No attestation claims exist for ${corridor.origin_country} → ${corridor.destination_country} yet. A corridor with zero claims cannot pass the gate — author claim stubs before the lawyer engagement.`
                : `This corridor CANNOT be marked sellable: ${gate.total - gate.counts.CONFIRMED} of ${gate.total} current claim${gate.total !== 1 ? 's' : ''} lack an active, unexpired CONFIRMED attestation. The gate opens only when every claim is confirmed and current.`}
          </p>
        </div>
      </div>

      {inconsistent && (
        <div className="p-2.5 rounded-lg border border-red-500/40 bg-red-500/10 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-red-300">
            Inconsistency: this corridor's pipeline status is <span className="font-bold">sellable</span> in Assurance Ops, but the claim-level gate is FALSE. Review the attestation register — the corridor should not be on sale.
          </p>
        </div>
      )}

      {/* Status counts */}
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
        {STATUS_ORDER.map((s) => (
          <div key={s} className="p-2.5 rounded-xl border border-[var(--space-border-default)] bg-[var(--space-surface-card)]">
            <div className="flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full ${STATUS_STYLE[s].dot}`} />
              <p className="text-lg font-bold text-[var(--space-text-primary)]">{gate.counts[s]}</p>
            </div>
            <p className="text-[9px] uppercase tracking-wider text-[var(--space-text-muted)] mt-0.5">{STATUS_STYLE[s].label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Claim status + verdict detail chip ──────────────────────────────────────

function ClaimStatusBadge({ claimId, attestations, lawyers }: { claimId: number; attestations: Attestation[]; lawyers: Lawyer[] }) {
  const status = claimStatus(claimId, attestations);
  const att = currentAttestation(claimId, attestations);
  const lawyer = att ? lawyers.find((l) => l.id === att.lawyer_id) : null;
  return (
    <div className="flex flex-col items-end gap-1 flex-shrink-0">
      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${STATUS_STYLE[status].badge}`}>
        {STATUS_STYLE[status].label}
      </span>
      {att && (
        <span className="text-[9px] text-[var(--space-text-muted)] text-right">
          {lawyer ? lawyer.name.slice(0, 28) : `Lawyer #${att.lawyer_id}`} · {fmtDateTime(att.attested_at)}
          {att.expires_at && ` · ${attestationExpired(att) ? 'expired' : 'expires'} ${fmtDateTime(att.expires_at)}`}
        </span>
      )}
    </div>
  );
}

// ─── A) Admin / Founder console ──────────────────────────────────────────────

const EMPTY_CLAIM_FORM = {
  dimension: 'nationality_resolution',
  fixture_row: '',
  claim_text: '',
  legal_basis: '',
  jurisdiction: 'EU',
  disposition_asserted: 'INFO' as 'INFO' | 'ROUTE',
  notes: '',
};

function AdminConsole({
  corridor, claims, attestations, lawyers, gate, onChanged,
}: {
  corridor: Corridor;
  claims: Claim[];
  attestations: Attestation[];
  lawyers: Lawyer[];
  gate: ReturnType<typeof computeGate>;
  onChanged: () => void;
}) {
  const [showAdd, setShowAdd] = useState(false);
  const [editClaim, setEditClaim] = useState<Claim | null>(null);
  const [showSheet, setShowSheet] = useState(false);

  const byDimension = useMemo(() => {
    const m: Record<string, Claim[]> = {};
    claims.forEach((c) => { (m[c.dimension] = m[c.dimension] || []).push(c); });
    return m;
  }, [claims]);

  // Canonical dimensions always shown; extra dimensions found in data appended.
  const dims = useMemo(() => {
    const extras = Object.keys(byDimension).filter((d) => !CANONICAL_DIMS.includes(d)).sort();
    return [...CANONICAL_DIMS, ...extras];
  }, [byDimension]);

  return (
    <div className="p-4 sm:p-5 space-y-4 max-w-5xl">
      <GateHeader corridor={corridor} gate={gate} />

      <div className="flex items-center justify-between gap-2 flex-wrap">
        <p className="text-xs text-[var(--space-text-secondary)]">
          {gate.total} current claim{gate.total !== 1 ? 's' : ''} on {corridorCode(corridor)} · claim stubs are authored here before a lawyer engagement, then attested in Lawyer Review
        </p>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowSheet(true)} className={`px-3 py-1.5 text-xs rounded-lg flex items-center gap-1.5 ${tw.button.secondary}`}>
            <FileText className="w-3.5 h-3.5" /> Generate attestation sheet
          </button>
          <button onClick={() => { setShowAdd(!showAdd); setEditClaim(null); }} className={`px-3 py-1.5 text-xs rounded-lg flex items-center gap-1 ${tw.button.accent}`}>
            {showAdd ? <X className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />} {showAdd ? 'Cancel' : 'Add claim stub'}
          </button>
        </div>
      </div>

      {showAdd && (
        <ClaimForm
          corridor={corridor}
          claim={null}
          hasAttestations={false}
          onDone={() => { setShowAdd(false); onChanged(); }}
          onCancel={() => setShowAdd(false)}
        />
      )}
      {editClaim && (
        <ClaimForm
          corridor={corridor}
          claim={editClaim}
          hasAttestations={attestations.some((a) => a.claim_id === editClaim.id)}
          onDone={() => { setEditClaim(null); onChanged(); }}
          onCancel={() => setEditClaim(null)}
        />
      )}

      {gate.total === 0 ? (
        <div className="text-center py-12 rounded-xl border border-dashed border-[var(--space-border-strong)]">
          <Gavel className="w-8 h-8 mx-auto text-[var(--space-text-muted)]" />
          <p className="text-sm text-[var(--space-text-secondary)] mt-3 font-medium">No attestation claims for this corridor yet.</p>
          <p className="text-xs text-[var(--space-text-muted)] mt-1 max-w-md mx-auto">
            Author precise, decidable claim stubs from the corridor engine fixture before engaging counsel. Nothing is invented here — every claim maps to content the product actually produces.
          </p>
        </div>
      ) : (
        dims.map((dim) => {
          const list = byDimension[dim] || [];
          if (list.length === 0 && !CANONICAL_DIMS.includes(dim)) return null;
          return (
            <div key={dim}>
              <h3 className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--space-text-secondary)] mb-2">
                <Gavel className="w-3.5 h-3.5" /> {dimLabel(dim)}
                <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-[var(--space-surface-muted)] text-[var(--space-text-secondary)]">{list.length}</span>
              </h3>
              {list.length === 0 ? (
                <p className="text-xs text-[var(--space-text-muted)] italic mb-2 pl-1">No claims in this dimension yet for {corridorCode(corridor)}.</p>
              ) : (
                <div className="space-y-2 mb-2">
                  {list.map((c) => (
                    <ClaimRow
                      key={c.id}
                      claim={c}
                      attestations={attestations}
                      lawyers={lawyers}
                      onEdit={() => { setEditClaim(c); setShowAdd(false); }}
                    />
                  ))}
                </div>
              )}
            </div>
          );
        })
      )}

      {showSheet && (
        <SheetModal
          corridor={corridor}
          claims={claims}
          attestations={attestations}
          lawyers={lawyers}
          gate={gate}
          onClose={() => setShowSheet(false)}
        />
      )}
    </div>
  );
}

function ClaimRow({
  claim, attestations, lawyers, onEdit,
}: {
  claim: Claim;
  attestations: Attestation[];
  lawyers: Lawyer[];
  onEdit: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const history = attestations
    .filter((a) => a.claim_id === claim.id)
    .sort((a, b) => String(b.attested_at || '').localeCompare(String(a.attested_at || '')));
  const att = currentAttestation(claim.id, attestations);

  return (
    <div className="p-3 rounded-xl border border-[var(--space-border-default)] bg-[var(--space-surface-card)]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 flex-wrap mb-1.5">
            <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-[var(--space-surface-muted)] text-[var(--space-text-muted)] border border-[var(--space-border-default)]">#{claim.id} · v{claim.version}</span>
            {claim.fixture_row && (
              <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-[var(--space-brand-primary-50)] text-[var(--space-text-brand)]" title="Engine fixture mapping">
                fixture {claim.fixture_row}
              </span>
            )}
            <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-[var(--space-surface-muted)] text-[var(--space-text-secondary)]">{claim.jurisdiction}</span>
            <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
              claim.disposition_asserted === 'ROUTE' ? 'bg-red-500/15 text-red-300' : 'bg-[var(--space-brand-highlight-100)] text-[var(--space-text-accent)]'
            }`} title={claim.disposition_asserted === 'ROUTE' ? 'Engine must route to a professional — never answer directly' : 'Engine may surface this as information'}>
              {claim.disposition_asserted}
            </span>
          </div>
          <p className="text-xs text-[var(--space-text-primary)] leading-relaxed">{claim.claim_text}</p>
          <p className="text-[10px] text-[var(--space-text-muted)] mt-1.5 flex items-start gap-1">
            <Scale className="w-3 h-3 flex-shrink-0 mt-px" />
            <span><span className="font-semibold">Legal basis:</span> {claim.legal_basis || 'None stated (routing determination)'}</span>
          </p>
        </div>
        <div className="flex flex-col items-end gap-2 flex-shrink-0">
          <ClaimStatusBadge claimId={claim.id} attestations={attestations} lawyers={lawyers} />
          <div className="flex items-center gap-1">
            {history.length > 0 && (
              <button onClick={() => setExpanded(!expanded)} className="p-1 rounded-md border border-[var(--space-border-default)] text-[var(--space-text-secondary)] hover:bg-[var(--space-surface-muted)] transition-colors" title="Verdict history">
                <Eye className="w-3.5 h-3.5" />
              </button>
            )}
            <button onClick={onEdit} className="p-1 rounded-md border border-[var(--space-border-default)] text-[var(--space-text-secondary)] hover:bg-[var(--space-surface-muted)] transition-colors" title="Edit claim">
              <Pencil className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {att?.verdict_note && (
        <div className="mt-2 p-2 rounded-lg bg-[var(--space-surface-muted)]/60 border border-[var(--space-border-default)]">
          <p className="text-[10px] text-[var(--space-text-secondary)]"><span className="font-semibold">Counsel note:</span> {att.verdict_note}</p>
        </div>
      )}

      {expanded && history.length > 0 && (
        <div className="mt-2 rounded-lg border border-[var(--space-border-default)] overflow-hidden">
          {history.map((a, i) => {
            const lawyer = lawyers.find((l) => l.id === a.lawyer_id);
            return (
              <div key={a.id} className={`px-2.5 py-2 bg-[var(--space-surface-muted)]/40 ${i > 0 ? 'border-t border-[var(--space-border-default)]' : ''}`}>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold border ${STATUS_STYLE[a.verdict].badge}`}>{STATUS_STYLE[a.verdict].label}</span>
                  <span className="text-[10px] text-[var(--space-text-secondary)]">{lawyer?.name || `Lawyer #${a.lawyer_id}`} · attested {fmtDateTime(a.attested_at)}</span>
                  {a.expires_at && <span className="text-[10px] text-[var(--space-text-muted)]">expires {fmtDateTime(a.expires_at)}</span>}
                  {a.superseded_by !== null && a.superseded_by !== undefined && (
                    <span className="px-1.5 py-0.5 rounded text-[9px] bg-[var(--space-surface-muted)] text-[var(--space-text-muted)]">superseded by #{a.superseded_by}</span>
                  )}
                </div>
                {a.verdict_note && <p className="text-[10px] text-[var(--space-text-muted)] mt-1">{a.verdict_note}</p>}
              </div>
            );
          })}
        </div>
      )}

      {claim.notes && (
        <p className="text-[10px] text-[var(--space-text-muted)] mt-2 italic leading-relaxed">{claim.notes}</p>
      )}
    </div>
  );
}

// ─── Claim stub add / edit form ──────────────────────────────────────────────

function ClaimForm({
  corridor, claim, hasAttestations, onDone, onCancel,
}: {
  corridor: Corridor;
  claim: Claim | null;
  hasAttestations: boolean;
  onDone: () => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState(() => claim ? {
    dimension: claim.dimension,
    fixture_row: claim.fixture_row || '',
    claim_text: claim.claim_text,
    legal_basis: claim.legal_basis || '',
    jurisdiction: claim.jurisdiction,
    disposition_asserted: claim.disposition_asserted,
    notes: claim.notes || '',
  } : { ...EMPTY_CLAIM_FORM });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    if (!form.claim_text.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const payload = {
        corridor_id: corridor.id,
        dimension: form.dimension,
        fixture_row: form.fixture_row.trim() || null,
        claim_text: form.claim_text.trim(),
        legal_basis: form.legal_basis.trim() || null,
        jurisdiction: form.jurisdiction,
        disposition_asserted: form.disposition_asserted,
        notes: form.notes.trim() || null,
      };
      if (!claim) {
        await db().from('attestation_claims', { shared: true }).insert({
          ...payload, version: 1, is_current_version: true,
        });
      } else if (!hasAttestations) {
        // Unattested stub — safe to edit in place.
        await db().from('attestation_claims', { shared: true }).update(claim.id, payload);
      } else {
        // Attested claim — versioned supersession: new row, old marked non-current.
        await db().from('attestation_claims', { shared: true }).insert({
          ...payload, version: claim.version + 1, is_current_version: true,
        });
        await db().from('attestation_claims', { shared: true }).update(claim.id, { is_current_version: false });
      }
      onDone();
    } catch (e: any) {
      setError(e?.message || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-4 rounded-xl border border-[var(--space-border-default)] bg-[var(--space-brand-highlight-50)] space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wider text-[var(--space-text-secondary)]">
          {claim ? `Edit claim #${claim.id} (v${claim.version})` : `New claim stub — ${corridorCode(corridor)}`}
        </p>
        <button onClick={onCancel} className="p-1 rounded-lg hover:bg-[var(--space-surface-muted)] text-[var(--space-text-secondary)]"><X className="w-4 h-4" /></button>
      </div>

      {claim && hasAttestations && (
        <div className="p-2.5 rounded-lg border border-amber-500/40 bg-amber-500/10 flex items-start gap-2">
          <Info className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-0.5" />
          <p className="text-[11px] text-amber-200">
            This claim has attestations on record. Saving creates <span className="font-bold">version {claim.version + 1}</span> and retires v{claim.version} — prior verdicts stay attached to the old version for audit, and the new version starts UNATTESTED.
          </p>
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <select value={form.dimension} onChange={(e) => setForm({ ...form, dimension: e.target.value })}
          className={tw.input.default + ' text-xs px-2.5 py-1.5 rounded-lg border'}>
          {DIMENSIONS.map((d) => <option key={d.id} value={d.id}>{d.label}</option>)}
        </select>
        <select value={form.jurisdiction} onChange={(e) => setForm({ ...form, jurisdiction: e.target.value })}
          className={tw.input.default + ' text-xs px-2.5 py-1.5 rounded-lg border'}>
          {JURISDICTIONS.map((j) => <option key={j} value={j}>{j}</option>)}
        </select>
        <select value={form.disposition_asserted} onChange={(e) => setForm({ ...form, disposition_asserted: e.target.value as 'INFO' | 'ROUTE' })}
          className={tw.input.default + ' text-xs px-2.5 py-1.5 rounded-lg border'}>
          <option value="INFO">INFO — engine may surface</option>
          <option value="ROUTE">ROUTE — must route to counsel</option>
        </select>
        <input type="text" placeholder="Fixture row (e.g. row 6)" value={form.fixture_row}
          onChange={(e) => setForm({ ...form, fixture_row: e.target.value })}
          className={tw.input.default + ' text-xs px-2.5 py-1.5 rounded-lg border'} />
      </div>
      <textarea
        placeholder="Claim text — a precise, self-contained, decidable statement the lawyer can answer CONFIRMED / NEEDS_REVISION / CROSSES_THE_LINE / OUT_OF_SCOPE…"
        value={form.claim_text}
        onChange={(e) => setForm({ ...form, claim_text: e.target.value })}
        rows={4}
        className={tw.input.default + ' w-full text-xs px-2.5 py-2 rounded-lg border resize-y'}
      />
      <input type="text" placeholder="Legal basis — statute / article / treaty the engine cites (blank for pure routing determinations)" value={form.legal_basis}
        onChange={(e) => setForm({ ...form, legal_basis: e.target.value })}
        className={tw.input.default + ' w-full text-xs px-2.5 py-1.5 rounded-lg border'} />
      <input type="text" placeholder="Internal pipeline notes (optional — not shown as the lawyer verdict)" value={form.notes}
        onChange={(e) => setForm({ ...form, notes: e.target.value })}
        className={tw.input.default + ' w-full text-xs px-2.5 py-1.5 rounded-lg border'} />

      {error && <p className="text-xs text-red-400">{error}</p>}
      <button onClick={handleSave} disabled={saving || !form.claim_text.trim()}
        className={`px-4 py-2 text-sm rounded-lg ${tw.button.primary} disabled:opacity-50`}>
        {saving ? 'Saving…' : claim ? (hasAttestations ? `Save as v${claim.version + 1}` : 'Save changes') : 'Add claim stub'}
      </button>
    </div>
  );
}

// ─── B) Lawyer review / attestation capture ──────────────────────────────────

function LawyerReview({
  corridor, claims, attestations, lawyers, gate, onChanged,
}: {
  corridor: Corridor;
  claims: Claim[];
  attestations: Attestation[];
  lawyers: Lawyer[];
  gate: ReturnType<typeof computeGate>;
  onChanged: () => void;
}) {
  const [lawyerId, setLawyerId] = useState<number | null>(null);
  const [index, setIndex] = useState(0);

  // Review order: claims needing a verdict first (UNATTESTED / EXPIRED), then the rest.
  const queue = useMemo(() => {
    const needsVerdict = (c: Claim) => {
      const s = claimStatus(c.id, attestations);
      return s === 'UNATTESTED' || s === 'EXPIRED';
    };
    return [...claims].sort((a, b) => Number(needsVerdict(b)) - Number(needsVerdict(a)) || a.id - b.id);
  }, [claims, attestations]);

  useEffect(() => { setIndex(0); }, [corridor.id]);
  const safeIndex = Math.min(index, Math.max(0, queue.length - 1));
  const claim = queue[safeIndex] || null;

  const selectedLawyer = lawyers.find((l) => l.id === lawyerId) || null;
  const selectablelawyers = lawyers.filter((l) => !isPlaceholderLawyer(l));
  const pendingCount = queue.filter((c) => {
    const s = claimStatus(c.id, attestations);
    return s === 'UNATTESTED' || s === 'EXPIRED';
  }).length;

  return (
    <div className="p-4 sm:p-5 space-y-4 max-w-3xl mx-auto">
      {/* Framing — the legal positioning that keeps ReloPass on the information side */}
      <div className="p-4 rounded-xl border border-[var(--space-border-strong)] bg-[var(--space-surface-panel)]">
        <h3 className="text-sm font-semibold text-[var(--space-text-primary)] flex items-center gap-2">
          <Scale className="w-4 h-4 text-[var(--space-text-accent)]" /> Attestation of product-produced content
        </h3>
        <p className="text-xs text-[var(--space-text-secondary)] mt-1.5 leading-relaxed">
          You are reviewing statements and determinations <span className="font-semibold text-[var(--space-text-primary)]">produced by the ReloPass engine</span> for the {corridor.origin_country} → {corridor.destination_country} corridor. You are <span className="font-semibold text-[var(--space-text-primary)]">attesting to the accuracy of this content against its stated legal basis</span> — you are not being asked to author advice, and no verdict recorded here constitutes legal advice to any end user. Each claim states the source the engine cites; your verdict confirms or corrects the engine's classification.
        </p>
      </div>

      {/* Lawyer selection — real roster only */}
      <div className="p-3 rounded-xl border border-[var(--space-border-default)] bg-[var(--space-surface-card)]">
        <label className="block text-[10px] font-semibold uppercase tracking-wider text-[var(--space-text-muted)] mb-1.5">Attesting lawyer (from roster)</label>
        {selectablelawyers.length === 0 ? (
          <div className="flex items-start gap-2 p-2.5 rounded-lg border border-amber-500/40 bg-amber-500/10">
            <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-amber-200">
              No confirmed counsel is on the roster yet{lawyers.some(isPlaceholderLawyer) ? ' (only a placeholder slot exists)' : ''}. Verdicts must be recorded against a real, identified lawyer — add the engaged counsel in Assurance Ops → Lawyer Roster first. Placeholder rows cannot attest.
            </p>
          </div>
        ) : (
          <select
            value={lawyerId ?? ''}
            onChange={(e) => setLawyerId(e.target.value === '' ? null : Number(e.target.value))}
            className={tw.input.default + ' w-full text-xs px-2.5 py-2 rounded-lg border'}
          >
            <option value="">— Select the lawyer recording verdicts —</option>
            {selectablelawyers.map((l) => (
              <option key={l.id} value={l.id}>{l.name}{l.firm ? ` (${l.firm})` : ''} — {l.jurisdiction}{l.specialty ? ` · ${l.specialty}` : ''}</option>
            ))}
          </select>
        )}
        {selectedLawyer && (
          <p className="text-[10px] text-[var(--space-text-muted)] mt-1.5">
            Verdicts will be recorded in the attestation register under <span className="font-semibold text-[var(--space-text-secondary)]">{selectedLawyer.name}</span> ({selectedLawyer.jurisdiction} · roster status: {selectedLawyer.status}).
          </p>
        )}
      </div>

      {/* Progress */}
      {queue.length > 0 && (
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs text-[var(--space-text-secondary)]">
            Claim {safeIndex + 1} of {queue.length} · <span className={pendingCount > 0 ? 'text-amber-300 font-semibold' : 'text-green-300 font-semibold'}>{pendingCount} awaiting a current verdict</span>
          </p>
          <div className="flex items-center gap-1">
            <button onClick={() => setIndex(Math.max(0, safeIndex - 1))} disabled={safeIndex === 0}
              className="p-1.5 rounded-md border border-[var(--space-border-default)] text-[var(--space-text-secondary)] hover:bg-[var(--space-surface-muted)] disabled:opacity-30 transition-colors">
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button onClick={() => setIndex(Math.min(queue.length - 1, safeIndex + 1))} disabled={safeIndex >= queue.length - 1}
              className="p-1.5 rounded-md border border-[var(--space-border-default)] text-[var(--space-text-secondary)] hover:bg-[var(--space-surface-muted)] disabled:opacity-30 transition-colors">
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* One claim at a time */}
      {queue.length === 0 ? (
        <div className="text-center py-12 rounded-xl border border-dashed border-[var(--space-border-strong)]">
          <Gavel className="w-8 h-8 mx-auto text-[var(--space-text-muted)]" />
          <p className="text-sm text-[var(--space-text-secondary)] mt-3 font-medium">Nothing to review — no claims exist for {corridorCode(corridor)}.</p>
          <p className="text-xs text-[var(--space-text-muted)] mt-1">Claim stubs are authored in the Founder Console before a lawyer engagement.</p>
        </div>
      ) : claim ? (
        <VerdictCard
          key={claim.id}
          claim={claim}
          attestations={attestations}
          lawyer={selectedLawyer}
          onRecorded={() => { onChanged(); if (safeIndex < queue.length - 1) setIndex(safeIndex + 1); }}
        />
      ) : null}

      {/* Gate reminder at the bottom of the review flow */}
      <div className={`p-2.5 rounded-lg border flex items-center gap-2 ${gate.fullyAttestedAndCurrent ? 'border-green-500/40 bg-green-500/10' : 'border-[var(--space-border-default)] bg-[var(--space-surface-muted)]/50'}`}>
        {gate.fullyAttestedAndCurrent ? <Unlock className="w-3.5 h-3.5 text-green-400" /> : <Lock className="w-3.5 h-3.5 text-[var(--space-text-muted)]" />}
        <p className="text-[11px] text-[var(--space-text-secondary)]">
          Sellability gate: <span className="font-bold">{gate.counts.CONFIRMED}/{gate.total}</span> claims confirmed & current — <code className="text-[10px]">fully_attested_and_current = {String(gate.fullyAttestedAndCurrent)}</code>
        </p>
      </div>
    </div>
  );
}

function VerdictCard({
  claim, attestations, lawyer, onRecorded,
}: {
  claim: Claim;
  attestations: Attestation[];
  lawyer: Lawyer | null;
  onRecorded: () => void;
}) {
  const [verdict, setVerdict] = useState<Attestation['verdict'] | null>(null);
  const [note, setNote] = useState('');
  const [expiry, setExpiry] = useState('12m');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const status = claimStatus(claim.id, attestations);
  const existing = currentAttestation(claim.id, attestations);
  const chosen = VERDICTS.find((v) => v.id === verdict) || null;
  const noteMissing = chosen ? chosen.noteRequired && !note.trim() : true;

  const handleRecord = async () => {
    if (!lawyer || !verdict || noteMissing) return;
    setSaving(true);
    setError(null);
    try {
      const preset = EXPIRY_PRESETS.find((p) => p.id === expiry)!;
      await db().from('attestations', { shared: true }).insert({
        claim_id: claim.id,
        lawyer_id: lawyer.id,
        verdict,
        verdict_note: note.trim() || null,
        attested_at: new Date().toISOString(),
        expires_at: preset.months === null ? null : addMonthsISO(preset.months),
        superseded_by: null,
      });
      // Versioned re-attestation: mark any prior active verdicts on this claim
      // as superseded by the row we just inserted (fetched back for its id).
      if (existing) {
        const res = await db().from('attestations', { shared: true })
          .eq('claim_id', claim.id).orderBy('id', 'desc').limit(50).get();
        const rows: Attestation[] = res?.data || [];
        const newest = rows[0];
        if (newest) {
          const priors = rows.filter((r) => r.id !== newest.id && (r.superseded_by === null || r.superseded_by === undefined));
          for (const p of priors) {
            await db().from('attestations', { shared: true }).update(p.id, { superseded_by: newest.id });
          }
        }
      }
      setVerdict(null);
      setNote('');
      onRecorded();
    } catch (e: any) {
      setError(e?.message || 'Failed to record verdict');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-xl border border-[var(--space-border-strong)] bg-[var(--space-surface-card)] overflow-hidden">
      {/* Claim header */}
      <div className="px-4 py-3 border-b border-[var(--space-border-default)] bg-[var(--space-surface-panel-strong)] flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-[var(--space-surface-muted)] text-[var(--space-text-muted)] border border-[var(--space-border-default)]">Claim #{claim.id} · v{claim.version}</span>
          <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-[var(--space-brand-primary-50)] text-[var(--space-text-brand)]">{dimLabel(claim.dimension)}</span>
          {claim.fixture_row && <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-[var(--space-surface-muted)] text-[var(--space-text-secondary)]">fixture {claim.fixture_row}</span>}
          <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-[var(--space-surface-muted)] text-[var(--space-text-secondary)]">{claim.jurisdiction}</span>
        </div>
        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${STATUS_STYLE[status].badge}`}>{STATUS_STYLE[status].label}</span>
      </div>

      <div className="p-4 space-y-3">
        {/* The claim, verbatim */}
        <div className="p-3.5 rounded-lg border-l-4 border-[var(--space-brand-highlight)] bg-[var(--space-surface-muted)]/60">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--space-text-muted)] mb-1.5">The engine asserts (verbatim)</p>
          <p className="text-sm text-[var(--space-text-primary)] leading-relaxed">{claim.claim_text}</p>
        </div>

        {/* Legal basis — the stated source being attested against */}
        <div className="flex items-start gap-2 p-2.5 rounded-lg border border-[var(--space-border-default)] bg-[var(--space-surface-card)]">
          <Scale className="w-4 h-4 text-[var(--space-text-accent)] flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--space-text-muted)]">Stated legal basis — attest against this source</p>
            <p className="text-xs text-[var(--space-text-primary)] mt-0.5">{claim.legal_basis || 'No single statutory basis stated — this is a routing determination.'}</p>
          </div>
        </div>

        {/* Disposition */}
        <div className="flex items-start gap-2 p-2.5 rounded-lg border border-[var(--space-border-default)] bg-[var(--space-surface-card)]">
          <Info className="w-4 h-4 text-[var(--space-text-accent)] flex-shrink-0 mt-0.5" />
          <p className="text-xs text-[var(--space-text-secondary)]">
            Engine classification: <span className={`font-bold ${claim.disposition_asserted === 'ROUTE' ? 'text-red-300' : 'text-[var(--space-text-accent)]'}`}>{claim.disposition_asserted}</span>
            {claim.disposition_asserted === 'INFO'
              ? ' — the engine treats this as an information point it may surface to users. Your verdict confirms or corrects that classification.'
              : ' — the engine never surfaces this as an answer; it routes the user to seek professional advice. Your verdict confirms or corrects that classification.'}
          </p>
        </div>

        {existing && (
          <p className="text-[10px] text-[var(--space-text-muted)]">
            Current verdict on record: {STATUS_STYLE[status].label} ({fmtDateTime(existing.attested_at)}{existing.expires_at ? `, ${attestationExpired(existing) ? 'expired' : 'expires'} ${fmtDateTime(existing.expires_at)}` : ''}). Recording a new verdict supersedes it — the prior verdict is retained for audit.
          </p>
        )}

        {/* Verdict buttons */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {VERDICTS.map((v) => (
            <button
              key={v.id}
              onClick={() => setVerdict(v.id)}
              className={`p-3 rounded-xl border text-left transition-colors ${v.style} ${verdict === v.id ? 'ring-2 ring-[var(--space-brand-highlight)]' : ''}`}
            >
              <p className="text-xs font-bold">{v.label}</p>
              <p className="text-[10px] opacity-80 mt-0.5 leading-snug">{v.hint}</p>
            </button>
          ))}
        </div>

        {chosen && (
          <div className="space-y-2">
            <textarea
              placeholder={
                chosen.id === 'NEEDS_REVISION' ? 'Correction note (required): what is wrong and how must the claim be fixed?'
                  : chosen.id === 'CROSSES_THE_LINE' ? 'Note (required): why does this constitute regulated advice as written? It must be reclassified to ROUTE or removed.'
                    : 'Optional note — caveats, qualifications, or expiry triggers'
              }
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
              className={tw.input.default + ' w-full text-xs px-2.5 py-2 rounded-lg border resize-y'}
            />
            <div className="flex items-center gap-2 flex-wrap">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-[var(--space-text-muted)] flex items-center gap-1"><Clock className="w-3 h-3" /> Re-verification cadence</label>
              <select value={expiry} onChange={(e) => setExpiry(e.target.value)}
                className={tw.input.default + ' text-xs px-2.5 py-1.5 rounded-lg border'}>
                {EXPIRY_PRESETS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
              </select>
            </div>
            {!lawyer && <p className="text-xs text-amber-300 flex items-center gap-1.5"><AlertTriangle className="w-3.5 h-3.5" /> Select the attesting lawyer above before recording.</p>}
            {chosen.noteRequired && !note.trim() && <p className="text-xs text-amber-300">A note is required for {chosen.label} verdicts.</p>}
            {error && <p className="text-xs text-red-400">{error}</p>}
            <button
              onClick={handleRecord}
              disabled={saving || !lawyer || noteMissing}
              className={`px-4 py-2 text-sm rounded-lg flex items-center gap-1.5 ${tw.button.primary} disabled:opacity-50`}
            >
              <Stamp className="w-4 h-4" /> {saving ? 'Recording…' : `Record ${chosen.label} verdict`}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Attestation sheet (read-only export / shareable link) ───────────────────

function buildSheetHtml(
  corridor: Corridor,
  claims: Claim[],
  attestations: Attestation[],
  lawyers: Lawyer[],
  gate: ReturnType<typeof computeGate>,
): string {
  const code = `${countryCode(corridor.origin_country)} → ${countryCode(corridor.destination_country)}`;
  const generated = new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
  const dims = [...CANONICAL_DIMS, ...Array.from(new Set(claims.map((c) => c.dimension))).filter((d) => !CANONICAL_DIMS.includes(d)).sort()];

  const dimSections = dims.map((dim) => {
    const list = claims.filter((c) => c.dimension === dim);
    if (list.length === 0) return '';
    const rows = list.map((c) => {
      const status = claimStatus(c.id, attestations);
      const att = currentAttestation(c.id, attestations);
      const lawyer = att ? lawyers.find((l) => l.id === att.lawyer_id) : null;
      return `
      <div class="claim">
        <div class="claim-meta">
          <span class="chip">Claim #${c.id} · v${c.version}</span>
          ${c.fixture_row ? `<span class="chip">Engine fixture: ${escapeHtml(c.fixture_row)}</span>` : ''}
          <span class="chip">Jurisdiction: ${escapeHtml(c.jurisdiction)}</span>
          <span class="chip ${c.disposition_asserted === 'ROUTE' ? 'chip-route' : 'chip-info'}">Engine disposition: ${c.disposition_asserted}</span>
          <span class="chip chip-status">Status: ${escapeHtml(STATUS_STYLE[status].label)}</span>
        </div>
        <p class="claim-text">${escapeHtml(c.claim_text)}</p>
        <p class="basis"><strong>Stated legal basis:</strong> ${escapeHtml(c.legal_basis || 'None stated — routing determination with no single statutory basis.')}</p>
        ${att ? `<p class="verdict"><strong>Verdict on record:</strong> ${escapeHtml(att.verdict)} — ${escapeHtml(lawyer ? lawyer.name : `Lawyer #${att.lawyer_id}`)}, ${escapeHtml(fmtDateTime(att.attested_at))}${att.expires_at ? ` (expires ${escapeHtml(fmtDateTime(att.expires_at))})` : ''}${att.verdict_note ? ` — ${escapeHtml(att.verdict_note)}` : ''}</p>` : ''}
        <div class="verdict-box">
          <span>Verdict:&nbsp; ☐ CONFIRMED &nbsp; ☐ NEEDS_REVISION &nbsp; ☐ CROSSES_THE_LINE (must ROUTE) &nbsp; ☐ OUT_OF_SCOPE</span>
          <div class="note-line">Note / correction: ______________________________________________________________________</div>
          <div class="note-line">Re-verification cadence: &nbsp; ☐ 6 months &nbsp; ☐ 12 months &nbsp; ☐ 24 months</div>
        </div>
      </div>`;
    }).join('\n');
    return `<section><h2>${escapeHtml(dimLabel(dim))} <span class="count">(${list.length} claim${list.length !== 1 ? 's' : ''})</span></h2>${rows}</section>`;
  }).join('\n');

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>ReloPass — Legal Attestation Sheet — ${escapeHtml(code)}</title>
<style>
  body { font-family: Georgia, 'Times New Roman', serif; color: #1a2330; margin: 0; background: #f6f7f9; }
  .page { max-width: 820px; margin: 0 auto; background: #fff; padding: 48px 56px; }
  header { border-bottom: 3px solid #1a2330; padding-bottom: 16px; margin-bottom: 8px; }
  h1 { font-size: 22px; margin: 0 0 4px; }
  .sub { font-size: 13px; color: #4a5568; margin: 0; }
  .framing { background: #f0f4f8; border-left: 4px solid #2a93e0; padding: 14px 16px; font-size: 12.5px; line-height: 1.6; margin: 20px 0; }
  .gate { padding: 12px 16px; font-size: 12.5px; border: 2px solid; margin: 0 0 20px; }
  .gate.open { border-color: #16a34a; background: #f0fdf4; }
  .gate.closed { border-color: #d97706; background: #fffbeb; }
  .counts { font-size: 11.5px; color: #4a5568; margin-top: 6px; }
  h2 { font-size: 15px; border-bottom: 1px solid #cbd5e0; padding-bottom: 5px; margin: 28px 0 12px; }
  .count { font-weight: normal; font-size: 12px; color: #718096; }
  .claim { border: 1px solid #d8dee6; padding: 14px 16px; margin-bottom: 14px; page-break-inside: avoid; }
  .claim-meta { margin-bottom: 8px; }
  .chip { display: inline-block; font-size: 10px; font-family: Arial, sans-serif; background: #edf2f7; border: 1px solid #cbd5e0; padding: 1px 7px; border-radius: 10px; margin: 0 4px 4px 0; color: #2d3748; }
  .chip-route { background: #fff5f5; border-color: #feb2b2; color: #c53030; font-weight: bold; }
  .chip-info { background: #ebf8ff; border-color: #90cdf4; color: #2b6cb0; font-weight: bold; }
  .chip-status { font-weight: bold; }
  .claim-text { font-size: 13.5px; line-height: 1.65; margin: 0 0 8px; }
  .basis { font-size: 11.5px; color: #4a5568; margin: 0 0 6px; }
  .verdict { font-size: 11.5px; color: #2d3748; background: #f7fafc; padding: 6px 8px; margin: 0 0 6px; }
  .verdict-box { border-top: 1px dashed #cbd5e0; margin-top: 8px; padding-top: 8px; font-size: 11px; font-family: Arial, sans-serif; color: #4a5568; }
  .note-line { margin-top: 6px; }
  footer { margin-top: 32px; border-top: 1px solid #cbd5e0; padding-top: 12px; font-size: 10.5px; color: #718096; line-height: 1.6; }
  @media print { body { background: #fff; } .page { padding: 0; } }
</style>
</head>
<body>
<div class="page">
  <header>
    <h1>ReloPass — Legal Attestation Sheet</h1>
    <p class="sub">Corridor: <strong>${escapeHtml(corridor.origin_country)} → ${escapeHtml(corridor.destination_country)} (${escapeHtml(code)})</strong> &nbsp;·&nbsp; Generated ${escapeHtml(generated)} &nbsp;·&nbsp; ${gate.total} current claim${gate.total !== 1 ? 's' : ''}</p>
  </header>

  <div class="framing">
    <strong>Purpose of this sheet.</strong> The statements below are produced by the ReloPass corridor engine and are presented verbatim.
    The reviewing lawyer is asked to <strong>attest to the accuracy of each statement against its stated legal basis</strong> and to
    confirm or correct the engine's INFO/ROUTE classification. The lawyer is <strong>not</strong> being asked to author legal advice,
    and no verdict recorded on this sheet constitutes legal advice to any end user. Claims classified ROUTE are never surfaced as
    answers by the product — they trigger a prompt to seek professional advice.
  </div>

  <div class="gate ${gate.fullyAttestedAndCurrent ? 'open' : 'closed'}">
    <strong>Sellability gate — fully_attested_and_current = ${String(gate.fullyAttestedAndCurrent).toUpperCase()}.</strong>
    ${gate.fullyAttestedAndCurrent
      ? 'Every current claim carries an active, unexpired CONFIRMED attestation. The corridor is eligible to be marked sellable.'
      : 'This corridor cannot be marked sellable until every current claim carries an active, unexpired CONFIRMED attestation.'}
    <div class="counts">Unattested: ${gate.counts.UNATTESTED} · Confirmed: ${gate.counts.CONFIRMED} · Needs revision: ${gate.counts.NEEDS_REVISION} · Crosses the line: ${gate.counts.CROSSES_THE_LINE} · Out of scope: ${gate.counts.OUT_OF_SCOPE} · Expired: ${gate.counts.EXPIRED}</div>
  </div>

  ${gate.total === 0 ? '<p style="font-size:13px;color:#718096;font-style:italic;">No attestation claims exist for this corridor yet.</p>' : dimSections}

  <footer>
    Verdict definitions — <strong>CONFIRMED:</strong> the statement is accurate as written and the INFO/ROUTE classification is correct.
    <strong>NEEDS_REVISION:</strong> material error or ambiguity; a correction note is required. <strong>CROSSES_THE_LINE:</strong> as written the
    statement would constitute regulated legal advice; it must be reclassified to ROUTE or removed. <strong>OUT_OF_SCOPE:</strong> the reviewer
    cannot opine due to jurisdictional or subject-matter limits.<br/>
    Generated by the ReloPass Legal Attestation Instrument. Claims are versioned; this sheet reflects current claim versions only.
  </footer>
</div>
</body>
</html>`;
}

function SheetModal({
  corridor, claims, attestations, lawyers, gate, onClose,
}: {
  corridor: Corridor;
  claims: Claim[];
  attestations: Attestation[];
  lawyers: Lawyer[];
  gate: ReturnType<typeof computeGate>;
  onClose: () => void;
}) {
  const [creating, setCreating] = useState(false);
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const html = useMemo(() => buildSheetHtml(corridor, claims, attestations, lawyers, gate), [corridor, claims, attestations, lawyers, gate]);

  const openPrintView = () => {
    const w = window.open('', '_blank');
    if (!w) return;
    w.document.write(html);
    w.document.close();
  };

  const createShareLink = async () => {
    setCreating(true);
    setError(null);
    try {
      const workspaceId = (window as any).__WORKSPACE_ID__ || 'd0c29613-9cb5-4652-9c6a-494eeed352e5';
      const sessionId = (window as any).__spaceSessionId;
      const code = `${countryCode(corridor.origin_country)}-${countryCode(corridor.destination_country)}`.toLowerCase();
      const res = await fetch(`/api/workspaces/${workspaceId}/permalink-pages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(sessionId ? { 'x-session-id': sessionId } : {}),
        },
        body: JSON.stringify({
          slug: `attestation-sheet-${code}-${Date.now()}`,
          title: `ReloPass — Legal Attestation Sheet — ${countryCode(corridor.origin_country)}→${countryCode(corridor.destination_country)}`,
          htmlContent: html,
          isPublic: true,
          metadata: { type: 'attestation-sheet', corridorId: corridor.id, generatedAt: new Date().toISOString() },
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.error || `Share link creation failed (${res.status})`);
      setShareUrl(data.publicUrl || null);
      if (!data.publicUrl) throw new Error('No public URL returned');
    } catch (e: any) {
      setError(e?.message || 'Failed to create shareable link');
    } finally {
      setCreating(false);
    }
  };

  const copyUrl = async () => {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* clipboard unavailable — URL is shown as text */ }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div
        className="w-full max-w-2xl max-h-[90vh] flex flex-col rounded-2xl border border-[var(--space-border-default)] bg-[var(--space-surface-panel)] shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-5 py-4 border-b border-[var(--space-border-default)] bg-[var(--space-surface-panel-strong)] flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-[var(--space-text-primary)] flex items-center gap-2">
              <FileText className="w-4 h-4 text-[var(--space-text-accent)]" /> Attestation sheet — {corridorCode(corridor)}
            </h3>
            <p className="text-[11px] text-[var(--space-text-secondary)] mt-0.5">
              A clean, read-only sheet of all {gate.total} current claim{gate.total !== 1 ? 's' : ''} to send counsel ahead of a paid consultation.
            </p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-[var(--space-surface-muted)] text-[var(--space-text-secondary)]"><X className="w-4 h-4" /></button>
        </div>

        <div className="p-5 space-y-3 overflow-y-auto">
          <div className="flex items-center gap-2 flex-wrap">
            <button onClick={createShareLink} disabled={creating || !!shareUrl}
              className={`px-3.5 py-2 text-xs rounded-lg flex items-center gap-1.5 ${tw.button.primary} disabled:opacity-50`}>
              <ExternalLink className="w-3.5 h-3.5" /> {creating ? 'Creating link…' : shareUrl ? 'Link created' : 'Create shareable link'}
            </button>
            <button onClick={openPrintView} className={`px-3.5 py-2 text-xs rounded-lg flex items-center gap-1.5 ${tw.button.secondary}`}>
              <Printer className="w-3.5 h-3.5" /> Open print view
            </button>
          </div>

          {shareUrl && (
            <div className="p-3 rounded-lg border border-green-500/40 bg-green-500/10">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-green-300 mb-1">Shareable link — send this to counsel</p>
              <div className="flex items-center gap-2">
                <a href={shareUrl} target="_blank" rel="noreferrer" className="text-xs text-[var(--space-text-brand)] hover:underline break-all flex-1">{shareUrl}</a>
                <button onClick={copyUrl} className={`px-2 py-1 text-[10px] rounded-md flex items-center gap-1 flex-shrink-0 ${tw.button.secondary}`}>
                  <Copy className="w-3 h-3" /> {copied ? 'Copied' : 'Copy'}
                </button>
              </div>
              <p className="text-[10px] text-[var(--space-text-muted)] mt-1.5">The link is a snapshot of the register as of now — regenerate after verdicts land to share an updated sheet.</p>
            </div>
          )}
          {error && (
            <div className="p-2.5 rounded-lg border border-red-500/40 bg-red-500/10 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
              <p className="text-xs text-red-300">{error} — you can still use the print view to export a PDF.</p>
            </div>
          )}

          {/* Inline preview */}
          <div className="rounded-lg border border-[var(--space-border-default)] overflow-hidden bg-white">
            <iframe title="Attestation sheet preview" srcDoc={html} className="w-full h-[420px] bg-white" sandbox="" />
          </div>
        </div>
      </div>
    </div>
  );
}
